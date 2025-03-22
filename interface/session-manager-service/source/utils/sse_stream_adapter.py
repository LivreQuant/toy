# sse_bridge.py
import logging
import json
import asyncio
import threading
import time
import queue
from aiohttp import web
import aiohttp_cors

logger = logging.getLogger('sse_bridge')

class SSEBridge:
    """Bridge between gRPC exchange streams and SSE client connections"""
    
    def __init__(self, session_service):
        self.session_service = session_service
        self.db = session_service.db
        self.exchange_manager = session_service.exchange_manager
        
        # Configuration
        self.port = int(session_service.sse_port)
        
        # Active SSE connections
        self.sse_clients = {}  # session_id -> list of client queues
        self.lock = threading.RLock()
        self.running = True
        
        # Start HTTP server
        self.app = web.Application()
        self._setup_routes()
        self.server_thread = threading.Thread(target=self._run_server, daemon=True)
        self.server_thread.start()
        
        logger.info(f"SSE Bridge initialized on port {self.port}")
    
    def _setup_routes(self):
        """Set up HTTP routes for SSE endpoints"""
        # Configure CORS
        cors = aiohttp_cors.setup(self.app, defaults={
            "*": aiohttp_cors.ResourceOptions(
                allow_credentials=True,
                expose_headers="*",
                allow_headers="*",
                allow_methods=["GET", "POST", "OPTIONS"]
            )
        })
        
        # Add routes
        self.app.router.add_get('/api/v1/market-data', self.handle_market_data_stream)
        self.app.router.add_get('/api/v1/health', self.handle_health)
        
        # Apply CORS to all routes
        for route in list(self.app.router.routes()):
            cors.add(route)
    
    def _run_server(self):
        """Run the HTTP server in a separate thread"""
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        
        self.runner = web.AppRunner(self.app)
        self.loop.run_until_complete(self.runner.setup())
        
        self.site = web.TCPSite(self.runner, '0.0.0.0', self.port)
        self.loop.run_until_complete(self.site.start())
        
        logger.info(f"SSE HTTP server running on port {self.port}")
        
        try:
            self.loop.run_forever()
        except Exception as e:
            logger.error(f"Error in SSE server: {e}")
        finally:
            if self.running:
                self.shutdown()
    
    def shutdown(self):
        """Gracefully shut down the SSE server"""
        if not self.running:
            return
            
        self.running = False
        logger.info("Shutting down SSE bridge")
        
        # Close all client connections
        with self.lock:
            for session_id in list(self.sse_clients.keys()):
                for client_queue in self.sse_clients[session_id]:
                    try:
                        # Put shutdown message
                        client_queue.put(b"event: shutdown\ndata: {\"reason\": \"server_shutdown\"}\n\n")
                    except:
                        pass
            
            # Clear clients
            self.sse_clients.clear()
        
        # Stop aiohttp server
        if hasattr(self, 'loop') and self.loop.is_running():
            asyncio.run_coroutine_threadsafe(self._close_server(), self.loop)
            
            # Give it a moment to close
            time.sleep(1)
            
            # Stop the event loop
            self.loop.call_soon_threadsafe(self.loop.stop)
    
    async def _close_server(self):
        """Close the aiohttp server"""
        if hasattr(self, 'site'):
            await self.site.stop()
        if hasattr(self, 'runner'):
            await self.runner.cleanup()
    
    async def handle_health(self, request):
        """Handle health check endpoint"""
        return web.Response(text="OK", status=200)
    
    async def handle_market_data_stream(self, request):
        """Handle SSE market data stream connections"""
        # Extract parameters from request
        session_id = request.query.get('sessionId')
        
        # Get token from query or header
        token = request.query.get('token')
        if not token and 'Authorization' in request.headers:
            token = request.headers.get('Authorization', '').replace('Bearer ', '')
            
        symbols = request.query.get('symbols', '').split(',') if request.query.get('symbols') else []
        
        if not session_id or not token:
            return web.Response(text="Missing sessionId or token", status=400)
        
        # Validate token and session
        user_id = self.session_service.validate_session_access(token, session_id)
        if not user_id:
            return web.Response(text="Invalid token or session", status=401)
        
        # Update session activity
        self.db.update_session_activity(session_id)
        
        # Set up SSE response
        response = web.StreamResponse()
        response.headers['Content-Type'] = 'text/event-stream'
        response.headers['Cache-Control'] = 'no-cache'
        response.headers['Connection'] = 'keep-alive'
        response.headers['Access-Control-Allow-Origin'] = '*'  # CORS
        
        # Initialize response
        await response.prepare(request)
        
        # Create client message queue
        client_queue = queue.Queue()
        client_index = -1
        
        # Register client
        with self.lock:
            if session_id not in self.sse_clients:
                self.sse_clients[session_id] = []
                
                # Activate exchange connection if this is the first client
                exchange_id, exchange_endpoint = self.exchange_manager.activate_session(session_id, user_id)
                if not exchange_id or not exchange_endpoint:
                    await response.write(b"event: error\ndata: {\"error\": \"Failed to activate exchange connection\"}\n\n")
                    await response.write_eof()
                    return response
                
                # Start exchange data stream in a separate thread
                threading.Thread(
                    target=self._start_exchange_stream,
                    args=(session_id, user_id, symbols),
                    daemon=True
                ).start()
            
            # Add client to session
            self.sse_clients[session_id].append(client_queue)
            client_index = len(self.sse_clients[session_id]) - 1
        
        # Send initial message
        await response.write(b"event: connected\ndata: {\"sessionId\": \"" + session_id.encode() + b"\"}\n\n")
        
        try:
            # Process messages from queue and forward to client
            last_activity = time.time()
            
            while self.running:
                try:
                    # Poll queue with timeout
                    message = client_queue.get(timeout=1)
                    
                    # Send message to client
                    await response.write(message)
                    last_activity = time.time()
                    
                except queue.Empty:
                    # No message in queue, send keepalive if needed
                    current_time = time.time()
                    if current_time - last_activity > 15:  # Send keepalive every 15 seconds
                        # Send comment as keepalive to avoid event parsing
                        await response.write(b": keepalive\n\n")
                        last_activity = current_time
                    
                    # Update session activity periodically
                    if current_time - last_activity > 30:  # Update every 30 seconds
                        self.db.update_session_activity(session_id)
                
                # Check if client is still connected
                if response.task.done():
                    logger.info(f"Client disconnected from session {session_id}")
                    break
        
        except ConnectionResetError:
            logger.warning(f"Connection reset for session {session_id}")
        except asyncio.CancelledError:
            logger.info(f"Stream cancelled for session {session_id}")
        except Exception as e:
            logger.error(f"Error in SSE stream for session {session_id}: {e}")
        
        finally:
            # Remove client from session
            with self.lock:
                if session_id in self.sse_clients and client_index >= 0:
                    if client_index < len(self.sse_clients[session_id]):
                        del self.sse_clients[session_id][client_index]

    def _start_exchange_stream(self, session_id, user_id, symbols):
        """Start the exchange data stream and forward messages to SSE clients"""
        try:
            logger.info(f"Starting exchange stream bridge for session {session_id}")
            
            # Create a stream request object
            class StreamRequest:
                def __init__(self, session_id, symbols):
                    self.session_id = session_id
                    self.symbols = symbols
            
            # Create a dummy context for the exchange stream
            class DummyContext:
                def __init__(self, bridge, session_id):
                    self.bridge = bridge
                    self.session_id = session_id
                    self.active = True
                
                def is_active(self):
                    # Check if we still have clients for this session
                    with self.bridge.lock:
                        return (self.session_id in self.bridge.sse_clients and 
                                len(self.bridge.sse_clients[self.session_id]) > 0 and
                                self.bridge.running)
                
                def write(self, exchange_data):
                    # Convert gRPC data to JSON and forward to all clients
                    self.bridge._forward_exchange_data(self.session_id, exchange_data)
                    
                def abort(self, code, details):
                    # Handle abort calls from the exchange manager
                    logger.info(f"Exchange stream for session {self.session_id} aborted: {details}")
                    self.active = False
                    
                def add_callback(self, callback):
                    # Dummy implementation to satisfy the interface
                    pass
            
            # Create request and context
            request = StreamRequest(session_id, symbols)
            context = DummyContext(self, session_id)
            
            # Start the exchange stream - this will run until the context is no longer active
            self.exchange_manager.stream_exchange_data(session_id, user_id, request, context)
            
        except Exception as e:
            logger.error(f"Error in exchange stream bridge for session {session_id}: {e}")
            
            # Notify clients about the error
            with self.lock:
                if session_id in self.sse_clients:
                    error_msg = f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n".encode()
                    for client_queue in self.sse_clients[session_id]:
                        try:
                            client_queue.put(error_msg)
                        except:
                            pass
    
    def _forward_exchange_data(self, session_id, exchange_data):
        """Convert gRPC exchange data to SSE format and forward to all clients"""
        try:
            # Convert gRPC message to dictionary
            data = self._convert_exchange_data(exchange_data)
            
            # Create SSE message
            sse_msg = f"event: market-data\ndata: {json.dumps(data)}\n\n".encode()
            
            # Forward to all clients
            with self.lock:
                if session_id in self.sse_clients:
                    for client_queue in self.sse_clients[session_id]:
                        try:
                            client_queue.put(sse_msg)
                        except:
                            pass
            
        except Exception as e:
            logger.error(f"Error forwarding exchange data for session {session_id}: {e}")
    
    def _convert_exchange_data(self, exchange_data):
        """Convert gRPC exchange data message to dictionary"""
        # Basic conversion - customize based on your specific protocol buffer structure
        data = {
            'timestamp': exchange_data.timestamp,
            'marketData': [],
            'orderUpdates': [],
            'portfolio': None
        }
        
        # Convert market data
        for market_data in exchange_data.market_data:
            data['marketData'].append({
                'symbol': market_data.symbol,
                'bid': market_data.bid,
                'ask': market_data.ask,
                'bidSize': market_data.bid_size,
                'askSize': market_data.ask_size,
                'lastPrice': market_data.last_price,
                'lastSize': market_data.last_size
            })
        
        # Convert order updates
        for order_update in exchange_data.order_updates:
            data['orderUpdates'].append({
                'orderId': order_update.order_id,
                'symbol': order_update.symbol,
                'status': order_update.status,
                'filledQuantity': order_update.filled_quantity,
                'averagePrice': order_update.average_price
            })
        
        # Convert portfolio if present
        if hasattr(exchange_data, 'portfolio') and exchange_data.portfolio:
            portfolio = {
                'cashBalance': exchange_data.portfolio.cash_balance,
                'totalValue': exchange_data.portfolio.total_value,
                'positions': []
            }
            
            for position in exchange_data.portfolio.positions:
                portfolio['positions'].append({
                    'symbol': position.symbol,
                    'quantity': position.quantity,
                    'averageCost': position.average_cost,
                    'marketValue': position.market_value
                })
            
            data['portfolio'] = portfolio
        
        return data
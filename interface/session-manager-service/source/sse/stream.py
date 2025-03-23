import logging
import asyncio
import time
import json
from aiohttp import web
from aiohttp.web import StreamResponse

logger = logging.getLogger('sse_stream')

def setup_sse_routes(app):
    """Set up SSE routes"""
    app.router.add_get('/api/stream/market-data', handle_market_data_stream)

async def handle_market_data_stream(request):
    """Handle SSE market data stream request"""
    # Get managers
    session_manager = request.app['session_manager']
    exchange_client = request.app['exchange_client']
    
    # Get parameters
    session_id = request.query.get('sessionId')
    token = request.query.get('token')
    symbols_param = request.query.get('symbols', '')
    symbols = symbols_param.split(',') if symbols_param else []
    
    if not session_id or not token:
        return web.json_response({
            'error': 'Missing sessionId or token'
        }, status=400)
    
    # Validate session
    user_id = await session_manager.validate_session(session_id, token)
    if not user_id:
        return web.json_response({
            'error': 'Invalid session or token'
        }, status=401)
    
    # Get session data
    session = await session_manager.get_session(session_id)
    simulator_id = session.get('simulator_id')
    simulator_endpoint = session.get('simulator_endpoint')
    
    if not simulator_id or not simulator_endpoint:
        return web.json_response({
            'error': 'No active simulator for this session'
        }, status=400)
    
    # Set up SSE response
    response = StreamResponse()
    response.headers['Content-Type'] = 'text/event-stream'
    response.headers['Cache-Control'] = 'no-cache'
    response.headers['Connection'] = 'keep-alive'
    response.headers['X-Accel-Buffering'] = 'no'  # Disable Nginx buffering
    
    # Prepare response
    await response.prepare(request)
    
    # Send initial message
    await response.write(
        f"event: connected\ndata: {json.dumps({'sessionId': session_id})}\n\n".encode()
    )
    
    # Update session metadata
    frontend_connections = session.get('frontend_connections', 0)
    await session_manager.db.update_session_metadata(session_id, {
        'frontend_connections': frontend_connections + 1,
        'last_sse_connection': time.time()
    })
    
    # Set up the exchange data bridge
    exchange_bridge = ExchangeDataBridge(
        exchange_client, 
        session_id, 
        user_id, 
        simulator_id, 
        simulator_endpoint
    )
    
    # Start the exchange stream
    try:
        await exchange_bridge.start_stream(symbols)
        
        # Process data from exchange and forward to client
        last_activity = time.time()
        keepalive_interval = 15  # seconds
        
        while True:
            # Check if client is still connected
            if not request.transport or request.transport.is_closing():
                logger.info(f"Client disconnected from SSE stream for session {session_id}")
                break
            
            # Try to get data from exchange bridge with a timeout
            data = await exchange_bridge.get_data(0.5)  # 500ms timeout
            
            if data:
                # Format data for SSE
                sse_data = f"event: market-data\ndata: {json.dumps(data)}\n\n"
                
                # Send to client
                await response.write(sse_data.encode())
                last_activity = time.time()
            else:
                # No data, check if we need to send keepalive
                current_time = time.time()
                if current_time - last_activity > keepalive_interval:
                    # Send comment for keepalive
                    await response.write(f": keepalive {int(current_time)}\n\n".encode())
                    last_activity = current_time
    
    except asyncio.CancelledError:
        logger.info(f"SSE stream cancelled for session {session_id}")
    except Exception as e:
        logger.error(f"Error in SSE stream for session {session_id}: {e}")
        # Try to send error to client
        try:
            error_data = f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"
            await response.write(error_data.encode())
        except:
            pass
    finally:
        # Stop the exchange bridge
        await exchange_bridge.stop_stream()
        
        # Update session metadata
        try:
            session = await session_manager.get_session(session_id)
            if session:
                frontend_connections = max(0, session.get('frontend_connections', 1) - 1)
                await session_manager.db.update_session_metadata(session_id, {
                    'frontend_connections': frontend_connections
                })
        except Exception as e:
            logger.error(f"Error updating session metadata: {e}")
    
    return response

class ExchangeDataBridge:
    """Bridge between gRPC exchange data streams and SSE"""
    
    def __init__(self, exchange_client, session_id, user_id, simulator_id, endpoint):
        self.exchange_client = exchange_client
        self.session_id = session_id
        self.user_id = user_id
        self.simulator_id = simulator_id
        self.endpoint = endpoint
        self.stream = None
        self.queue = asyncio.Queue(maxsize=100)  # Buffer for exchange data
        self.running = False
    
    async def start_stream(self, symbols=None):
        """Start the exchange data stream"""
        if self.running:
            return
        
        self.running = True
        
        # Start stream in background task
        self.stream_task = asyncio.create_task(
            self._run_stream(symbols or [])
        )
    
    async def stop_stream(self):
        """Stop the exchange data stream"""
        self.running = False
        
        if hasattr(self, 'stream_task') and self.stream_task:
            self.stream_task.cancel()
            try:
                await self.stream_task
            except asyncio.CancelledError:
                pass
    
    async def get_data(self, timeout=None):
        """Get data from the queue with optional timeout"""
        try:
            if timeout:
                return await asyncio.wait_for(self.queue.get(), timeout)
            else:
                return await self.queue.get()
        except asyncio.TimeoutError:
            return None
    
    async def _run_stream(self, symbols):
        """Run the exchange data stream"""
        try:
            # Connect to exchange service
            stream = await self.exchange_client.stream_exchange_data(
                self.session_id, 
                self.user_id,
                self.simulator_id,
                symbols
            )
            
            # Process data from stream
            async for data in stream:
                if not self.running:
                    break
                
                # Convert to dictionary for SSE
                sse_data = self._convert_exchange_data(data)
                
                # Put in queue, drop if queue is full (backpressure)
                try:
                    self.queue.put_nowait(sse_data)
                except asyncio.QueueFull:
                    # Queue is full, drop oldest item
                    try:
                        self.queue.get_nowait()
                        self.queue.put_nowait(sse_data)
                    except:
                        pass
        
        except asyncio.CancelledError:
            logger.info(f"Exchange stream cancelled for session {self.session_id}")
            raise
        except Exception as e:
            logger.error(f"Error in exchange stream for session {self.session_id}: {e}")
            # Put error in queue
            if self.running:
                try:
                    error_data = {
                        'error': str(e),
                        'timestamp': int(time.time() * 1000)
                    }
                    self.queue.put_nowait(error_data)
                except:
                    pass
        finally:
            self.running = False
    
    def _convert_exchange_data(self, exchange_data):
        """Convert gRPC exchange data to dictionary for SSE"""
        # Convert based on your actual data structure
        data = {
            'timestamp': exchange_data.timestamp,
            'marketData': [],
            'orderUpdates': [],
            'portfolio': None
        }
        
        # Convert market data
        for item in exchange_data.market_data:
            data['marketData'].append({
                'symbol': item.symbol,
                'bid': item.bid,
                'ask': item.ask,
                'bidSize': item.bid_size,
                'askSize': item.ask_size,
                'lastPrice': item.last_price,
                'lastSize': item.last_size
            })
        
        # Convert order updates
        for update in exchange_data.order_updates:
            data['orderUpdates'].append({
                'orderId': update.order_id,
                'symbol': update.symbol,
                'status': update.status,
                'filledQuantity': update.filled_quantity,
                'averagePrice': update.average_price
            })
        
        # Convert portfolio if present
        if hasattr(exchange_data, 'portfolio'):
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
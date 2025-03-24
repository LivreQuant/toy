"""
Server-Sent Events (SSE) stream implementation.
Provides the HTTP endpoint and streaming functionality for SSE.
"""
import logging
import asyncio
import json
import time
from typing import Dict, Any, Optional
from aiohttp import web

from source.config import config

logger = logging.getLogger('sse_stream')

async def handle_stream(request):
    """
    Handle an SSE stream request
    
    Args:
        request: HTTP request
        
    Returns:
        StreamResponse for SSE
    """
    # Get components from app
    session_manager = request.app['session_manager']
    exchange_client = request.app['exchange_client']
    sse_adapter = request.app['sse_adapter']
    
    # Get parameters
    session_id = request.query.get('sessionId')
    token = request.query.get('token')
    symbols_param = request.query.get('symbols', '')
    symbols = symbols_param.split(',') if symbols_param and symbols_param.strip() else []
    
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
    
    # Get session and check simulator
    session = await session_manager.get_session(session_id)
    simulator_id = session.get('simulator_id')
    simulator_endpoint = session.get('simulator_endpoint')
    
    if not simulator_id or not simulator_endpoint:
        return web.json_response({
            'error': 'No active simulator for this session'
        }, status=400)
    
    # Setup SSE response
    response = web.StreamResponse()
    response.headers['Content-Type'] = 'text/event-stream'
    response.headers['Cache-Control'] = 'no-cache'
    response.headers['Connection'] = 'keep-alive'
    response.headers['X-Accel-Buffering'] = 'no'  # Disable Nginx buffering
    
    # Prepare response
    await response.prepare(request)
    
    # Generate client ID for this connection
    client_id = request.query.get('clientId', f"sse-{time.time()}")
    
    # Use the SSE adapter to start or get the stream
    stream = await sse_adapter.get_or_create_stream(
        session_id,
        user_id,
        simulator_id,
        simulator_endpoint,
        symbols
    )
    
    # Register this client with the stream
    stream.add_client(client_id, response)
    
    # Update session metadata
    client_count = stream.client_count()
    await session_manager.db_manager.update_session_metadata(session_id, {
        'sse_connections': client_count,
        'last_sse_connection': time.time()
    })
    
    # Send initial connected message
    try:
        # Send connected event
        sse_data = f"event: connected\ndata: {json.dumps({'sessionId': session_id, 'clientId': client_id})}\n\n"
        await response.write(sse_data.encode())
        
        # Send initial snapshot
        initial_data = await stream.get_initial_data()
        if initial_data:
            sse_data = f"event: market-data\ndata: {json.dumps(initial_data)}\n\n"
            await response.write(sse_data.encode())
        
        # Keep the connection alive
        keepalive_interval = config.sse.keepalive_interval
        last_keepalive = time.time()
        
        while True:
            # Check if client disconnected
            if request.transport is None or request.transport.is_closing():
                logger.info(f"SSE client {client_id} disconnected (transport closed)")
                break
            
            # Send periodic keepalive
            current_time = time.time()
            if current_time - last_keepalive > keepalive_interval:
                await response.write(f": keepalive {int(current_time)}\n\n".encode())
                last_keepalive = current_time
            
            # Short sleep to avoid CPU spinning
            await asyncio.sleep(1)
    
    except asyncio.CancelledError:
        logger.info(f"SSE stream for client {client_id} was cancelled")
    except ConnectionResetError:
        logger.info(f"SSE connection reset for client {client_id}")
    except Exception as e:
        logger.error(f"Error in SSE stream for client {client_id}: {e}")
    finally:
        # Unregister client from stream
        stream.remove_client(client_id)
        
        # Update session metadata
        client_count = stream.client_count()
        await session_manager.db_manager.update_session_metadata(session_id, {
            'sse_connections': client_count,
            'last_sse_disconnection': time.time()
        })
        
        # If no clients left, close the stream
        if client_count == 0:
            await sse_adapter.close_stream(session_id)
    
    return response

class SSEStream:
    """Manages the SSE stream for a specific session"""
    
    def __init__(self, exchange_client, session_id, user_id, simulator_id, endpoint):
        """
        Initialize SSE stream
        
        Args:
            exchange_client: Exchange client for gRPC communication
            session_id: Session ID
            user_id: User ID
            simulator_id: Simulator ID
            endpoint: Simulator endpoint
        """
        self.exchange_client = exchange_client
        self.session_id = session_id
        self.user_id = user_id
        self.simulator_id = simulator_id
        self.endpoint = endpoint
        self.clients = {}  # client_id -> response
        self.buffer = asyncio.Queue(maxsize=100)  # Buffer for data
        self.running = False
        self.stream_task = None
        self.distribution_task = None
        
        # Cache for latest data
        self.latest_market_data = {}  # symbol -> data
        self.latest_portfolio = None
        self.latest_order_updates = []
    
    async def start(self, symbols=None):
        """
        Start the SSE stream
        
        Args:
            symbols: Optional list of symbols to track
        """
        if self.running:
            return
        
        self.running = True
        
        # Start the exchange data stream
        self.stream_task = asyncio.create_task(
            self._run_exchange_stream(symbols)
        )
        
        # Start the distribution task
        self.distribution_task = asyncio.create_task(
            self._distribute_data()
        )
        
        logger.info(f"Started SSE stream for session {self.session_id}")
    
    async def stop(self):
        """Stop the SSE stream"""
        self.running = False
        
        # Cancel tasks
        if self.stream_task:
            self.stream_task.cancel()
            try:
                await self.stream_task
            except asyncio.CancelledError:
                pass
        
        if self.distribution_task:
            self.distribution_task.cancel()
            try:
                await self.distribution_task
            except asyncio.CancelledError:
                pass
        
        # Close all client connections
        for client_id, response in list(self.clients.items()):
            try:
                # Send close message
                await response.write(f"event: close\ndata: {json.dumps({'reason': 'Stream closed'})}\n\n".encode())
            except:
                pass
        
        self.clients.clear()
        logger.info(f"Stopped SSE stream for session {self.session_id}")
    
    def add_client(self, client_id, response):
        """
        Add a client to the stream
        
        Args:
            client_id: Client ID
            response: HTTP response for streaming
        """
        self.clients[client_id] = response
        logger.info(f"Added client {client_id} to SSE stream for session {self.session_id}")
    
    def remove_client(self, client_id):
        """
        Remove a client from the stream
        
        Args:
            client_id: Client ID
        """
        if client_id in self.clients:
            del self.clients[client_id]
            logger.info(f"Removed client {client_id} from SSE stream for session {self.session_id}")
    
    def client_count(self):
        """Get the number of connected clients"""
        return len(self.clients)
    
    async def get_initial_data(self):
        """Get initial data snapshot for a new client"""
        if not self.latest_market_data and not self.latest_portfolio:
            return None
        
        # Create initial snapshot from cached data
        snapshot = {
            'timestamp': int(time.time() * 1000),
            'market_data': list(self.latest_market_data.values()),
            'order_updates': self.latest_order_updates[-10:] if self.latest_order_updates else [],
            'portfolio': self.latest_portfolio
        }
        
        return snapshot
    
    async def _run_exchange_stream(self, symbols=None):
        """
        Run the exchange data stream
        
        Args:
            symbols: Optional list of symbols to track
        """
        client_id = f"sse-{self.session_id}-{time.time()}"
        
        try:
            # Start streaming from exchange
            async for data in self.exchange_client.stream_exchange_data(
                self.endpoint,
                self.session_id,
                client_id,
                symbols
            ):
                if not self.running:
                    break
                
                # Update cache
                self._update_cache(data)
                
                # Put data in buffer
                try:
                    self.buffer.put_nowait(data)
                except asyncio.QueueFull:
                    # Queue full - implement backpressure handling
                    try:
                        # Discard oldest item
                        _ = self.buffer.get_nowait()
                        # Add new item
                        self.buffer.put_nowait(data)
                    except:
                        # Ignore if queue manipulation fails
                        pass
        
        except asyncio.CancelledError:
            logger.info(f"Exchange stream for session {self.session_id} cancelled")
            raise
        except Exception as e:
            logger.error(f"Error in exchange stream for session {self.session_id}: {e}")
            
            # Put error in buffer
            try:
                error_data = {
                    'error': str(e),
                    'timestamp': int(time.time() * 1000)
                }
                self.buffer.put_nowait(error_data)
            except:
                pass
    
    async def _distribute_data(self):
        """Distribute data to all connected clients"""
        try:
            while self.running:
                # Get data from buffer
                data = await self.buffer.get()
                
                # Convert to SSE format
                sse_data = f"event: market-data\ndata: {json.dumps(data)}\n\n"
                
                # Send to all clients
                for client_id, response in list(self.clients.items()):
                    try:
                        await response.write(sse_data.encode())
                    except Exception as e:
                        logger.error(f"Error sending data to client {client_id}: {e}")
                        # Client will be removed on next iteration
        
        except asyncio.CancelledError:
            logger.info(f"Distribution task for session {self.session_id} cancelled")
            raise
        except Exception as e:
            logger.error(f"Error in distribution task for session {self.session_id}: {e}")
    
    def _update_cache(self, data):
        """
        Update the data cache
        
        Args:
            data: Exchange data update
        """
        # Update market data cache
        for item in data.get('market_data', []):
            symbol = item.get('symbol')
            if symbol:
                self.latest_market_data[symbol] = item
        
        # Update portfolio
        if 'portfolio' in data and data['portfolio']:
            self.latest_portfolio = data['portfolio']
        
        # Update order updates (keep last 50)
        order_updates = data.get('order_updates', [])
        if order_updates:
            self.latest_order_updates.extend(order_updates)
            if len(self.latest_order_updates) > 50:
                self.latest_order_updates = self.latest_order_updates[-50:]
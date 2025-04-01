"""
Server-Sent Events (SSE) adapter.
Converts gRPC streams to SSE streams for the frontend.
"""
import logging
import asyncio
import json
import time
from typing import Dict, Any, Set, Optional
from opentelemetry import trace
from aiohttp import web
import random

from source.utils.metrics import track_sse_connection_count, track_sse_message
from source.utils.tracing import optional_trace_span

logger = logging.getLogger('sse_adapter')

class SSEAdapter:
    """Adapter for SSE streams from exchange service"""
    
    def __init__(self, exchange_client, session_manager, redis_client=None):
        """
        Initialize SSE adapter
        
        Args:
            exchange_client: Exchange client for gRPC communication
            session_manager: Session manager for session validation
            redis_client: Optional Redis client for coordination
        """
        self.exchange_client = exchange_client
        self.session_manager = session_manager
        self.redis = redis_client
        self.active_streams = {}  # session_id -> StreamHandler
        self.tracer = trace.get_tracer("sse_adapter")

        # Initialize metrics
        track_sse_connection_count(0)

    async def handle_stream(self, request):
        """
        Handle an SSE stream request with fake data
        
        Args:
            request: HTTP request
        
        Returns:
            StreamResponse
        """
        logger.info(f"SSE stream connection attempt received with query params: {request.query}")
        
        # Get parameters
        session_id = request.query.get('sessionId')
        token = request.query.get('token')
        symbols_param = request.query.get('symbols', '')
        symbols = symbols_param.split(',') if symbols_param else []

        logger.info(f"SSE params - sessionId: {session_id}, token: {'present' if token else 'missing'}, symbols: {symbols}")

        if not session_id or not token:
            logger.error("SSE request missing sessionId or token")
            return web.json_response({
                'error': 'Missing sessionId or token'
            }, status=400)

        # Validate session
        logger.info(f"Validating session {session_id} for SSE connection")
        user_id = await self.session_manager.validate_session(session_id, token)
        logger.info(f"Session validation result: user_id={user_id}")

        if not user_id:
            logger.error(f"Invalid session or token for SSE connection: {session_id}")
            return web.json_response({
                'error': 'Invalid session or token'
            }, status=401)

        # Set up SSE response
        logger.info(f"Setting up SSE response for session {session_id}")
        response = web.StreamResponse()
        response.headers['Content-Type'] = 'text/event-stream'
        response.headers['Cache-Control'] = 'no-cache'
        response.headers['Connection'] = 'keep-alive'
        response.headers['X-Accel-Buffering'] = 'no'  # Disable Nginx buffering

        # Prepare response
        logger.info("Preparing SSE response")
        await response.prepare(request)
        logger.info("SSE response prepared")

        # Track connection
        client_id = request.query.get('clientId', f"sse-{time.time()}")
        logger.info(f"SSE client tracking: client_id={client_id}")

        # Generate fake symbols if none provided
        if not symbols:
            symbols = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'FB']
        
        # Send initial event
        try:
            # Send connected event
            logger.info(f"Sending 'connected' event to client {client_id}")
            sse_data = f"event: connected\ndata: {json.dumps({'sessionId': session_id, 'clientId': client_id})}\n\n"
            await response.write(sse_data.encode())

            # Send initial fake data
            logger.info("Sending initial fake market data")
            initial_data = {
                'timestamp': int(time.time() * 1000),
                'market_data': []
            }
            
            # Generate fake data for each symbol
            for symbol in symbols:
                initial_data['market_data'].append({
                    'symbol': symbol,
                    'price': round(random.uniform(100, 1000), 2),
                    'change': round(random.uniform(-5, 5), 2),
                    'bid': round(random.uniform(95, 995), 2),
                    'ask': round(random.uniform(105, 1005), 2),
                    'bidSize': random.randint(100, 1000),
                    'askSize': random.randint(100, 1000),
                    'volume': random.randint(10000, 100000),
                    'timestamp': int(time.time() * 1000)
                })
            
            sse_data = f"event: market-data\ndata: {json.dumps(initial_data)}\n\n"
            await response.write(sse_data.encode())
            
            # Keep sending updates periodically
            logger.info(f"Entering fake data generation loop for client {client_id}")
            update_count = 0
            
            while not response.task.done():
                # Check if client disconnected
                if request.transport is None or request.transport.is_closing():
                    logger.info(f"Client transport closed for {client_id}")
                    break
                    
                # Generate updated fake data every second
                await asyncio.sleep(1)
                update_count += 1
                
                # Only send updates every 1-3 seconds
                if update_count % random.randint(1, 3) == 0:
                    update_data = {
                        'timestamp': int(time.time() * 1000),
                        'market_data': []
                    }
                    
                    # Update each symbol with slightly changed values
                    for symbol in symbols:
                        price = round(random.uniform(100, 1000), 2)
                        update_data['market_data'].append({
                            'symbol': symbol,
                            'price': price,
                            'change': round(random.uniform(-5, 5), 2),
                            'bid': round(price * 0.99, 2),
                            'ask': round(price * 1.01, 2),
                            'bidSize': random.randint(100, 1000),
                            'askSize': random.randint(100, 1000),
                            'volume': random.randint(10000, 100000),
                            'timestamp': int(time.time() * 1000)
                        })
                    
                    logger.debug(f"Sending market data update #{update_count}")
                    sse_data = f"event: market-data\ndata: {json.dumps(update_data)}\n\n"
                    await response.write(sse_data.encode())

        except asyncio.CancelledError:
            # Normal disconnection
            logger.info(f"SSE connection cancelled for client {client_id}")
        except Exception as e:
            logger.error(f"Error in SSE stream for session {session_id}: {e}", exc_info=True)
        
        logger.info(f"SSE stream connection completed for client {client_id}")
        return response

    async def _send_mock_data(self, response):
        """Send mock data when no simulator is available"""
        mock_symbols = ['AAPL', 'GOOGL', 'MSFT', 'AMZN']
        
        while True:
            mock_data = {
                'timestamp': int(time.time() * 1000),
                'data': {
                    'market_data': [{
                        'symbol': symbol,
                        'price': round(random.uniform(50, 500), 2),
                        'change': round(random.uniform(-5, 5), 2),
                        'volume': random.randint(1000, 100000)
                    } for symbol in mock_symbols],
                    'portfolio': {
                        'cash': round(random.uniform(50000, 200000), 2),
                        'equity': round(random.uniform(100000, 500000), 2),
                        'positions': [{
                            'symbol': symbol,
                            'quantity': random.randint(10, 500),
                            'avg_price': round(random.uniform(50, 500), 2),
                            'market_value': round(random.uniform(5000, 50000), 2)
                        } for symbol in mock_symbols]
                    }
                }
            }
            
            sse_data = f"data: {json.dumps(mock_data)}\n\n"
            await response.write(sse_data.encode())
            
            await asyncio.sleep(5)  # Send mock data every 5 seconds

    async def _stream_simulator_data(self, session_id, simulator_endpoint, response):
        """Stream real simulator data"""
        client_id = f"sse-{time.time()}"
        
        async for data in self.exchange_client.stream_exchange_data(
            simulator_endpoint, session_id, client_id
        ):
            # Flatten the nested structure into a single stream
            unified_data = {
                'timestamp': data['timestamp'],
                'data': {
                    'market_data': data.get('market_data', []),
                    'portfolio': data.get('portfolio')
                }
            }
            
            sse_data = f"data: {json.dumps(unified_data)}\n\n"
            await response.write(sse_data.encode())    

    def _get_total_connections(self):
        """Get total SSE connections across all streams"""
        return sum(stream.client_count() for stream in self.active_streams.values())

    async def close_all_streams(self):
        """Close all active SSE streams"""
        for session_id, stream in list(self.active_streams.items()):
            await stream.stop()
        
        self.active_streams.clear()


class StreamHandler:
    """Handles a gRPC stream and distributes data to SSE clients"""
    
    def __init__(self, exchange_client, session_id, user_id, simulator_id, endpoint, tracer=None):
        """
        Initialize stream handler
        
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
        self.stream_task = None
        self.queue = asyncio.Queue(maxsize=100)  # Buffer for exchange data
        self.running = False
        
        # Data cache for new clients
        self.latest_data = None

        # Tracing
        self.tracer = tracer or trace.get_tracer("stream_handler")

        # Start client distribution task
        self.distribution_task = asyncio.create_task(self._distribute_data())
    
    async def start(self, symbols=None):
        """
        Start the stream
        
        Args:
            symbols: Optional list of symbols to stream
        """
        with optional_trace_span(self.tracer, "stream_start") as span:
            span.set_attribute("session_id", self.session_id)
            span.set_attribute("simulator_id", self.simulator_id)
            span.set_attribute("symbols_count", len(symbols or []))

            if self.running:
                span.set_attribute("already_running", True)
                return

            self.running = True

            # Start gRPC stream in background task
            self.stream_task = asyncio.create_task(self._run_stream(symbols))

            logger.info(f"Started exchange stream for session {self.session_id}")
            span.set_attribute("success", True)
    
    async def stop(self):
        """Stop the stream"""
        self.running = False

        # Cancel stream task
        if self.stream_task:
            self.stream_task.cancel()
            try:
                await self.stream_task
            except asyncio.CancelledError:
                pass

        # Cancel distribution task
        if self.distribution_task:
            self.distribution_task.cancel()
            try:
                await self.distribution_task
            except asyncio.CancelledError:
                pass

        logger.info(f"Stopped exchange stream for session {self.session_id}")

    def add_client(self, client_id, response):
        """
        Add a new client
        
        Args:
            client_id: Client ID
            response: StreamResponse
        """
        self.clients[client_id] = response
    
    def remove_client(self, client_id):
        """
        Remove a client
        
        Args:
            client_id: Client ID
        """
        self.clients.pop(client_id, None)
    
    def client_count(self):
        """Get number of connected clients"""
        return len(self.clients)
    
    async def get_initial_data(self):
        """Get initial data snapshot for a new client"""
        return self.latest_data

    async def _run_stream(self, symbols=None):
        """
        Run the gRPC stream
        
        Args:
            symbols: Optional list of symbols to stream
        """
        with optional_trace_span(self.tracer, "stream_run") as span:
            span.set_attribute("session_id", self.session_id)
            span.set_attribute("simulator_id", self.simulator_id)

            try:
                # Generate a client ID for this stream
                client_id = f"sse-stream-{self.simulator_id}"
                logger.info(f"Starting exchange stream for client {client_id} with symbols: {symbols}")
                span.set_attribute("client_id", client_id)

                # Start the stream
                logger.info(f"Connecting to exchange stream at endpoint {self.endpoint}")
                stream_gen = self.exchange_client.stream_market_data(
                    self.endpoint,
                    self.session_id,
                    client_id,
                    symbols
                )
                
                logger.info("Stream generator created, starting async iteration")
                
                async for data in stream_gen:
                    if not self.running:
                        logger.info("Stream handler no longer running, breaking loop")
                        break

                    logger.debug(f"Received data from exchange stream: {data.get('timestamp')}")
                    # Update latest data
                    self.latest_data = data
                    track_sse_message("market-data")

                    # Put data in queue for distribution
                    try:
                        self.queue.put_nowait(data)
                        logger.debug("Data added to distribution queue")
                    except asyncio.QueueFull:
                        # Queue is full (backpressure), drop oldest item
                        logger.warning("Distribution queue full, dropping oldest item")
                        try:
                            _ = self.queue.get_nowait()
                            self.queue.put_nowait(data)
                            logger.debug("Oldest item dropped, new data added")
                        except Exception as e:
                            logger.error(f"Error handling queue backpressure: {e}")

            except asyncio.CancelledError:
                # Normal cancellation
                logger.info("Stream task cancelled")
                raise
            except Exception as e:
                logger.error(f"Error in exchange stream: {e}", exc_info=True)
                span.record_exception(e)

                # Put error in queue
                try:
                    error_data = {
                        'error': str(e),
                        'timestamp': int(time.time() * 1000)
                    }
                    self.queue.put_nowait(error_data)
                    logger.info("Error info added to distribution queue")
                except Exception as inner_e:
                    logger.error(f"Failed to add error to queue: {inner_e}")
                    
    async def _distribute_data(self):
        """Distribute data to all connected clients"""
        while True:
            try:
                # Wait for data from the exchange
                data = await self.queue.get()
                
                # Convert to SSE format
                sse_data = f"event: market-data\ndata: {json.dumps(data)}\n\n"
                
                # Send to all clients
                for client_id, response in list(self.clients.items()):
                    try:
                        await response.write(sse_data.encode())
                    except Exception as e:
                        logger.error(f"Error sending SSE data to client {client_id}: {e}")
                        # Client will be removed on next iteration
                
                # Send keepalive periodically (implement if needed)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in SSE distribution: {e}")
                await asyncio.sleep(1)  # Avoid tight loop on error
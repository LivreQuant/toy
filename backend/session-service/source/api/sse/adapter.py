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
        Handle an SSE stream request
        
        Args:
            request: HTTP request
        
        Returns:
            StreamResponse
        """
        with optional_trace_span(self.tracer, "handle_sse_stream") as span:
            # Get parameters
            session_id = request.query.get('sessionId')
            token = request.query.get('token')
            symbols_param = request.query.get('symbols', '')
            symbols = symbols_param.split(',') if symbols_param else []

            span.set_attribute("session_id", session_id)
            span.set_attribute("has_token", token is not None)
            span.set_attribute("symbols_count", len(symbols))

            if not session_id or not token:
                span.set_attribute("error", "Missing sessionId or token")
                return web.json_response({
                    'error': 'Missing sessionId or token'
                }, status=400)

            # Validate session
            user_id = await self.session_manager.validate_session(session_id, token)
            span.set_attribute("user_id", user_id)
            span.set_attribute("session_valid", user_id is not None)

            if not user_id:
                span.set_attribute("error", "Invalid session or token")
                return web.json_response({
                    'error': 'Invalid session or token'
                }, status=401)

            # Get session details
            session = await self.session_manager.get_session(session_id)

            # Check if simulator is running
            simulator_id = session.get('simulator_id')
            simulator_endpoint = session.get('simulator_endpoint')

            span.set_attribute("simulator_id", simulator_id)
            span.set_attribute("simulator_available", simulator_id is not None and simulator_endpoint is not None)

            if not simulator_id or not simulator_endpoint:
                span.set_attribute("error", "No active simulator for this session")
                return web.json_response({
                    'error': 'No active simulator for this session'
                }, status=400)

            # Set up SSE response
            response = web.StreamResponse()
            response.headers['Content-Type'] = 'text/event-stream'
            response.headers['Cache-Control'] = 'no-cache'
            response.headers['Connection'] = 'keep-alive'
            response.headers['X-Accel-Buffering'] = 'no'  # Disable Nginx buffering

            # Prepare response
            await response.prepare(request)

            # Track connection
            client_id = request.query.get('clientId', f"sse-{time.time()}")
            span.set_attribute("client_id", client_id)

            # Get or create stream handler
            if session_id in self.active_streams:
                stream = self.active_streams[session_id]
                span.set_attribute("stream_created", False)
            else:
                # Create new stream handler
                stream = StreamHandler(
                    self.exchange_client,
                    session_id,
                    user_id,
                    simulator_id,
                    simulator_endpoint,
                    self.tracer
                )
                self.active_streams[session_id] = stream
                span.set_attribute("stream_created", True)

                # Start the stream
                await stream.start(symbols)

            # Register this client
            stream.add_client(client_id, response)

            # Update session metadata
            sse_count = stream.client_count()
            await self.session_manager.db_manager.update_session_metadata(session_id, {
                'sse_connections': sse_count,
                'last_sse_connection': time.time()
            })

            # Update metrics
            track_sse_connection_count(self._get_total_connections())

            # Send initial event
            try:
                # Send connected event
                sse_data = f"event: connected\ndata: {json.dumps({'sessionId': session_id, 'clientId': client_id})}\n\n"
                await response.write(sse_data.encode())
                track_sse_message("connected")

                # Get initial data snapshot
                initial_data = await stream.get_initial_data()

                if initial_data:
                    sse_data = f"event: market-data\ndata: {json.dumps(initial_data)}\n\n"
                    await response.write(sse_data.encode())
                    track_sse_message("market-data")

                # Update Redis if available
                if self.redis:
                    await self.redis.set(
                        f"connection:{session_id}:sse_count",
                        sse_count,
                        ex=3600  # 1 hour expiry
                    )

                # Keep connection open
                while not response.task.done():
                    # Check if client disconnected
                    if request.transport is None or request.transport.is_closing():
                        break

                    # Wait for a while
                    await asyncio.sleep(1)

            except asyncio.CancelledError:
                # Normal disconnection
                pass
            except Exception as e:
                logger.error(f"Error in SSE stream for session {session_id}: {e}")
                span.record_exception(e)
            finally:
                # Unregister client
                stream.remove_client(client_id)

                # Check if we need to close the stream
                if stream.client_count() == 0:
                    await stream.stop()
                    self.active_streams.pop(session_id, None)

                # Update session metadata
                sse_count = stream.client_count()
                await self.session_manager.db_manager.update_session_metadata(session_id, {
                    'sse_connections': sse_count,
                    'last_sse_disconnection': time.time()
                })

                # Update metrics
                track_sse_connection_count(self._get_total_connections())

                # Update Redis if available
                if self.redis:
                    await self.redis.set(
                        f"connection:{session_id}:sse_count",
                        sse_count,
                        ex=3600  # 1 hour expiry
                    )

            return response

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
                span.set_attribute("client_id", client_id)

                # Start the stream
                async for data in self.exchange_client.stream_exchange_data(
                    self.endpoint,
                    self.session_id,
                    client_id,
                    symbols
                ):
                    if not self.running:
                        break

                    # Update latest data
                    self.latest_data = data
                    track_sse_message("market-data")

                    # Put data in queue for distribution
                    try:
                        self.queue.put_nowait(data)
                    except asyncio.QueueFull:
                        # Queue is full (backpressure), drop oldest item
                        try:
                            _ = self.queue.get_nowait()
                            self.queue.put_nowait(data)
                        except Exception:
                            pass

            except asyncio.CancelledError:
                # Normal cancellation
                raise
            except Exception as e:
                logger.error(f"Error in exchange stream: {e}")
                span.record_exception(e)

                # Put error in queue
                try:
                    error_data = {
                        'error': str(e),
                        'timestamp': int(time.time() * 1000)
                    }
                    self.queue.put_nowait(error_data)
                except:
                    pass
    
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
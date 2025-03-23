import logging
import json
import time
import asyncio
from typing import Dict, List, Any, Optional

logger = logging.getLogger('sse_adapter')

class SSEAdapter:
    """Adapter for converting gRPC exchange data to SSE format"""
    
    def __init__(self, exchange_client):
        self.exchange_client = exchange_client
        self.active_streams = {}  # session_id -> StreamContext
    
    async def create_stream(self, session_id, user_id, simulator_id, symbols=None):
        """Create a new gRPC stream and return a stream context"""
        # Check if a stream already exists for this session
        if session_id in self.active_streams:
            return self.active_streams[session_id]
        
        # Create a new stream context
        stream_ctx = StreamContext(
            self.exchange_client,
            session_id, 
            user_id, 
            simulator_id, 
            symbols
        )
        
        # Store the context
        self.active_streams[session_id] = stream_ctx
        
        # Start the stream
        await stream_ctx.start()
        
        return stream_ctx
    
    async def close_stream(self, session_id):
        """Close a stream for a session"""
        if session_id in self.active_streams:
            await self.active_streams[session_id].stop()
            del self.active_streams[session_id]
    
    async def close_all_streams(self):
        """Close all active streams"""
        for session_id, stream_ctx in list(self.active_streams.items()):
            await stream_ctx.stop()
        
        self.active_streams.clear()

class StreamContext:
    """Context for a gRPC exchange data stream"""
    
    def __init__(self, exchange_client, session_id, user_id, simulator_id, symbols=None):
        self.exchange_client = exchange_client
        self.session_id = session_id
        self.user_id = user_id
        self.simulator_id = simulator_id
        self.symbols = symbols or []
        
        # Stream state
        self.stream = None
        self.task = None
        self.queue = asyncio.Queue(maxsize=100)  # Buffer for exchange data
        self.running = False
        self.last_data_time = None
        self.connected_clients = 0
        
        # Market data cache for new clients
        self.latest_market_data = {}  # symbol -> data
        self.latest_order_updates = []  # Last 10 order updates
        self.latest_portfolio = None  # Latest portfolio update
    
    async def start(self):
        """Start the exchange data stream"""
        if self.running:
            return
        
        self.running = True
        self.task = asyncio.create_task(self._run_stream())
        logger.info(f"Started exchange stream for session {self.session_id}")
    
    async def stop(self):
        """Stop the exchange data stream"""
        self.running = False
        
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
            
            self.task = None
        
        logger.info(f"Stopped exchange stream for session {self.session_id}")
    
    async def get_data(self, timeout=None):
        """Get data from the queue with optional timeout"""
        try:
            if timeout:
                return await asyncio.wait_for(self.queue.get(), timeout)
            else:
                return await self.queue.get()
        except asyncio.TimeoutError:
            return None
    
    async def get_initial_data(self):
        """Get initial data snapshot for a new client"""
        data = {
            'timestamp': int(time.time() * 1000),
            'marketData': list(self.latest_market_data.values()),
            'orderUpdates': self.latest_order_updates[-10:],  # Last 10 updates
            'portfolio': self.latest_portfolio
        }
        
        return data
    
    def client_connected(self):
        """Track a new client connection"""
        self.connected_clients += 1
    
    def client_disconnected(self):
        """Track a client disconnection"""
        self.connected_clients = max(0, self.connected_clients - 1)
    
    async def _run_stream(self):
        """Run the gRPC exchange data stream"""
        try:
            # Connect to exchange service and start streaming
            stream = await self.exchange_client.stream_exchange_data(
                self.session_id,
                self.user_id,
                self.simulator_id,
                self.symbols
            )
            
            self.stream = stream
            
            # Process data from stream
            async for exchange_data in stream:
                if not self.running:
                    break
                
                # Update last data time
                self.last_data_time = time.time()
                
                # Convert to dictionary for SSE
                sse_data = self._convert_exchange_data(exchange_data)
                
                # Update caches
                self._update_caches(sse_data)
                
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
            logger.info(f"Exchange stream task cancelled for session {self.session_id}")
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
        # Customize based on your protobuf definitions
        data = {
            'timestamp': exchange_data.timestamp,
            'marketData': [],
            'orderUpdates': [],
            'portfolio': None
        }
        
        # Convert market data
        for item in exchange_data.market_data:
            market_data = {
                'symbol': item.symbol,
                'bid': item.bid,
                'ask': item.ask,
                'bidSize': item.bid_size,
                'askSize': item.ask_size,
                'lastPrice': item.last_price,
                'lastSize': item.last_size
            }
            data['marketData'].append(market_data)
        
        # Convert order updates
        for update in exchange_data.order_updates:
            order_update = {
                'orderId': update.order_id,
                'symbol': update.symbol,
                'status': update.status,
                'filledQuantity': update.filled_quantity,
                'averagePrice': update.average_price
            }
            data['orderUpdates'].append(order_update)
        
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
    
    def _update_caches(self, data):
        """Update cache data for new client connections"""
        # Update market data cache
        for item in data.get('marketData', []):
            self.latest_market_data[item['symbol']] = item
        
        # Update order updates (keep last 50)
        self.latest_order_updates.extend(data.get('orderUpdates', []))
        if len(self.latest_order_updates) > 50:
            self.latest_order_updates = self.latest_order_updates[-50:]
        
        # Update portfolio
        if data.get('portfolio'):
            self.latest_portfolio = data['portfolio']
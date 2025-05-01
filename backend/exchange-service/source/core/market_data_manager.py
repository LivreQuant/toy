# source/core/market_data_client.py
import asyncio
import logging
import grpc
from typing import Dict, List, Any, Optional, Callable

from source.api.grpc.market_exchange_interface_pb2 import SubscriptionRequest
from source.api.grpc.market_exchange_interface_pb2_grpc import MarketDataServiceStub
from source.config import config

logger = logging.getLogger('market_data_client')

class MarketDataClient:
    """
    Client for connecting to the market data service and receiving market data updates.
    """
    
    def __init__(self, exchange_manager, symbols=None):
        """
        Initialize the market data client
        
        Args:
            exchange_manager: Reference to the exchange manager to receive updates
            symbols: List of symbols to subscribe to (optional)
        """
        self.exchange_manager = exchange_manager
        self.symbols = symbols or config.simulator.default_symbols
        self.market_data_service_url = config.market_data.service_url
        self.channel = None
        self.stub = None
        self.subscription_stream = None
        self.subscription_task = None
        self.running = False
        self.subscriber_id = f"exchange-simulator-{config.simulator.user_id}"
        
        logger.info(f"Market data client initialized with service URL: {self.market_data_service_url}")
    
    async def start(self):
        """Start the market data client and subscribe to updates"""
        if self.running:
            logger.warning("Market data client is already running")
            return
            
        logger.info("Starting market data client")
        self.running = True
        
        # Start a background task to handle the subscription
        self.subscription_task = asyncio.create_task(self._subscribe_to_market_data())
    
    async def stop(self):
        """Stop the market data client"""
        if not self.running:
            return
            
        logger.info("Stopping market data client")
        self.running = False
        
        # Cancel the subscription task
        if self.subscription_task:
            self.subscription_task.cancel()
            try:
                await self.subscription_task
            except asyncio.CancelledError:
                pass
        
        # Close the gRPC channel
        if self.channel:
            await self.channel.close()
            self.channel = None
            self.stub = None
        
        logger.info("Market data client stopped")
    
    async def _subscribe_to_market_data(self):
        """Subscribe to market data updates from the service"""
        retry_count = 0
        max_retries = 10
        retry_delay = 1.0
        
        while self.running:
            try:
                logger.info(f"Connecting to market data service at {self.market_data_service_url}")
                
                # Create a gRPC channel
                self.channel = grpc.aio.insecure_channel(self.market_data_service_url)
                self.stub = MarketDataServiceStub(self.channel)
                
                # Create a subscription request
                request = SubscriptionRequest(
                    subscriber_id=self.subscriber_id,
                    symbols=self.symbols
                )
                
                # Start the subscription
                subscription_stream = self.stub.SubscribeMarketData(request)
                
                logger.info(f"Subscribed to market data for symbols: {self.symbols}")
                
                # Process incoming market data updates
                async for update in subscription_stream:
                    if not self.running:
                        break
                    
                    # Convert gRPC format to internal format
                    market_data = []
                    for data in update.data:
                        market_data.append({
                            'symbol': data.symbol,
                            'open': data.open,
                            'high': data.high,
                            'low': data.low,
                            'close': data.close,
                            'volume': data.volume,
                            'trade_count': data.trade_count,
                            'vwap': data.vwap
                        })
                    
                    # Forward the market data to the exchange manager
                    await self.exchange_manager.update_market_data(market_data)
                    logger.debug(f"Received market data for {len(market_data)} symbols")
                    
                    # Reset retry count on successful update
                    retry_count = 0
                    retry_delay = 1.0
                
                # If we get here, the stream has ended
                logger.warning("Market data subscription stream ended")
                
            except asyncio.CancelledError:
                logger.info("Market data subscription cancelled")
                break
                
            except Exception as e:
                retry_count += 1
                logger.error(f"Error in market data subscription (attempt {retry_count}): {e}")
                
                if retry_count >= max_retries:
                    logger.error("Maximum retry attempts reached, giving up")
                    break
                
                # Exponential backoff for retries
                await asyncio.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, 60.0)  # Cap at 60 seconds
                
                # Close the channel before retrying
                if self.channel:
                    await self.channel.close()
                    self.channel = None
                    self.stub = None
        
        logger.info("Market data subscription task ended")
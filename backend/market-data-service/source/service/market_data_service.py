# source/market_data_service.py
import asyncio
import logging
import time
import grpc
from typing import Dict, List, Any

from source.api.grpc.market_exchange_interface_pb2 import SubscriptionRequest, MarketDataUpdate, SymbolData
from source.api.grpc.market_exchange_interface_pb2_grpc import MarketDataServiceServicer
from source.generator.market_data_generator import MarketDataGenerator
from source.db.database import DatabaseManager
from source.config import config

logger = logging.getLogger(__name__)

class MarketDataService(MarketDataServiceServicer):
    """
    Simple gRPC service that broadcasts market data to subscribers.
    """
    
    def __init__(self, generator: MarketDataGenerator, db_manager: DatabaseManager, update_interval: int = 60):
        self.generator = generator
        self.db_manager = db_manager
        self.update_interval = update_interval
        self.subscribers = {}  # Maps client_id to subscription stream context
        self.running = False
        self.broadcast_task = None
        
        # Metrics
        self.updates_sent = 0
        self.subscribers_count = 0
        
        logger.info(f"Market data service initialized with {update_interval}s interval")
    
    async def start(self):
        """Start the market data broadcast service"""
        if self.running:
            return
        
        # Connect to database
        await self.db_manager.connect()
        
        self.running = True
        logger.info("Market data service started")
        
        # Start the broadcast task
        self.broadcast_task = asyncio.create_task(self._broadcast_loop())
    
    async def stop(self):
        """Stop the market data broadcast service"""
        if not self.running:
            return
            
        logger.info("Stopping market data service")
        self.running = False
        
        if self.broadcast_task:
            self.broadcast_task.cancel()
            try:
                await self.broadcast_task
            except asyncio.CancelledError:
                pass
        
        # Close database connection
        await self.db_manager.close()
        
        logger.info("Market data service stopped")
    
    async def _broadcast_loop(self):
        """Main loop that broadcasts market data at regular intervals"""
        try:
            while self.running:
                if self.subscribers or True:  # Always generate and save data, even with no subscribers
                    # Update market data
                    self.generator.update_prices()
                    market_data = self.generator.get_market_data()
                    
                    # Save to database
                    await self.db_manager.save_market_data(market_data)
                    
                    # Broadcast to all subscribers (if any)
                    if self.subscribers:
                        await self._broadcast_market_data(market_data)
                        self.updates_sent += 1
                    
                # Sleep until next update
                await asyncio.sleep(self.update_interval)
        except asyncio.CancelledError:
            logger.info("Broadcast loop cancelled")
        except Exception as e:
            logger.error(f"Error in broadcast loop: {e}", exc_info=True)
            if self.running:
                # Restart the loop after a short delay
                await asyncio.sleep(5)
                self.broadcast_task = asyncio.create_task(self._broadcast_loop())
    
    async def _broadcast_market_data(self, market_data):
        """Broadcast market data to all subscribers"""
        logger.info(f"Broadcasting market data for {len(market_data)} symbols to {len(self.subscribers)} subscribers")
        
        # Convert market data to gRPC format
        timestamp = int(time.time() * 1000)
        
        symbol_data_list = []
        for md in market_data:
            symbol_data = SymbolData(
                symbol=md['symbol'],
                bid=md['bid'],
                ask=md['ask'],
                bid_size=md['bid_size'],
                ask_size=md['ask_size'],
                last_price=md['last_price'],
                last_size=md['last_size']
            )
            symbol_data_list.append(symbol_data)
        
        update = MarketDataUpdate(
            timestamp=timestamp,
            data=symbol_data_list
        )
        
        # Send to all subscribers
        dead_subscribers = []
        
        for client_id, context in self.subscribers.items():
            try:
                # Send update to this subscriber
                await context.write(update)
                logger.debug(f"Sent update to {client_id}")
            except Exception as e:
                logger.warning(f"Failed to send to {client_id}: {e}")
                dead_subscribers.append(client_id)
        
        # Remove dead subscribers
        for client_id in dead_subscribers:
            logger.info(f"Removing dead subscriber: {client_id}")
            del self.subscribers[client_id]
        
        self.subscribers_count = len(self.subscribers)
    
    async def SubscribeMarketData(self, request, context):
        """
        Handle subscription request from an exchange simulator.
        This is the gRPC method that subscribers call.
        """
        client_id = request.subscriber_id
        symbols = request.symbols
        
        logger.info(f"New subscription from {client_id} for symbols: {symbols}")
        
        # Register this subscriber
        self.subscribers[client_id] = context
        self.subscribers_count = len(self.subscribers)
        
        # Generate initial market data for requested symbols
        market_data = self.generator.get_market_data()
        
        # Filter for requested symbols if specified
        if symbols:
            market_data = [md for md in market_data if md['symbol'] in symbols]
        
        # Convert to gRPC format
        timestamp = int(time.time() * 1000)
        
        symbol_data_list = []
        for md in market_data:
            symbol_data = SymbolData(
                symbol=md['symbol'],
                bid=md['bid'],
                ask=md['ask'],
                bid_size=md['bid_size'],
                ask_size=md['ask_size'],
                last_price=md['last_price'],
                last_size=md['last_size']
            )
            symbol_data_list.append(symbol_data)
        
        initial_update = MarketDataUpdate(
            timestamp=timestamp,
            data=symbol_data_list
        )
        
        # Send initial update
        await context.write(initial_update)
        
        # Keep the stream open until client disconnects or we shut down
        try:
            while self.running and client_id in self.subscribers:
                await asyncio.sleep(10)  # Just keep the stream alive
        except Exception as e:
            logger.warning(f"Subscriber {client_id} disconnected: {e}")
        finally:
            # Clean up when client disconnects
            if client_id in self.subscribers:
                del self.subscribers[client_id]
                self.subscribers_count = len(self.subscribers)
                logger.info(f"Subscription ended for {client_id}")
                
        # Return value is ignored for server streaming RPCs
        return None
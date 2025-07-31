# source/service/market_data_service.py
import asyncio
import logging
import time
import grpc
from typing import Dict, List, Any

from source.api.grpc.market_exchange_interface_pb2 import SubscriptionRequest, MarketDataUpdate, SymbolData
from source.api.grpc.market_exchange_interface_pb2_grpc import MarketDataServiceServicer
from source.generator.market_data_generator import ControlledMarketDataGenerator
from source.db.database import DatabaseManager
from source.config import config

logger = logging.getLogger(__name__)

class MarketDataService(MarketDataServiceServicer):
    """
    Market data service that generates controlled data and streams to subscribers.
    All data is stored in PostgreSQL only.
    """
    
    def __init__(self, generator: ControlledMarketDataGenerator, db_manager: DatabaseManager, update_interval: int = 60):
        self.generator = generator
        self.db_manager = db_manager
        self.update_interval = update_interval
        self.subscribers = {}  # Maps client_id to subscription stream context
        self.running = False
        self.broadcast_task = None
        
        # Metrics
        self.updates_sent = 0
        self.subscribers_count = 0
        self.batch_count = 0
        self.database_saves = 0
        self.database_errors = 0
        
        logger.info(f"Market data service initialized with {update_interval}s interval")
        logger.info(f"PostgreSQL-only output - no CSV files")
    
    async def start(self):
        """Start the market data broadcast service"""
        if self.running:
            return
        
        # Connect to database
        await self.db_manager.connect()
        
        self.running = True
        logger.info("✅ Market data service started - PostgreSQL storage enabled")
        
        # Start the broadcast task
        self.broadcast_task = asyncio.create_task(self._broadcast_loop())
    
    async def stop(self):
        """Stop the market data broadcast service"""
        if not self.running:
            return
            
        logger.info("🛑 Stopping market data service")
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
        """Main loop that broadcasts controlled market data at regular intervals"""
        try:
            while self.running:
                # Update controlled prices and generate data
                self.generator.update_prices()
                market_data = self.generator.get_market_data()
                
                current_time = self.generator.get_current_time()
                
                # Save to PostgreSQL database only
                equity_saved = await self.db_manager.save_equity_data(market_data['equity'], current_time)
                fx_saved = await self.db_manager.save_fx_data(market_data['fx'], current_time)
                
                if equity_saved and fx_saved:
                    self.database_saves += 1
                    logger.debug("💾 Successfully saved data to PostgreSQL")
                else:
                    self.database_errors += 1
                    logger.error("❌ Failed to save data to PostgreSQL")
                
                # Broadcast to all subscribers
                if self.subscribers:
                    await self._broadcast_market_data(market_data)
                    self.updates_sent += 1
                
                self.batch_count += 1
                
                # Log controlled data generation
                timestamp_str = current_time.strftime('%H:%M:%S')
                prices = [f"{eq['symbol']}=${eq['close']:.2f}" for eq in market_data['equity']]
                fx_rates = [f"{fx['from_currency']}/{fx['to_currency']}={fx['rate']:.4f}" for fx in market_data['fx']]
                
                logger.info(f"💥 Generated controlled data batch #{self.batch_count} at {timestamp_str}")
                logger.info(f"💰 Prices: {', '.join(prices)}")
                if fx_rates:
                    logger.info(f"💱 FX rates: {', '.join(fx_rates)}")
                logger.info(f"💾 Saved to PostgreSQL: exch_us_equity schema")
                
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
        """Broadcast controlled market data to all subscribers"""
        logger.info(f"📡 Broadcasting controlled data for {len(market_data['equity'])} symbols to {len(self.subscribers)} subscribers")
        
        # Convert equity data to gRPC format
        symbol_data_list = []
        for eq in market_data['equity']:
            symbol_data = SymbolData(
                symbol=eq['symbol'],
                open=eq['open'],
                high=eq['high'],
                low=eq['low'],
                close=eq['close'],
                volume=eq['volume'],
                trade_count=eq['trade_count'],
                vwap=eq['vwap']
            )
            symbol_data_list.append(symbol_data)
        
        update = MarketDataUpdate(
            timestamp=market_data['timestamp'],
            data=symbol_data_list
        )
        
        # Send to all subscribers
        dead_subscribers = []
        
        for client_id, context in self.subscribers.items():
            try:
                await context.write(update)
                logger.debug(f"✅ Sent controlled data update to {client_id}")
            except Exception as e:
                logger.warning(f"⚠️ Failed to send to {client_id}: {e}")
                dead_subscribers.append(client_id)
        
        # Remove dead subscribers
        for client_id in dead_subscribers:
            logger.info(f"🗑️ Removing dead subscriber: {client_id}")
            del self.subscribers[client_id]
        
        self.subscribers_count = len(self.subscribers)
    
    async def SubscribeMarketData(self, request, context):
        """
        Handle subscription request from an exchange simulator.
        """
        client_id = request.subscriber_id
        symbols = request.symbols
        
        logger.info(f"📡 New subscription from {client_id} for symbols: {symbols}")
        
        # Register this subscriber
        self.subscribers[client_id] = context
        self.subscribers_count = len(self.subscribers)
        
        # Generate initial controlled market data
        market_data = self.generator.get_market_data()
        
        # Filter for requested symbols if specified
        equity_data = market_data['equity']
        if symbols:
            equity_data = [eq for eq in equity_data if eq['symbol'] in symbols]
        
        # Convert to gRPC format
        symbol_data_list = []
        for eq in equity_data:
            symbol_data = SymbolData(
                symbol=eq['symbol'],
                open=eq['open'],
                high=eq['high'],
                low=eq['low'],
                close=eq['close'],
                volume=eq['volume'],
                trade_count=eq['trade_count'],
                vwap=eq['vwap']
            )
            symbol_data_list.append(symbol_data)
        
        initial_update = MarketDataUpdate(
            timestamp=market_data['timestamp'],
            data=symbol_data_list
        )
        
        # Send initial update
        await context.write(initial_update)
        logger.info(f"📤 Sent initial data to {client_id}")
        
        # Keep the stream open until client disconnects or we shut down
        try:
            while self.running and client_id in self.subscribers:
                await asyncio.sleep(10)  # Keep stream alive
        except Exception as e:
            logger.warning(f"📡 Subscriber {client_id} disconnected: {e}")
        finally:
            # Clean up when client disconnects
            if client_id in self.subscribers:
                del self.subscribers[client_id]
                self.subscribers_count = len(self.subscribers)
                logger.info(f"📡 Subscription ended for {client_id}")
        
        return None

    def get_stats(self) -> Dict[str, Any]:
        """Get service statistics"""
        current_prices = self.generator.get_current_prices()
        current_fx_rates = self.generator.get_current_fx_rates()
        
        return {
            'batch_count': self.batch_count,
            'updates_sent': self.updates_sent,
            'database_saves': self.database_saves,
            'database_errors': self.database_errors,
            'subscribers_count': self.subscribers_count,
            'current_time': self.generator.get_current_time().isoformat(),
            'symbols': self.generator.get_symbols(),
            'fx_pairs': [f"{pair[0]}/{pair[1]}" for pair in self.generator.get_fx_pairs()],
            'current_prices': current_prices,
            'current_fx_rates': {f"{pair[0]}/{pair[1]}": rate for pair, rate in current_fx_rates.items()},
            'storage_type': 'PostgreSQL only'
        }
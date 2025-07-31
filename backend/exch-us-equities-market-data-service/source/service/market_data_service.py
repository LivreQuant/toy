# source/service/market_data_service.py
import asyncio
import logging
import time
import grpc
from datetime import datetime, timedelta
from typing import Dict, List, Any

from source.api.grpc.market_exchange_interface_pb2 import SubscriptionRequest, MarketDataUpdate, SymbolData
from source.api.grpc.market_exchange_interface_pb2_grpc import MarketDataServiceServicer
from source.generator.market_data_generator import ControlledMarketDataGenerator
from source.db.database import DatabaseManager
from source.config import config

logger = logging.getLogger(__name__)

class MarketDataService(MarketDataServiceServicer):
    """
    Market data service that generates minute bar data automatically at each minute boundary.
    Simulates real-time market data feed with minute bars.
    """
    
    def __init__(self, generator: ControlledMarketDataGenerator, db_manager: DatabaseManager):
        self.generator = generator
        self.db_manager = db_manager
        self.subscribers = {}  # Maps client_id to subscription stream context
        self.running = False
        self.broadcast_task = None
        
        # Metrics
        self.updates_sent = 0
        self.subscribers_count = 0
        self.batch_count = 0
        self.database_saves = 0
        self.database_errors = 0
        
        logger.info(f"Market data service initialized for minute bar generation")
        logger.info(f"Will generate data at each minute boundary (real-time simulation)")
    
    async def start(self):
        """Start the market data broadcast service"""
        if self.running:
            return
        
        # Connect to database
        await self.db_manager.connect()
        
        self.running = True
        logger.info("✅ Market data service started - minute bar generation enabled")
        
        # Start the broadcast task
        self.broadcast_task = asyncio.create_task(self._minute_bar_loop())
    
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
    
    async def _minute_bar_loop(self):
        """
        Main loop that generates minute bar data at each minute boundary.
        This simulates real-time market data feed behavior.
        """
        try:
            logger.info("🕐 Starting minute bar generation loop")
            
            while self.running:
                # Wait until the next minute boundary
                await self._wait_for_next_minute()
                
                if not self.running:
                    break
                
                # Generate minute bar data
                await self._generate_minute_bar()
                
        except asyncio.CancelledError:
            logger.info("Minute bar loop cancelled")
        except Exception as e:
            logger.error(f"Error in minute bar loop: {e}", exc_info=True)
            if self.running:
                # Restart the loop after a short delay
                await asyncio.sleep(5)
                self.broadcast_task = asyncio.create_task(self._minute_bar_loop())
    
    async def _wait_for_next_minute(self):
        """Wait until the next minute boundary (e.g., 10:31:00, 10:32:00, etc.)"""
        now = datetime.now()
        
        # Calculate next minute boundary
        next_minute = (now.replace(second=0, microsecond=0) + timedelta(minutes=1))
        
        # Calculate how long to wait
        wait_seconds = (next_minute - now).total_seconds()
        
        if wait_seconds > 0:
            logger.debug(f"⏰ Waiting {wait_seconds:.2f} seconds until next minute: {next_minute.strftime('%H:%M:%S')}")
            await asyncio.sleep(wait_seconds)
        
        # Log the minute bar timing
        actual_time = datetime.now()
        logger.info(f"🕐 Minute bar trigger at {actual_time.strftime('%H:%M:%S.%f')[:-3]}")
    
    async def _generate_minute_bar(self):
        """Generate and broadcast minute bar data"""
        try:
            # Update controlled prices and generate data
            self.generator.update_prices()
            market_data = self.generator.get_market_data()
            
            current_time = self.generator.get_current_time()
            real_time = datetime.now()
            
            # Save to PostgreSQL database
            equity_saved = await self.db_manager.save_equity_data(market_data['equity'], current_time)
            fx_saved = await self.db_manager.save_fx_data(market_data['fx'], current_time)
            
            if equity_saved and fx_saved:
                self.database_saves += 1
                logger.debug("💾 Successfully saved minute bar to PostgreSQL")
            else:
                self.database_errors += 1
                logger.error("❌ Failed to save minute bar to PostgreSQL")
            
            # Broadcast to all subscribers
            if self.subscribers:
                await self._broadcast_market_data(market_data)
                self.updates_sent += 1
            
            self.batch_count += 1
            
            # Log minute bar generation
            sim_time_str = current_time.strftime('%H:%M:%S')
            real_time_str = real_time.strftime('%H:%M:%S')
            prices = [f"{eq['symbol']}=${eq['close']:.2f}" for eq in market_data['equity']]
            fx_rates = [f"{fx['from_currency']}/{fx['to_currency']}={fx['rate']:.4f}" for fx in market_data['fx']]
            
            logger.info(f"📊 MINUTE BAR #{self.batch_count} | Sim: {sim_time_str} | Real: {real_time_str}")
            logger.info(f"💰 Prices: {', '.join(prices)}")
            if fx_rates:
                logger.info(f"💱 FX: {', '.join(fx_rates)}")
            logger.info(f"💾 Saved to exch_us_equity schema")
            
        except Exception as e:
            logger.error(f"Error generating minute bar: {e}", exc_info=True)
    
    async def _broadcast_market_data(self, market_data):
        """Broadcast minute bar data to all subscribers"""
        logger.debug(f"📡 Broadcasting minute bar for {len(market_data['equity'])} symbols to {len(self.subscribers)} subscribers")
        
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
                logger.debug(f"✅ Sent minute bar to {client_id}")
            except Exception as e:
                logger.warning(f"⚠️ Failed to send minute bar to {client_id}: {e}")
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
        
        # Generate initial market data
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
        logger.info(f"📤 Sent initial minute bar to {client_id}")
        
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
            'real_time': datetime.now().isoformat(),
            'symbols': self.generator.get_symbols(),
            'fx_pairs': [f"{pair[0]}/{pair[1]}" for pair in self.generator.get_fx_pairs()],
            'current_prices': current_prices,
            'current_fx_rates': {f"{pair[0]}/{pair[1]}": rate for pair, rate in current_fx_rates.items()},
            'storage_type': 'PostgreSQL only',
            'generation_type': 'Minute bar (real-time boundaries)'
        }
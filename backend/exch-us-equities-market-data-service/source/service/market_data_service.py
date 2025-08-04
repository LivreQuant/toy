# source/service/market_data_service.py
import asyncio
import logging
import time
import grpc
from datetime import datetime, timedelta
from typing import Dict, List, Any

from source.api.grpc.market_exchange_interface_pb2 import SubscriptionRequest, MarketDataStream, EquityData, FXRate
from source.api.grpc.market_exchange_interface_pb2_grpc import MarketDataServiceServicer
from source.generator.market_data_generator import ControlledMarketDataGenerator
from source.db.database import DatabaseManager
from source.config import config

logger = logging.getLogger(__name__)

class MarketDataService(MarketDataServiceServicer):
    """
    Market data service that generates minute bar data automatically at each minute boundary.
    Runs 24/7/365 in Kubernetes - provides live data during market hours, last available data otherwise.
    Uses current UTC time and converts to market timezone for hour determination.
    Always provides data regardless of weekends, holidays, or time of day.
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
        self.market_hours_updates = 0
        self.closed_hours_updates = 0
        self.weekend_updates = 0
        
        logger.info(f"Market data service initialized for 24/7/365 Kubernetes operation")
        logger.info(f"Always provides data - live during market hours, last available otherwise")
    
    async def start(self):
        """Start the market data broadcast service"""
        if self.running:
            return
        
        # Connect to database
        await self.db_manager.connect()
        
        self.running = True
        logger.info("✅ Market data service started - 24/7/365 Kubernetes operation")
        
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
        Runs 24/7/365 - always provides data based on market hours and exchange parameters.
        """
        try:
            logger.info("🕐 Starting 24/7/365 minute bar generation loop for Kubernetes")
            
            while self.running:
                # Wait until the next minute boundary
                await self._wait_for_next_minute()
                
                if not self.running:
                    break
                
                # Generate minute bar data (always generates data based on market hours)
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
        now = datetime.utcnow()
        
        # Calculate next minute boundary
        next_minute = (now.replace(second=0, microsecond=0) + timedelta(minutes=1))
        
        # Calculate how long to wait
        wait_seconds = (next_minute - now).total_seconds()
        
        if wait_seconds > 0:
            logger.debug(f"⏰ Waiting {wait_seconds:.2f} seconds until next minute: {next_minute.strftime('%H:%M:%S')} UTC")
            await asyncio.sleep(wait_seconds)
        
        # Log the minute bar timing
        actual_time = datetime.utcnow()
        logger.debug(f"🕐 Minute bar trigger at {actual_time.strftime('%H:%M:%S.%f')[:-3]} UTC")
    
    async def _generate_minute_bar(self):
        """Generate and broadcast minute bar data - always provides data based on exchange parameters"""
        try:
            # Update controlled prices and generate data (includes market hours logic)
            self.generator.update_prices()
            market_data = self.generator.get_market_data()
            
            utc_time = market_data['current_time']
            market_time = market_data['market_time']
            is_trading = market_data['is_trading_hours']
            market_status = market_data['market_status']
            is_weekend = market_data['is_weekend']
            weekday = market_data['weekday']
            
            # Save to PostgreSQL database (always save - Kubernetes runs 24/7/365)
            equity_saved = await self.db_manager.save_equity_data(market_data['equity'], utc_time)
            fx_saved = await self.db_manager.save_fx_data(market_data['fx'], utc_time)
            
            if equity_saved and fx_saved:
                self.database_saves += 1
                logger.debug("💾 Successfully saved minute bar to PostgreSQL")
            else:
                self.database_errors += 1
                logger.error("❌ Failed to save minute bar to PostgreSQL")
            
            # Broadcast to all subscribers (always broadcast - data depends on exchange parameters)
            if self.subscribers:
                await self._broadcast_market_data(market_data)
                self.updates_sent += 1
            
            # Update metrics
            if is_trading:
                self.market_hours_updates += 1
            elif is_weekend:
                self.weekend_updates += 1
            else:
                self.closed_hours_updates += 1
            
            self.batch_count += 1
            
            # Log minute bar generation with comprehensive status
            utc_time_str = utc_time.strftime('%H:%M:%S')
            market_time_str = market_time.strftime('%H:%M:%S %Z')
            prices = [f"{eq['symbol']}=${eq['close']:.2f}" for eq in market_data['equity']]
            fx_rates = [f"{fx['from_currency']}/{fx['to_currency']}={fx['rate']:.4f}" for fx in market_data['fx']]
            
            status_emoji = {
                'pre_market': '🌅',
                'regular_hours': '📈', 
                'after_hours': '🌆',
                'closed_hours': '🌙',
                'closed_weekend': '🏖️'
            }.get(market_status, '❓')
            
            data_type = "LIVE" if is_trading else "LAST"
            
            logger.info(f"📊 {status_emoji} MINUTE BAR #{self.batch_count} ({market_status.upper()}) | {weekday} | UTC: {utc_time_str} | Market: {market_time_str}")
            logger.info(f"💰 {data_type} Prices: {', '.join(prices)}")
            if fx_rates:
                logger.info(f"💱 {data_type} FX: {', '.join(fx_rates)}")
            logger.info(f"💾 Saved to exch_us_equity schema | K8s: Always Running")
            
            if not is_trading:
                reason = "Weekend" if is_weekend else "Closed Hours"
                logger.debug(f"🔄 {reason} - providing last available market data")
            
        except Exception as e:
            logger.error(f"Error generating minute bar: {e}", exc_info=True)
    
    async def _broadcast_market_data(self, market_data):
        """Broadcast minute bar data to all subscribers - always broadcasts based on exchange parameters"""
        is_trading = market_data['is_trading_hours']
        market_status = market_data['market_status']
        is_weekend = market_data['is_weekend']
        
        logger.debug(f"📡 Broadcasting {market_status} minute bar for {len(market_data['equity'])} symbols to {len(self.subscribers)} subscribers")
        
        # Convert equity data to protobuf EquityData format
        equity_data_list = []
        for eq in market_data['equity']:
            equity_data = EquityData(
                symbol=eq['symbol'],
                open=eq['open'],
                high=eq['high'],
                low=eq['low'],
                close=eq['close'],
                volume=eq['volume'],
                trade_count=eq['trade_count'],
                vwap=eq['vwap'],
                exchange=eq['exchange'],
                currency=eq['currency'],
                vwas=eq['vwas'],
                vwav=eq['vwav']
            )
            equity_data_list.append(equity_data)
        
        # Convert FX data to protobuf FXRate format
        fx_data_list = []
        for fx in market_data['fx']:
            fx_rate = FXRate(
                from_currency=fx['from_currency'],
                to_currency=fx['to_currency'],
                timestamp=fx['timestamp'],
                rate=fx['rate']
            )
            fx_data_list.append(fx_rate)
        
        # Create MarketDataStream message as defined in protobuf
        stream_message = MarketDataStream(
            timestamp=market_data['timestamp'],
            bin_time=market_data['bin_time'],
            equity=equity_data_list,
            fx=fx_data_list,
            batch_number=self.batch_count
        )
        
        # Send to all subscribers
        dead_subscribers = []
        
        for client_id, context in self.subscribers.items():
            try:
                await context.write(stream_message)
                data_type = "live" if is_trading else ("weekend last" if is_weekend else "last market")
                logger.debug(f"✅ Sent {data_type} minute bar to {client_id}")
            except Exception as e:
                logger.warning(f"⚠️ Failed to send minute bar to {client_id}: {e}")
                dead_subscribers.append(client_id)
        
        # Remove dead subscribers
        for client_id in dead_subscribers:
            logger.info(f"🗑️ Removing dead subscriber: {client_id}")
            del self.subscribers[client_id]
        
        self.subscribers_count = len(self.subscribers)
    
    async def SubscribeToMarketData(self, request: SubscriptionRequest, context):
        """
        Handle subscription request from an exchange simulator.
        Always provides data - live during market hours, last available otherwise.
        Matches the protobuf service definition exactly.
        """
        client_id = request.subscriber_id
        include_history = request.include_history
        
        logger.info(f"📡 New subscription from {client_id} (include_history: {include_history})")
        
        # Register this subscriber
        self.subscribers[client_id] = context
        self.subscribers_count = len(self.subscribers)
        
        # Generate initial market data
        market_data = self.generator.get_market_data()
        is_trading = market_data['is_trading_hours']
        market_status = market_data['market_status']
        is_weekend = market_data['is_weekend']
       
        # Convert equity data to protobuf format
        equity_data_list = []
        for eq in market_data['equity']:
            equity_data = EquityData(
                symbol=eq['symbol'],
                open=eq['open'],
                high=eq['high'],
                low=eq['low'],
                close=eq['close'],
                volume=eq['volume'],
                trade_count=eq['trade_count'],
                vwap=eq['vwap'],
                exchange=eq['exchange'],
                currency=eq['currency'],
                vwas=eq['vwas'],
                vwav=eq['vwav']
            )
            equity_data_list.append(equity_data)
        
        # Convert FX data to protobuf format
        fx_data_list = []
        for fx in market_data['fx']:
            fx_rate = FXRate(
                from_currency=fx['from_currency'],
                to_currency=fx['to_currency'],
                timestamp=fx['timestamp'],
                rate=fx['rate']
            )
            fx_data_list.append(fx_rate)
        
        # Create initial MarketDataStream message
        initial_stream = MarketDataStream(
            timestamp=market_data['timestamp'],
            bin_time=market_data['bin_time'],
            equity=equity_data_list,
            fx=fx_data_list,
            batch_number=self.batch_count
        )
        
        # Send initial update with market status info
        await context.write(initial_stream)
        data_type = "live" if is_trading else ("weekend last" if is_weekend else "last market")
        logger.info(f"📤 Sent initial {data_type} minute bar to {client_id} (market: {market_status})")
        
        # If history is requested, send historical data (implement as needed)
        if include_history:
            logger.info(f"📚 Historical data requested by {client_id} - implement historical data logic here")
            # TODO: Implement historical data retrieval from database
        
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

    def get_stats(self) -> Dict[str, Any]:
        """Get service statistics including 24/7/365 operation info"""
        current_prices = self.generator.get_current_prices()
        current_fx_rates = self.generator.get_current_fx_rates()
        is_trading, market_status = self.generator.get_market_status()
        utc_time = self.generator.get_current_time()
        market_time = self.generator.get_current_market_time()
        
        return {
            'batch_count': self.batch_count,
            'updates_sent': self.updates_sent,
            'database_saves': self.database_saves,
            'database_errors': self.database_errors,
            'subscribers_count': self.subscribers_count,
            'market_hours_updates': self.market_hours_updates,
            'closed_hours_updates': self.closed_hours_updates,
            'weekend_updates': self.weekend_updates,
            'utc_time': utc_time.isoformat() + 'Z',
            'market_time': market_time.strftime('%Y-%m-%d %H:%M:%S %Z'),
            'market_status': market_status,
            'is_trading_hours': is_trading,
            'is_weekend': market_time.weekday() >= 5,
            'weekday': market_time.strftime('%A'),
            'symbols': self.generator.get_symbols(),
            'fx_pairs': [f"{pair[0]}/{pair[1]}" for pair in self.generator.get_fx_pairs()],
            'current_prices': current_prices,
            'current_fx_rates': {f"{pair[0]}/{pair[1]}": rate for pair, rate in current_fx_rates.items()},
            'storage_type': 'PostgreSQL only',
            'generation_type': '24/7/365 Kubernetes operation - always provides data',
            'timezone': self.generator.timezone_name,
            'data_policy': 'Live during market hours, last available otherwise',
            'kubernetes_operation': 'Continuous 24/7/365',
            'market_hours_config': {
                'pre_market': f"{self.generator.pre_market_start_hour:02d}:{self.generator.pre_market_start_minute:02d}-{self.generator.market_open_hour:02d}:{self.generator.market_open_minute:02d}",
                'regular': f"{self.generator.market_open_hour:02d}:{self.generator.market_open_minute:02d}-{self.generator.market_close_hour:02d}:{self.generator.market_close_minute:02d}",
                'after_hours': f"{self.generator.market_close_hour:02d}:{self.generator.market_close_minute:02d}-{self.generator.after_hours_end_hour:02d}:{self.generator.after_hours_end_minute:02d}",
                'timezone': self.generator.timezone_name
            }
        }
# scheduler.py
import asyncio
import logging
from datetime import datetime, timedelta, time
import pytz

logger = logging.getLogger(__name__)

class Scheduler:
    def __init__(self, db_manager, k8s_manager, check_interval=60):
        self.db_manager = db_manager
        self.k8s_manager = k8s_manager
        self.check_interval = check_interval  # seconds
        self.running = False
    
    def should_exchange_be_running(self, exchange) -> bool:
        """Determine if exchange should be running based on market hours"""
        # Get current time in UTC
        now_utc = datetime.utcnow().replace(tzinfo=pytz.UTC)
        
        # Get exchange timezone
        exchange_tz_str = exchange.get('timezone', 'America/New_York')
        try:
            exchange_tz = pytz.timezone(exchange_tz_str)
        except Exception as e:
            logger.error(f"Invalid timezone {exchange_tz_str} for {exchange.get('exchange_name', 'Unknown')}: {e}")
            exchange_tz = pytz.timezone('America/New_York')  # Fallback
        
        # Convert to exchange local time
        now_local = now_utc.astimezone(exchange_tz)
        today_local = now_local.date()
        
        # Skip weekends (Saturday=5, Sunday=6)
        if now_local.weekday() >= 5:
            logger.info(f"Weekend detected ({now_local.strftime('%A')}), exchange {exchange.get('exchange_name', 'Unknown')} should not run")
            return False
        
        # Get market hours (these are time objects)
        pre_open = exchange['pre_open_time']  # e.g., 04:00:00
        post_close = exchange['post_close_time']  # e.g., 20:00:00
        
        # Convert times to datetime objects in the exchange timezone
        pre_open_dt = exchange_tz.localize(datetime.combine(today_local, pre_open))
        post_close_dt = exchange_tz.localize(datetime.combine(today_local, post_close))
        
        # Add 5-minute buffers
        buffer = timedelta(minutes=5)
        start_time = pre_open_dt - buffer  # 03:55:00 NY time
        end_time = post_close_dt + buffer   # 20:05:00 NY time
        
        should_run = start_time <= now_local <= end_time
        
        # Detailed logging
        exchange_name = exchange.get('exchange_name', 'Unknown')
        logger.info(f"🕐 Exchange {exchange_name} time check:")
        logger.info(f"   Current UTC: {now_utc.strftime('%Y-%m-%d %H:%M:%S %Z')}")
        logger.info(f"   Current {exchange_tz_str}: {now_local.strftime('%Y-%m-%d %H:%M:%S %Z')}")
        logger.info(f"   Market window: {start_time.strftime('%H:%M:%S')} - {end_time.strftime('%H:%M:%S')} {exchange_tz_str}")
        logger.info(f"   Should be running: {should_run}")
        
        return should_run
    
    async def check_and_update_exchanges(self):
        """Main logic: check each exchange and start/stop as needed"""
        try:
            exchanges = await self.db_manager.get_active_exchanges()
            logger.info(f"🔍 Checking {len(exchanges)} exchanges for market hours")
            
            if not exchanges:
                logger.warning("⚠️  No exchanges found in database!")
                return
            
            for exchange in exchanges:
                exch_id = exchange['exch_id']
                exchange_name = exchange.get('exchange_name', 'Unknown')
                
                should_run = self.should_exchange_be_running(exchange)
                is_running = exch_id in self.k8s_manager.get_running_exchanges()
                
                logger.info(f"📊 Exchange {exchange_name} (ID: {exch_id}): should_run={should_run}, is_running={is_running}")
                
                if should_run and not is_running:
                    logger.info(f"🚀 Market hours: Starting {exchange_name}")
                    try:
                        await self.k8s_manager.start_exchange(exchange)
                        logger.info(f"✅ Successfully started {exchange_name}")
                    except Exception as e:
                        logger.error(f"❌ Failed to start {exchange_name}: {e}")
                        
                elif not should_run and is_running:
                    logger.info(f"🛑 Market closed: Stopping {exchange_name}")
                    try:
                        await self.k8s_manager.stop_exchange(exchange)
                        logger.info(f"✅ Successfully stopped {exchange_name}")
                    except Exception as e:
                        logger.error(f"❌ Failed to stop {exchange_name}: {e}")
                        
                else:
                    logger.debug(f"😴 No action needed for {exchange_name}")
                    
        except Exception as e:
            logger.error(f"Error in scheduler check: {e}", exc_info=True)
    
    async def check_exchange_health(self):
        """Check health of all running exchanges"""
        try:
            # Get all exchanges to have proper metadata for health checks
            exchanges = await self.db_manager.get_active_exchanges()
            running_exchanges = self.k8s_manager.get_running_exchanges()
            
            if not running_exchanges:
                logger.debug("No running exchanges to health check")
                return
            
            logger.debug(f"🏥 Health checking {len(running_exchanges)} running exchanges")
            
            for exchange in exchanges:
                if exchange['exch_id'] in running_exchanges:
                    # Check this specific exchange's health
                    is_healthy = await self.k8s_manager.check_exchange_health(exchange)
                    if not is_healthy:
                        logger.error(f"💔 Exchange {exchange.get('exchange_name', 'Unknown')} failed health check!")
                        # For now, just log the error. In the future, we could restart it here.
                        
        except Exception as e:
            logger.error(f"Error during health check: {e}", exc_info=True)
    
    async def run(self):
        """Main scheduler loop"""
        self.running = True
        logger.info(f"🔄 Scheduler started (checking every {self.check_interval}s)")
        
        while self.running:
            logger.info("🔍 Starting scheduler check cycle...")
            
            # Check and start/stop exchanges based on market hours
            await self.check_and_update_exchanges()
            
            # Check health of running exchanges
            await self.check_exchange_health()
            
            logger.info(f"⏰ Scheduler cycle complete, sleeping for {self.check_interval}s...")
            await asyncio.sleep(self.check_interval)
        
        logger.info("Scheduler stopped")
    
    def stop(self):
        """Stop the scheduler"""
        self.running = False
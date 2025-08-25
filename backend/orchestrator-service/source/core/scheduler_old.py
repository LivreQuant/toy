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
            logger.error(f"Invalid timezone {exchange_tz_str} for exchange service {exchange.get('exch_id', 'Unknown')}: {e}")
            exchange_tz = pytz.timezone('America/New_York')  # Fallback
        
        # Get today's date in the exchange timezone to handle date rollover correctly
        today_local = now_utc.astimezone(exchange_tz).date()
        
        # Skip weekends (Saturday=5, Sunday=6) based on exchange local date
        local_weekday = now_utc.astimezone(exchange_tz).weekday()
        if local_weekday >= 5:
            logger.debug(f"Weekend detected in {exchange_tz_str}, exchange service should not run")
            return False
        
        # Get market hours from database (these are in exchange local time)
        pre_open_local = exchange['pre_open_time']      # e.g., 04:00:00 EDT
        post_close_local = exchange['post_close_time']  # e.g., 13:44:00 EDT
        
        # Convert local market hours to UTC datetime objects
        pre_open_local_dt = exchange_tz.localize(datetime.combine(today_local, pre_open_local))
        post_close_local_dt = exchange_tz.localize(datetime.combine(today_local, post_close_local))
        
        # Convert to UTC
        pre_open_utc = pre_open_local_dt.astimezone(pytz.UTC)
        post_close_utc = post_close_local_dt.astimezone(pytz.UTC)
        
        # Add 5-minute buffers
        buffer = timedelta(minutes=5)
        start_time_utc = pre_open_utc - buffer
        end_time_utc = post_close_utc + buffer
        
        # Check if we should be running (all in UTC)
        should_run = start_time_utc <= now_utc <= end_time_utc
        
        # Detailed logging for debugging
        exch_id = exchange.get('exch_id', 'Unknown')
        exchange_type = exchange.get('exchange_type', 'Unknown')
        
        logger.info(f"⏰ Exchange service {exch_id} ({exchange_type}) time check:")
        logger.info(f"   Current UTC: {now_utc.strftime('%Y-%m-%d %H:%M:%S %Z')}")
        logger.info(f"   Exchange timezone: {exchange_tz_str}")
        logger.info(f"   Market hours (local): {pre_open_local} - {post_close_local} {exchange_tz_str}")
        logger.info(f"   Market hours (UTC): {pre_open_utc.strftime('%H:%M:%S')} - {post_close_utc.strftime('%H:%M:%S')} UTC")
        logger.info(f"   Market window with buffer (UTC): {start_time_utc.strftime('%H:%M:%S')} - {end_time_utc.strftime('%H:%M:%S')} UTC")
        logger.info(f"   Should be running: {should_run}")
        
        # Additional debug info
        if not should_run:
            if now_utc < start_time_utc:
                logger.info(f"   Reason: Current UTC time {now_utc.strftime('%H:%M:%S')} is before market start {start_time_utc.strftime('%H:%M:%S')} UTC")
            elif now_utc > end_time_utc:
                logger.info(f"   Reason: Current UTC time {now_utc.strftime('%H:%M:%S')} is after market end {end_time_utc.strftime('%H:%M:%S')} UTC")
        
        return should_run
    
    async def check_and_update_exchanges(self):
        """Main logic: check each exchange and start/stop as needed"""
        try:
            exchanges = await self.db_manager.get_active_exchanges()
            logger.info(f"🔍 Checking {len(exchanges)} exchange services for market hours")
            
            if not exchanges:
                logger.warning("⚠️ No exchange services found in database!")
                return
            
            for exchange in exchanges:
                exch_id = exchange['exch_id']
                exchange_type = exchange.get('exchange_type', 'Unknown')
                
                should_run = self.should_exchange_be_running(exchange)
                is_running = str(exch_id) in self.k8s_manager.get_running_exchanges()
                
                logger.info(f"📊 Exchange service {exch_id} ({exchange_type}): should_run={should_run}, is_running={is_running}")
                
                if should_run and not is_running:
                    logger.info(f"🚀 Market hours: Starting exchange service {exch_id}")
                    try:
                        await self.k8s_manager.start_exchange(exchange)
                        logger.info(f"✅ Successfully started exchange service {exch_id}")
                    except Exception as e:
                        logger.error(f"❌ Failed to start exchange service {exch_id}: {e}")
                        
                elif not should_run and is_running:
                    logger.info(f"🛑 Market closed: Stopping exchange service {exch_id}")
                    try:
                        await self.k8s_manager.stop_exchange(exchange)
                        logger.info(f"✅ Successfully stopped exchange service {exch_id}")
                    except Exception as e:
                        logger.error(f"❌ Failed to stop exchange service {exch_id}: {e}")
                        
                else:
                    logger.debug(f"😴 No action needed for exchange service {exch_id}")
                    
        except Exception as e:
            logger.error(f"Error in scheduler check: {e}", exc_info=True)
    
    async def check_exchange_health(self):
        """Check health of all running exchanges"""
        try:
            # Get all exchanges to have proper metadata for health checks
            exchanges = await self.db_manager.get_active_exchanges()
            running_exchanges = self.k8s_manager.get_running_exchanges()
            
            if not running_exchanges:
                logger.debug("No running exchange services to health check")
                return
            
            logger.debug(f"🏥 Health checking {len(running_exchanges)} running exchange services")
            
            for exchange in exchanges:
                if str(exchange['exch_id']) in running_exchanges:
                    # Check this specific exchange's health
                    is_healthy = await self.k8s_manager.check_exchange_health(exchange)
                    if not is_healthy:
                        logger.error(f"💔 Exchange service {exchange.get('exch_id', 'Unknown')} failed health check!")
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
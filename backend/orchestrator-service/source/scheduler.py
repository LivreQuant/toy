# orchestrator/scheduler.py
import asyncio
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class Scheduler:
    def __init__(self, db_manager, k8s_manager, check_interval=60):
        self.db_manager = db_manager
        self.k8s_manager = k8s_manager
        self.check_interval = check_interval  # seconds
        self.running = False
    
    def should_exchange_be_running(self, exchange) -> bool:
        """Determine if exchange should be running based on market hours"""
        now = datetime.utcnow().time()
        
        # Skip weekends (Saturday=5, Sunday=6)
        if datetime.utcnow().weekday() >= 5:
            return False
        
        # Calculate start/end times with 5-minute buffers
        start_time = (datetime.combine(datetime.today(), exchange['pre_open_time']) 
                     - timedelta(minutes=5)).time()
        end_time = (datetime.combine(datetime.today(), exchange['post_close_time']) 
                   + timedelta(minutes=5)).time()
        
        return start_time <= now <= end_time
    
    async def check_and_update_exchanges(self):
        """Main logic: check each exchange and start/stop as needed"""
        try:
            exchanges = await self.db_manager.get_active_exchanges()
            logger.debug(f"Checking {len(exchanges)} exchanges")
            
            for exchange in exchanges:
                should_run = self.should_exchange_be_running(exchange)
                is_running = exchange['exch_id'] in self.k8s_manager.get_running_exchanges()
                
                if should_run and not is_running:
                    logger.info(f"Market hours: Starting {exchange['exchange_id']}")
                    await self.k8s_manager.start_exchange(exchange)
                    
                elif not should_run and is_running:
                    logger.info(f"Market closed: Stopping {exchange['exchange_id']}")
                    await self.k8s_manager.stop_exchange(exchange)
                    
        except Exception as e:
            logger.error(f"Error in scheduler check: {e}")
    
    async def check_exchange_health(self):
        """Check health of all running exchanges"""
        try:
            # Get all exchanges to have proper metadata for health checks
            exchanges = await self.db_manager.get_active_exchanges()
            running_exchanges = self.k8s_manager.get_running_exchanges()
            
            if not running_exchanges:
                logger.debug("No running exchanges to health check")
                return
            
            logger.debug(f"Health checking {len(running_exchanges)} running exchanges")
            
            for exchange in exchanges:
                if exchange['exch_id'] in running_exchanges:
                    # Check this specific exchange's health
                    is_healthy = await self.k8s_manager.check_exchange_health(exchange)
                    if not is_healthy:
                        logger.error(f"Exchange {exchange['exchange_id']} failed health check!")
                        # For now, just log the error. In the future, we could restart it here.
                        
        except Exception as e:
            logger.error(f"Error during health check: {e}")
    
    async def run(self):
        """Main scheduler loop"""
        self.running = True
        logger.info(f"Scheduler started (checking every {self.check_interval}s)")
        
        while self.running:
            # Check and start/stop exchanges based on market hours
            await self.check_and_update_exchanges()
            
            # Check health of running exchanges
            await self.check_exchange_health()
            
            await asyncio.sleep(self.check_interval)
        
        logger.info("Scheduler stopped")
    
    def stop(self):
        """Stop the scheduler"""
        self.running = False
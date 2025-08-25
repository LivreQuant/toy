# source/core/scheduler.py
import asyncio
import logging
from datetime import datetime, time, timedelta
from typing import Dict, Any
import pytz

logger = logging.getLogger(__name__)

class EnhancedScheduler:
    """Enhanced scheduler handling SOD, EOD, and exchange operations"""
    
    def __init__(self, orchestrator, check_interval=30):
        self.orchestrator = orchestrator
        self.check_interval = check_interval  # seconds
        
        # Schedule configuration - these would normally come from config
        self.sod_time = time(3, 0)  # 3:00 AM EDT (before pre-market)
        self.eod_time = time(18, 0)  # 6:00 PM EDT (after post-market)
        
        # Tracking
        self.last_sod_check = None
        self.last_eod_check = None
        
        logger.info(f"📅 Enhanced scheduler initialized (SOD: {self.sod_time}, EOD: {self.eod_time})")
    
    async def check_and_execute_operations(self):
        """Main scheduler check - handles SOD, EOD, and exchange lifecycle"""
        now_utc = datetime.utcnow().replace(tzinfo=pytz.UTC)
        ny_tz = pytz.timezone('America/New_York')
        now_ny = now_utc.astimezone(ny_tz)
        
        logger.debug(f"⏰ Scheduler check at {now_ny.strftime('%H:%M:%S')} NY time")
        
        # Skip weekends
        if now_ny.weekday() >= 5:
            logger.debug("📅 Weekend - skipping all operations")
            return
        
        # Check for SOD operations
        await self._check_sod_operations(now_ny)
        
        # Check for exchange lifecycle management (only if SOD complete)
        if self.orchestrator.sod_complete:
            await self._check_exchange_operations(now_ny)
        
        # Check for EOD operations
        await self._check_eod_operations(now_ny)
        
        # Perform health checks
        await self._perform_health_checks()
    
    async def _check_sod_operations(self, now_ny: datetime):
        """Check if SOD operations should be triggered"""
        from core.orchestrator import SystemState
        
        # Only trigger SOD if we're in IDLE state and haven't run SOD today
        if (self.orchestrator.current_state != SystemState.IDLE or 
            self.orchestrator.sod_complete):
            return
        
        # Check if it's time for SOD
        if now_ny.time() >= self.sod_time:
            # Make sure we haven't already tried SOD today
            today = now_ny.date()
            if (self.last_sod_check is None or 
                self.last_sod_check.date() < today):
                
                logger.info(f"🌅 SOD time reached at {now_ny.strftime('%H:%M:%S')} - triggering SOD operations")
                self.last_sod_check = now_ny
                
                # Trigger SOD in background
                asyncio.create_task(self.orchestrator.trigger_sod_operations())
    
    async def _check_exchange_operations(self, now_ny: datetime):
        """Check exchange lifecycle (start/stop based on market hours)"""
        try:
            exchanges = await self.orchestrator.db_manager.get_active_exchanges()
            
            for exchange in exchanges:
                should_run = self.should_exchange_be_running(exchange, now_ny)
                is_running = str(exchange['exch_id']) in self.orchestrator.k8s_manager.get_running_exchanges()
                
                if should_run and not is_running:
                    logger.info(f"🚀 Market hours: Starting exchange {exchange['exch_id']}")
                    await self.orchestrator.k8s_manager.start_exchange(exchange)
                    
                elif not should_run and is_running:
                    logger.info(f"🛑 Market closed: Stopping exchange {exchange['exch_id']}")
                    await self.orchestrator.k8s_manager.stop_exchange(exchange)
                    
        except Exception as e:
            logger.error(f"❌ Error in exchange operations check: {e}", exc_info=True)
    
    async def _check_eod_operations(self, now_ny: datetime):
        """Check if EOD operations should be triggered"""
        from core.orchestrator import SystemState
        
        # Only trigger EOD if we're in TRADING_ACTIVE state and haven't run EOD today
        if (self.orchestrator.current_state != SystemState.TRADING_ACTIVE or 
            self.orchestrator.eod_complete):
            return
        
        # Check if it's time for EOD
        if now_ny.time() >= self.eod_time:
            # Make sure we haven't already tried EOD today
            today = now_ny.date()
            if (self.last_eod_check is None or 
                self.last_eod_check.date() < today):
                
                logger.info(f"🌅 EOD time reached at {now_ny.strftime('%H:%M:%S')} - triggering EOD operations")
                self.last_eod_check = now_ny
                
                # Trigger EOD in background
                asyncio.create_task(self.orchestrator.trigger_eod_operations())
    
    def should_exchange_be_running(self, exchange, now_ny: datetime) -> bool:
        """Determine if exchange should be running (same logic as before but enhanced)"""
        # Get exchange timezone
        exchange_tz_str = exchange.get('timezone', 'America/New_York')
        try:
            exchange_tz = pytz.timezone(exchange_tz_str)
        except Exception as e:
            logger.error(f"Invalid timezone {exchange_tz_str}: {e}")
            exchange_tz = pytz.timezone('America/New_York')
        
        # Convert to exchange timezone
        now_local = now_ny.astimezone(exchange_tz)
        today_local = now_local.date()
        
        # Skip weekends
        if now_local.weekday() >= 5:
            return False
        
        # Get market hours
        pre_open_local = exchange['pre_open_time']
        post_close_local = exchange['post_close_time']
        
        # Convert to datetime objects in exchange timezone
        pre_open_dt = exchange_tz.localize(datetime.combine(today_local, pre_open_local))
        post_close_dt = exchange_tz.localize(datetime.combine(today_local, post_close_local))
        
        # Add buffers
        buffer = timedelta(minutes=5)
        start_time = pre_open_dt - buffer
        end_time = post_close_dt + buffer
        
        return start_time <= now_local <= end_time
    
    async def _perform_health_checks(self):
        """Perform system health checks"""
        try:
            # Check running exchanges health
            await self.orchestrator.k8s_manager.check_all_running_exchanges_health()
            
            # Check database connectivity
            await self._check_database_health()
            
            # Update metrics
            await self.orchestrator.metrics.update_health_metrics()
            
        except Exception as e:
            logger.error(f"❌ Health check failed: {e}", exc_info=True)
    
    async def _check_database_health(self):
        """Check database connectivity"""
        try:
            # Simple query to check DB health
            await self.orchestrator.db_manager.get_active_exchanges()
            logger.debug("✅ Database health check passed")
        except Exception as e:
            logger.error(f"💔 Database health check failed: {e}")
            raise
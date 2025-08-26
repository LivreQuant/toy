# source/core/orchestrator.py
import asyncio
import logging
from datetime import datetime, time
from typing import Dict, Any, Optional, List
from enum import Enum
import pytz

from database import DatabaseManager
from exchanges.kubernetes_manager import KubernetesManager
from core.scheduler import EnhancedScheduler
from core.state_manager import StateManager
from sod.coordinator import SODCoordinator
from eod.coordinator import EODCoordinator
from workflows.workflow_engine import WorkflowEngine
from common.notifications import NotificationManager
from common.metrics import MetricsCollector

logger = logging.getLogger(__name__)

class SystemState(Enum):
    STARTING = "starting"
    SOD_RUNNING = "sod_running"
    TRADING_ACTIVE = "trading_active" 
    EOD_RUNNING = "eod_running"
    IDLE = "idle"
    ERROR = "error"

class TradingOrchestrator:
    """Enhanced orchestrator managing complete trading operations lifecycle"""
    
    def __init__(self):
        # Core components
        self.db_manager = DatabaseManager()
        self.k8s_manager = KubernetesManager()
        self.state_manager = StateManager()
        self.workflow_engine = WorkflowEngine()
        self.notifications = NotificationManager()
        self.metrics = MetricsCollector()
        
        # Operations coordinators
        self.sod_coordinator = SODCoordinator(self)
        self.eod_coordinator = EODCoordinator(self)
        
        # Scheduler (initialized after other components)
        self.scheduler = None
        
        # State tracking
        self.current_state = SystemState.STARTING
        self.running = False
        self.sod_complete = False
        self.eod_complete = False
        
        # Timezone
        self.market_tz = pytz.timezone('America/New_York')
        
        logger.info("🏗️ Trading Orchestrator initialized")
    
    async def initialize(self):
        """Initialize all components with proper state recovery"""
        logger.info("🔧 Initializing orchestrator components...")
        
        # Initialize database first
        await self.db_manager.init()
        logger.info("✅ Database manager initialized")
        
        # Initialize state manager and load previous state
        await self.state_manager.initialize(self.db_manager)
        logger.info("✅ State manager initialized")
        
        # Load and recover state
        recovery_info = await self.state_manager.load_current_state()
        await self._recover_system_state(recovery_info)
        
        # Initialize workflow engine
        await self.workflow_engine.initialize()
        logger.info("✅ Workflow engine initialized")
        
        # Initialize coordinators
        await self.sod_coordinator.initialize()
        await self.eod_coordinator.initialize()
        logger.info("✅ SOD/EOD coordinators initialized")
        
        # Initialize metrics collection
        await self.metrics.initialize()
        logger.info("✅ Metrics collector initialized")
        
        # Initialize scheduler last (needs orchestrator reference)
        self.scheduler = EnhancedScheduler(self)
        logger.info("✅ Enhanced scheduler initialized")
        
        logger.info("🎉 All components initialized successfully")
        logger.info(f"📊 System state: {self.current_state.value}")
        logger.info(f"📊 SOD complete: {self.sod_complete}, EOD complete: {self.eod_complete}")
    
    async def _recover_system_state(self, recovery_info: Dict[str, Any]):
        """Recover system state after restart"""
        logger.info("🔄 Recovering system state...")
        
        if recovery_info.get("eod_complete"):
            # EOD completed today - system should be idle
            self.eod_complete = True
            self.sod_complete = False  # Reset for next day
            self.current_state = SystemState.IDLE
            logger.info("🌙 Recovered to IDLE state (EOD completed today)")
            
        elif recovery_info.get("sod_complete"):
            # SOD completed today but not EOD - system should be trading active
            self.sod_complete = True
            self.eod_complete = False
            self.current_state = SystemState.TRADING_ACTIVE
            logger.info("🌅 Recovered to TRADING_ACTIVE state (SOD completed today)")
            
            # Check if any exchanges are already running and reconcile
            await self._reconcile_running_exchanges()
        else:
            # Neither SOD nor EOD completed today - system should be idle
            self.sod_complete = False
            self.eod_complete = False
            self.current_state = SystemState.IDLE
            logger.info("⏸️ Recovered to IDLE state (no operations completed today)")
    
    async def _reconcile_running_exchanges(self):
        """Reconcile running exchanges with expected state on startup"""
        try:
            running_exchange_ids = self.k8s_manager.get_running_exchanges()
            
            if running_exchange_ids:
                logger.info(f"🔄 Found {len(running_exchange_ids)} exchanges already running: {list(running_exchange_ids)}")
                
                if self.sod_complete:
                    logger.info("✅ SOD complete - running exchanges are acceptable")
                else:
                    logger.warning("⚠️ Exchanges running but SOD not complete - may need manual intervention")
            else:
                logger.info("✅ No exchanges currently running")
                
        except Exception as e:
            logger.error(f"❌ Failed to reconcile running exchanges: {e}")
    
    async def run(self):
        """Main orchestrator loop"""
        self.running = True
        logger.info("🔄 Starting orchestrator main loop")
        
        while self.running:
            try:
                await self.scheduler.check_and_execute_operations()
                
                # Collect metrics
                await self.metrics.collect_system_metrics()
                
                # Sleep for scheduler interval
                await asyncio.sleep(self.scheduler.check_interval)
                
            except Exception as e:
                logger.error(f"❌ Error in orchestrator main loop: {e}", exc_info=True)
                await self.handle_system_error(e)
                await asyncio.sleep(30)  # Wait before retrying
        
        logger.info("🛑 Orchestrator main loop stopped")
    
    async def trigger_sod_operations(self) -> bool:
        """Trigger start of day operations"""
        if self.current_state != SystemState.IDLE:
            logger.warning(f"⚠️ Cannot start SOD - current state: {self.current_state}")
            return False
        
        logger.info("🌅 Starting Start of Day operations")
        self.current_state = SystemState.SOD_RUNNING
        self.sod_complete = False
        
        try:
            # Execute SOD workflow
            sod_result = await self.sod_coordinator.execute_sod_workflow()
            
            if sod_result.success:
                self.sod_complete = True
                self.current_state = SystemState.TRADING_ACTIVE
                logger.info("✅ Start of Day operations completed successfully")
                
                # Send success notification
                await self.notifications.send_notification(
                    "SOD_SUCCESS", 
                    "Start of Day operations completed successfully",
                    {"duration_seconds": sod_result.execution_time}
                )
                return True
            else:
                logger.error(f"❌ Start of Day operations failed: {sod_result.error}")
                self.current_state = SystemState.ERROR
                
                # Send failure notification
                await self.notifications.send_notification(
                    "SOD_FAILED",
                    f"Start of Day operations failed: {sod_result.error}",
                    {"error": str(sod_result.error)}
                )
                return False
                
        except Exception as e:
            logger.error(f"❌ Exception during SOD operations: {e}", exc_info=True)
            self.current_state = SystemState.ERROR
            await self.notifications.send_notification(
                "SOD_ERROR", 
                f"Exception during SOD operations: {str(e)}"
            )
            return False
    
    async def trigger_eod_operations(self) -> bool:
        """Trigger end of day operations"""
        if self.current_state != SystemState.TRADING_ACTIVE:
            logger.warning(f"⚠️ Cannot start EOD - current state: {self.current_state}")
            return False
        
        logger.info("🌙 Starting End of Day operations")
        self.current_state = SystemState.EOD_RUNNING
        self.eod_complete = False
        
        try:
            # Stop all exchanges first
            await self.stop_all_exchanges()
            
            # Execute EOD workflow
            eod_result = await self.eod_coordinator.execute_eod_workflow()
            
            if eod_result.success:
                self.eod_complete = True
                self.current_state = SystemState.IDLE
                logger.info("✅ End of Day operations completed successfully")
                
                # Send success notification
                await self.notifications.send_notification(
                    "EOD_SUCCESS",
                    "End of Day operations completed successfully", 
                    {"duration_seconds": eod_result.execution_time}
                )
                return True
            else:
                logger.error(f"❌ End of Day operations failed: {eod_result.error}")
                self.current_state = SystemState.ERROR
                
                # Send failure notification
                await self.notifications.send_notification(
                    "EOD_FAILED",
                    f"End of Day operations failed: {eod_result.error}",
                    {"error": str(eod_result.error)}
                )
                return False
                
        except Exception as e:
            logger.error(f"❌ Exception during EOD operations: {e}", exc_info=True)
            self.current_state = SystemState.ERROR
            await self.notifications.send_notification(
                "EOD_ERROR",
                f"Exception during EOD operations: {str(e)}"
            )
            return False
    
    async def start_exchange(self, exchange):
        """Start a specific exchange (only if SOD is complete)"""
        if not self.sod_complete:
            raise ValueError("Cannot start exchanges before SOD operations are complete")
        
        await self.k8s_manager.start_exchange(exchange)
    
    async def start_all_exchanges(self) -> bool:
        """Start all exchanges that should be running"""
        if not self.sod_complete:
            logger.error("❌ Cannot start exchanges - SOD not complete")
            return False
        
        try:
            logger.info("🚀 Starting all exchanges that should be running")
            exchanges = await self.db_manager.get_active_exchanges()
            
            now_utc = datetime.utcnow().replace(tzinfo=pytz.UTC)
            exchanges_to_start = []
            
            for exchange in exchanges:
                should_run = self.scheduler.should_exchange_be_running_utc(exchange, now_utc)
                is_running = str(exchange['exch_id']) in self.k8s_manager.get_running_exchanges()
                
                if should_run and not is_running:
                    exchanges_to_start.append(exchange)
            
            if not exchanges_to_start:
                logger.info("✅ All exchanges already running or not in market hours")
                return True
            
            logger.info(f"🚀 Starting {len(exchanges_to_start)} exchanges")
            
            # Start exchanges concurrently (but with some throttling)
            start_tasks = []
            for exchange in exchanges_to_start:
                start_tasks.append(self._safe_start_exchange(exchange))
            
            results = await asyncio.gather(*start_tasks, return_exceptions=True)
            
            # Check results
            success_count = sum(1 for r in results if r is True)
            logger.info(f"✅ Started {success_count}/{len(exchanges_to_start)} exchanges successfully")
            
            return success_count == len(exchanges_to_start)
            
        except Exception as e:
            logger.error(f"❌ Failed to start all exchanges: {e}")
            return False
    
    async def _safe_start_exchange(self, exchange) -> bool:
        """Safely start a single exchange with error handling"""
        try:
            await self.start_exchange(exchange)
            logger.info(f"✅ Started exchange {exchange['exch_id']}")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to start exchange {exchange['exch_id']}: {e}")
            return False
    
    async def stop_exchange(self, exchange):
        """Stop a specific exchange"""
        await self.k8s_manager.stop_exchange(exchange)
    
    async def stop_all_exchanges(self):
        """Stop all running exchanges"""
        logger.info("🛑 Stopping all running exchanges")
        exchanges = await self.db_manager.get_active_exchanges()
        
        exchanges_to_stop = []
        running_exchange_ids = self.k8s_manager.get_running_exchanges()
        
        for exchange in exchanges:
            if str(exchange['exch_id']) in running_exchange_ids:
                exchanges_to_stop.append(exchange)
        
        if not exchanges_to_stop:
            logger.info("✅ No exchanges currently running")
            return
        
        logger.info(f"🛑 Stopping {len(exchanges_to_stop)} exchanges")
        
        # Stop exchanges concurrently
        stop_tasks = []
        for exchange in exchanges_to_stop:
            stop_tasks.append(self._safe_stop_exchange(exchange))
        
        results = await asyncio.gather(*stop_tasks, return_exceptions=True)
        
        success_count = sum(1 for r in results if r is True)
        logger.info(f"✅ Stopped {success_count}/{len(exchanges_to_stop)} exchanges successfully")
    
    async def _safe_stop_exchange(self, exchange) -> bool:
        """Safely stop a single exchange with error handling"""
        try:
            await self.stop_exchange(exchange)
            logger.info(f"✅ Stopped exchange {exchange['exch_id']}")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to stop exchange {exchange['exch_id']}: {e}")
            return False
    
    async def handle_system_error(self, error: Exception):
        """Handle system-level errors"""
        logger.error(f"🚨 System error occurred: {error}")
        self.current_state = SystemState.ERROR
        
        # Save error state
        await self.state_manager.save_error_state(str(error))
        
        # Send critical alert
        await self.notifications.send_critical_alert(
            "SYSTEM_ERROR",
            f"Critical system error: {str(error)}"
        )
    
    def get_system_status(self) -> Dict[str, Any]:
        """Get comprehensive system status"""
        return {
            "current_state": self.current_state.value,
            "sod_complete": self.sod_complete,
            "eod_complete": self.eod_complete,
            "running_exchanges": list(self.k8s_manager.get_running_exchanges()),
            "running_exchange_count": len(self.k8s_manager.get_running_exchanges()),
            "system_uptime": self.metrics.get_uptime() if self.metrics else None,
            "last_sod_time": self.state_manager.last_sod_time,
            "last_eod_time": self.state_manager.last_eod_time,
            "current_window": self.scheduler.get_current_window_info_utc() if self.scheduler else None
        }
    
    async def shutdown(self):
        """Gracefully shutdown orchestrator"""
        logger.info("🛑 Shutting down orchestrator...")
        self.running = False
        
        # Stop all exchanges
        await self.stop_all_exchanges()
        
        # Save current state
        await self.state_manager.save_current_state(self.current_state)
        
        # Close database connections
        await self.db_manager.close()
        
        logger.info("✅ Orchestrator shutdown complete")
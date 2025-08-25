# source/core/orchestrator.py
import asyncio
import logging
from datetime import datetime, time
from typing import Dict, Any, Optional
from enum import Enum

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
        self.scheduler = EnhancedScheduler(self)
        self.notifications = NotificationManager()
        self.metrics = MetricsCollector()
        
        # Operations coordinators
        self.sod_coordinator = SODCoordinator(self)
        self.eod_coordinator = EODCoordinator(self)
        
        # State tracking
        self.current_state = SystemState.STARTING
        self.running = False
        self.sod_complete = False
        self.eod_complete = False
        
        logger.info("🏗️ Trading Orchestrator initialized")
    
    async def initialize(self):
        """Initialize all components"""
        logger.info("🔧 Initializing orchestrator components...")
        
        # Initialize database first
        await self.db_manager.init()
        logger.info("✅ Database manager initialized")
        
        # Initialize state manager
        await self.state_manager.initialize(self.db_manager)
        logger.info("✅ State manager initialized")
        
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
        
        # Load current system state
        await self.state_manager.load_current_state()
        
        logger.info("🎉 All components initialized successfully")
    
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
        
        logger.info("🌅 Starting End of Day operations")
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
        """Start an exchange (only if SOD is complete)"""
        if not self.sod_complete:
            raise ValueError("Cannot start exchanges before SOD operations are complete")
        
        await self.k8s_manager.start_exchange(exchange)
    
    async def stop_exchange(self, exchange):
        """Stop a specific exchange"""
        await self.k8s_manager.stop_exchange(exchange)
    
    async def stop_all_exchanges(self):
        """Stop all running exchanges"""
        logger.info("🛑 Stopping all running exchanges for EOD")
        exchanges = await self.db_manager.get_active_exchanges()
        
        for exchange in exchanges:
            if str(exchange['exch_id']) in self.k8s_manager.get_running_exchanges():
                await self.stop_exchange(exchange)
        
        logger.info("✅ All exchanges stopped")
    
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
            "running_exchanges": len(self.k8s_manager.get_running_exchanges()),
            "system_uptime": self.metrics.get_uptime(),
            "last_sod_time": self.state_manager.last_sod_time,
            "last_eod_time": self.state_manager.last_eod_time
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
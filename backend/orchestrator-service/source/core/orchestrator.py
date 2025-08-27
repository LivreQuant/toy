# source/core/orchestrator.py
import asyncio
import logging
from datetime import datetime
from enum import Enum
import pytz

from source.core.scheduler import SimpleScheduler
from source.core.state_manager import SimpleStateManager
from source.db.database import DatabaseManager
from source.exchanges.kubernetes_manager import KubernetesManager
from source.sod.coordinator import SODCoordinator
from source.eod.coordinator import EODCoordinator

logger = logging.getLogger(__name__)


class SystemState(Enum):
    STARTING = "starting"
    SOD_RUNNING = "sod_running"
    TRADING_ACTIVE = "trading_active"
    EOD_RUNNING = "eod_running"
    IDLE = "idle"
    ERROR = "error"


class TradingOrchestrator:
    """Simple trading orchestrator"""

    def __init__(self):
        self.config = get_config()

        # Core components
        self.db_manager = DatabaseManager()
        self.k8s_manager = KubernetesManager()
        self.state_manager = SimpleStateManager()

        # Operations coordinators
        self.sod_coordinator = SODCoordinator(self)
        self.eod_coordinator = EODCoordinator(self)

        # Scheduler
        self.scheduler = None

        # State tracking
        self.current_state = SystemState.STARTING
        self.running = False
        self.sod_complete = False
        self.eod_complete = False

        # Timezone
        self.market_tz = pytz.timezone(self.config.MARKET_TIMEZONE)

        logger.info("🏗️ Trading Orchestrator initialized")

    async def initialize(self):
        """Initialize all components"""
        logger.info("🔧 Initializing orchestrator components...")

        # Initialize database
        await self.db_manager.init()
        logger.info("✅ Database manager initialized")

        # Initialize state manager
        await self.state_manager.initialize(self.db_manager)
        logger.info("✅ State manager initialized")

        # Initialize coordinators
        await self.sod_coordinator.initialize()
        await self.eod_coordinator.initialize()
        logger.info("✅ SOD/EOD coordinators initialized")

        # Initialize scheduler
        self.scheduler = SimpleScheduler(self)
        logger.info("✅ Scheduler initialized")

        # Set initial state
        self.current_state = SystemState.IDLE
        logger.info("🎉 All components initialized successfully")

    async def run(self):
        """Main orchestrator loop"""
        self.running = True
        logger.info("🔄 Starting orchestrator main loop")

        while self.running:
            try:
                await self.scheduler.check_schedule()
                await asyncio.sleep(60)  # Check every minute
            except Exception as e:
                logger.error(f"❌ Error in orchestrator main loop: {e}", exc_info=True)
                await asyncio.sleep(30)

        logger.info("🛑 Orchestrator main loop stopped")

    async def trigger_sod_operations(self) -> bool:
        """Trigger SOD operations"""
        if self.current_state != SystemState.IDLE:
            logger.warning(f"⚠️ Cannot start SOD - current state: {self.current_state}")
            return False

        logger.info("🌅 Starting SOD operations")
        self.current_state = SystemState.SOD_RUNNING
        self.sod_complete = False

        try:
            result = await self.sod_coordinator.execute_sod_workflow()

            if result.success:
                self.sod_complete = True
                self.current_state = SystemState.TRADING_ACTIVE
                logger.info("✅ SOD operations completed successfully")
                return True
            else:
                self.current_state = SystemState.ERROR
                logger.error(f"❌ SOD operations failed: {result.error}")
                return False

        except Exception as e:
            self.current_state = SystemState.ERROR
            logger.error(f"❌ Exception during SOD operations: {e}", exc_info=True)
            return False

    async def trigger_eod_operations(self) -> bool:
        """Trigger EOD operations"""
        if self.current_state != SystemState.TRADING_ACTIVE:
            logger.warning(f"⚠️ Cannot start EOD - current state: {self.current_state}")
            return False

        logger.info("🌙 Starting EOD operations")
        self.current_state = SystemState.EOD_RUNNING
        self.eod_complete = False

        try:
            # Stop all exchanges first
            await self.stop_all_exchanges()

            result = await self.eod_coordinator.execute_eod_workflow()

            if result.success:
                self.eod_complete = True
                self.current_state = SystemState.IDLE
                logger.info("✅ EOD operations completed successfully")
                return True
            else:
                self.current_state = SystemState.ERROR
                logger.error(f"❌ EOD operations failed: {result.error}")
                return False

        except Exception as e:
            self.current_state = SystemState.ERROR
            logger.error(f"❌ Exception during EOD operations: {e}", exc_info=True)
            return False

    async def start_all_exchanges(self):
        """Start all exchanges"""
        logger.info("🚀 Starting all exchanges")
        # Implementation here

    async def stop_all_exchanges(self):
        """Stop all exchanges"""
        logger.info("🛑 Stopping all exchanges")
        # Implementation here

    async def shutdown(self):
        """Shutdown orchestrator"""
        logger.info("🛑 Shutting down orchestrator")
        self.running = False
        await self.stop_all_exchanges()
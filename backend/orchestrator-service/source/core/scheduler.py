# source/core/scheduler.py
import asyncio
import logging
from datetime import datetime, time, timedelta, date
from typing import Dict, Any
import pytz

from source.core.orchestrator import SystemState

logger = logging.getLogger(__name__)


class EnhancedScheduler:
    """Enhanced scheduler with strict time windows for SOD, Trading, and EOD operations
    All internal operations work in UTC, timezone conversions only for display/logging
    """

    def __init__(self, orchestrator, check_interval=60):
        self.orchestrator = orchestrator
        self.check_interval = check_interval  # seconds

        # US market timezone
        self.market_tz = pytz.timezone('America/New_York')

        # Critical time boundaries in US Eastern Time (will convert to UTC)
        # These are the WALL CLOCK times in Eastern Time
        self.sod_window_start_et = time(0, 0)  # 12:00 AM ET - SOD can start
        self.sod_window_end_et = time(4, 0)  # 4:00 AM ET - SOD must complete
        self.pre_market_start_et = time(4, 0)  # 4:00 AM ET - Pre-market opens
        self.post_market_end_et = time(20, 0)  # 8:00 PM ET - Post-market closes
        self.eod_window_start_et = time(20, 0)  # 8:00 PM ET - EOD can start
        self.eod_window_end_et = time(23, 59)  # 11:59 PM ET - EOD should complete

        # Tracking for duplicate prevention
        self.last_sod_attempt = None
        self.last_eod_attempt = None

        logger.info("📅 Enhanced scheduler initialized for US exchanges")
        logger.info(f"   SOD Window: {self.sod_window_start_et} - {self.sod_window_end_et} ET")
        logger.info(f"   Trading Window: {self.pre_market_start_et} - {self.post_market_end_et} ET")
        logger.info(f"   EOD Window: {self.eod_window_start_et} - {self.eod_window_end_et} ET")

    async def check_and_execute_operations(self):
        """Enhanced main scheduler - all operations in UTC with ET display"""
        now_utc = datetime.utcnow().replace(tzinfo=pytz.UTC)
        now_et = now_utc.astimezone(self.market_tz)

        logger.debug(f"⏰ Scheduler check at {now_et.strftime('%H:%M:%S %Z')} "
                     f"(UTC: {now_utc.strftime('%H:%M:%S')})")

        # Skip weekends based on ET timezone
        if now_et.weekday() >= 5:
            logger.debug("📅 Weekend in ET timezone - skipping all operations")
            return

        et_date = now_et.date()

        # Determine which window we're in (based on ET time)
        window = self._get_current_window_utc(now_utc)

        try:
            if window == "SOD_WINDOW":
                await self._handle_sod_window(now_utc, et_date)
            elif window == "TRADING_WINDOW":
                await self._handle_trading_window(now_utc)
            elif window == "EOD_WINDOW":
                await self._handle_eod_window(now_utc, et_date)
            elif window == "TRANSITION":
                await self._handle_transition_window(now_utc)

            # Always perform health checks
            await self._perform_health_checks()

        except Exception as e:
            logger.error(f"❌ Error in scheduler operations: {e}", exc_info=True)
            await self.orchestrator.handle_system_error(e)

    def _get_current_window_utc(self, now_utc: datetime) -> str:
        """Determine operational window - converts ET boundaries to UTC for comparison"""
        # Convert current UTC to ET for display, but work with UTC times
        now_et = now_utc.astimezone(self.market_tz)
        today_et = now_et.date()

        # Convert ET time boundaries to UTC for today
        sod_start_utc = self._et_time_to_utc(today_et, self.sod_window_start_et)
        sod_end_utc = self._et_time_to_utc(today_et, self.sod_window_end_et)
        trading_start_utc = self._et_time_to_utc(today_et, self.pre_market_start_et)
        trading_end_utc = self._et_time_to_utc(today_et, self.post_market_end_et)
        eod_start_utc = self._et_time_to_utc(today_et, self.eod_window_start_et)
        eod_end_utc = self._et_time_to_utc(today_et, self.eod_window_end_et)

        # All comparisons in UTC
        if sod_start_utc <= now_utc < sod_end_utc:
            return "SOD_WINDOW"
        elif trading_start_utc <= now_utc < trading_end_utc:
            return "TRADING_WINDOW"
        elif eod_start_utc <= now_utc <= eod_end_utc:
            return "EOD_WINDOW"
        else:
            return "TRANSITION"

    def _et_time_to_utc(self, et_date: date, et_time: time) -> datetime:
        """Convert ET date/time to UTC datetime"""
        # Create ET datetime (handles DST automatically)
        et_dt = self.market_tz.localize(datetime.combine(et_date, et_time))
        # Convert to UTC
        return et_dt.astimezone(pytz.UTC)

    async def _handle_sod_window(self, now_utc: datetime, et_date: date):
        """Handle SOD window - all operations in UTC"""
        now_et = now_utc.astimezone(self.market_tz)
        logger.debug(f"🌅 In SOD window at {now_et.strftime('%H:%M:%S %Z')}")

        # Priority 1: Check if we need to run EOD from yesterday first
        yesterday_et = et_date - timedelta(days=1)
        eod_status = await self._get_operation_status("EOD", yesterday_et)

        if eod_status not in ["SUCCESS", "RUNNING"]:
            logger.warning(f"⚠️ Yesterday's EOD status: {eod_status} - attempting recovery")
            if await self._attempt_eod_recovery(yesterday_et):
                logger.info("✅ Yesterday's EOD recovery completed")
            else:
                logger.error("❌ Failed to recover yesterday's EOD - blocking SOD")
                await self._send_critical_alert(
                    "EOD_RECOVERY_FAILED",
                    f"Failed to recover EOD from {yesterday_et} - SOD blocked"
                )
                return

        # Priority 2: Check SOD for today
        sod_status = await self._get_operation_status("SOD", et_date)

        if sod_status == "SUCCESS":
            logger.debug("✅ SOD already completed today")
            self._ensure_sod_state_consistency()
            return

        if sod_status == "RUNNING":
            logger.info("🔄 SOD currently running - monitoring")
            return

        if sod_status == "FAILED":
            logger.error("❌ SOD failed earlier - manual intervention required")
            await self._send_critical_alert(
                "SOD_FAILED_MANUAL_INTERVENTION",
                "SOD failed - manual intervention required before trading window"
            )
            return

        # SOD hasn't run yet - check if we should trigger it
        if self._should_trigger_sod_utc(et_date, now_utc):
            await self._trigger_sod_safely(now_utc)

    async def _handle_trading_window(self, now_utc: datetime):
        """Handle trading window - exchanges only, all in UTC"""
        now_et = now_utc.astimezone(self.market_tz)
        logger.debug(f"📈 In trading window at {now_et.strftime('%H:%M:%S %Z')}")

        # Critical: Ensure SOD is complete before allowing exchange operations
        if not self.orchestrator.sod_complete:
            logger.error("🚨 CRITICAL: Trading window reached but SOD not complete!")

            # Attempt state recovery
            et_date = now_et.date()
            sod_status = await self._get_operation_status("SOD", et_date)

            if sod_status == "SUCCESS":
                logger.info("🔄 SOD was complete - recovering state")
                self._recover_sod_state()
            else:
                logger.error("❌ SOD not complete - BLOCKING ALL EXCHANGE OPERATIONS")
                await self._send_critical_alert(
                    "TRADING_WINDOW_SOD_INCOMPLETE",
                    "Trading window reached but SOD not complete - ALL EXCHANGES BLOCKED"
                )
                await self._emergency_stop_all_exchanges()
                return

        # Normal exchange lifecycle management (only if SOD complete)
        await self._manage_exchange_lifecycle_utc(now_utc)

    async def _handle_eod_window(self, now_utc: datetime, et_date: date):
        """Handle EOD window - all operations in UTC"""
        now_et = now_utc.astimezone(self.market_tz)
        logger.debug(f"🌙 In EOD window at {now_et.strftime('%H:%M:%S %Z')}")

        # First priority: Stop all exchanges
        await self._ensure_all_exchanges_stopped("EOD window")

        # Check EOD status for today
        eod_status = await self._get_operation_status("EOD", et_date)

        if eod_status == "SUCCESS":
            logger.debug("✅ EOD already completed today")
            self._ensure_eod_state_consistency()
            return

        if eod_status == "RUNNING":
            logger.info("🔄 EOD currently running - monitoring")
            return

        if eod_status == "FAILED":
            logger.error("❌ EOD failed earlier - will retry in next cycle")

        # EOD hasn't run or failed - check if we should trigger it
        if self._should_trigger_eod_utc(et_date, now_utc):
            await self._trigger_eod_safely(now_utc)

    async def _handle_transition_window(self, now_utc: datetime):
        """Handle brief transition window between EOD and SOD"""
        now_et = now_utc.astimezone(self.market_tz)
        logger.debug(f"⏸️ In transition window at {now_et.strftime('%H:%M:%S %Z')}")

        # Ensure all exchanges are stopped
        await self._ensure_all_exchanges_stopped("transition window")

        # Just health checks - no major operations
        await self._perform_health_checks()

    async def _manage_exchange_lifecycle_utc(self, now_utc: datetime):
        """Manage exchange start/stop during trading window - all comparisons in UTC"""
        try:
            exchanges = await self.orchestrator.db_manager.get_active_exchanges()

            for exchange in exchanges:
                should_run = self.should_exchange_be_running_utc(exchange, now_utc)
                is_running = str(exchange['exch_id']) in self.orchestrator.k8s_manager.get_running_exchanges()

                if should_run and not is_running:
                    logger.info(f"🚀 Market hours: Starting exchange {exchange['exch_id']}")
                    await self.orchestrator.k8s_manager.start_exchange(exchange)

                elif not should_run and is_running:
                    logger.info(f"🛑 Market closed: Stopping exchange {exchange['exch_id']}")
                    await self.orchestrator.k8s_manager.stop_exchange(exchange)

        except Exception as e:
            logger.error(f"❌ Error in exchange lifecycle management: {e}", exc_info=True)

    def should_exchange_be_running_utc(self, exchange: Dict[str, Any], now_utc: datetime) -> bool:
        """Determine if exchange should be running - all comparisons in UTC"""
        # Get exchange timezone (should be America/New_York for US exchanges)
        exchange_tz_str = exchange.get('timezone', 'America/New_York')
        try:
            exchange_tz = pytz.timezone(exchange_tz_str)
        except Exception as e:
            logger.error(f"Invalid timezone {exchange_tz_str}: {e}")
            exchange_tz = self.market_tz  # Fallback to market timezone

        # Get today's date in exchange timezone
        now_local = now_utc.astimezone(exchange_tz)
        today_local = now_local.date()

        # Skip weekends based on exchange local time
        if now_local.weekday() >= 5:
            return False

        # Get market hours from database (stored as TIME in exchange local time)
        pre_open_local = exchange.get('pre_open_time') or exchange.get('pre_market_open')
        post_close_local = exchange.get('post_close_time') or exchange.get('post_market_close')

        if not pre_open_local or not post_close_local:
            logger.error(f"Missing market hours for exchange {exchange.get('exch_id')}")
            return False

        # Convert exchange local market hours to UTC datetime objects
        pre_open_local_dt = exchange_tz.localize(datetime.combine(today_local, pre_open_local))
        post_close_local_dt = exchange_tz.localize(datetime.combine(today_local, post_close_local))

        # Convert to UTC
        pre_open_utc = pre_open_local_dt.astimezone(pytz.UTC)
        post_close_utc = post_close_local_dt.astimezone(pytz.UTC)

        # Add small buffers for startup/shutdown
        buffer = timedelta(minutes=5)
        start_time_utc = pre_open_utc - buffer
        end_time_utc = post_close_utc + buffer

        # All comparisons in UTC
        should_run = start_time_utc <= now_utc <= end_time_utc

        # Detailed logging for debugging (display in local time)
        logger.debug(f"⏰ Exchange {exchange.get('exch_id')} time check:")
        logger.debug(f"   Current UTC: {now_utc.strftime('%H:%M:%S %Z')}")
        logger.debug(f"   Current Local: {now_local.strftime('%H:%M:%S %Z')}")
        logger.debug(f"   Market hours (local): {pre_open_local} - {post_close_local}")
        logger.debug(
            f"   Market window (UTC): {start_time_utc.strftime('%H:%M:%S')} - {end_time_utc.strftime('%H:%M:%S')}")
        logger.debug(f"   Should be running: {should_run}")

        return should_run

    def _should_trigger_sod_utc(self, et_date: date, now_utc: datetime) -> bool:
        """Determine if SOD should be triggered - using UTC for consistency"""

        # Check if already attempted today
        if (self.last_sod_attempt and
                self.last_sod_attempt.astimezone(self.market_tz).date() == et_date):
            return False

        # Check system state
        if self.orchestrator.current_state not in [SystemState.IDLE, SystemState.STARTING]:
            return False

        return True

    def _should_trigger_eod_utc(self, et_date: date, now_utc: datetime) -> bool:
        """Determine if EOD should be triggered - using UTC for consistency"""
        # Check if already attempted today
        if (self.last_eod_attempt and
                self.last_eod_attempt.astimezone(self.market_tz).date() == et_date):
            return False

        # Check system state
        if self.orchestrator.current_state != SystemState.TRADING_ACTIVE:
            return False

        return True

    async def _trigger_sod_safely(self, now_utc: datetime):
        """Safely trigger SOD operations"""
        try:
            now_et = now_utc.astimezone(self.market_tz)
            logger.info(f"🌅 Triggering SOD operations at {now_et.strftime('%H:%M:%S %Z')}")
            self.last_sod_attempt = now_utc
            await asyncio.create_task(self.orchestrator.trigger_sod_operations())
        except Exception as e:
            logger.error(f"Failed to trigger SOD: {e}", exc_info=True)

    async def _trigger_eod_safely(self, now_utc: datetime):
        """Safely trigger EOD operations"""
        try:
            now_et = now_utc.astimezone(self.market_tz)
            logger.info(f"🌙 Triggering EOD operations at {now_et.strftime('%H:%M:%S %Z')}")
            self.last_eod_attempt = now_utc
            await asyncio.create_task(self.orchestrator.trigger_eod_operations())
        except Exception as e:
            logger.error(f"Failed to trigger EOD: {e}", exc_info=True)

    async def _get_operation_status(self, operation_type: str, operation_date: date) -> str:
        """Get the status of an operation for a specific date"""
        try:
            recent_ops = await self.orchestrator.state_manager.get_recent_operations(
                operation_type, limit=10
            )

            for op in recent_ops:
                if op.get('operation_date') == operation_date:
                    return op.get('status', 'UNKNOWN')

            return "NOT_RUN"

        except Exception as e:
            logger.error(f"Failed to get operation status for {operation_type}: {e}")
            return "UNKNOWN"

    async def _ensure_all_exchanges_stopped(self, reason: str):
        """Ensure all exchanges are stopped"""
        try:
            running_exchanges = self.orchestrator.k8s_manager.get_running_exchanges()

            if running_exchanges:
                logger.info(f"🛑 Stopping {len(running_exchanges)} exchanges for {reason}")
                await self.orchestrator.stop_all_exchanges()
            else:
                logger.debug(f"✅ All exchanges already stopped for {reason}")

        except Exception as e:
            logger.error(f"Failed to stop exchanges for {reason}: {e}")

    async def _emergency_stop_all_exchanges(self):
        """Emergency stop all exchanges with alerts"""
        try:
            logger.error("🚨 EMERGENCY: Stopping all exchanges due to SOD failure")
            await self.orchestrator.stop_all_exchanges()

            await self._send_critical_alert(
                "EMERGENCY_EXCHANGE_STOP",
                "All exchanges emergency stopped due to SOD failure"
            )

        except Exception as e:
            logger.error(f"Failed emergency stop: {e}", exc_info=True)

    def _ensure_sod_state_consistency(self):
        """Ensure SOD state flags are consistent with database"""
        if not self.orchestrator.sod_complete:
            logger.info("🔄 Recovering SOD state consistency")
            self._recover_sod_state()

    def _ensure_eod_state_consistency(self):
        """Ensure EOD state flags are consistent with database"""
        if not self.orchestrator.eod_complete:
            logger.info("🔄 Recovering EOD state consistency")
            self._recover_eod_state()

    def _recover_sod_state(self):
        """Recover SOD state after restart"""
        logger.info("🔄 Recovering SOD completion state")
        self.orchestrator.sod_complete = True
        self.orchestrator.current_state = SystemState.TRADING_ACTIVE

    def _recover_eod_state(self):
        """Recover EOD state after restart"""
        logger.info("🔄 Recovering EOD completion state")
        self.orchestrator.eod_complete = True
        self.orchestrator.current_state = SystemState.IDLE

    async def _perform_health_checks(self):
        """Perform comprehensive system health checks"""
        try:
            # Check database connectivity
            await self._check_database_health()

            # Check running exchanges health
            await self.orchestrator.k8s_manager.check_all_running_exchanges_health()

            # Update system metrics
            await self.orchestrator.metrics.update_health_metrics()

            logger.debug("✅ Health checks completed")

        except Exception as e:
            logger.error(f"❌ Health check failed: {e}", exc_info=True)

    async def _check_database_health(self):
        """Check database connectivity and health"""
        try:
            # Simple query to verify DB health
            await self.orchestrator.db_manager.get_active_exchanges()
            logger.debug("✅ Database health check passed")
        except Exception as e:
            logger.error(f"💔 Database health check failed: {e}")
            raise

    async def _send_critical_alert(self, alert_type: str, message: str):
        """Send critical system alert"""
        try:
            await self.orchestrator.notifications.send_critical_alert(alert_type, message)
        except Exception as e:
            logger.error(f"Failed to send critical alert: {e}")

    async def _attempt_eod_recovery(self, recovery_date: date) -> bool:
        """Attempt to recover failed EOD from previous day"""
        try:
            logger.info(f"🔄 Attempting EOD recovery for {recovery_date}")

            # Stop all exchanges first
            await self._ensure_all_exchanges_stopped("EOD recovery")

            # Trigger EOD with recovery flag
            result = await self.orchestrator.trigger_eod_operations()

            if result:
                logger.info("✅ EOD recovery successful")
                return True
            else:
                logger.error("❌ EOD recovery failed")
                return False

        except Exception as e:
            logger.error(f"❌ Exception during EOD recovery: {e}", exc_info=True)
            return False

    def get_current_window_info_utc(self) -> Dict[str, Any]:
        """Get information about current operational window - all times in UTC with ET display"""
        now_utc = datetime.utcnow().replace(tzinfo=pytz.UTC)
        now_et = now_utc.astimezone(self.market_tz)

        window = self._get_current_window_utc(now_utc)

        return {
            "current_time_utc": now_utc.strftime('%H:%M:%S %Z'),
            "current_time_et": now_et.strftime('%H:%M:%S %Z'),
            "current_window": window,
            "sod_window_et": f"{self.sod_window_start_et} - {self.sod_window_end_et}",
            "trading_window_et": f"{self.pre_market_start_et} - {self.post_market_end_et}",
            "eod_window_et": f"{self.eod_window_start_et} - {self.eod_window_end_et}",
            "is_weekend": now_et.weekday() >= 5,
            "market_timezone": str(self.market_tz)
        }

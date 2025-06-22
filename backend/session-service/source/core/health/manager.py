# source/core/health/manager.py
"""
Health check manager for the current session's simulator.
Handles periodic health checks for the single simulator in this session service.
"""
import asyncio
import logging
import time
from typing import Optional, Tuple
from opentelemetry import trace

from source.clients.exchange import ExchangeClient
from source.clients.k8s import KubernetesClient
from source.core.session.manager import SessionManager
from source.models.simulator import SimulatorStatus
from source.utils.tracing import optional_trace_span
from source.utils.metrics import track_simulator_operation

logger = logging.getLogger('health_manager')


class HealthCheckManager:
    """Manages health checks for the current session's simulator only"""

    def __init__(
        self,
        session_manager: SessionManager,
        check_interval: int = 30,  # Check every 30 seconds
        timeout_threshold: int = 120  # Mark as unhealthy after 2 minutes
    ):
        """
        Initialize health check manager for this session service

        Args:
            session_manager: The session manager for this service
            check_interval: How often to run health checks (seconds)
            timeout_threshold: How long to wait before marking as unhealthy (seconds)
        """
        self.session_manager = session_manager
        self.check_interval = check_interval
        self.timeout_threshold = timeout_threshold
        
        self.tracer = trace.get_tracer("health_manager")
        self.running = False
        self.health_task = None
        
        logger.info(f"Health check manager initialized for single session with {check_interval}s interval")

    async def start(self):
        """Start the health check background task"""
        if self.running:
            logger.warning("Health check manager already running")
            return

        self.running = True
        self.health_task = asyncio.create_task(self._health_check_loop())
        self.health_task.set_name("session_health_check_loop")
        logger.info("Session health check manager started")

    async def stop(self):
        """Stop the health check background task"""
        if not self.running:
            return

        self.running = False
        if self.health_task and not self.health_task.done():
            self.health_task.cancel()
            try:
                await self.health_task
            except asyncio.CancelledError:
                pass
        logger.info("Session health check manager stopped")

    async def _health_check_loop(self):
        """Main health check loop for this session's simulator"""
        logger.info("Starting session health check loop")
        
        while self.running:
            try:
                await self._check_session_simulator_health()
            except Exception as e:
                logger.error(f"Error in health check loop: {e}", exc_info=True)
            
            # Wait for next check
            try:
                await asyncio.sleep(self.check_interval)
            except asyncio.CancelledError:
                break

        logger.info("Session health check loop stopped")

    async def _check_session_simulator_health(self):
        """Check health of this session's simulator only"""
        with optional_trace_span(self.tracer, "check_session_simulator_health") as span:
            try:
                # Only check if we have an active session
                if not self.session_manager.state_manager.is_active():
                    logger.debug("No active session, skipping health check")
                    return

                # Only check if there's a current simulator
                current_simulator_id = self.session_manager.simulator_manager.current_simulator_id
                if not current_simulator_id:
                    logger.debug("No current simulator, skipping health check")
                    return

                # Get the current session's simulator
                simulator = await self.session_manager.store_manager.simulator_store.get_simulator(current_simulator_id)
                if not simulator:
                    logger.warning(f"Current simulator {current_simulator_id} not found in database")
                    # Clear the current simulator tracking since it doesn't exist
                    self.session_manager.simulator_manager.current_simulator_id = None
                    self.session_manager.simulator_manager.current_endpoint = None
                    return

                # Only check if it's supposed to be running
                if simulator.status != SimulatorStatus.RUNNING:
                    logger.debug(f"Simulator {current_simulator_id} status is {simulator.status.value}, not checking health")
                    return

                span.set_attribute("simulator_id", current_simulator_id)
                span.set_attribute("session_id", simulator.session_id)

                logger.debug(f"Checking health of session simulator {current_simulator_id}")

                # Check if simulator has been inactive for too long
                current_time = time.time()
                if simulator.last_active and (current_time - simulator.last_active) > self.timeout_threshold:
                    logger.warning(f"Simulator {current_simulator_id} last active {current_time - simulator.last_active:.0f}s ago, checking health")

                # Perform health check
                is_healthy = await self._perform_simulator_health_check(simulator)

                if is_healthy:
                    # Update last_active time
                    await self._update_simulator_activity(current_simulator_id)
                    span.set_attribute("health_status", "healthy")
                    logger.debug(f"Session simulator {current_simulator_id} is healthy")
                else:
                    # Mark as unhealthy and clear current tracking
                    await self._mark_simulator_unhealthy(current_simulator_id, "Health check failed")
                    span.set_attribute("health_status", "unhealthy")
                    logger.warning(f"Session simulator {current_simulator_id} marked as unhealthy")

            except Exception as e:
                logger.error(f"Error in session simulator health check: {e}", exc_info=True)
                span.record_exception(e)

    async def _perform_simulator_health_check(self, simulator) -> bool:
        """Perform actual health check on the session's simulator"""
        
        # First check: Kubernetes pod status
        try:
            k8s_status = await self.session_manager.simulator_manager.k8s_client.check_simulator_status(simulator.simulator_id)
            if k8s_status not in ["RUNNING", "PENDING"]:
                logger.warning(f"Session simulator {simulator.simulator_id} Kubernetes status: {k8s_status}")
                return False
        except Exception as e:
            logger.error(f"Error checking Kubernetes status for session simulator {simulator.simulator_id}: {e}")
            return False

        # Second check: gRPC heartbeat
        try:
            if not simulator.endpoint:
                logger.warning(f"Session simulator {simulator.simulator_id} has no endpoint")
                return False

            heartbeat_result = await self.session_manager.simulator_manager.exchange_client.send_heartbeat(
                simulator.endpoint, 
                simulator.session_id, 
                f"health-check-{simulator.simulator_id}"
            )
            
            if not heartbeat_result.get('success', False):
                logger.warning(f"Session simulator {simulator.simulator_id} heartbeat failed: {heartbeat_result.get('error', 'Unknown error')}")
                return False
                
        except Exception as e:
            logger.warning(f"Error sending heartbeat to session simulator {simulator.simulator_id}: {e}")
            return False

        return True

    async def _mark_simulator_unhealthy(self, simulator_id: str, reason: str):
        """Mark the session's simulator as unhealthy"""
        try:
            success = await self.session_manager.store_manager.simulator_store.update_simulator_status(
                simulator_id, SimulatorStatus.ERROR
            )
            
            if success:
                logger.warning(f"Marked session simulator {simulator_id} as ERROR: {reason}")
                track_simulator_operation("health_check", "marked_unhealthy")
                
                # Clear current simulator tracking since it's now unhealthy
                if self.session_manager.simulator_manager.current_simulator_id == simulator_id:
                    self.session_manager.simulator_manager.current_simulator_id = None
                    self.session_manager.simulator_manager.current_endpoint = None
                    logger.info(f"Cleared current simulator tracking for unhealthy simulator {simulator_id}")
            else:
                logger.error(f"Failed to update status for session simulator {simulator_id}")
                
        except Exception as e:
            logger.error(f"Error marking session simulator {simulator_id} as unhealthy: {e}")

    async def _update_simulator_activity(self, simulator_id: str):
        """Update the last_active timestamp for the healthy session simulator"""
        try:
            pool = await self.session_manager.store_manager.simulator_store._get_pool()
            async with pool.acquire() as conn:
                await conn.execute('''
                    UPDATE simulator.instances
                    SET last_active = NOW()
                    WHERE simulator_id = $1
                ''', simulator_id)
        except Exception as e:
            logger.error(f"Error updating activity for session simulator {simulator_id}: {e}")

    async def force_check_current_simulator(self) -> Tuple[bool, str]:
        """
        Force a health check on the current session's simulator
        
        Returns:
            Tuple of (is_healthy, reason)
        """
        with optional_trace_span(self.tracer, "force_check_current_simulator") as span:
            
            try:
                # Check if we have an active session
                if not self.session_manager.state_manager.is_active():
                    return False, "No active session"

                # Check if there's a current simulator
                current_simulator_id = self.session_manager.simulator_manager.current_simulator_id
                if not current_simulator_id:
                    return False, "No current simulator"

                span.set_attribute("simulator_id", current_simulator_id)
                
                # Get simulator details
                simulator = await self.session_manager.store_manager.simulator_store.get_simulator(current_simulator_id)
                if not simulator:
                    return False, "Current simulator not found in database"
                
                if simulator.status != SimulatorStatus.RUNNING:
                    return False, f"Simulator status is {simulator.status.value}, not RUNNING"
                
                # Perform health check
                is_healthy = await self._perform_simulator_health_check(simulator)
                
                if is_healthy:
                    await self._update_simulator_activity(current_simulator_id)
                    return True, "Simulator is healthy"
                else:
                    await self._mark_simulator_unhealthy(current_simulator_id, "Forced health check failed")
                    return False, "Simulator failed health check"
                    
            except Exception as e:
                logger.error(f"Error in force check for current simulator: {e}")
                span.record_exception(e)
                return False, f"Health check error: {str(e)}"

    def get_current_simulator_status(self) -> dict:
        """Get status information about the current session's simulator"""
        try:
            current_simulator_id = self.session_manager.simulator_manager.current_simulator_id
            current_endpoint = self.session_manager.simulator_manager.current_endpoint
            is_active = self.session_manager.state_manager.is_active()
            
            return {
                "has_active_session": is_active,
                "current_simulator_id": current_simulator_id,
                "current_endpoint": current_endpoint,
                "health_check_running": self.running,
                "check_interval": self.check_interval,
                "timeout_threshold": self.timeout_threshold
            }
        except Exception as e:
            logger.error(f"Error getting current simulator status: {e}")
            return {"error": str(e)}
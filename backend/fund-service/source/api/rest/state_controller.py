# source/api/rest/state_controller.py
import logging
import time
import asyncio
from aiohttp import web

from source.core.state_manager import StateManager

logger = logging.getLogger('state_controllers')

class StateController:
    """Controller for session-related and general service endpoints"""

    def __init__(self, state_manager: StateManager):
        """
        Initialize controller with dependencies
        
        Args:
            state_manager: Service state manager
        """
        self.state_manager = state_manager
        logger.info("🏥 StateController initialized")

    async def health_check(self, request: web.Request) -> web.Response:
        """Simple health check endpoint - should always return 200 OK"""
        logger.info("🩺 Health check endpoint called!")
        try:
            response_data = {
                'status': 'UP',
                'service': 'fund-service',
                'timestamp': int(time.time())
            }
            logger.info(f"🟢 Health check returning: {response_data}")
            return web.json_response(response_data)
        except Exception as e:
            logger.error(f"🔴 Health check failed: {e}")
            return web.json_response({
                'status': 'DOWN',
                'error': str(e)
            }, status=500)

    async def readiness_check(self, request: web.Request) -> web.Response:
        """Readiness check endpoint that verifies database connection and service availability"""
        logger.info("🔍 Readiness check endpoint called!")
        try:
            # Check database connection with timeout
            db_ready = False
            try:
                logger.info("🔌 Checking database connection...")
                db_ready = await asyncio.wait_for(
                    self.state_manager.validate_connection(), 
                    timeout=3.0
                )
                logger.info(f"📊 Database ready: {db_ready}")
            except asyncio.TimeoutError:
                logger.warning("⏰ Database connection check timed out")
                db_ready = False
            except Exception as e:
                logger.warning(f"❌ Database connection check failed: {e}")
                db_ready = False

            # For readiness, we don't check if service is busy - just if it can accept requests
            service_ready = True
            logger.info(f"🎯 Service ready: {service_ready}")

            if db_ready and service_ready:
                response_data = {
                    'status': 'READY',
                    'timestamp': int(time.time()),
                    'checks': {
                        'database': 'UP',
                        'service': 'AVAILABLE'
                    }
                }
                logger.info(f"🟢 Readiness check returning: {response_data}")
                return web.json_response(response_data)
            else:
                checks = {
                    'database': 'UP' if db_ready else 'DOWN',
                    'service': 'AVAILABLE' if service_ready else 'NOT_AVAILABLE'
                }

                reasons = []
                if not db_ready:
                    reasons.append('Database is not available')
                if not service_ready:
                    reasons.append('Service is not available')

                response_data = {
                    'status': 'NOT_READY',
                    'reason': '; '.join(reasons),
                    'checks': checks
                }
                logger.warning(f"🟡 Readiness check returning NOT_READY: {response_data}")
                return web.json_response(response_data, status=503)
        except Exception as e:
            logger.error(f"🔴 Readiness check failed: {e}")
            return web.json_response({
                'status': 'NOT_READY',
                'reason': f"Readiness check exception: {str(e)}"
            }, status=503)
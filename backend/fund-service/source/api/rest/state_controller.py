# source/api/rest/state_controllers.py
import logging
import time
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

    async def health_check(self, request: web.Request) -> web.Response:
        """Simple health check endpoint"""
        return web.json_response({
            'status': 'UP',
            'timestamp': int(time.time())
        })

    async def readiness_check(self, request: web.Request) -> web.Response:
        """Readiness check endpoint that verifies database connection and service availability"""
        try:
            # Check database connection
            db_ready = await self.state_manager.validate_connection()

            # Check if the service is already busy with another request
            service_ready = self.state_manager.is_ready()

            if db_ready and service_ready:
                return web.json_response({
                    'status': 'READY',
                    'timestamp': int(time.time()),
                    'checks': {
                        'database': 'UP',
                        'service': 'AVAILABLE'
                    }
                })
            else:
                checks = {
                    'database': 'UP' if db_ready else 'DOWN',
                    'service': 'AVAILABLE' if service_ready else 'BUSY'
                }

                reasons = []
                if not db_ready:
                    reasons.append('Database is not available')
                if not service_ready:
                    reasons.append('Service is currently processing a request')

                return web.json_response({
                    'status': 'NOT READY',
                    'reason': '; '.join(reasons),
                    'checks': checks
                }, status=503)
        except Exception as e:
            logger.error(f"Readiness check failed: {e}")
            return web.json_response({
                'status': 'NOT READY',
                'reason': str(e)
            }, status=503)
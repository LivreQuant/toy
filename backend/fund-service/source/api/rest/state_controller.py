# source/api/rest/state_controller.py
import logging
import time
import datetime
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
        """Enhanced health check endpoint with database connectivity"""
        try:
            # Get database pool from app context if available
            db_pool = request.app.get('db_pool')
            
            health_status = {
                'service': 'fund-service',
                'status': 'healthy',
                'timestamp': datetime.datetime.utcnow().isoformat(),
                'uptime': int(time.time()),
                'components': {}
            }
            
            # Check database connectivity
            if db_pool:
                try:
                    db_health = await db_pool.health_check()
                    health_status['components']['database'] = db_health
                    
                    if db_health['status'] != 'healthy':
                        health_status['status'] = 'degraded'
                        
                except Exception as e:
                    health_status['components']['database'] = {
                        'status': 'unhealthy',
                        'error': str(e)
                    }
                    health_status['status'] = 'unhealthy'
            else:
                health_status['components']['database'] = {
                    'status': 'unavailable',
                    'error': 'Database pool not available in app context'
                }
                health_status['status'] = 'degraded'
            
            # Check state manager
            try:
                service_ready = self.state_manager.is_ready()
                health_status['components']['state_manager'] = {
                    'status': 'healthy' if service_ready else 'busy',
                    'ready': service_ready
                }
                
                if not service_ready:
                    health_status['status'] = 'degraded'
                    
            except Exception as e:
                health_status['components']['state_manager'] = {
                    'status': 'unhealthy',
                    'error': str(e)
                }
                health_status['status'] = 'unhealthy'
            
            # Return appropriate HTTP status
            if health_status['status'] == 'healthy':
                return web.json_response(health_status, status=200)
            elif health_status['status'] == 'degraded':
                return web.json_response(health_status, status=200)  # Still accessible but degraded
            else:
                return web.json_response(health_status, status=503)
                
        except Exception as e:
            logger.error(f"Health check failed with exception: {e}")
            error_response = {
                'service': 'fund-service',
                'status': 'unhealthy',
                'error': str(e),
                'timestamp': datetime.datetime.utcnow().isoformat()
            }
            return web.json_response(error_response, status=503)

    async def simple_health_check(self, request: web.Request) -> web.Response:
        """Simple health check endpoint (original functionality)"""
        return web.json_response({
            'status': 'UP',
            'timestamp': int(time.time())
        })

    async def readiness_check(self, request: web.Request) -> web.Response:
        """Enhanced readiness check endpoint that verifies database connection and service availability"""
        try:
            # Check database connection using state manager
            db_ready = await self.state_manager.validate_connection()

            # Check if the service is ready
            service_ready = self.state_manager.is_ready()
            
            # Additional check: verify database pool from app context
            db_pool = request.app.get('db_pool')
            db_pool_ready = False
            
            if db_pool:
                try:
                    db_pool_ready = await db_pool.check_connection()
                except Exception as e:
                    logger.error(f"Database pool check failed: {e}")
                    db_pool_ready = False

            # Combine all readiness checks
            all_ready = db_ready and service_ready and db_pool_ready

            if all_ready:
                return web.json_response({
                    'status': 'READY',
                    'timestamp': int(time.time()),
                    'checks': {
                        'database': 'UP',
                        'service': 'AVAILABLE',
                        'database_pool': 'UP'
                    }
                })
            else:
                checks = {
                    'database': 'UP' if db_ready else 'DOWN',
                    'service': 'AVAILABLE' if service_ready else 'BUSY',
                    'database_pool': 'UP' if db_pool_ready else 'DOWN'
                }

                reasons = []
                if not db_ready:
                    reasons.append('Database connection via state manager failed')
                if not service_ready:
                    reasons.append('Service is currently processing a request')
                if not db_pool_ready:
                    reasons.append('Database pool connection failed')

                return web.json_response({
                    'status': 'NOT READY',
                    'reason': '; '.join(reasons),
                    'checks': checks
                }, status=503)
                
        except Exception as e:
            logger.error(f"Readiness check failed: {e}")
            return web.json_response({
                'status': 'NOT READY',
                'reason': str(e),
                'checks': {
                    'database': 'UNKNOWN',
                    'service': 'UNKNOWN',
                    'database_pool': 'UNKNOWN'
                }
            }, status=503)
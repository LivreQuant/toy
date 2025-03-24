import logging
import asyncio
from typing import Dict, Any, Optional, List

from source.utils.redis_client import RedisClient
from source.utils.circuit_breaker import CircuitBreaker, CircuitOpenError

logger = logging.getLogger('session_service')

class SessionService:
    """
    Service for interacting with the Session Service through Redis.
    Handles session discovery and status checks.
    """
    
    def __init__(self, redis_client: RedisClient):
        """
        Initialize the session service
        
        Args:
            redis_client: Redis client for accessing session data
        """
        self.redis = redis_client
        
        # Create circuit breaker for Redis operations
        self.redis_breaker = CircuitBreaker(
            name="redis_session_service",
            failure_threshold=3,
            reset_timeout_ms=10000  # 10 seconds
        )
    
    async def get_session_info(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get information about a session from Redis
        
        Args:
            session_id: The session ID
            
        Returns:
            Session information or None if not found
        """
        try:
            return await self.redis_breaker.execute(self._get_session_info, session_id)
        except CircuitOpenError:
            logger.warning("Redis session service circuit breaker open")
            return None
        except Exception as e:
            logger.error(f"Error getting session info: {e}")
            return None
    
    async def _get_session_info(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Internal method to fetch session info with error handling"""
        # Check if session exists
        exists = await self.redis.exists(f"session:{session_id}")
        if not exists:
            return None
        
        # Get session data
        user_id = await self.redis.get(f"session:{session_id}:user_id")
        simulator_id = await self.redis.get(f"session:{session_id}:simulator")
        
        if not user_id:
            logger.warning(f"Session {session_id} exists but no user_id found")
            return None
        
        # Get simulator info if available
        simulator_info = None
        if simulator_id:
            simulator_endpoint = await self.redis.get(f"simulator:{simulator_id}:endpoint")
            simulator_status = await self.redis.get(f"simulator:{simulator_id}:status") or "UNKNOWN"
            
            if simulator_endpoint:
                simulator_info = {
                    "simulator_id": simulator_id,
                    "endpoint": simulator_endpoint,
                    "status": simulator_status
                }
        
        # Build session info
        session_info = {
            "session_id": session_id,
            "user_id": user_id,
            "simulator": simulator_info
        }
        
        # Get additional metadata if available
        connection_quality = await self.redis.get(f"connection:{session_id}:quality")
        if connection_quality:
            session_info["connection_quality"] = connection_quality
        
        frontend_connections = await self.redis.get(f"connection:{session_id}:ws_count")
        if frontend_connections:
            session_info["frontend_connections"] = int(frontend_connections)
        
        return session_info
    
    async def get_simulator_info(self, simulator_id: str) -> Optional[Dict[str, Any]]:
        """
        Get information about a simulator
        
        Args:
            simulator_id: The simulator ID
            
        Returns:
            Simulator information or None if not found
        """
        try:
            return await self.redis_breaker.execute(self._get_simulator_info, simulator_id)
        except CircuitOpenError:
            logger.warning("Redis simulator service circuit breaker open")
            return None
        except Exception as e:
            logger.error(f"Error getting simulator info: {e}")
            return None
    
    async def _get_simulator_info(self, simulator_id: str) -> Optional[Dict[str, Any]]:
        """Internal method to fetch simulator info with error handling"""
        # Check if simulator exists
        endpoint = await self.redis.get(f"simulator:{simulator_id}:endpoint")
        if not endpoint:
            return None
        
        # Get simulator data
        status = await self.redis.get(f"simulator:{simulator_id}:status") or "UNKNOWN"
        session_id = await self.redis.get(f"simulator:{simulator_id}:session")
        
        return {
            "simulator_id": simulator_id,
            "endpoint": endpoint,
            "status": status,
            "session_id": session_id
        }
    
    async def find_session_by_user(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Find all sessions for a user
        
        Args:
            user_id: The user ID
            
        Returns:
            List of session information
        """
        try:
            return await self.redis_breaker.execute(self._find_session_by_user, user_id)
        except CircuitOpenError:
            logger.warning("Redis session search circuit breaker open")
            return []
        except Exception as e:
            logger.error(f"Error finding sessions for user: {e}")
            return []
    
    async def _find_session_by_user(self, user_id: str) -> List[Dict[str, Any]]:
        """Internal method to find sessions by user with error handling"""
        # In a real implementation, this would use a Redis search or index
        # For simplicity, we'll just assume a "user_sessions" hash exists
        session_ids = await self.redis.get(f"user:{user_id}:sessions")
        if not session_ids:
            return []
        
        # Parse comma-separated list of session IDs
        session_id_list = session_ids.split(',')
        
        # Get info for each session
        sessions = []
        for session_id in session_id_list:
            session_info = await self.get_session_info(session_id)
            if session_info:
                sessions.append(session_info)
        
        return sessions
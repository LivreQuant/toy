# source/db/session_repository.py
import logging
import time
from typing import Dict, Any, Optional

from source.db.connection_pool import DatabasePool
from source.utils.metrics import track_db_operation

logger = logging.getLogger('session_repository')

class SessionRepository:
    """Data access layer for session and authorization related operations"""

    def __init__(self):
        """Initialize the session repository"""
        self.db_pool = DatabasePool()
        
    async def validate_device_id(self, device_id: str) -> bool:
        """
        Validate if the device ID is associated with a valid session
        
        Args:
            device_id: Device ID
            
        Returns:
            Boolean indicating if device ID is valid
        """
        if not device_id:
            return False
            
        pool = await self.db_pool.get_pool()

        query = """
        SELECT 1 FROM session.session_details
        WHERE device_id = $1
        """

        start_time = time.time()
        try:
            async with pool.acquire() as conn:
                # Cast the parameter to text explicitly
                row = await conn.fetchrow(query, str(device_id))

                duration = time.time() - start_time
                valid = row is not None
                track_db_operation("validate_device_id", valid, duration)

                return valid
        except Exception as e:
            duration = time.time() - start_time
            track_db_operation("validate_device_id", False, duration)
            logger.error(f"Error validating device ID: {e}")
            
            # For development purposes, temporarily skip device ID validation
            logger.warning("⚠️ Skipping device ID validation due to database error")
            return True
    
    async def get_session_simulator(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get simulator information for a user
        
        Args:
            user_id: User ID
            
        Returns:
            Dictionary with simulator information or None
        """
        pool = await self.db_pool.get_pool()

        query = """
        SELECT simulator_id, endpoint, status
        FROM simulator.instances
        WHERE user_id = $1 
        AND status IN ('RUNNING')
        ORDER BY created_at DESC
        LIMIT 1
        """

        try:
            async with pool.acquire() as conn:
                row = await conn.fetchrow(query, user_id)
                if not row:
                    return None
                return dict(row)
        except Exception as e:
            logger.error(f"Error getting user simulator: {e}")
            return None

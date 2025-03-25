# source/db/session_store.py
"""
Database access layer for session management.
Handles persisting and retrieving session data from PostgreSQL.
"""
import logging
import asyncio
import json
import time
import uuid
import asyncpg
from typing import Dict, List, Any, Optional, Tuple

from source.models.session import Session, SessionStatus
from source.models.simulator import Simulator, SimulatorStatus
from source.config import config

logger = logging.getLogger('session_store')

class DatabaseManager:
    """Database access for session service"""
    
    def __init__(self):
        """Initialize database manager"""
        self.pool = None
        self.db_config = config.db
        self._conn_lock = asyncio.Lock()
    
    async def connect(self):
        """Connect to the database"""
        async with self._conn_lock:
            if self.pool is not None:
                return
            
            max_retries = 5
            retry_count = 0
            retry_delay = 1.0
            
            while retry_count < max_retries:
                try:
                    self.pool = await asyncpg.create_pool(
                        host=self.db_config.host,
                        port=self.db_config.port,
                        user=self.db_config.user,
                        password=self.db_config.password,
                        database=self.db_config.database,
                        min_size=self.db_config.min_connections,
                        max_size=self.db_config.max_connections
                    )
                    
                    logger.info("Connected to database")
                    return
                    
                except Exception as e:
                    retry_count += 1
                    logger.error(f"Database connection error (attempt {retry_count}/{max_retries}): {e}")
                    
                    if retry_count < max_retries:
                        await asyncio.sleep(retry_delay)
                        retry_delay *= 2  # Exponential backoff
                    else:
                        logger.error("Maximum database connection retries reached")
                        raise
    
    async def close(self):
        """Close database connections"""
        if self.pool:
            await self.pool.close()
            self.pool = None
            logger.info("Closed database connections")
    
    async def check_connection(self) -> bool:
        """Check database connection health"""
        if not self.pool:
            try:
                await self.connect()
                return True
            except:
                return False
        
        try:
            async with self.pool.acquire() as conn:
                result = await conn.fetchval("SELECT 1")
                return result == 1
        except Exception as e:
            logger.error(f"Database connection check failed: {e}")
            return False
    
    async def create_session(self, user_id: str, ip_address: Optional[str] = None) -> Tuple[str, bool]:
        """
        Create a new session for a user
        
        Returns:
            Tuple of (session_id, is_new)
        """
        if not self.pool:
            await self.connect()
        
        try:
            # First check if user has an active session
            async with self.pool.acquire() as conn:
                active_session = await conn.fetchrow('''
                    SELECT session_id 
                    FROM session.active_sessions 
                    WHERE user_id = $1 AND expires_at > NOW()
                    LIMIT 1
                ''', user_id)
                
                if active_session:
                    # Update existing session activity
                    session_id = active_session['session_id']
                    await self.update_session_activity(session_id)
                    return session_id, False
                
                # Create new session
                session_id = str(uuid.uuid4())
                current_time = time.time()
                expires_at = current_time + config.session.timeout_seconds
                
                # Insert session record
                await conn.execute('''
                    INSERT INTO session.active_sessions 
                    (session_id, user_id, status, created_at, last_active, expires_at)
                    VALUES ($1, $2, $3, to_timestamp($4), to_timestamp($5), to_timestamp($6))
                ''', 
                    session_id, 
                    user_id, 
                    SessionStatus.ACTIVE.value,
                    current_time,
                    current_time,
                    expires_at
                )
                
                # Initialize metadata with pod information
                metadata = {
                    'pod_name': config.kubernetes.pod_name,
                    'ip_address': ip_address,
                    'created_at': current_time,
                    'updated_at': current_time
                }
                
                # Insert metadata
                await conn.execute('''
                    INSERT INTO session.session_metadata
                    (session_id, metadata)
                    VALUES ($1, $2)
                ''', session_id, json.dumps(metadata))
                
                return session_id, True
                
        except Exception as e:
            logger.error(f"Error creating session: {e}")
            raise
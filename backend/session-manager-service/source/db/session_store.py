import logging
import asyncio
import os
import json
import time
import asyncpg
from typing import Dict, List, Any, Optional

logger = logging.getLogger('db_manager')

class DatabaseManager:
    """Handles PostgreSQL database operations for sessions"""
    
    def __init__(self):
        self.pool = None
        self.db_config = {
            'host': os.getenv('DB_HOST', 'postgres'),
            'port': int(os.getenv('DB_PORT', '5432')),
            'database': os.getenv('DB_NAME', 'opentp'),
            'user': os.getenv('DB_USER', 'opentp'),
            'password': os.getenv('DB_PASSWORD', 'samaral')
        }
        self.min_connections = int(os.getenv('DB_MIN_CONNECTIONS', '1'))
        self.max_connections = int(os.getenv('DB_MAX_CONNECTIONS', '10'))
    
    async def connect(self):
        """Connect to database and create connection pool"""
        if self.pool:
            return
        
        try:
            self.pool = await asyncpg.create_pool(
                min_size=self.min_connections,
                max_size=self.max_connections,
                **self.db_config
            )
            logger.info("Connected to database")
        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")
            raise
    
    async def check_connection(self):
        """Check if database connection is alive"""
        if not self.pool:
            await self.connect()
            return self.pool is not None
        
        try:
            async with self.pool.acquire() as conn:
                await conn.execute('SELECT 1')
            return True
        except Exception as e:
            logger.error(f"Database connection check failed: {e}")
            return False
    
    async def close(self):
        """Close database connections"""
        if self.pool:
            await self.pool.close()
            self.pool = None
    
    async def get_session(self, session_id):
        """Get session data by ID"""
        if not self.pool:
            await self.connect()
        
        async with self.pool.acquire() as conn:
            # Get session data
            session_row = await conn.fetchrow(
                """
                SELECT 
                    session_id, user_id, created_at, last_active, expires_at, ip_address
                FROM 
                    session.active_sessions 
                WHERE 
                    session_id = $1
                """,
                session_id
            )
            
            if not session_row:
                return None
            
            # Convert to dict
            session = dict(session_row)
            
            # Get metadata
            metadata_row = await conn.fetchrow(
                """
                SELECT metadata FROM session.session_metadata 
                WHERE session_id = $1
                """,
                session_id
            )
            
            # Add metadata if available
            if metadata_row and metadata_row['metadata']:
                try:
                    session.update(json.loads(metadata_row['metadata']))
                except json.JSONDecodeError:
                    logger.error(f"Invalid JSON metadata for session {session_id}")
            
            return session
    
    async def get_user_session(self, user_id):
        """Get active session for a user"""
        if not self.pool:
            await self.connect()
        
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT session_id
                FROM session.active_sessions 
                WHERE user_id = $1 AND expires_at > NOW()
                """,
                user_id
            )
            
            return row['session_id'] if row else None
    
    async def create_session(self, session_id, user_id, client_ip=None):
        """Create a new session"""
        if not self.pool:
            await self.connect()
        
        async with self.pool.acquire() as conn:
            try:
                # Start transaction
                async with conn.transaction():
                    # Insert session record
                    await conn.execute(
                        """
                        INSERT INTO session.active_sessions 
                        (session_id, user_id, token, created_at, last_active, expires_at, ip_address) 
                        VALUES ($1, $2, $3, NOW(), NOW(), NOW() + INTERVAL '1 hour', $4)
                        """,
                        session_id, user_id, str(uuid.uuid4()), client_ip
                    )
                    
                    # Initialize empty metadata
                    await conn.execute(
                        """
                        INSERT INTO session.session_metadata
                        (session_id, metadata)
                        VALUES ($1, $2)
                        """,
                        session_id, '{}'
                    )
                
                return True
            except Exception as e:
                logger.error(f"Error creating session: {e}")
                return False
    
    async def update_session_activity(self, session_id):
        """Update last_active timestamp for a session"""
        if not self.pool:
            await self.connect()
        
        async with self.pool.acquire() as conn:
            result = await conn.execute(
                """
                UPDATE session.active_sessions 
                SET last_active = NOW(), expires_at = NOW() + INTERVAL '1 hour'
                WHERE session_id = $1
                """,
                session_id
            )
            
            return result != "UPDATE 0"
    
    async def update_session_metadata(self, session_id, updates):
        """Update session metadata fields"""
        if not self.pool:
            await self.connect()
        
        async with self.pool.acquire() as conn:
            # Get current metadata
            metadata_row = await conn.fetchrow(
                """
                SELECT metadata FROM session.session_metadata 
                WHERE session_id = $1
                """,
                session_id
            )
            
            # Process metadata
            if not metadata_row:
                # Create new metadata entry
                metadata = updates
                await conn.execute(
                    """
                    INSERT INTO session.session_metadata (session_id, metadata)
                    VALUES ($1, $2)
                    """,
                    session_id, json.dumps(metadata)
                )
            else:
                # Update existing metadata
                try:
                    current = json.loads(metadata_row['metadata']) if metadata_row['metadata'] else {}
                except json.JSONDecodeError:
                    current = {}
                
                # Apply updates
                current.update(updates)
                
                # Save back to database
                await conn.execute(
                    """
                    UPDATE session.session_metadata
                    SET metadata = $1
                    WHERE session_id = $2
                    """,
                    json.dumps(current), session_id
                )
            
            return True
    
    async def end_session(self, session_id):
        """Delete a session"""
        if not self.pool:
            await self.connect()
        
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                # Delete metadata first
                await conn.execute(
                    """
                    DELETE FROM session.session_metadata
                    WHERE session_id = $1
                    """,
                    session_id
                )
                
                # Delete session
                result = await conn.execute(
                    """
                    DELETE FROM session.active_sessions 
                    WHERE session_id = $1
                    RETURNING user_id
                    """,
                    session_id
                )
                
                return result != "DELETE 0"
    
    async def cleanup_expired_sessions(self):
        """Run the cleanup function for expired sessions"""
        if not self.pool:
            await self.connect()
        
        async with self.pool.acquire() as conn:
            await conn.execute("SELECT session.cleanup_expired_sessions()")
            return True
    
    async def register_exchange_service(self, session_id, exchange_id, endpoint, inactivity_timeout_seconds=300):
        """Register a new exchange service for a session"""
        if not self.pool:
            await self.connect()
        
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO session.exchange_services
                (exchange_id, session_id, endpoint, created_at, last_active, inactivity_timeout_seconds)
                VALUES ($1, $2, $3, NOW(), NOW(), $4)
                ON CONFLICT (session_id) DO UPDATE
                SET exchange_id = EXCLUDED.exchange_id,
                    endpoint = EXCLUDED.endpoint,
                    last_active = NOW(),
                    inactivity_timeout_seconds = EXCLUDED.inactivity_timeout_seconds
                """,
                exchange_id, session_id, endpoint, inactivity_timeout_seconds
            )
            return True
    
    async def update_exchange_last_active(self, session_id):
        """Update last_active timestamp for exchange service attached to session"""
        if not self.pool:
            await self.connect()
        
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE session.exchange_services
                SET last_active = NOW()
                WHERE session_id = $1
                """,
                session_id
            )
            return True
    
    async def get_exchange_for_session(self, session_id):
        """Get exchange service info for a session"""
        if not self.pool:
            await self.connect()
        
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT 
                    exchange_id, endpoint, last_active, inactivity_timeout_seconds
                FROM 
                    session.exchange_services
                WHERE 
                    session_id = $1
                """,
                session_id
            )
            
            return dict(row) if row else None
    
    async def deactivate_exchange_service(self, exchange_id):
        """Deactivate an exchange service"""
        if not self.pool:
            await self.connect()
        
        async with self.pool.acquire() as conn:
            # Get session ID first for metadata update
            row = await conn.fetchrow(
                """
                SELECT session_id
                FROM session.exchange_services
                WHERE exchange_id = $1
                """,
                exchange_id
            )
            
            if row:
                session_id = row['session_id']
                
                async with conn.transaction():
                    # Delete exchange service
                    await conn.execute(
                        """
                        DELETE FROM session.exchange_services
                        WHERE exchange_id = $1
                        """,
                        exchange_id
                    )
                    
                    # Update session metadata
                    metadata_row = await conn.fetchrow(
                        """
                        SELECT metadata
                        FROM session.session_metadata
                        WHERE session_id = $1
                        """, 
                        session_id
                    )
                    
                    if metadata_row and metadata_row['metadata']:
                        try:
                            metadata = json.loads(metadata_row['metadata'])
                            
                            # Clear simulator info
                            metadata['simulator_id'] = None
                            metadata['simulator_endpoint'] = None
                            metadata['simulator_status'] = 'STOPPED'
                            
                            # Update metadata
                            await conn.execute(
                                """
                                UPDATE session.session_metadata
                                SET metadata = $1
                                WHERE session_id = $2
                                """,
                                json.dumps(metadata), session_id
                            )
                        except:
                            logger.error(f"Error updating metadata for session {session_id}")
            
            return True
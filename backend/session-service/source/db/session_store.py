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
                    
                    # Initialize schema if needed
                    await self._initialize_schema()
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
    
    async def _initialize_schema(self):
        """Initialize database schema if needed"""
        async with self.pool.acquire() as conn:
            # Create schemas
            await conn.execute('''
                CREATE SCHEMA IF NOT EXISTS session;
                CREATE SCHEMA IF NOT EXISTS simulator;
            ''')
            
            # Create sessions table
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS session.active_sessions (
                    session_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    last_active TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    expires_at TIMESTAMPTZ NOT NULL,
                    token TEXT
                );
                
                CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON session.active_sessions(user_id);
                CREATE INDEX IF NOT EXISTS idx_sessions_expires_at ON session.active_sessions(expires_at);
            ''')
            
            # Create session metadata table
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS session.session_metadata (
                    session_id TEXT PRIMARY KEY REFERENCES session.active_sessions(session_id) ON DELETE CASCADE,
                    metadata JSONB NOT NULL DEFAULT '{}'::jsonb
                );
            ''')
            
            # Create simulators table
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS simulator.instances (
                    simulator_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    endpoint TEXT,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    last_active TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    initial_symbols JSONB,
                    initial_cash FLOAT NOT NULL DEFAULT 100000.0
                );
                
                CREATE INDEX IF NOT EXISTS idx_simulators_session_id ON simulator.instances(session_id);
                CREATE INDEX IF NOT EXISTS idx_simulators_user_id ON simulator.instances(user_id);
            ''')
            
            # Create cleanup function for expired sessions
            await conn.execute('''
                CREATE OR REPLACE FUNCTION session.cleanup_expired_sessions() 
                RETURNS INTEGER AS $$
                DECLARE
                    deleted_count INTEGER;
                BEGIN
                    DELETE FROM session.active_sessions
                    WHERE expires_at < NOW();
                    
                    GET DIAGNOSTICS deleted_count = ROW_COUNT;
                    RETURN deleted_count;
                END;
                $$ LANGUAGE plpgsql;
            ''')
            
            logger.info("Initialized database schema")
    
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
    
    async def get_session(self, session_id: str) -> Optional[Session]:
        """Get a session by ID"""
        if not self.pool:
            await self.connect()
        
        try:
            async with self.pool.acquire() as conn:
                # Get session data
                session_row = await conn.fetchrow('''
                    SELECT 
                        s.session_id, 
                        s.user_id, 
                        s.status, 
                        EXTRACT(EPOCH FROM s.created_at) as created_at,
                        EXTRACT(EPOCH FROM s.last_active) as last_active,
                        EXTRACT(EPOCH FROM s.expires_at) as expires_at,
                        s.token,
                        m.metadata
                    FROM 
                        session.active_sessions s
                    LEFT JOIN 
                        session.session_metadata m ON s.session_id = m.session_id
                    WHERE 
                        s.session_id = $1
                ''', session_id)
                
                if not session_row:
                    return None
                
                # Combine session data with metadata
                session_data = dict(session_row)
                metadata = json.loads(session_data.pop('metadata') or '{}')
                
                # Merge session data with metadata for a complete view
                combined_data = {**session_data, **metadata}
                
                # Create session object
                return Session.from_dict(combined_data)
                
        except Exception as e:
            logger.error(f"Error getting session: {e}")
            return None
    
    async def update_session_activity(self, session_id: str) -> bool:
        """Update session activity timestamp"""
        if not self.pool:
            await self.connect()
        
        try:
            async with self.pool.acquire() as conn:
                # Update last active timestamp
                current_time = time.time()
                expires_at = current_time + config.session.timeout_seconds
                
                result = await conn.execute('''
                    UPDATE session.active_sessions
                    SET last_active = to_timestamp($1),
                        expires_at = to_timestamp($2)
                    WHERE session_id = $3
                ''', current_time, expires_at, session_id)
                
                return "UPDATE 1" in result
                
        except Exception as e:
            logger.error(f"Error updating session activity: {e}")
            return False
    
    async def update_session_metadata(self, session_id: str, updates: Dict[str, Any]) -> bool:
        """Update session metadata"""
        if not self.pool:
            await self.connect()
        
        try:
            async with self.pool.acquire() as conn:
                # Get current metadata
                metadata_row = await conn.fetchval('''
                    SELECT metadata FROM session.session_metadata 
                    WHERE session_id = $1
                ''', session_id)
                
                # Parse current metadata
                current_metadata = json.loads(metadata_row or '{}')
                
                # Update metadata
                current_metadata.update(updates)
                current_metadata['updated_at'] = time.time()
                
                # Save back to database
                await conn.execute('''
                    INSERT INTO session.session_metadata (session_id, metadata)
                    VALUES ($1, $2)
                    ON CONFLICT (session_id) 
                    DO UPDATE SET metadata = $2
                ''', session_id, json.dumps(current_metadata))
                
                return True
                
        except Exception as e:
            logger.error(f"Error updating session metadata: {e}")
            return False
    
    async def end_session(self, session_id: str) -> bool:
        """End a session"""
        if not self.pool:
            await self.connect()
        
        try:
            async with self.pool.acquire() as conn:
                # Begin transaction
                async with conn.transaction():
                    # Delete metadata first (cascade will handle foreign key)
                    await conn.execute('''
                        DELETE FROM session.session_metadata
                        WHERE session_id = $1
                    ''', session_id)
                    
                    # Delete session
                    result = await conn.execute('''
                        DELETE FROM session.active_sessions
                        WHERE session_id = $1
                    ''', session_id)
                    
                    return "DELETE 1" in result
                    
        except Exception as e:
            logger.error(f"Error ending session: {e}")
            return False
    
    async def create_simulator(self, simulator: Simulator) -> bool:
        """Create a new simulator record"""
        if not self.pool:
            await self.connect()
        
        try:
            async with self.pool.acquire() as conn:
                simulator_dict = simulator.to_dict()
                
                await conn.execute('''
                    INSERT INTO simulator.instances
                    (simulator_id, session_id, user_id, status, endpoint, 
                     created_at, last_active, initial_symbols, initial_cash)
                    VALUES ($1, $2, $3, $4, $5, to_timestamp($6), to_timestamp($7), $8, $9)
                ''',
                    simulator_dict['simulator_id'],
                    simulator_dict['session_id'],
                    simulator_dict['user_id'],
                    simulator_dict['status'],
                    simulator_dict['endpoint'],
                    simulator_dict['created_at'],
                    simulator_dict['last_active'],
                    json.dumps(simulator_dict['initial_symbols']),
                    simulator_dict['initial_cash']
                )
                
                return True
                
        except Exception as e:
            logger.error(f"Error creating simulator: {e}")
            return False
    
    async def get_simulator(self, simulator_id: str) -> Optional[Simulator]:
        """Get a simulator by ID"""
        if not self.pool:
            await self.connect()
        
        try:
            async with self.pool.acquire() as conn:
                simulator_row = await conn.fetchrow('''
                    SELECT
                        simulator_id,
                        session_id,
                        user_id,
                        status,
                        endpoint,
                        EXTRACT(EPOCH FROM created_at) as created_at,
                        EXTRACT(EPOCH FROM last_active) as last_active,
                        initial_symbols,
                        initial_cash
                    FROM
                        simulator.instances
                    WHERE
                        simulator_id = $1
                ''', simulator_id)
                
                if not simulator_row:
                    return None
                
                # Convert to dict
                simulator_dict = dict(simulator_row)
                
                # Parse JSON fields
                simulator_dict['initial_symbols'] = json.loads(simulator_dict['initial_symbols'] or '[]')
                
                return Simulator.from_dict(simulator_dict)
                
        except Exception as e:
            logger.error(f"Error getting simulator: {e}")
            return None
    
    async def get_simulator_by_session(self, session_id: str) -> Optional[Simulator]:
        """Get the simulator for a session"""
        if not self.pool:
            await self.connect()
        
        try:
            async with self.pool.acquire() as conn:
                simulator_row = await conn.fetchrow('''
                    SELECT
                        simulator_id,
                        session_id,
                        user_id,
                        status,
                        endpoint,
                        EXTRACT(EPOCH FROM created_at) as created_at,
                        EXTRACT(EPOCH FROM last_active) as last_active,
                        initial_symbols,
                        initial_cash
                    FROM
                        simulator.instances
                    WHERE
                        session_id = $1 AND status != 'STOPPED'
                    ORDER BY created_at DESC
                    LIMIT 1
                ''', session_id)
                
                if not simulator_row:
                    return None
                
                # Convert to dict
                simulator_dict = dict(simulator_row)
                
                # Parse JSON fields
                simulator_dict['initial_symbols'] = json.loads(simulator_dict['initial_symbols'] or '[]')
                
                return Simulator.from_dict(simulator_dict)
                
        except Exception as e:
            logger.error(f"Error getting simulator by session: {e}")
            return None
    
    async def update_simulator_status(self, simulator_id: str, status: SimulatorStatus) -> bool:
        """Update simulator status"""
        if not self.pool:
            await self.connect()
        
        try:
            async with self.pool.acquire() as conn:
                result = await conn.execute('''
                    UPDATE simulator.instances
                    SET status = $1, last_active = NOW()
                    WHERE simulator_id = $2
                ''', status.value, simulator_id)
                
                return "UPDATE 1" in result
                
        except Exception as e:
            logger.error(f"Error updating simulator status: {e}")
            return False
    
    async def update_simulator_activity(self, simulator_id: str) -> bool:
        """Update simulator last active timestamp"""
        if not self.pool:
            await self.connect()
        
        try:
            async with self.pool.acquire() as conn:
                result = await conn.execute('''
                    UPDATE simulator.instances
                    SET last_active = NOW()
                    WHERE simulator_id = $1
                ''', simulator_id)
                
                return "UPDATE 1" in result
                
        except Exception as e:
            logger.error(f"Error updating simulator activity: {e}")
            return False
    
    async def update_simulator_endpoint(self, simulator_id: str, endpoint: str) -> bool:
        """Update simulator endpoint"""
        if not self.pool:
            await self.connect()
        
        try:
            async with self.pool.acquire() as conn:
                result = await conn.execute('''
                    UPDATE simulator.instances
                    SET endpoint = $1, last_active = NOW()
                    WHERE simulator_id = $2
                ''', endpoint, simulator_id)
                
                return "UPDATE 1" in result
                
        except Exception as e:
            logger.error(f"Error updating simulator endpoint: {e}")
            return False
    
    async def get_active_user_simulators(self, user_id: str) -> List[Simulator]:
        """Get all active simulators for a user"""
        if not self.pool:
            await self.connect()
        
        try:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch('''
                    SELECT
                        simulator_id,
                        session_id,
                        user_id,
                        status,
                        endpoint,
                        EXTRACT(EPOCH FROM created_at) as created_at,
                        EXTRACT(EPOCH FROM last_active) as last_active,
                        initial_symbols,
                        initial_cash
                    FROM
                        simulator.instances
                    WHERE
                        user_id = $1 AND status != 'STOPPED'
                ''', user_id)
                
                simulators = []
                for row in rows:
                    simulator_dict = dict(row)
                    simulator_dict['initial_symbols'] = json.loads(simulator_dict['initial_symbols'] or '[]')
                    simulators.append(Simulator.from_dict(simulator_dict))
                
                return simulators
                
        except Exception as e:
            logger.error(f"Error getting active user simulators: {e}")
            return []
    
    async def get_all_active_simulators(self) -> List[Dict[str, Any]]:
        """Get all active simulators"""
        if not self.pool:
            await self.connect()
        
        try:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch('''
                    SELECT
                        simulator_id,
                        session_id,
                        user_id,
                        status,
                        endpoint,
                        EXTRACT(EPOCH FROM created_at) as created_at,
                        EXTRACT(EPOCH FROM last_active) as last_active,
                        initial_symbols,
                        initial_cash
                    FROM
                        simulator.instances
                    WHERE
                        status != 'STOPPED'
                ''')
                
                simulators = []
                for row in rows:
                    simulator_dict = dict(row)
                    simulator_dict['initial_symbols'] = json.loads(simulator_dict['initial_symbols'] or '[]')
                    simulators.append(simulator_dict)
                
                return simulators
                
        except Exception as e:
            logger.error(f"Error getting all active simulators: {e}")
            return []
    
    async def cleanup_expired_sessions(self) -> int:
        """Clean up expired sessions"""
        if not self.pool:
            await self.connect()
        
        try:
            async with self.pool.acquire() as conn:
                result = await conn.fetchval('''
                    SELECT session.cleanup_expired_sessions()
                ''')
                
                return result
                
        except Exception as e:
            logger.error(f"Error cleaning up expired sessions: {e}")
            return 0
    
    async def cleanup_inactive_simulators(self, timeout_seconds: int = 3600) -> int:
        """Clean up inactive simulators"""
        if not self.pool:
            await self.connect()
        
        try:
            async with self.pool.acquire() as conn:
                # Find inactive simulators
                inactive_simulators = await conn.fetch('''
                    SELECT simulator_id
                    FROM simulator.instances
                    WHERE last_active < NOW() - INTERVAL '$1 seconds'
                    AND status != 'STOPPED'
                ''', timeout_seconds)
                
                # Update status to STOPPED
                for row in inactive_simulators:
                    simulator_id = row['simulator_id']
                    await conn.execute('''
                        UPDATE simulator.instances
                        SET status = 'STOPPED'
                        WHERE simulator_id = $1
                    ''', simulator_id)
                
                return len(inactive_simulators)
                
        except Exception as e:
            logger.error(f"Error cleaning up inactive simulators: {e}")
            return 0
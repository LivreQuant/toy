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
from opentelemetry import trace
from typing import Dict, List, Any, Optional, Tuple
from source.models.session import Session, SessionStatus, SessionMetadata

from source.utils.metrics import (
    track_db_operation,
    track_db_error,
    track_session_operation,
    track_session_count,
    track_cleanup_operation,
    TimedOperation
)
from source.utils.tracing import optional_trace_span
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
        self.tracer = trace.get_tracer("db_manager")

    async def connect(self):
        """Connect to the database"""
        with optional_trace_span(self.tracer, "db_connect") as span:
            span.set_attribute("db.system", "postgresql")
            span.set_attribute("db.name", self.db_config.database)
            span.set_attribute("db.user", self.db_config.user)
            span.set_attribute("db.host", self.db_config.host)

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
                        span.record_exception(e)
                        span.set_attribute("retry_count", retry_count)

                        if retry_count < max_retries:
                            await asyncio.sleep(retry_delay)
                            retry_delay *= 2  # Exponential backoff
                        else:
                            logger.error("Maximum database connection retries reached")
                            span.set_attribute("success", False)
                            track_db_error("connect")
                            raise

    async def cleanup_inactive_simulators(self, inactivity_timeout: int) -> int:
        """
        Mark simulators as STOPPED if they've been inactive beyond the timeout

        Args:
            inactivity_timeout: Timeout in seconds

        Returns:
            Number of simulators marked as stopped
        """
        with optional_trace_span(self.tracer, "db_cleanup_inactive_simulators") as span:
            span.set_attribute("inactivity_timeout", inactivity_timeout)

            if not self.pool:
                await self.connect()

            try:
                with TimedOperation(track_db_operation, "cleanup_inactive_simulators"):
                    async with self.pool.acquire() as conn:
                        # Mark simulators as STOPPED if they've been inactive
                        result = await conn.execute('''
                            UPDATE simulator.instances
                            SET status = $1
                            WHERE status != $1
                            AND last_active < NOW() - INTERVAL '1 second' * $2
                        ''', SimulatorStatus.STOPPED.value, inactivity_timeout)

                        count = int(result.split()[-1]) if result else 0
                        span.set_attribute("simulators_cleaned", count)

                        if count > 0:
                            logger.info(f"Marked {count} inactive simulators as STOPPED")
                            track_cleanup_operation("simulators", count)
                        return count
            except Exception as e:
                logger.error(f"Error cleaning up inactive simulators: {e}")
                span.record_exception(e)
                track_db_error("cleanup_inactive_simulators")
                return 0

    async def get_active_user_simulators(self, user_id: str) -> List[Simulator]:
        """
        Get active simulators for a user

        Args:
            user_id: User ID

        Returns:
            List of active simulators
        """
        with optional_trace_span(self.tracer, "db_get_active_user_simulators") as span:
            span.set_attribute("user_id", user_id)

            if not self.pool:
                await self.connect()

            try:
                async with self.pool.acquire() as conn:
                    rows = await conn.fetch('''
                        SELECT * FROM simulator.instances
                        WHERE user_id = $1
                        AND status != $2
                    ''', user_id, SimulatorStatus.STOPPED.value)

                    simulators = []
                    for row in rows:
                        simulator = Simulator(
                            simulator_id=row['simulator_id'],
                            session_id=row['session_id'],
                            user_id=row['user_id'],
                            status=SimulatorStatus(row['status']),
                            endpoint=row['endpoint'],
                            created_at=row['created_at'].timestamp(),
                            last_active=row['last_active'].timestamp(),
                            initial_symbols=row['initial_symbols'] or [],
                            initial_cash=row['initial_cash']
                        )
                        simulators.append(simulator)

                    return simulators
            except Exception as e:
                logger.error(f"Error getting active user simulators: {e}")
                return []

    async def get_active_user_sessions(self, user_id: str) -> List[Session]:
        """Get all active sessions"""
        with optional_trace_span(self.tracer, "db_get_active_user_sessions") as span:
            if not self.pool:
                await self.connect()

            try:
                with TimedOperation(track_db_operation, "get_active_user_sessions"):
                    async with self.pool.acquire() as conn:
                        # Get active sessions
                        session_rows = await conn.fetch('''
                            SELECT s.* FROM session.active_sessions s
                            WHERE s.user_id = $1
                            AND s.status != $2
                        ''', user_id, SessionStatus.ACTIVE.value)

                        sessions = []
                        for row in session_rows:
                            # Create session
                            session = Session(
                                session_id=row['session_id'],
                                user_id=row['user_id'],
                                status=SessionStatus(row['status']),
                                created_at=row['created_at'].timestamp(),
                                last_active=row['last_active'].timestamp(),
                                expires_at=row['expires_at'].timestamp()
                            )

                            # Get metadata for this session
                            metadata_row = await conn.fetchrow('''
                                SELECT metadata FROM session.session_metadata
                                WHERE session_id = $1
                            ''', row['session_id'])

                            # Add metadata if exists
                            if metadata_row and metadata_row['metadata']:
                                metadata_dict = metadata_row['metadata']
                                if isinstance(metadata_dict, dict):
                                    session.metadata = SessionMetadata(**metadata_dict)
                                else:
                                    session.metadata = SessionMetadata.parse_raw(metadata_dict)

                            sessions.append(session)

                        span.set_attribute("session_count", len(sessions))
                        return sessions

            except Exception as e:
                logger.error(f"Error getting active user sessions: {e}")
                span.record_exception(e)
                track_db_error("get_active_user_sessions")
                return []

    async def get_all_simulators(self):
        """Get all simulators from the database"""
        if not self.pool:
            await self.connect()

        try:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch('''
                    SELECT * FROM simulator.instances
                ''')

                simulators = []
                for row in rows:
                    simulator = Simulator(
                        simulator_id=row['simulator_id'],
                        session_id=row['session_id'],
                        user_id=row['user_id'],
                        status=SimulatorStatus(row['status']),
                        endpoint=row['endpoint'],
                        created_at=row['created_at'].timestamp(),
                        last_active=row['last_active'].timestamp(),
                        initial_symbols=row['initial_symbols'] or [],
                        initial_cash=row['initial_cash']
                    )
                    simulators.append(simulator)

                return simulators
        except Exception as e:
            logger.error(f"Error getting all simulators: {e}")
            return []

    async def get_active_sessions(self) -> List[Session]:
        """Get all active sessions"""
        with optional_trace_span(self.tracer, "db_get_active_sessions") as span:
            if not self.pool:
                await self.connect()

            try:
                with TimedOperation(track_db_operation, "get_active_sessions"):
                    async with self.pool.acquire() as conn:
                        # Get active sessions
                        session_rows = await conn.fetch('''
                            SELECT s.* FROM session.active_sessions s
                            WHERE s.status = $1 AND s.expires_at > NOW()
                        ''', SessionStatus.ACTIVE.value)

                        sessions = []
                        for row in session_rows:
                            # Create session
                            session = Session(
                                session_id=row['session_id'],
                                user_id=row['user_id'],
                                status=SessionStatus(row['status']),
                                created_at=row['created_at'].timestamp(),
                                last_active=row['last_active'].timestamp(),
                                expires_at=row['expires_at'].timestamp()
                            )

                            # Get metadata for this session
                            metadata_row = await conn.fetchrow('''
                                SELECT metadata FROM session.session_metadata
                                WHERE session_id = $1
                            ''', row['session_id'])

                            # Add metadata if exists
                            if metadata_row and metadata_row['metadata']:
                                metadata_dict = metadata_row['metadata']
                                if isinstance(metadata_dict, dict):
                                    session.metadata = SessionMetadata(**metadata_dict)
                                else:
                                    session.metadata = SessionMetadata.parse_raw(metadata_dict)

                            sessions.append(session)

                        span.set_attribute("session_count", len(sessions))
                        return sessions

            except Exception as e:
                logger.error(f"Error getting active sessions: {e}")
                span.record_exception(e)
                track_db_error("get_active_sessions")
                return []

    async def update_simulator_last_active(self, simulator_id: str, timestamp: float) -> bool:
        """
        Update the last_active time for a simulator
        
        Args:
            simulator_id: Simulator ID
            timestamp: New last_active timestamp
            
        Returns:
            Success flag
        """
        if not self.pool:
            await self.connect()
            
        try:
            async with self.pool.acquire() as conn:
                result = await conn.execute('''
                    UPDATE simulator.instances
                    SET last_active = to_timestamp($1)
                    WHERE simulator_id = $2
                ''', timestamp, simulator_id)
                
                return 'UPDATE 1' in result
        except Exception as e:
            logger.error(f"Error updating simulator last_active: {e}")
            return False
        
    async def update_session_status(self, session_id: str, status: str) -> bool:
        """Update session status"""
        with optional_trace_span(self.tracer, "db_update_session_status") as span:
            span.set_attribute("session_id", session_id)
            span.set_attribute("status", status)
            
            if not self.pool:
                await self.connect()
            
            try:
                with TimedOperation(track_db_operation, "update_session_status"):
                    async with self.pool.acquire() as conn:
                        result = await conn.execute('''
                            UPDATE session.active_sessions
                            SET status = $1
                            WHERE session_id = $2
                        ''', status, session_id)
                        
                        return 'UPDATE 1' in result
            except Exception as e:
                logger.error(f"Error updating session status: {e}")
                span.record_exception(e)
                track_db_error("update_session_status")
                return False

    async def get_sessions_with_criteria(self, criteria: Dict[str, Any]) -> List[Session]:
        """Get sessions matching specified criteria"""
        with optional_trace_span(self.tracer, "db_get_sessions_with_criteria") as span:
            if not self.pool:
                await self.connect()
            
            try:
                query_parts = ["SELECT s.*, m.metadata FROM session.active_sessions s"]
                query_parts.append("LEFT JOIN session.session_metadata m ON s.session_id = m.session_id")
                
                conditions = []
                params = []
                param_idx = 1
                
                # Add conditions based on criteria
                if 'last_active_before' in criteria:
                    conditions.append(f"s.last_active < to_timestamp(${param_idx})")
                    params.append(criteria['last_active_before'])
                    param_idx += 1
                    
                if 'status' in criteria:
                    conditions.append(f"s.status = ${param_idx}")
                    params.append(criteria['status'])
                    param_idx += 1
                
                if conditions:
                    query_parts.append("WHERE " + " AND ".join(conditions))
                
                query = " ".join(query_parts)
                span.set_attribute("query", query)
                
                with TimedOperation(track_db_operation, "get_sessions_with_criteria"):
                    async with self.pool.acquire() as conn:
                        rows = await conn.fetch(query, *params)
                        
                        sessions = []
                        for row in rows:
                            # Create session from row data
                            session = Session(
                                session_id=row['session_id'],
                                user_id=row['user_id'],
                                status=SessionStatus(row['status']),
                                created_at=row['created_at'].timestamp(),
                                last_active=row['last_active'].timestamp(),
                                expires_at=row['expires_at'].timestamp()
                            )
                            
                            # Add metadata if exists
                            if row['metadata']:
                                metadata_dict = row['metadata']
                                if isinstance(metadata_dict, dict):
                                    session.metadata = SessionMetadata(**metadata_dict)
                                else:
                                    session.metadata = SessionMetadata.parse_raw(metadata_dict)
                            
                            sessions.append(session)
                        
                        return sessions
            
            except Exception as e:
                logger.error(f"Error getting sessions with criteria: {e}")
                span.record_exception(e)
                track_db_error("get_sessions_with_criteria")
                return []
            
    async def update_session_metadata(self, session_id: str, metadata_updates: Dict[str, Any]) -> bool:
        """
        Update session metadata
        
        Args:
            session_id: Session ID
            metadata_updates: Dictionary of metadata fields to update
            
        Returns:
            Success flag
        """
        with optional_trace_span(self.tracer, "db_update_session_metadata") as span:
            span.set_attribute("session_id", session_id)
            
            if not self.pool:
                await self.connect()
                
            try:
                with TimedOperation(track_db_operation, "update_session_metadata"):
                    async with self.pool.acquire() as conn:
                        # First, get current metadata
                        current_metadata = await conn.fetchval('''
                            SELECT metadata FROM session.session_metadata
                            WHERE session_id = $1
                        ''', session_id)
                        
                        # Merge with updates
                        if current_metadata:
                            # Convert to dict if it's a string
                            if isinstance(current_metadata, str):
                                current_metadata = json.loads(current_metadata)
                                
                            # Update with new values
                            merged_metadata = {**current_metadata, **metadata_updates}
                        else:
                            # Create new metadata
                            merged_metadata = metadata_updates
                        
                        # Always include timestamp
                        merged_metadata['updated_at'] = time.time()
                        
                        # Update in database
                        await conn.execute('''
                            INSERT INTO session.session_metadata (session_id, metadata)
                            VALUES ($1, $2)
                            ON CONFLICT (session_id) 
                            DO UPDATE SET metadata = $2
                        ''', session_id, json.dumps(merged_metadata))

                        # Add log at the beginning
                        logger.info(f"Updating metadata for session {session_id} with updates: {json.dumps(metadata_updates)}")
                        
                        # After fetching current metadata
                        if current_metadata:
                            logger.info(f"Current metadata for session {session_id}: {json.dumps(current_metadata if isinstance(current_metadata, dict) else current_metadata)}")
                        else:
                            logger.warning(f"No existing metadata found for session {session_id} before update")
                        
                        # Before update
                        logger.info(f"Merged metadata for session {session_id}: {json.dumps(merged_metadata)}")
                        
                        # After update
                        logger.info(f"Successfully updated metadata for session {session_id}")
    
                        return True
                        
            except Exception as e:
                logger.error(f"Error updating session metadata: {e}")
                span.record_exception(e)
                track_db_error("update_session_metadata")
                return False
            
    async def get_session(self, session_id: str) -> Session:
        """
        Get a session by ID
        
        Args:
            session_id: Session ID
            
        Returns:
            Session or None if not found
        """
        with optional_trace_span(self.tracer, "db_get_session") as span:
            span.set_attribute("session_id", session_id)

            if not self.pool:
                await self.connect()
                
            try:
                with TimedOperation(track_db_operation, "get_session"):
                    async with self.pool.acquire() as conn:
                        # Get session data
                        session_row = await conn.fetchrow('''
                            SELECT * FROM session.active_sessions 
                            WHERE session_id = $1 AND expires_at > NOW()
                        ''', session_id)
                        
                        if not session_row:
                            return None
                        
                        # Get session metadata
                        metadata_row = await conn.fetchrow('''
                            SELECT metadata FROM session.session_metadata
                            WHERE session_id = $1
                        ''', session_id)
                        
                        # Create session object
                        session = Session(
                            session_id=session_row['session_id'],
                            user_id=session_row['user_id'],
                            status=SessionStatus(session_row['status']),
                            created_at=session_row['created_at'].timestamp(),
                            last_active=session_row['last_active'].timestamp(),
                            expires_at=session_row['expires_at'].timestamp()
                        )
                        
                        logger.info(f"Session Store - Session object type: {type(session)}")
                                      
                        # Add metadata if exists
                        if metadata_row and metadata_row['metadata']:
                            metadata_dict = metadata_row['metadata']
                            # Convert the raw metadata dict to SessionMetadata properly
                            if isinstance(metadata_dict, dict):
                                session.metadata = SessionMetadata(**metadata_dict)
                            else:
                                # Handle case where metadata might be a JSON string
                                session.metadata = SessionMetadata.parse_raw(metadata_dict)
                              
                        # Add detailed logging
                        logger.info(f"Fetching session {session_id} from database")
                        
                        # After fetching session data
                        if not session_row:
                            logger.warning(f"Session {session_id} not found in database")
                            return None
                        logger.info(f"Found session {session_id} for user {session_row['user_id']}")
                        
                        # After fetching metadata
                        if metadata_row and metadata_row['metadata']:
                            logger.info(f"Found metadata for session {session_id}: {json.dumps(metadata_row['metadata'] if isinstance(metadata_row['metadata'], dict) else metadata_row['metadata'])}")
                        else:
                            logger.warning(f"No metadata found for session {session_id}")
                        
                        logger.info(f"Session Store - Session object type: {type(session)}")

                        return session
                        
            except Exception as e:
                logger.error(f"Error getting session: {e}")
                span.record_exception(e)
                track_db_error("get_session")
                return None
            
    async def get_simulator_by_session(self, session_id: str) -> Optional[Simulator]:
        """
        Get simulator for a session

        Args:
            session_id: Session ID

        Returns:
            Simulator or None
        """
        with optional_trace_span(self.tracer, "db_simulator_by_session") as span:
            span.set_attribute("session_id", session_id)

            if not self.pool:
                await self.connect()

            try:
                async with self.pool.acquire() as conn:
                    row = await conn.fetchrow('''
                        SELECT * FROM simulator.instances
                        WHERE session_id = $1
                    ''', session_id)

                    if not row:
                        return None

                    return Simulator(
                        simulator_id=row['simulator_id'],
                        session_id=row['session_id'],
                        user_id=row['user_id'],
                        status=SimulatorStatus(row['status']),
                        endpoint=row['endpoint'],
                        created_at=row['created_at'].timestamp(),
                        last_active=row['last_active'].timestamp(),
                        initial_symbols=row['initial_symbols'] or [],
                        initial_cash=row['initial_cash']
                    )
            except Exception as e:
                logger.error(f"Error getting simulator by session: {e}")
                return None

    async def cleanup_expired_sessions(self) -> int:
        """
        Clean up expired sessions by calling the database function

        Returns:
            Number of sessions deleted
        """
        with optional_trace_span(self.tracer, "db_cleanup_expired_sessions") as span:

            if not self.pool:
                await self.connect()

            try:
                async with self.pool.acquire() as conn:
                    # Call the database function
                    result = await conn.fetchval("SELECT session.cleanup_expired_sessions()")
                    logger.info(f"Cleaned up {result} expired sessions")
                    return result
            except Exception as e:
                logger.error(f"Error cleaning up expired sessions: {e}")
                return 0

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

    async def update_session_activity(self, session_id: str) -> bool:
        """
        Update the last_active and expires_at time for a session
        
        Args:
            session_id: The session ID
            
        Returns:
            Success status
        """
        with optional_trace_span(self.tracer, "db_update_session_activity") as span:
            span.set_attribute("session_id", session_id)
            
            if not self.pool:
                await self.connect()
            
            try:
                with TimedOperation(track_db_operation, "update_session_activity"):
                    current_time = time.time()
                    # Calculate new expiry time
                    expires_at = current_time + config.session.timeout_seconds
                    
                    async with self.pool.acquire() as conn:
                        # Update session activity and expiry
                        result = await conn.execute('''
                            UPDATE session.active_sessions
                            SET last_active = to_timestamp($1), expires_at = to_timestamp($2)
                            WHERE session_id = $3
                        ''', current_time, expires_at, session_id)
                        
                        return 'UPDATE 1' in result
            except Exception as e:
                logger.error(f"Error updating session activity: {e}")
                span.record_exception(e)
                track_db_error("update_session_activity")
                return False
            
    async def create_session(self, user_id: str, ip_address: Optional[str] = None) -> Tuple[str, bool]:
        """
        Create a new session for a user
        
        Returns:
            Tuple of (session_id, is_new)
        """
        with optional_trace_span(self.tracer, "db_create_session") as span:
            span.set_attribute("user_id", user_id)
            span.set_attribute("ip_address", ip_address)

            if not self.pool:
                await self.connect()

            try:
                with TimedOperation(track_db_operation, "create_session"):
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
                            span.set_attribute("session_id", session_id)
                            span.set_attribute("is_new", False)
                            track_session_operation("reuse_existing")
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

                        span.set_attribute("session_id", session_id)
                        span.set_attribute("is_new", True)
                        track_session_operation("create")

                        # Update active session count
                        session_count = await self._get_active_session_count(conn)
                        track_session_count(session_count)

                        return session_id, True

            except Exception as e:
                logger.error(f"Error creating session: {e}")
                span.record_exception(e)
                track_db_error("create_session")
                raise

    async def get_active_session_count(self) -> int:
        """Get count of active sessions"""
        if not self.pool:
            await self.connect()

        try:
            async with self.pool.acquire() as conn:
                count = await conn.fetchval('''
                    SELECT COUNT(*) 
                    FROM session.active_sessions
                    WHERE expires_at > NOW()
                ''')
                return count or 0
        except Exception as e:
            logger.error(f"Error getting active session count: {e}")
            return 0

    async def get_active_simulator_count(self) -> int:
        """Get count of active simulators"""
        if not self.pool:
            await self.connect()

        try:
            async with self.pool.acquire() as conn:
                count = await conn.fetchval('''
                    SELECT COUNT(*) 
                    FROM simulator.instances
                    WHERE status NOT IN ($1, $2)
                ''', SimulatorStatus.STOPPED.value, SimulatorStatus.ERROR.value)
                return count or 0
        except Exception as e:
            logger.error(f"Error getting active simulator count: {e}")
            return 0

    async def _get_active_session_count(self, conn):
        """Helper to get active session count for metrics"""
        try:
            count = await conn.fetchval('''
                SELECT COUNT(*) FROM session.active_sessions
                WHERE expires_at > NOW()
            ''')
            return count or 0
        except Exception:
            return 0

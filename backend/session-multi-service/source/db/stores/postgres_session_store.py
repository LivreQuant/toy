# data_access/stores/postgres/postgres_session_store.py
"""
Handles PostgreSQL interactions for Session data.
"""
import logging
import json
import time
import uuid
import asyncpg
import asyncio
from typing import Dict, List, Any, Optional, Tuple

from opentelemetry import trace

from source.config import config
from source.models.session import Session, SessionStatus, SessionMetadata
from source.utils.metrics import track_db_operation, track_db_error, TimedOperation, track_cleanup_operation
from source.utils.tracing import optional_trace_span
from source.db.stores.postgres_base import PostgresRepository

logger = logging.getLogger('pg_session_store')


class PostgresSessionStore(PostgresRepository[Session]):
    """PostgreSQL store for session data."""

    def __init__(self, db_config=None):
        """Initialize PostgreSQL session store."""
        super().__init__(
            entity_class=Session,
            schema_name="session",
            table_name="active_sessions",
            id_field="session_id",
            tracer_name="postgres_session_store",
            db_config=db_config
        )
        logger.info("PostgresSessionStore initialized.")

    async def create_session(self, user_id: str, ip_address: Optional[str] = None) -> Tuple[str, bool]:
        """
        Create a new session or find an existing active one in PostgreSQL.
        Never reuses expired sessions.

        Returns:
            Tuple of (session_id, is_new)
        """
        with optional_trace_span(self.tracer, "pg_store_create_session") as span:
            span.set_attribute("user_id", user_id)
            if ip_address: span.set_attribute("ip_address", ip_address)

            pool = await self._get_pool()
            try:
                with TimedOperation(track_db_operation, "pg_create_session"):
                    async with pool.acquire() as conn:
                        # Check for existing ACTIVE session
                        active_session = await conn.fetchrow('''
                            SELECT session_id
                            FROM session.active_sessions
                            WHERE user_id = $1
                            AND status = $2
                            AND expires_at > NOW()
                            LIMIT 1
                        ''', user_id, SessionStatus.ACTIVE.value)

                        if active_session:
                            session_id = active_session['session_id']
                            logger.info(f"Found existing active session {session_id} for user {user_id}.")
                            # Update activity time for the existing session
                            await self.update_activity(session_id)
                            span.set_attribute("session_id", session_id)
                            span.set_attribute("is_new", False)
                            return session_id, False

                        # Create new session
                        session_id = str(uuid.uuid4())
                        current_time = time.time()
                        expires_at = current_time + config.session.timeout_seconds

                        logger.info(f"Creating new session {session_id} for user {user_id}.")
                        await conn.execute('''
                            INSERT INTO session.active_sessions
                            (session_id, user_id, status, created_at, last_active, expires_at)
                            VALUES ($1, $2, $3, to_timestamp($4), to_timestamp($5), to_timestamp($6))
                        ''',
                                           session_id,
                                           user_id,
                                           SessionStatus.ACTIVE.value,  # Start as ACTIVE
                                           current_time,
                                           current_time,
                                           expires_at
                                           )

                        # Initialize metadata
                        metadata = {
                            'pod_name': config.kubernetes.pod_name,
                            'ip_address': ip_address,
                            'user_agent': None,  # Can be updated later via update_metadata
                            'created_at': current_time,
                            'updated_at': current_time
                            # Ensure all required fields of SessionMetadata have defaults
                        }
                        # Filter metadata to only include keys defined in SessionMetadata model
                        valid_metadata = SessionMetadata(**metadata).dict(exclude_unset=True)

                        await conn.execute('''
                            INSERT INTO session.session_metadata
                            (session_id, metadata)
                            VALUES ($1, $2)
                        ''', session_id, json.dumps(valid_metadata))

                        span.set_attribute("session_id", session_id)
                        span.set_attribute("is_new", True)
                        return session_id, True

            except Exception as e:
                logger.error(f"Error creating session for user {user_id} in PostgreSQL: {e}", exc_info=True)
                span.record_exception(e)
                track_db_error("pg_create_session")
                raise  # Re-raise the exception to be handled by the manager

    async def get_session_from_db(self, session_id: str, skip_activity_check: bool = False) -> Optional[Session]:
        """
        Get a session by ID from PostgreSQL.

        Args:
            session_id: Session ID.
            skip_activity_check: If True, allows fetching sessions even if expired or not ACTIVE (used internally).

        Returns:
            Session or None if not found.
        """
        with optional_trace_span(self.tracer, "pg_store_get_session") as span:
            span.set_attribute("session_id", session_id)
            span.set_attribute("skip_activity_check", skip_activity_check)

            pool = await self._get_pool()
            try:
                with TimedOperation(track_db_operation, "pg_get_session"):
                    async with pool.acquire() as conn:
                        session_query = '''
                            SELECT * FROM session.active_sessions
                            WHERE session_id = $1
                        '''
                        params = [session_id]
                        if not skip_activity_check:
                            # Standard check for active sessions
                            session_query += ' AND status = $2 AND expires_at > NOW()'
                            params.append(SessionStatus.ACTIVE.value)

                        session_row = await conn.fetchrow(session_query, *params)

                        if not session_row:
                            logger.debug(f"Session {session_id} not found or not active in database.")
                            return None

                        metadata_row = await conn.fetchrow('''
                            SELECT metadata FROM session.session_metadata
                            WHERE session_id = $1
                        ''', session_id)

                        return self._create_session_from_rows(session_row, metadata_row)

            except Exception as e:
                logger.error(f"Error getting session {session_id} from PostgreSQL: {e}", exc_info=True)
                span.record_exception(e)
                track_db_error("pg_get_session")
                return None  # Return None on error

    def _row_to_entity(self, row: asyncpg.Record) -> Optional[Session]:
        """
        Override the base method to handle Session-specific conversion.
        
        Args:
            row: Database row from query
            
        Returns:
            Session object or None on error
        """
        try:
            # This is a simplified version - actual implementation would need
            # to join with session_metadata table or do a separate query
            session_data = {
                'session_id': row['session_id'],
                'user_id': row['user_id'],
                'status': SessionStatus(row['status']),
                'created_at': row['created_at'].timestamp(),
                'last_active': row['last_active'].timestamp(),
                'expires_at': row['expires_at'].timestamp(),
                'token': row.get('token')  # Assuming token column exists
            }
            
            # This is a placeholder - actual implementation would get metadata
            session_data['metadata'] = SessionMetadata()
            
            return Session(**session_data)
        except Exception as e:
            logger.error(f"Error converting row to Session: {e}")
            return None

    def _create_session_from_rows(self, session_row: asyncpg.Record, metadata_row: Optional[asyncpg.Record]) -> Session:
        """
        Create a Session object from database rows.
        
        Args:
            session_row: Row from active_sessions table
            metadata_row: Row from session_metadata table
            
        Returns:
            Session object
        """
        session_data = {
            'session_id': session_row['session_id'],
            'user_id': session_row['user_id'],
            'status': SessionStatus(session_row['status']),
            'created_at': session_row['created_at'].timestamp(),
            'last_active': session_row['last_active'].timestamp(),
            'expires_at': session_row['expires_at'].timestamp(),
            'token': session_row.get('token')  # Assuming token column exists
        }

        metadata_data = {}
        if metadata_row and metadata_row['metadata']:
            # metadata is stored as JSONB, asyncpg returns it as dict
            if isinstance(metadata_row['metadata'], dict):
                metadata_data = metadata_row['metadata']
            elif isinstance(metadata_row['metadata'], str):
                try:
                    metadata_data = json.loads(metadata_row['metadata'])
                except json.JSONDecodeError:
                    logger.error(f"Failed to decode metadata JSON for session {session_data['session_id']}")
                    metadata_data = {}  # Fallback to empty
            else:
                logger.warning(
                    f"Unexpected metadata type ({type(metadata_row['metadata'])}) for session {session_data['session_id']}")
                metadata_data = {}

        # Create SessionMetadata object and add to session data
        session_data['metadata'] = SessionMetadata(**metadata_data)
        return Session(**session_data)

    async def update_session_status(self, session_id: str, status: str) -> bool:
        """
        Update session status in PostgreSQL. Prevents EXPIRED -> ACTIVE.
        Enhanced version of the generic update_status method with business logic.
        """
        with optional_trace_span(self.tracer, "pg_store_update_session_status") as span:
            span.set_attribute("session_id", session_id)
            span.set_attribute("status", status)

            # Validate status enum
            try:
                target_status = SessionStatus(status)
            except ValueError:
                logger.error(f"Invalid status value '{status}' provided for session {session_id}.")
                return False

            pool = await self._get_pool()
            try:
                with TimedOperation(track_db_operation, "pg_update_session_status"):
                    async with pool.acquire() as conn:
                        async with conn.transaction():  # Use transaction for read-then-write
                            # Check current status
                            current_status_val = await conn.fetchval('''
                                   SELECT status FROM session.active_sessions
                                   WHERE session_id = $1 FOR UPDATE
                              ''', session_id)  # Lock row

                            if current_status_val is None:
                                logger.warning(f"Session {session_id} not found for status update.")
                                return False

                            # Prevent EXPIRED -> ACTIVE
                            if current_status_val == SessionStatus.EXPIRED.value and target_status == SessionStatus.ACTIVE:
                                logger.warning(
                                    f"Attempted to change EXPIRED session {session_id} back to ACTIVE. Denied.")
                                span.set_attribute("update_denied", "ExpiredToActive")
                                return False

                            # Perform update only if status is different
                            if current_status_val != target_status.value:
                                logger.info(
                                    f"Updating session {session_id} status from {current_status_val} to {target_status.value}")
                                result = await conn.execute('''
                                        UPDATE session.active_sessions
                                        SET status = $1
                                        WHERE session_id = $2
                                   ''', target_status.value, session_id)
                                updated = 'UPDATE 1' in result
                                span.set_attribute("updated", updated)
                                return updated
                            else:
                                logger.debug(
                                    f"Session {session_id} already has status {target_status.value}. No update needed.")
                                span.set_attribute("updated", False)
                                span.set_attribute("reason", "StatusUnchanged")
                                return True  # Indicate success as the state is already correct

            except Exception as e:
                logger.error(f"Error updating session status for {session_id} to {status} in PostgreSQL: {e}",
                             exc_info=True)
                span.record_exception(e)
                track_db_error("pg_update_session_status")
                return False

    async def update_session_metadata(self, session_id: str, metadata_updates: Dict[str, Any]) -> bool:
        """
        Update session metadata in PostgreSQL using JSONB merge.
        Wrapper around the generic update_json_metadata method.
        """
        return await self.update_json_metadata(session_id, metadata_updates)

    async def get_active_user_sessions(self, user_id: str) -> List[Session]:
        """
        Get truly active (status ACTIVE, not expired) sessions for a user from PostgreSQL.
        """
        with optional_trace_span(self.tracer, "pg_store_get_active_user_sessions") as span:
            span.set_attribute("user_id", user_id)
            
            # Use the get_with_criteria method but with custom query logic
            pool = await self._get_pool()
            sessions = []
            try:
                query = '''
                    SELECT s.*, m.metadata
                    FROM session.active_sessions s
                    LEFT JOIN session.session_metadata m ON s.session_id = m.session_id
                    WHERE s.user_id = $1
                    AND s.status = $2
                    AND s.expires_at > NOW()
                '''
                params = [user_id, SessionStatus.ACTIVE.value]
                span.set_attribute("db.statement", query)

                with TimedOperation(track_db_operation, "pg_get_active_user_sessions"):
                    async with pool.acquire() as conn:
                        rows = await conn.fetch(query, *params)
                        logger.info(f"Found {len(rows)} active sessions for user {user_id}.")
                        span.set_attribute("session_count", len(rows))

                        for row in rows:
                            try:
                                # Get metadata from the joined query
                                metadata_data = row['metadata'] if row['metadata'] else {}
                                
                                # Create session with metadata
                                session_data = {
                                    'session_id': row['session_id'],
                                    'user_id': row['user_id'],
                                    'status': SessionStatus(row['status']),
                                    'created_at': row['created_at'].timestamp(),
                                    'last_active': row['last_active'].timestamp(),
                                    'expires_at': row['expires_at'].timestamp(),
                                    'token': row.get('token'),
                                    'metadata': SessionMetadata(**metadata_data)
                                }
                                sessions.append(Session(**session_data))
                            except Exception as e:
                                logger.error(f"Error processing session row: {e}", exc_info=True)

                        return sessions

            except Exception as e:
                logger.error(f"Error getting active sessions for user {user_id} from PostgreSQL: {e}", exc_info=True)
                span.record_exception(e)
                track_db_error("pg_get_active_user_sessions")
                return []

    async def get_active_session_count(self) -> int:
        """Get count of active (status ACTIVE, not expired) sessions from PostgreSQL."""
        with optional_trace_span(self.tracer, "pg_store_get_active_session_count"):
            pool = await self._get_pool()
            try:
                query = '''
                     SELECT COUNT(*)
                     FROM session.active_sessions
                     WHERE status = $1 AND expires_at > NOW()
                 '''
                async with pool.acquire() as conn:
                    count = await conn.fetchval(query, SessionStatus.ACTIVE.value)
                    logger.debug(f"Active session count: {count or 0}")
                    return count or 0
            except Exception as e:
                logger.error(f"Error getting active session count from PostgreSQL: {e}", exc_info=True)

                
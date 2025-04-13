# data_access/stores/postgres/postgres_session_store.py
"""
Handles PostgreSQL interactions for Session data.
"""
import logging
import json
import time
import asyncpg
from typing import Dict, Any, Optional

from source.config import config
from source.models.session import Session, SessionStatus, SessionMetadata
from source.utils.metrics import track_db_operation, track_db_error, TimedOperation
from source.utils.tracing import optional_trace_span
from source.db.stores.postgres_base import PostgresRepository

logger = logging.getLogger('pg_session_store')


def _create_session_from_rows(session_row: asyncpg.Record, metadata_row: Optional[asyncpg.Record]) -> Session:
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

    async def create_session(self, session_id: str, user_id: str, device_id: Optional[str] = None, ip_address: Optional[str] = None) -> bool:
        """
        Create a new session with a specific ID (for singleton mode).

        Args:
            session_id: The session ID to use
            user_id: The user ID to associate with this session
            device_id: Optional device ID for metadata
            ip_address: Optional IP address for metadata

        Returns:
            bool: True if session was created successfully
        """
        with optional_trace_span(self.tracer, "pg_store_create_session_with_id") as span:
            span.set_attribute("session_id", session_id)
            span.set_attribute("user_id", user_id)
            if device_id: span.set_attribute("device_id", device_id)
            if ip_address: span.set_attribute("ip_address", ip_address)

            pool = await self._get_pool()
            try:
                with TimedOperation(track_db_operation, "pg_create_session_with_id"):
                    async with pool.acquire() as conn:
                        # Check if session already exists
                        existing_session = await conn.fetchrow('''
                            SELECT session_id
                            FROM session.active_sessions
                            WHERE session_id = $1
                            LIMIT 1
                        ''', session_id)

                        if existing_session:
                            logger.info(f"Session with ID {session_id} already exists, updating activity.")
                            # Update activity time for the existing session
                            await self.update_activity(session_id)
                            return True

                        # Create new session with the provided ID
                        current_time = time.time()
                        expires_at = current_time + config.session.timeout_seconds

                        logger.info(f"Creating new session with ID {session_id} for user {user_id}.")
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
                            'device_id': device_id,
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

                        return True

            except Exception as e:
                logger.error(f"Error creating session with ID {session_id} for user {user_id} in PostgreSQL: {e}", exc_info=True)
                span.record_exception(e)
                track_db_error("pg_create_session_with_id")
                return False

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

                        return _create_session_from_rows(session_row, metadata_row)

            except Exception as e:
                logger.error(f"Error getting session {session_id} from PostgreSQL: {e}", exc_info=True)
                span.record_exception(e)
                track_db_error("pg_get_session")
                return None

    async def update_session_metadata(self, session_id: str, metadata_updates: Dict[str, Any]) -> bool:
        """
        Update session metadata in PostgreSQL using JSONB merge.
        Wrapper around the generic update_json_metadata method.
        """
        return await self.update_json_metadata(session_id, metadata_updates)

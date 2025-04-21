# data_access/stores/postgres/postgres_session_store.py
"""
Handles PostgreSQL interactions for Session data with proper table structure.
"""
import logging
import time
from enum import Enum

import asyncpg
from typing import Dict, Any, Optional, List

from source.config import config
from source.models.session import Session, SessionDetails, SessionWithDetails, SessionStatus, ConnectionQuality
from source.utils.metrics import track_db_operation, track_db_error, TimedOperation
from source.utils.tracing import optional_trace_span
from source.db.stores.postgres_base import PostgresRepository

logger = logging.getLogger('pg_session_store')


class PostgresSessionStore(PostgresRepository[Session]):
    """PostgreSQL store for session data with separate details table."""

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

    async def create_session(self, session_id: str, user_id: str, device_id: Optional[str] = None,
                             ip_address: Optional[str] = None) -> bool:
        """
        Create a new session with a specific ID (for singleton mode).

        Args:
            session_id: The session ID to use
            user_id: The user ID to associate with this session
            device_id: Optional device ID for details
            ip_address: Optional IP address for details

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
                        # Start a transaction
                        async with conn.transaction():
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
                                await self.update_session_activity(session_id)
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

                            # Insert session details
                            await conn.execute('''
                                INSERT INTO session.session_details
                                (session_id, device_id, ip_address, pod_name, created_at, updated_at)
                                VALUES ($1, $2, $3, $4, to_timestamp($5), to_timestamp($6))
                            ''',
                                               session_id,
                                               device_id,
                                               ip_address,
                                               config.kubernetes.pod_name,
                                               current_time,
                                               current_time
                                               )

                        return True

            except Exception as e:
                logger.error(f"Error creating session with ID {session_id} for user {user_id} in PostgreSQL: {e}",
                             exc_info=True)
                span.record_exception(e)
                track_db_error("pg_create_session_with_id")
                return False

    async def get_session_from_db(self, session_id: str, skip_activity_check: bool = False) -> Optional[
        SessionWithDetails]:
        """
        Get a session by ID from PostgreSQL with details.

        Args:
            session_id: Session ID.
            skip_activity_check: If True, allows fetching sessions even if expired or not ACTIVE (used internally).

        Returns:
            SessionWithDetails or None if not found.
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

                        # Get session details from the details table
                        details_row = await conn.fetchrow('''
                            SELECT * FROM session.session_details
                            WHERE session_id = $1
                        ''', session_id)

                        if not details_row:
                            logger.warning(f"Session details not found for session {session_id}.")
                            # Create a basic session with default details
                            return await self._create_session_with_default_details(session_row)

                        return self._create_session_with_details(session_row, details_row)

            except Exception as e:
                logger.error(f"Error getting session {session_id} from PostgreSQL: {e}", exc_info=True)
                span.record_exception(e)
                track_db_error("pg_get_session")
                return None

    async def update_session_details(self, session_id: str, details_updates: Dict[str, Any]) -> bool:
        """
        Update session details in PostgreSQL.

        Args:
            session_id: Session ID
            details_updates: Dictionary of details fields to update

        Returns:
            True if update successful, False otherwise
        """
        with optional_trace_span(self.tracer, "pg_store_update_session_details") as span:
            span.set_attribute("session_id", session_id)

            pool = await self._get_pool()
            try:
                with TimedOperation(track_db_operation, "pg_update_session_details"):
                    async with pool.acquire() as conn:
                        # Check if record exists
                        existing = await conn.fetchrow('''
                            SELECT 1 FROM session.session_details
                            WHERE session_id = $1
                        ''', session_id)

                        # Prepare field updates
                        fields = []
                        values = [session_id]  # First parameter is always session_id
                        param_idx = 2  # Start parameter indexing at 2

                        # Add updated_at timestamp
                        fields.append(f"updated_at = to_timestamp($%d)" % param_idx)
                        values.append(time.time())
                        param_idx += 1

                        # Add each field to update
                        for key, value in details_updates.items():
                            # Skip null values unless explicitly setting to null
                            if value is None and key not in details_updates:
                                continue

                            # Convert enum values to strings
                            if isinstance(value, Enum):
                                value = value.value

                            fields.append(f"{key} = ${param_idx}")
                            values.append(value)
                            param_idx += 1

                        if not fields:
                            logger.debug(f"No fields to update for session {session_id}")
                            return True  # No fields to update is still a success

                        # Build and execute query
                        if existing:
                            # Update existing record
                            query = f'''
                                UPDATE session.session_details
                                SET {', '.join(fields)}
                                WHERE session_id = $1
                            '''
                            result = await conn.execute(query, *values)
                            return 'UPDATE 1' in result
                        else:
                            # Insert new record with defaults for missing fields
                            fields_list = ["session_id"]
                            values_placeholders = ["$1"]

                            # Add each field being set
                            field_idx = 2
                            for key in details_updates.keys():
                                fields_list.append(key)
                                values_placeholders.append(f"${field_idx}")
                                field_idx += 1

                            query = f'''
                                INSERT INTO session.session_details
                                ({', '.join(fields_list)})
                                VALUES ({', '.join(values_placeholders)})
                            '''
                            result = await conn.execute(query, *values[0:len(fields_list)])
                            return 'INSERT' in result

            except Exception as e:
                logger.error(f"Error updating session details for {session_id} in PostgreSQL: {e}", exc_info=True)
                span.record_exception(e)
                track_db_error("pg_update_session_details")
                return False

    async def update_session_activity(self, session_id: str) -> bool:
        """
        Update the last_active timestamp for a session.

        Args:
            session_id: The session ID to update

        Returns:
            True if update successful, False otherwise
        """
        with optional_trace_span(self.tracer, "pg_store_update_session_activity") as span:
            span.set_attribute("session_id", session_id)

            pool = await self._get_pool()
            try:
                with TimedOperation(track_db_operation, "pg_update_session_activity"):
                    async with pool.acquire() as conn:
                        # Update last_active timestamp to current time
                        result = await conn.execute('''
                            UPDATE session.active_sessions
                            SET last_active = NOW(), expires_at = NOW() + interval '1 hour'
                            WHERE session_id = $1
                        ''', session_id)

                        return 'UPDATE 1' in result

            except Exception as e:
                logger.error(f"Error updating session activity for {session_id} in PostgreSQL: {e}", exc_info=True)
                span.record_exception(e)
                track_db_error("pg_update_session_activity")
                return False

    async def find_user_active_sessions(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Find active sessions for a specific user.

        Args:
            user_id: The user ID to search for

        Returns:
            List of session records
        """
        with optional_trace_span(self.tracer, "pg_store_find_user_active_sessions") as span:
            span.set_attribute("user_id", user_id)

            pool = await self._get_pool()
            try:
                with TimedOperation(track_db_operation, "pg_find_user_active_sessions"):
                    async with pool.acquire() as conn:
                        # Find active sessions for this user
                        rows = await conn.fetch('''
                            SELECT session_id, user_id, status, created_at, last_active, expires_at
                            FROM session.active_sessions
                            WHERE user_id = $1
                            AND status = $2
                            AND expires_at > NOW()
                        ''', user_id, SessionStatus.ACTIVE.value)

                        # Convert to list of dictionaries
                        sessions = []
                        for row in rows:
                            sessions.append({
                                'session_id': row['session_id'],
                                'user_id': row['user_id'],
                                'status': row['status'],
                                'created_at': row['created_at'].timestamp() if row['created_at'] else None,
                                'last_active': row['last_active'].timestamp() if row['last_active'] else None,
                                'expires_at': row['expires_at'].timestamp() if row['expires_at'] else None
                            })

                        return sessions
            except Exception as e:
                logger.error(f"Error finding active sessions for user {user_id} in PostgreSQL: {e}", exc_info=True)
                span.record_exception(e)
                track_db_error("pg_find_user_active_sessions")
                return []

    async def update_session_status(self, session_id: str, status: SessionStatus) -> bool:
        """
        Update the status of a session.

        Args:
            session_id: The session ID to update
            status: The new status

        Returns:
            True if update successful, False otherwise
        """
        with optional_trace_span(self.tracer, "pg_store_update_session_status") as span:
            span.set_attribute("session_id", session_id)
            span.set_attribute("status", status.value)

            pool = await self._get_pool()
            try:
                with TimedOperation(track_db_operation, "pg_update_session_status"):
                    async with pool.acquire() as conn:
                        result = await conn.execute('''
                            UPDATE session.active_sessions
                            SET status = $2, last_active = NOW()
                            WHERE session_id = $1
                        ''', session_id, status.value)

                        return 'UPDATE 1' in result

            except Exception as e:
                logger.error(f"Error updating session status for {session_id} in PostgreSQL: {e}", exc_info=True)
                span.record_exception(e)
                track_db_error("pg_update_session_status")
                return False

    def _create_session_with_details(self,
                                     session_row: asyncpg.Record,
                                     details_row: asyncpg.Record) -> SessionWithDetails:
        """
        Create a SessionWithDetails object from database rows.

        Args:
            session_row: Row from active_sessions table
            details_row: Row from session_details table

        Returns:
            SessionWithDetails object
        """
        # Create the core Session object
        session = Session(
            session_id=session_row['session_id'],
            user_id=session_row['user_id'],
            status=SessionStatus(session_row['status']),
            created_at=session_row['created_at'].timestamp(),
            last_active=session_row['last_active'].timestamp(),
            expires_at=session_row['expires_at'].timestamp(),
        )

        # Create the SessionDetails object
        connection_quality = details_row.get('connection_quality')
        if connection_quality:
            try:
                connection_quality = ConnectionQuality(connection_quality)
            except ValueError:
                connection_quality = ConnectionQuality.GOOD
        else:
            connection_quality = ConnectionQuality.GOOD

        details = SessionDetails(
            # Device and connection information
            device_id=details_row.get('device_id'),
            user_agent=details_row.get('user_agent'),
            ip_address=details_row.get('ip_address'),
            pod_name=details_row.get('pod_name'),

            # Connection quality metrics
            connection_quality=connection_quality,
            heartbeat_latency=details_row.get('heartbeat_latency'),
            missed_heartbeats=details_row.get('missed_heartbeats', 0),
            reconnect_count=details_row.get('reconnect_count', 0),

            # Timestamps
            last_reconnect=details_row['last_reconnect'].timestamp() if details_row.get('last_reconnect') else None,
            last_device_update=details_row['last_device_update'].timestamp() if details_row.get(
                'last_device_update') else None,
            last_quality_update=details_row['last_quality_update'].timestamp() if details_row.get(
                'last_quality_update') else None
        )

        # Return combined object
        return SessionWithDetails(session=session, details=details)

    async def _create_session_with_default_details(self, session_row: asyncpg.Record) -> SessionWithDetails:
        """
        Create a SessionWithDetails with default details when none are found.

        Args:
            session_row: Row from active_sessions table

        Returns:
            SessionWithDetails object
        """
        # Create the core Session object
        session = Session(
            session_id=session_row['session_id'],
            user_id=session_row['user_id'],
            status=SessionStatus(session_row['status']),
            created_at=session_row['created_at'].timestamp(),
            last_active=session_row['last_active'].timestamp(),
            expires_at=session_row['expires_at'].timestamp(),
        )

        # Create default details
        details = SessionDetails(
            pod_name=config.kubernetes.pod_name,
            created_at=session.created_at,
            updated_at=session.last_active
        )

        # Try to create the missing details record
        try:
            pool = await self._get_pool()
            async with pool.acquire() as conn:
                await conn.execute('''
                    INSERT INTO session.session_details
                    (session_id, pod_name, created_at, updated_at)
                    VALUES ($1, $2, to_timestamp($3), to_timestamp($4))
                    ON CONFLICT (session_id) DO NOTHING
                ''',
                                   session.session_id,
                                   config.kubernetes.pod_name,
                                   session.created_at,
                                   session.last_active
                                   )
        except Exception as e:
            logger.warning(f"Failed to create missing session details for {session.session_id}: {e}")

        # Return combined object
        return SessionWithDetails(session=session, details=details)

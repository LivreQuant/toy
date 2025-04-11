# data_access/stores/postgres/postgres_session_store.py
"""
Handles PostgreSQL interactions for Session data.
"""
import logging
import asyncio
import json
import time
import uuid
import asyncpg
from typing import Dict, List, Any, Optional, Tuple

from opentelemetry import trace

from source.config import config
from source.models.session import Session, SessionStatus, SessionMetadata
from source.utils.metrics import track_db_operation, track_db_error, TimedOperation
from source.utils.tracing import optional_trace_span

logger = logging.getLogger('pg_session_store')


class PostgresSessionStore:
    """PostgreSQL store for session data."""

    def __init__(self):
        """Initialize PostgreSQL session store."""
        self.pool: Optional[asyncpg.Pool] = None
        self.db_config = config.db
        self._conn_lock = asyncio.Lock()
        self.tracer = trace.get_tracer("postgres_session_store")
        logger.info("PostgresSessionStore initialized.")

    # --- Connection Management (Duplicated from original for now) ---
    async def connect(self):
        """Connect to the PostgreSQL database."""
        # Reusing connect logic from original PostgresStore
        with optional_trace_span(self.tracer, "pg_session_connect") as span:
            span.set_attribute("db.system", "postgresql")
            span.set_attribute("db.name", self.db_config.database)
            # Add other attributes as needed

            async with self._conn_lock:
                if self.pool is not None:
                    logger.debug("PostgreSQL connection pool already exists.")
                    return

                max_retries = 5
                retry_count = 0
                retry_delay = 1.0
                logger.info(
                    f"Attempting to connect to PostgreSQL at {self.db_config.host}:{self.db_config.port} DB: {self.db_config.database}")

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
                        logger.info("Successfully connected to PostgreSQL database.")
                        span.set_attribute("success", True)
                        return
                    except Exception as e:
                        retry_count += 1
                        logger.error(f"PostgreSQL connection error (attempt {retry_count}/{max_retries}): {e}",
                                     exc_info=True)
                        span.record_exception(e)
                        span.set_attribute("retry_count", retry_count)

                        if retry_count < max_retries:
                            await asyncio.sleep(retry_delay)
                            retry_delay *= 2
                        else:
                            logger.error("Maximum PostgreSQL connection retries reached.")
                            span.set_attribute("success", False)
                            track_db_error("pg_session_connect")
                            raise ConnectionError("Failed to connect to PostgreSQL after multiple retries.") from e

    async def close(self):
        """Close PostgreSQL database connections."""
        # Reusing close logic from original PostgresStore
        async with self._conn_lock:
            if self.pool:
                logger.info("Closing PostgreSQL database connection pool...")
                await self.pool.close()
                self.pool = None
                logger.info("Closed PostgreSQL database connection pool.")
            else:
                logger.info("PostgreSQL connection pool already closed.")

    async def check_connection(self) -> bool:
        """Check PostgreSQL database connection health."""
        # Reusing check_connection logic from original PostgresStore
        if not self.pool:
            logger.warning("Checking connection status: Pool does not exist.")
            # Optionally try to connect here if desired behavior
            # try:
            #     await self.connect()
            #     return self.pool is not None
            # except:
            #     return False
            return False

        try:
            async with self.pool.acquire() as conn:
                # Use a timeout for the query
                result = await asyncio.wait_for(conn.fetchval("SELECT 1"), timeout=5.0)
                is_healthy = (result == 1)
                logger.debug(f"PostgreSQL connection check result: {is_healthy}")
                return is_healthy
        except (asyncio.TimeoutError, Exception) as e:
            logger.error(f"PostgreSQL connection check failed: {e}", exc_info=True)
            # Attempt to close the potentially broken pool? Or just report failure.
            # await self.close() # Consider implications
            # self.pool = None
            return False

    async def _get_pool(self) -> asyncpg.Pool:
        """Internal helper to get the pool, ensuring it's connected."""
        if self.pool is None:
            # If called before connect, try connecting.
            logger.warning("Accessing pool before explicit connect(). Attempting connection...")
            await self.connect()
        if self.pool is None:  # Check again after trying to connect
            raise ConnectionError("PostgreSQL pool is not initialized.")
        return self.pool

    # --- Session Specific Methods ---

    async def create_session(self, user_id: str, ip_address: Optional[str] = None) -> Tuple[str, bool]:
        """
        Create a new session or find an existing active one in PostgreSQL.
        Never reuses expired sessions.

        Returns:
            Tuple of (session_id, is_new)
        """
        # Logic from original PostgresStore.create_session
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
                            await self._update_session_activity_internal(conn, session_id)
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
        # Logic from original PostgresStore.get_session_from_db
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
                                    logger.error(f"Failed to decode metadata JSON for session {session_id}")
                                    metadata_data = {}  # Fallback to empty
                            else:
                                logger.warning(
                                    f"Unexpected metadata type ({type(metadata_row['metadata'])}) for session {session_id}")
                                metadata_data = {}

                        # Merge session data with metadata using Session.from_dict logic if available
                        # Or manually construct:
                        session_data['metadata'] = SessionMetadata(**metadata_data)
                        session = Session(**session_data)

                        logger.debug(f"Successfully fetched session {session_id} from database.")
                        return session

            except Exception as e:
                logger.error(f"Error getting session {session_id} from PostgreSQL: {e}", exc_info=True)
                span.record_exception(e)
                track_db_error("pg_get_session")
                return None  # Return None on error

    async def _update_session_activity_internal(self, conn: asyncpg.Connection, session_id: str) -> bool:
        """Internal helper to update activity time using an existing connection."""
        try:
            current_time = time.time()
            expires_at = current_time + config.session.timeout_seconds
            # Only update ACTIVE sessions
            result = await conn.execute('''
                 UPDATE session.active_sessions
                 SET last_active = to_timestamp($1), expires_at = to_timestamp($2)
                 WHERE session_id = $3 AND status = $4
             ''', current_time, expires_at, session_id, SessionStatus.ACTIVE.value)
            updated = 'UPDATE 1' in result
            if updated:
                logger.debug(f"Updated activity for session {session_id}")
            else:
                logger.debug(f"Session {session_id} not found or not active, activity not updated.")
            return updated
        except Exception as e:
            logger.error(f"Internal error updating session activity for {session_id}: {e}", exc_info=True)
            # Don't track db_error here as it's internal
            return False

    async def update_session_activity(self, session_id: str) -> bool:
        """
        Update the last_active and expires_at time for an ACTIVE session in PostgreSQL.
        """
        # Logic from original PostgresStore.update_session_activity
        with optional_trace_span(self.tracer, "pg_store_update_session_activity") as span:
            span.set_attribute("session_id", session_id)

            pool = await self._get_pool()
            try:
                with TimedOperation(track_db_operation, "pg_update_session_activity"):
                    async with pool.acquire() as conn:
                        return await self._update_session_activity_internal(conn, session_id)
            except Exception as e:
                # Log error from acquiring connection or the operation itself
                logger.error(f"Error updating session activity for {session_id} in PostgreSQL: {e}", exc_info=True)
                span.record_exception(e)
                track_db_error("pg_update_session_activity")
                return False

    async def update_session_status(self, session_id: str, status: str) -> bool:
        """
        Update session status in PostgreSQL. Prevents EXPIRED -> ACTIVE.
        """
        # Logic from original PostgresStore.update_session_status
        with optional_trace_span(self.tracer, "pg_store_update_session_status") as span:
            span.set_attribute("session_id", session_id)
            span.set_attribute("status", status)

            pool = await self._get_pool()
            try:
                # Validate status enum
                try:
                    target_status = SessionStatus(status)
                except ValueError:
                    logger.error(f"Invalid status value '{status}' provided for session {session_id}.")
                    return False

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

                            # Prevent changing from other terminal states if needed
                            # if current_status_val in [SessionStatus.ERROR.value] and target_status == SessionStatus.ACTIVE:
                            #     logger.warning(f"Attempted to change {current_status_val} session {session_id} back to ACTIVE. Denied.")
                            #     return False

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
        """
        # Logic from original PostgresStore.update_session_metadata
        with optional_trace_span(self.tracer, "pg_store_update_session_metadata") as span:
            span.set_attribute("session_id", session_id)

            pool = await self._get_pool()
            try:
                with TimedOperation(track_db_operation, "pg_update_session_metadata"):
                    async with pool.acquire() as conn:
                        # Add updated_at timestamp
                        metadata_updates['updated_at'] = time.time()

                        # Use JSONB concatenation for merging
                        # Ensure updates are valid according to SessionMetadata model before merging
                        # This validation should ideally happen in the manager or service layer
                        update_json = json.dumps(metadata_updates)

                        logger.info(f"Updating metadata for session {session_id} with JSON: {update_json}")

                        # UPSERT logic: Insert if not exists, update if exists
                        # `metadata || $2::jsonb` merges the existing JSONB with the new one
                        result = await conn.execute('''
                            INSERT INTO session.session_metadata (session_id, metadata)
                            VALUES ($1, $2::jsonb)
                            ON CONFLICT (session_id)
                            DO UPDATE SET metadata = session.session_metadata.metadata || $2::jsonb
                        ''', session_id, update_json)

                        updated = 'INSERT 1' in result or 'UPDATE 1' in result
                        span.set_attribute("updated", updated)
                        if updated:
                            logger.info(f"Successfully updated metadata for session {session_id}")
                        else:
                            # This case should ideally not happen with UPSERT unless there's an issue
                            logger.warning(
                                f"Metadata update command for session {session_id} did not return expected result: {result}")
                        return updated

            except Exception as e:
                logger.error(f"Error updating session metadata for {session_id} in PostgreSQL: {e}", exc_info=True)
                span.record_exception(e)
                track_db_error("pg_update_session_metadata")
                return False

    async def get_sessions_with_criteria(self, criteria: Dict[str, Any]) -> List[Session]:
        """
        Get sessions matching specified criteria from PostgreSQL.
        """
        # Logic from original PostgresStore.get_sessions_with_criteria
        with optional_trace_span(self.tracer, "pg_store_get_sessions_with_criteria") as span:
            pool = await self._get_pool()
            sessions = []
            try:
                # Base query
                query_parts = [
                    "SELECT s.*, m.metadata FROM session.active_sessions s LEFT JOIN session.session_metadata m ON s.session_id = m.session_id"]
                conditions = []
                params = []
                param_idx = 1

                logger.info(f"Getting sessions with criteria: {criteria}")
                span.set_attribute("criteria", json.dumps(criteria))

                # Build conditions (ensure keys match metadata structure or session fields)
                if 'pod_name' in criteria:
                    conditions.append(f"m.metadata->>'pod_name' = ${param_idx}")
                    params.append(criteria['pod_name'])
                    param_idx += 1
                if 'status' in criteria:
                    conditions.append(f"s.status = ${param_idx}")
                    params.append(criteria['status'])
                    param_idx += 1
                if 'user_id' in criteria:
                    conditions.append(f"s.user_id = ${param_idx}")
                    params.append(criteria['user_id'])
                    param_idx += 1
                if 'last_active_before' in criteria:
                    # Assuming criteria['last_active_before'] is a timestamp float
                    conditions.append(f"s.last_active < to_timestamp(${param_idx})")
                    params.append(criteria['last_active_before'])
                    param_idx += 1
                if 'expires_before' in criteria:  # Example: Find sessions that will expire soon
                    conditions.append(f"s.expires_at < to_timestamp(${param_idx})")
                    params.append(criteria['expires_before'])
                    param_idx += 1

                if conditions:
                    query_parts.append("WHERE " + " AND ".join(conditions))

                final_query = " ".join(query_parts)
                logger.debug(f"Executing query for sessions with criteria: {final_query} PARAMS: {params}")
                span.set_attribute("db.statement", final_query)

                with TimedOperation(track_db_operation, "pg_get_sessions_with_criteria"):
                    async with pool.acquire() as conn:
                        rows = await conn.fetch(final_query, *params)

                        logger.info(f"Query returned {len(rows)} sessions matching criteria.")
                        span.set_attribute("result_count", len(rows))

                        for row in rows:
                            try:
                                session_data = {
                                    'session_id': row['session_id'], 'user_id': row['user_id'],
                                    'status': SessionStatus(row['status']),
                                    'created_at': row['created_at'].timestamp(),
                                    'last_active': row['last_active'].timestamp(),
                                    'expires_at': row['expires_at'].timestamp(),
                                    'token': row.get('token')
                                }
                                metadata_data = row['metadata'] if row['metadata'] else {}
                                if isinstance(metadata_data, str): metadata_data = json.loads(metadata_data)

                                session_data['metadata'] = SessionMetadata(**metadata_data)
                                sessions.append(Session(**session_data))
                            except (TypeError, ValueError, KeyError, json.JSONDecodeError) as validation_error:
                                logger.error(
                                    f"Failed to parse session data for session_id {row.get('session_id')}: {validation_error}",
                                    exc_info=True)
                                # Skip this session or handle error as appropriate
                        return sessions

            except Exception as e:
                logger.error(f"Error getting sessions with criteria {criteria} from PostgreSQL: {e}", exc_info=True)
                span.record_exception(e)
                track_db_error("pg_get_sessions_with_criteria")
                return []  # Return empty list on error

    async def get_active_user_sessions(self, user_id: str) -> List[Session]:
        """
        Get truly active (status ACTIVE, not expired) sessions for a user from PostgreSQL.
        """
        # Logic from original PostgresStore.get_active_user_sessions
        with optional_trace_span(self.tracer, "pg_store_get_active_user_sessions") as span:
            span.set_attribute("user_id", user_id)
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
                                # Similar parsing as get_sessions_with_criteria
                                session_data = {
                                    'session_id': row['session_id'], 'user_id': row['user_id'],
                                    'status': SessionStatus(row['status']),
                                    'created_at': row['created_at'].timestamp(),
                                    'last_active': row['last_active'].timestamp(),
                                    'expires_at': row['expires_at'].timestamp(),
                                    'token': row.get('token')
                                }
                                metadata_data = row['metadata'] if row['metadata'] else {}
                                if isinstance(metadata_data, str): metadata_data = json.loads(metadata_data)

                                session_data['metadata'] = SessionMetadata(**metadata_data)
                                sessions.append(Session(**session_data))
                            except (TypeError, ValueError, KeyError, json.JSONDecodeError) as validation_error:
                                logger.error(
                                    f"Failed to parse active session data for session_id {row.get('session_id')}: {validation_error}",
                                    exc_info=True)

                        return sessions

            except Exception as e:
                logger.error(f"Error getting active sessions for user {user_id} from PostgreSQL: {e}", exc_info=True)
                span.record_exception(e)
                track_db_error("pg_get_active_user_sessions")
                return []

    async def get_active_session_count(self) -> int:
        """Get count of active (status ACTIVE, not expired) sessions from PostgreSQL."""
        # Logic from original PostgresStore.get_active_session_count
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
                track_db_error("pg_get_active_session_count")
                return 0

    async def cleanup_expired_sessions(self) -> int:
        """
        Calls the database function `session.cleanup_expired_sessions()`
        which should handle moving expired sessions or deleting them.

        Returns:
            Number of sessions processed/deleted by the function.
        """
        # Logic from original PostgresStore.cleanup_expired_sessions
        with optional_trace_span(self.tracer, "pg_store_cleanup_expired_sessions") as span:
            pool = await self._get_pool()
            deleted_count = 0
            try:
                # Ensure the function exists in your DB schema:
                # CREATE OR REPLACE FUNCTION session.cleanup_expired_sessions()
                # RETURNS integer AS $$
                # DECLARE
                #   deleted_count integer;
                # BEGIN
                #   -- Example: Delete directly (Adjust logic as needed, e.g., move to history table)
                #   WITH deleted AS (
                #     DELETE FROM session.active_sessions
                #     WHERE expires_at <= NOW()
                #     RETURNING session_id
                #   )
                #   SELECT count(*) INTO deleted_count FROM deleted;
                #
                #   -- Also clean up associated metadata (important!)
                #   DELETE FROM session.session_metadata
                #   WHERE session_id IN (SELECT session_id FROM deleted); -- Requires deleted CTE above
                #   -- Or, if not deleting directly from active_sessions:
                #   -- DELETE FROM session.session_metadata
                #   -- WHERE session_id IN (SELECT session_id FROM session.active_sessions WHERE expires_at <= NOW());
                #
                #   RETURN deleted_count;
                # END;
                # $$ LANGUAGE plpgsql;

                # Call the function
                logger.info("Calling database function session.cleanup_expired_sessions()...")
                async with pool.acquire() as conn:
                    # Set a statement timeout for the cleanup function
                    await conn.execute("SET statement_timeout = '120s';")  # 2 minutes timeout
                    result = await conn.fetchval("SELECT session.cleanup_expired_sessions()")
                    await conn.execute("RESET statement_timeout;")  # Reset timeout
                deleted_count = result if isinstance(result, int) else 0
                logger.info(f"Database function cleaned up {deleted_count} expired sessions.")
                span.set_attribute("deleted_count", deleted_count)
                # Optionally track cleanup operation metric
                # track_cleanup_operation("pg_sessions", deleted_count)
                return deleted_count
            except asyncpg.exceptions.UndefinedFunctionError:
                logger.error("Database function 'session.cleanup_expired_sessions()' not found. Please create it.",
                             exc_info=True)
                span.record_exception(asyncpg.exceptions.UndefinedFunctionError("Function not found"))
                track_db_error("pg_cleanup_expired_sessions_func_missing")
                return 0  # Return 0 as nothing was done
            except Exception as e:
                logger.error(f"Error calling cleanup_expired_sessions function in PostgreSQL: {e}", exc_info=True)
                span.record_exception(e)
                track_db_error("pg_cleanup_expired_sessions")
                return 0  # Return 0 on error

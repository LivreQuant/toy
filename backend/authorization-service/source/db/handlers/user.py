# source/db/user_db.py
import logging

from source.utils.tracing import optional_trace_span
from source.db.base_manager import BaseDatabaseManager

logger = logging.getLogger('user_db')


async def _create_default_profile(conn, user_id):
    """Create default user profile (internal method)"""
    query = """
        INSERT INTO auth.user_profiles (user_id)
        VALUES ($1)
    """
    await conn.execute(query, user_id)


class UserDatabaseManager(BaseDatabaseManager):
    async def get_user_by_username(self, username):
        """Get user by username"""
        with optional_trace_span(self.tracer, "db_get_user_by_username") as span:
            span.set_attribute("username", username)
            
            if not self.pool:
                await self.connect()

            query = """
                SELECT id, username, password_hash, is_active, user_role, email, email_verified, 
                       first_name, last_name, created_at, last_login
                FROM auth.users
                WHERE username = $1
            """
            span.set_attribute("db.statement", query)

            async with self.pool.acquire() as conn:
                row = await conn.fetchrow(query, username)
                result = dict(row) if row else None
                span.set_attribute("success", result is not None)
                span.set_attribute("user_found", result is not None)
                return result

    async def get_user_by_id(self, user_id):
        """Get user by ID"""
        with optional_trace_span(self.tracer, "db_get_user_by_id") as span:
            span.set_attribute("user_id", str(user_id))
            
            if not self.pool:
                await self.connect()

            query = """
                SELECT id, username, email, first_name, last_name, is_active, user_role, 
                       email_verified, created_at, last_login
                FROM auth.users
                WHERE id = $1
            """
            span.set_attribute("db.statement", query)

            async with self.pool.acquire() as conn:
                row = await conn.fetchrow(query, user_id)
                result = dict(row) if row else None
                span.set_attribute("success", result is not None)
                span.set_attribute("user_found", result is not None)
                return result

    async def get_user_by_email(self, email):
        """Get user by email"""
        with optional_trace_span(self.tracer, "db_get_user_by_email") as span:
            span.set_attribute("email", email)
            
            if not self.pool:
                await self.connect()

            query = """
                SELECT id, username, email, is_active, email_verified, user_role
                FROM auth.users
                WHERE email = $1
            """
            span.set_attribute("db.statement", query)

            try:
                async with self.pool.acquire() as conn:
                    row = await conn.fetchrow(query, email)
                    result = dict(row) if row else None
                    span.set_attribute("success", result is not None)
                    span.set_attribute("user_found", result is not None)
                    return result
            except Exception as e:
                span.record_exception(e)
                span.set_attribute("success", False)
                span.set_attribute("error", str(e))
                raise

    async def create_user(self, username, email, password_hash):
        """Create a new user account"""
        with optional_trace_span(self.tracer, "db_create_user") as span:
            span.set_attribute("username", username)
            
            if not self.pool:
                await self.connect()

            query = """
                INSERT INTO auth.users 
                (username, email, password_hash)
                VALUES ($1, $2, $3)
                RETURNING id
            """
            span.set_attribute("db.statement", query)

            try:
                async with self.pool.acquire() as conn:
                    async with conn.transaction():
                        user_id = await conn.fetchval(query, username, email, password_hash)
                        # Create default profile
                        await _create_default_profile(conn, user_id)
                    
                    span.set_attribute("success", True)
                    span.set_attribute("user_id", str(user_id))
                    return user_id
            except Exception as e:
                span.record_exception(e)
                span.set_attribute("success", False)
                span.set_attribute("error", str(e))
                raise

    async def verify_password(self, username, password):
        """Verify user password"""
        with optional_trace_span(self.tracer, "db_verify_password") as span:
            span.set_attribute("username", username)
            
            logger.debug(f"Starting verify_password for username: {username}")
            
            if not self.pool:
                logger.debug("Database pool not initialized, connecting...")
                await self.connect()

            query = """
                SELECT * FROM auth.verify_password($1, $2)
            """
            span.set_attribute("db.statement", query)
            logger.debug(f"Executing query: {query} with username={username}")

            try:
                async with self.pool.acquire() as conn:
                    logger.debug("Acquired database connection")
                    row = await conn.fetchrow(query, username, password)
                    logger.debug(f"Query result: {row}")
                    
                    result = dict(row) if row else None
                    logger.debug(f"Processed result: {result}")
                    
                    span.set_attribute("success", result is not None)
                    span.set_attribute("authentication_success", result is not None)
                    return result
            except Exception as e:
                logger.error(f"Error in verify_password: {e}", exc_info=True)
                raise

    async def update_password(self, user_id, new_password_hash):
        """Update user password"""
        with optional_trace_span(self.tracer, "db_update_password") as span:
            span.set_attribute("user_id", str(user_id))
            
            if not self.pool:
                await self.connect()

            query = """
                UPDATE auth.users
                SET password_hash = $2
                WHERE id = $1
            """
            span.set_attribute("db.statement", query)

            try:
                async with self.pool.acquire() as conn:
                    await conn.execute(query, user_id, new_password_hash)
                    span.set_attribute("success", True)
            except Exception as e:
                span.record_exception(e)
                span.set_attribute("success", False)
                span.set_attribute("error", str(e))
                raise

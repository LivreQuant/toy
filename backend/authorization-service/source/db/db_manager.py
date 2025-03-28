# source/db/database.py
import logging
import asyncpg
import os
import datetime
import json
from opentelemetry import trace

from source.utils.tracing import optional_trace_span

logger = logging.getLogger('database')


class DatabaseManager:
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
        self.tracer = trace.get_tracer("db_manager")

    async def connect(self):
        """Create the database connection pool"""
        with optional_trace_span(self.tracer, "db_connect") as span:
            if self.pool:
                return

            try:
                span.set_attribute("db.system", "postgresql")
                span.set_attribute("db.name", self.db_config['database'])
                span.set_attribute("db.user", self.db_config['user'])
                span.set_attribute("db.host", self.db_config['host'])
                span.set_attribute("db.port", self.db_config['port'])
                
                self.pool = await asyncpg.create_pool(
                    min_size=self.min_connections,
                    max_size=self.max_connections,
                    **self.db_config
                )
                logger.info("Database connection established")
                span.set_attribute("success", True)
            except Exception as e:
                logger.error(f"Database connection failed: {e}")
                span.record_exception(e)
                span.set_attribute("success", False)
                span.set_attribute("error", str(e))
                raise

    async def close(self):
        """Close all database connections"""
        with optional_trace_span(self.tracer, "db_close") as span:
            if self.pool:
                await self.pool.close()
                self.pool = None
                logger.info("Database connections closed")
                span.set_attribute("success", True)

    async def get_user_by_username(self, username):
        """Get user by username"""
        with optional_trace_span(self.tracer, "db_get_user_by_username") as span:
            span.set_attribute("username", username)
            
            if not self.pool:
                await self.connect()

            query = """
                SELECT id, username, password_hash, is_active, user_role
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
                SELECT id, username, email, first_name, last_name, is_active, user_role
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

    async def verify_password(self, username, password):
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

    async def save_refresh_token(self, user_id, token_hash, expires_at):
        """Save a refresh token to the database"""
        with optional_trace_span(self.tracer, "db_save_refresh_token") as span:
            span.set_attribute("user_id", str(user_id))
            
            if not self.pool:
                await self.connect()

            query = """
                INSERT INTO auth.refresh_tokens
                (user_id, token_hash, expires_at)
                VALUES ($1, $2, $3)
                ON CONFLICT (token_hash) 
                DO UPDATE SET expires_at = $3, is_revoked = FALSE
            """
            span.set_attribute("db.statement", query)

            try:
                async with self.pool.acquire() as conn:
                    await conn.execute(query, user_id, token_hash, expires_at)
                    span.set_attribute("success", True)
            except Exception as e:
                span.record_exception(e)
                span.set_attribute("success", False)
                span.set_attribute("error", str(e))
                raise

    async def get_refresh_token(self, token_hash):
        """Get refresh token info"""
        with optional_trace_span(self.tracer, "db_get_refresh_token") as span:
            span.set_attribute("token_hash_length", len(token_hash))
            
            if not self.pool:
                await self.connect()

            query = """
                SELECT user_id, expires_at, is_revoked
                FROM auth.refresh_tokens
                WHERE token_hash = $1
            """
            span.set_attribute("db.statement", query)

            async with self.pool.acquire() as conn:
                row = await conn.fetchrow(query, token_hash)
                result = dict(row) if row else None
                span.set_attribute("success", result is not None)
                span.set_attribute("token_found", result is not None)
                if result:
                    span.set_attribute("is_revoked", result.get('is_revoked', False))
                return result

    async def revoke_refresh_token(self, token_hash):
        """Revoke a refresh token"""
        with optional_trace_span(self.tracer, "db_revoke_refresh_token") as span:
            span.set_attribute("token_hash_length", len(token_hash))
            
            if not self.pool:
                await self.connect()

            query = """
                UPDATE auth.refresh_tokens
                SET is_revoked = TRUE
                WHERE token_hash = $1
            """
            span.set_attribute("db.statement", query)

            try:
                async with self.pool.acquire() as conn:
                    result = await conn.execute(query, token_hash)
                    span.set_attribute("success", True)
            except Exception as e:
                span.record_exception(e)
                span.set_attribute("success", False)
                span.set_attribute("error", str(e))
                raise

    async def revoke_all_user_tokens(self, user_id):
        """Revoke all refresh tokens for a user"""
        with optional_trace_span(self.tracer, "db_revoke_all_user_tokens") as span:
            span.set_attribute("user_id", str(user_id))
            
            if not self.pool:
                await self.connect()

            query = """
                UPDATE auth.refresh_tokens
                SET is_revoked = TRUE
                WHERE user_id = $1
            """
            span.set_attribute("db.statement", query)

            try:
                async with self.pool.acquire() as conn:
                    result = await conn.execute(query, user_id)
                    span.set_attribute("success", True)
            except Exception as e:
                span.record_exception(e)
                span.set_attribute("success", False)
                span.set_attribute("error", str(e))
                raise

    async def cleanup_expired_tokens(self):
        """Clean up expired tokens"""
        with optional_trace_span(self.tracer, "db_cleanup_expired_tokens") as span:
            if not self.pool:
                await self.connect()

            query = "SELECT auth.cleanup_expired_tokens()"
            span.set_attribute("db.statement", query)

            try:
                async with self.pool.acquire() as conn:
                    await conn.execute(query)
                    span.set_attribute("success", True)
            except Exception as e:
                span.record_exception(e)
                span.set_attribute("success", False)
                span.set_attribute("error", str(e))
                raise

    async def check_connection(self):
        """Check if database connection is working"""
        with optional_trace_span(self.tracer, "db_check_connection") as span:
            if not self.pool:
                try:
                    await self.connect()
                    span.set_attribute("success", True)
                    return True
                except:
                    span.set_attribute("success", False)
                    return False

            try:
                async with self.pool.acquire() as conn:
                    await conn.execute("SELECT 1")
                    span.set_attribute("success", True)
                    return True
            except Exception as e:
                logger.error(f"Database connection check failed: {e}")
                span.record_exception(e)
                span.set_attribute("success", False)
                span.set_attribute("error", str(e))
                return False
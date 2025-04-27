# source/db/password_reset_db.py
import logging
from opentelemetry import trace

from source.utils.tracing import optional_trace_span
from source.db.base_manager import BaseDatabaseManager

logger = logging.getLogger('password_reset_db')

class PasswordResetDatabaseManager(BaseDatabaseManager):
    async def create_password_reset_token(self, user_id, token_hash, expires_at):
        """Create password reset token"""
        with optional_trace_span(self.tracer, "db_create_password_reset_token") as span:
            span.set_attribute("user_id", str(user_id))
            
            if not self.pool:
                await self.connect()

            query = """
                SELECT auth.create_password_reset_token($1, $2, $3)
            """
            span.set_attribute("db.statement", query)

            try:
                async with self.pool.acquire() as conn:
                    result = await conn.fetchval(query, user_id, token_hash, expires_at)
                    span.set_attribute("success", result)
                    return result
            except Exception as e:
                span.record_exception(e)
                span.set_attribute("success", False)
                span.set_attribute("error", str(e))
                raise

    async def get_password_reset_token(self, token_hash):
        """Get password reset token data"""
        with optional_trace_span(self.tracer, "db_get_password_reset_token") as span:
            span.set_attribute("token_hash_length", len(token_hash))
            
            if not self.pool:
                await self.connect()

            query = """
                SELECT user_id, created_at, expires_at, is_used
                FROM auth.password_reset_tokens
                WHERE token_hash = $1
            """
            span.set_attribute("db.statement", query)

            try:
                async with self.pool.acquire() as conn:
                    row = await conn.fetchrow(query, token_hash)
                    result = dict(row) if row else None
                    span.set_attribute("success", result is not None)
                    span.set_attribute("token_found", result is not None)
                    return result
            except Exception as e:
                span.record_exception(e)
                span.set_attribute("success", False)
                span.set_attribute("error", str(e))
                raise

    async def mark_reset_token_used(self, token_hash):
        """Mark password reset token as used"""
        with optional_trace_span(self.tracer, "db_mark_reset_token_used") as span:
            span.set_attribute("token_hash_length", len(token_hash))
            
            if not self.pool:
                await self.connect()

            query = """
                UPDATE auth.password_reset_tokens
                SET is_used = TRUE
                WHERE token_hash = $1
            """
            span.set_attribute("db.statement", query)

            try:
                async with self.pool.acquire() as conn:
                    await conn.execute(query, token_hash)
                    span.set_attribute("success", True)
            except Exception as e:
                span.record_exception(e)
                span.set_attribute("success", False)
                span.set_attribute("error", str(e))
                raise

    async def cleanup_expired_reset_tokens(self):
        """Clean up expired password reset tokens"""
        with optional_trace_span(self.tracer, "db_cleanup_expired_reset_tokens") as span:
            if not self.pool:
                await self.connect()

            query = "SELECT auth.cleanup_expired_reset_tokens()"
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
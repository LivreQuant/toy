# source/db/auth_db.py
import logging

from source.utils.tracing import optional_trace_span
from source.db.base_manager import BaseDatabaseManager

logger = logging.getLogger('auth_db')


class AuthDatabaseManager(BaseDatabaseManager):
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

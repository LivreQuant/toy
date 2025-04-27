# source/db/verification_db.py
import logging
from opentelemetry import trace

from source.utils.tracing import optional_trace_span
from source.db.base_manager import BaseDatabaseManager

logger = logging.getLogger('verification_db')

class VerificationDatabaseManager(BaseDatabaseManager):
    async def update_verification_code(self, user_id, code, expires_at):
        """Update user verification code"""
        with optional_trace_span(self.tracer, "db_update_verification_code") as span:
            span.set_attribute("user_id", str(user_id))
            
            if not self.pool:
                await self.connect()

            query = """
                UPDATE auth.users
                SET verification_code = $2, verification_sent_at = $3
                WHERE id = $1
            """
            span.set_attribute("db.statement", query)

            try:
                async with self.pool.acquire() as conn:
                    await conn.execute(query, user_id, code, expires_at)
                    span.set_attribute("success", True)
            except Exception as e:
                span.record_exception(e)
                span.set_attribute("success", False)
                span.set_attribute("error", str(e))
                raise

    async def mark_email_verified(self, user_id):
        """Mark user email as verified"""
        with optional_trace_span(self.tracer, "db_mark_email_verified") as span:
            span.set_attribute("user_id", str(user_id))
            
            if not self.pool:
                await self.connect()

            query = """
                UPDATE auth.users
                SET email_verified = TRUE,
                    verification_code = NULL,
                    verification_sent_at = NULL
                WHERE id = $1
            """
            span.set_attribute("db.statement", query)

            try:
                async with self.pool.acquire() as conn:
                    await conn.execute(query, user_id)
                    span.set_attribute("success", True)
            except Exception as e:
                span.record_exception(e)
                span.set_attribute("success", False)
                span.set_attribute("error", str(e))
                raise
# source/db/handlers/verification.py
import logging

from source.utils.tracing import optional_trace_span
from source.db.base_manager import BaseDatabaseManager

# Create a logger for this module
logger = logging.getLogger('verification_db')

class VerificationDatabaseManager(BaseDatabaseManager):
    async def update_verification_code(self, user_id, code, expires_at):
        """Update user verification code"""
        with optional_trace_span(self.tracer, "db_update_verification_code") as span:
            span.set_attribute("user_id", str(user_id))
            
            # Use the module-level logger instead of self.logger
            logger.debug(f"Storing verification code for user {user_id}: '{code}'")
            
            if not self.pool:
                await self.connect()

            # Ensure code is stored as string
            code_str = str(code) if code is not None else None
            
            query = """
                UPDATE auth.users
                SET verification_code = $2, verification_sent_at = $3
                WHERE user_id = $1
            """
            span.set_attribute("db.statement", query)

            try:
                async with self.pool.acquire() as conn:
                    await conn.execute(query, user_id, code_str, expires_at)
                    logger.debug(f"Verification code stored successfully for user {user_id}")
                    span.set_attribute("success", True)
            except Exception as e:
                logger.error(f"Error storing verification code for user {user_id}: {e}")
                span.record_exception(e)
                span.set_attribute("success", False)
                span.set_attribute("error", str(e))
                raise

    async def mark_email_verified(self, user_id):
        """Mark user email as verified"""
        with optional_trace_span(self.tracer, "db_mark_email_verified") as span:
            span.set_attribute("user_id", str(user_id))
            
            # Log start of operation
            logger.debug(f"Marking email as verified for user {user_id}")
            
            if not self.pool:
                await self.connect()

            query = """
                UPDATE auth.users
                SET email_verified = TRUE,
                    verification_code = NULL,
                    verification_sent_at = NULL
                WHERE user_id = $1
            """
            span.set_attribute("db.statement", query)

            try:
                async with self.pool.acquire() as conn:
                    await conn.execute(query, user_id)
                    logger.debug(f"Email verified successfully for user {user_id}")
                    span.set_attribute("success", True)
            except Exception as e:
                logger.error(f"Error marking email as verified for user {user_id}: {e}")
                span.record_exception(e)
                span.set_attribute("success", False)
                span.set_attribute("error", str(e))
                raise
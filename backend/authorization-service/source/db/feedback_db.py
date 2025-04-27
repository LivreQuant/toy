# source/db/feedback_db.py
import logging
from opentelemetry import trace

from source.utils.tracing import optional_trace_span
from source.db.base_manager import BaseDatabaseManager

logger = logging.getLogger('feedback_db')

class FeedbackDatabaseManager(BaseDatabaseManager):
    async def save_feedback(self, user_id, feedback_type, title, content):
        """Save user feedback"""
        with optional_trace_span(self.tracer, "db_save_feedback") as span:
            if user_id:
                span.set_attribute("user_id", str(user_id))
            span.set_attribute("feedback_type", feedback_type)
            
            if not self.pool:
                await self.connect()

            query = """
                INSERT INTO auth.user_feedback
                (user_id, feedback_type, title, content)
                VALUES ($1, $2, $3, $4)
                RETURNING id
            """
            span.set_attribute("db.statement", query)

            try:
                async with self.pool.acquire() as conn:
                    feedback_id = await conn.fetchval(query, user_id, feedback_type, title, content)
                    span.set_attribute("success", True)
                    span.set_attribute("feedback_id", str(feedback_id))
                    return feedback_id
            except Exception as e:
                span.record_exception(e)
                span.set_attribute("success", False)
                span.set_attribute("error", str(e))
                raise
# source/core/services/feedback_service.py
from source.core.base_manager import BaseManager
from source.utils.tracing import optional_trace_span


class FeedbackService(BaseManager):
    """Service for handling user feedback submissions"""

    def __init__(self, db_manager):
        super().__init__(db_manager)

    async def submit_feedback(self, user_id, feedback_type, title, content):
        """Handle feedback submission"""
        with optional_trace_span(self.tracer, "submit_feedback") as span:
            if user_id:
                span.set_attribute("user_id", str(user_id))
            span.set_attribute("feedback_type", feedback_type)

            try:
                # Save feedback to database
                feedback_id = await self.db.save_feedback(user_id, feedback_type, title, content)

                span.set_attribute("feedback.success", True)
                span.set_attribute("feedback_id", str(feedback_id))
                return {
                    'success': True,
                    'feedbackId': feedback_id,
                    'message': "Feedback submitted successfully"
                }
            except Exception as e:
                self.logger.error(f"Feedback submission error: {e}", exc_info=True)
                span.record_exception(e)
                span.set_attribute("feedback.success", False)
                span.set_attribute("feedback.error", str(e))
                return {
                    'success': False,
                    'error': "Feedback submission failed"
                }

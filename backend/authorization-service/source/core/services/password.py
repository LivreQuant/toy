# source/core/services/password_service.py
from source.core.base_manager import BaseManager
from source.utils.tracing import optional_trace_span
from source.utils.security import is_strong_password


class PasswordService(BaseManager):
    """Service for handling password operations"""

    def __init__(self, db_manager):
        super().__init__(db_manager)
        # These will be set via dependency injection
        self.email_manager = None
        self.verification_manager = None

    async def forgot_username(self, email):
        """Handle forgot username request"""
        with optional_trace_span(self.tracer, "forgot_username") as span:
            span.set_attribute("email", email)

            try:
                # Look up user by email
                user = await self.db.get_user_by_email(email)

                if not user:
                    # Don't indicate if email exists or not - security best practice
                    self.logger.info(f"Forgot username request for non-existent email: {email}")
                    span.set_attribute("user_found", False)
                    return {
                        'success': True  # Always return success
                    }

                # Send username reminder email
                username = user.get('username')
                await self.email_manager.send_forgot_username_email(email, username)

                span.set_attribute("user_found", True)
                span.set_attribute("email_sent", True)
                return {
                    'success': True
                }
            except Exception as e:
                self.logger.error(f"Forgot username error: {e}", exc_info=True)
                span.record_exception(e)
                span.set_attribute("error", str(e))
                return {
                    'success': True  # Always return success for security
                }

    async def forgot_password(self, email):
        """Handle forgot password request"""
        with optional_trace_span(self.tracer, "forgot_password") as span:
            span.set_attribute("email", email)

            try:
                # Look up user by email
                user = await self.db.get_user_by_email(email)

                if not user:
                    # Don't indicate if email exists or not - security best practice
                    self.logger.info(f"Forgot password request for non-existent email: {email}")
                    span.set_attribute("user_found", False)
                    return {
                        'success': True  # Always return success
                    }

                reset_token = await self.verification_manager.create_password_reset_token(user_id)

                try:
                    # Generate reset token
                    user_id = user.get('id')

                    # Send reset email
                    email_sent = await  self.email_manager.send_password_reset_email(
                        email, user.get('username'), reset_token
                    )
                    
                    if not email_sent:
                        # Log the failure but don't reveal to user
                        self.logger.error(f"Failed to send password reset email to {email}")
                    
                    
                    span.set_attribute("user_found", True)
                    span.set_attribute("reset_token_created", True)
                    span.set_attribute("email_sent", True)
                    return {
                        'success': True
                    }
                
                except Exception as e:
                    # Log the email sending error but return success to user
                    self.logger.error(f"Email sending error in forgot_password: {e}", exc_info=True)
                    return {'success': True}  # Still return success for security
                    
            except Exception as e:
                self.logger.error(f"Forgot password error: {e}", exc_info=True)
                span.record_exception(e)
                span.set_attribute("error", str(e))
                return {
                    'success': True  # Always return success for security
                }

    async def reset_password(self, reset_token, new_password):
        """Handle password reset request"""
        with optional_trace_span(self.tracer, "reset_password") as span:
            try:
                # Validate password strength
                if not is_strong_password(new_password):
                    span.set_attribute("reset.success", False)
                    span.set_attribute("reset.error", "Password does not meet strength requirements")
                    return {
                        'success': False,
                        'error': "Password must be at least 8 characters long and include uppercase, lowercase, number, and special character"
                    }

                # Verify reset token
                user_id = await self.verification_manager.verify_password_reset_token(reset_token)

                if not user_id:
                    span.set_attribute("reset.success", False)
                    span.set_attribute("reset.error", "Invalid or expired token")
                    return {
                        'success': False,
                        'error': "Invalid or expired token"
                    }

                span.set_attribute("user_id", str(user_id))

                # Hash new password
                new_password_hash = await self._hash_password(new_password)

                # Update password in database
                await self.db.update_password(user_id, new_password_hash)

                # Invalidate all refresh tokens for this user
                await self.db.revoke_all_user_tokens(user_id)

                # Mark token as used
                token_hash = self.verification_manager.hash_token(reset_token)
                await self.db.mark_reset_token_used(token_hash)

                span.set_attribute("reset.success", True)
                return {
                    'success': True,
                    'message': "Password reset successful"
                }
            except Exception as e:
                self.logger.error(f"Reset password error: {e}", exc_info=True)
                span.record_exception(e)
                span.set_attribute("reset.success", False)
                span.set_attribute("reset.error", str(e))
                return {
                    'success': False,
                    'error': "Password reset failed"
                }

    async def _hash_password(self, password):
        """Generate a secure password hash"""
        # Use bcrypt through the PostgreSQL crypt function
        async with self.db.pool.acquire() as conn:
            query = "SELECT crypt($1, gen_salt('bf'))"
            return await conn.fetchval(query, password)

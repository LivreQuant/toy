# source/core/auth_manager.py
import logging
import asyncio
import threading
import time
import datetime
from opentelemetry import trace

from source.core.token_manager import TokenManager

from source.utils.tracing import optional_trace_span
from source.utils.metrics import (
    track_login_attempt,
    track_login_duration,
    track_token_issued
)

logger = logging.getLogger('auth_manager')


class AuthManager:
    def __init__(self, db_manager):
        self.db = db_manager
        self.token_manager = TokenManager()
        self.stop_cleanup_event = threading.Event()
        self.cleanup_thread = None
        self.tracer = trace.get_tracer("auth_manager")

        # Start background task to clean up expired tokens periodically
        self._start_cleanup_thread()

    def _start_cleanup_thread(self):
        """Start the cleanup thread"""
        self.cleanup_thread = threading.Thread(
            target=self._cleanup_expired_tokens, 
            daemon=True
        )
        self.cleanup_thread.start()
        logger.info("Background token cleanup thread started")

    def _cleanup_expired_tokens(self):
        """Background task to clean up expired tokens"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        while not self.stop_cleanup_event.is_set():
            try:
                # Run cleanup every 6 hours
                self.stop_cleanup_event.wait(6 * 60 * 60)  # This allows graceful interruption
                
                if not self.stop_cleanup_event.is_set():
                    logger.info("Running expired token cleanup")
                    # Use run_coroutine_threadsafe to run async method from another thread
                    future = asyncio.run_coroutine_threadsafe(
                        self.db.cleanup_expired_tokens(), 
                        loop
                    )
                    future.result(timeout=60)  # Wait up to 60 seconds
            except asyncio.CancelledError:
                logger.info("Token cleanup task was cancelled")
                break
            except Exception as e:
                logger.error(f"Error in token cleanup: {e}", exc_info=True)
                # Add a small delay to prevent tight error loops
                time.sleep(60)

        logger.info("Token cleanup thread stopped gracefully")
        loop.close()

    def stop_cleanup_thread(self):
        """Gracefully stop the cleanup thread"""
        logger.info("Signaling token cleanup thread to stop...")
        self.stop_cleanup_event.set()
        
        if self.cleanup_thread and self.cleanup_thread.is_alive():
            # Wait up to 10 seconds for thread to stop
            self.cleanup_thread.join(timeout=10)
            
            if self.cleanup_thread.is_alive():
                logger.warning("Token cleanup thread did not stop promptly")

    async def login(self, username, password):
        with optional_trace_span(self.tracer, "login") as span:
            span.set_attribute("username", username)
            start_time = time.time()
            
            logger.debug(f"Login attempt for username: {username}")
            
            try:
                # Verify username and password
                logger.debug("Calling verify_password")
                user = await self.db.verify_password(username, password)
                logger.debug(f"verify_password returned: {user}")

                if not user:
                    # Use metrics tracking
                    logger.debug("Authentication failed: No user data returned")
                    track_login_attempt(username, False)
                    track_login_duration(start_time, False)
                    
                    span.set_attribute("login.success", False)
                    span.set_attribute("login.error", "Invalid username or password")
                    return {
                        'success': False,
                        'error': "Invalid username or password"
                    }

                logger.debug(f"User authenticated successfully: {user}")
                
                # Track successful login
                track_login_attempt(username, True)
                track_login_duration(start_time, True)

                # Generate JWT tokens
                logger.debug("Generating JWT tokens")
                tokens = self.token_manager.generate_tokens(user['user_id'], user.get('user_role', 'user'))
                logger.debug("Tokens generated successfully")
                
                # Track token issuance
                track_token_issued('access', user.get('user_role', 'user'))
                track_token_issued('refresh', user.get('user_role', 'user'))

                return {
                    'success': True,
                    'accessToken': tokens['accessToken'],
                    'refreshToken': tokens['refreshToken'],
                    'expiresIn': tokens['expiresIn'],
                    'userId': user['user_id'],
                    'userRole': user.get('user_role', 'user')
                }
                
            except Exception as e:
                # Track login failure due to exception
                logger.error(f"Login error: {e}", exc_info=True)
                track_login_attempt(username, False)
                track_login_duration(start_time, False)
                
                span.record_exception(e)
                return {
                    'success': False,
                    'error': "Authentication service error"
                }

    async def logout(self, access_token, refresh_token=None, logout_all=False):
        """Handle logout request"""
        with optional_trace_span(self.tracer, "logout") as span:
            span.set_attribute("refresh_token_provided", refresh_token is not None)
            span.set_attribute("logout_all", logout_all)
            try:
                # Validate access token to get user_id
                token_data = self.token_manager.validate_access_token(access_token)
                user_id = token_data.get('user_id') if token_data.get('valid') else None
                
                span.set_attribute("token_valid", token_data.get('valid', False))
                if user_id:
                    span.set_attribute("user.id", str(user_id))

                if refresh_token:
                    # Revoke the specific refresh token
                    refresh_token_hash = self.token_manager.hash_token(refresh_token)
                    await self.db.revoke_refresh_token(refresh_token_hash)
                    logger.info(f"Revoked refresh token for user {user_id}")
                    span.set_attribute("refresh_token_revoked", True)

                if user_id and logout_all:
                    # Revoke all user's refresh tokens
                    await self.db.revoke_all_user_tokens(user_id)
                    logger.info(f"Revoked all refresh tokens for user {user_id}")
                    span.set_attribute("all_tokens_revoked", True)

                span.set_attribute("logout.success", True)
                return {
                    'success': True
                }
            except Exception as e:
                logger.error(f"Logout error: {e}", exc_info=True)
                span.record_exception(e)
                span.set_attribute("logout.success", False)
                span.set_attribute("logout.error", str(e))
                return {
                    'success': False,
                    'error': str(e)
                }

    async def refresh_token(self, refresh_token):
        """Handle token refresh request"""
        with optional_trace_span(self.tracer, "refresh_token") as span:
            try:
                # Validate refresh token
                validation = self.token_manager.validate_refresh_token(refresh_token)
                
                span.set_attribute("token_valid", validation.get('valid', False))
                if not validation.get('valid'):
                    span.set_attribute("error", validation.get('error', 'Invalid refresh token'))
                    return {
                        'success': False,
                        'error': validation.get('error', 'Invalid refresh token')
                    }

                user_id = validation.get('user_id')
                span.set_attribute("user.id", str(user_id))

                # Check if token exists in database
                token_hash = self.token_manager.hash_token(refresh_token)
                token_record = await self.db.get_refresh_token(token_hash)
                
                span.set_attribute("token_found", token_record is not None)
                if token_record:
                    span.set_attribute("token_revoked", token_record.get('is_revoked', False))

                if not token_record or token_record.get('is_revoked'):
                    logger.warning(f"Refresh token not found or revoked for user {user_id}")
                    span.set_attribute("error", "Invalid refresh token")
                    return {
                        'success': False,
                        'error': "Invalid refresh token"
                    }

                # Get user info
                user = await self.db.get_user_by_id(user_id)
                
                span.set_attribute("user_found", user is not None)
                if user:
                    span.set_attribute("user_active", user.get('is_active', False))

                if not user or not user.get('is_active', False):
                    logger.warning(f"User inactive or not found: {user_id}")
                    span.set_attribute("error", "User account inactive or not found")
                    return {
                        'success': False,
                        'error': "User account inactive or not found"
                    }

                # Generate new tokens
                user_role = user.get('user_role', 'user')
                span.set_attribute("user.role", user_role)
                tokens = self.token_manager.generate_tokens(user_id, user_role)

                # Revoke old refresh token
                await self.db.revoke_refresh_token(token_hash)
                span.set_attribute("old_token_revoked", True)

                # Save new refresh token
                new_token_hash = self.token_manager.hash_token(tokens['refreshToken'])
                refresh_token_expires = datetime.datetime.fromtimestamp(
                    time.time() + self.token_manager.refresh_token_expiry)
                await self.db.save_refresh_token(user_id, new_token_hash, refresh_token_expires)
                span.set_attribute("new_token_saved", True)

                logger.info(f"Refreshed token for user {user_id}")
                span.set_attribute("refresh.success", True)

                return {
                    'success': True,
                    'accessToken': tokens['accessToken'],
                    'refreshToken': tokens['refreshToken'],
                    'expiresIn': tokens['expiresIn']
                }
            except Exception as e:
                logger.error(f"Token refresh error: {e}", exc_info=True)
                span.record_exception(e)
                span.set_attribute("refresh.success", False)
                span.set_attribute("refresh.error", str(e))
                return {
                    'success': False,
                    'error': "Authentication service error"
                }

    async def validate_token(self, token):
        """Validate an access token"""
        with optional_trace_span(self.tracer, "validate_token") as span:
            try:
                # Verify JWT token
                validation = self.token_manager.validate_access_token(token)

                logger.debug(f"Validate token received: {token}...")
                logger.debug(f"Validation result: {validation}")
                
                span.set_attribute("token_valid", validation.get('valid', False))
                if not validation.get('valid'):
                    span.set_attribute("error", validation.get('error', 'Invalid token'))
                    return {
                        'valid': False,
                        'error': validation.get('error', 'Invalid token')
                    }

                user_id = validation.get('user_id')
                span.set_attribute("user.id", str(user_id))
                span.set_attribute("user.role", validation.get('user_role', 'user'))

                # Get user info
                user = await self.db.get_user_by_id(user_id)
                
                span.set_attribute("user_found", user is not None)
                if user:
                    span.set_attribute("user_active", user.get('is_active', False))

                if not user or not user.get('is_active', False):
                    span.set_attribute("error", "User account inactive or not found")
                    return {
                        'valid': False,
                        'error': 'User account inactive or not found'
                    }

                span.set_attribute("validation.success", True)
                return {
                    'valid': True,
                    'userId': str(user_id),
                    'user_role': validation.get('user_role', 'user')
                }
            except Exception as e:
                logger.error(f"Token validation error: {e}", exc_info=True)
                span.record_exception(e)
                span.set_attribute("validation.success", False)
                span.set_attribute("validation.error", str(e))
                return {
                    'valid': False,
                    'error': 'Token validation failed'
                }
            

    async def signup(self, username, email, password):
        """Handle signup request"""
        with optional_trace_span(self.tracer, "signup") as span:
            span.set_attribute("username", username)
            span.set_attribute("email", email)
            
            try:
                # Check if username or email already exists
                existing_user = await self.db.get_user_by_username(username)
                if existing_user:
                    span.set_attribute("signup.success", False)
                    span.set_attribute("signup.error", "Username already exists")
                    return {
                        'success': False,
                        'error': "Username already exists"
                    }
                
                existing_email = await self.db.get_user_by_email(email)
                if existing_email:
                    span.set_attribute("signup.success", False)
                    span.set_attribute("signup.error", "Email already exists")
                    return {
                        'success': False,
                        'error': "Email already exists"
                    }
                
                # Hash password
                password_hash = await self._hash_password(password)
                
                # Create user
                user_id = await self.db.create_user(username, email, password_hash)
                logger.info(f"Created user with ID: {user_id}")
                
                # Generate verification code
                verification_code = await self.verification_manager.create_email_verification(user_id, email)
                
                # Send verification email
                await self.email_manager.send_verification_email(email, username, verification_code)
                
                span.set_attribute("signup.success", True)
                span.set_attribute("user.id", str(user_id))
                
                return {
                    'success': True,
                    'userId': user_id,
                    'message': "Registration successful. Please check your email to verify your account."
                }
            except Exception as e:
                logger.error(f"Signup error: {e}", exc_info=True)
                span.record_exception(e)
                span.set_attribute("signup.success", False)
                span.set_attribute("signup.error", str(e))
                return {
                    'success': False,
                    'error': "Registration failed"
                }
        
    async def resend_verification(self, user_id):
        """Resend verification email"""
        with optional_trace_span(self.tracer, "resend_verification") as span:
            span.set_attribute("user_id", str(user_id))
            
            try:
                # Get user info
                user = await self.db.get_user_by_id(user_id)
                
                if not user:
                    span.set_attribute("resend.success", False)
                    span.set_attribute("resend.error", "User not found")
                    return {
                        'success': False,
                        'error': "User not found"
                    }
                
                if user.get('email_verified'):
                    span.set_attribute("resend.success", False)
                    span.set_attribute("resend.error", "Email already verified")
                    return {
                        'success': False,
                        'error': "Email already verified"
                    }
                
                # Generate new verification code
                verification_code = await self.verification_manager.create_email_verification(
                    user_id, user.get('email')
                )
                
                # Send verification email
                email_sent = await self.email_manager.send_verification_email(
                    user.get('email'), user.get('username'), verification_code
                )
                
                if not email_sent:
                    span.set_attribute("resend.success", False)
                    span.set_attribute("resend.error", "Failed to send verification email")
                    return {
                        'success': False,
                        'error': "Failed to send verification email"
                    }
                
                span.set_attribute("resend.success", True)
                return {
                    'success': True,
                    'message': "Verification email sent"
                }
            except Exception as e:
                logger.error(f"Resend verification error: {e}", exc_info=True)
                span.record_exception(e)
                span.set_attribute("resend.success", False)
                span.set_attribute("resend.error", str(e))
                return {
                    'success': False,
                    'error': "Failed to resend verification email"
                }

    async def forgot_username(self, email):
        """Handle forgot username request"""
        with optional_trace_span(self.tracer, "forgot_username") as span:
            span.set_attribute("email", email)
            
            try:
                # Look up user by email
                user = await self.db.get_user_by_email(email)
                
                if not user:
                    # Don't indicate if email exists or not - security best practice
                    logger.info(f"Forgot username request for non-existent email: {email}")
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
                logger.error(f"Forgot username error: {e}", exc_info=True)
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
                    logger.info(f"Forgot password request for non-existent email: {email}")
                    span.set_attribute("user_found", False)
                    return {
                        'success': True  # Always return success
                    }
                
                # Generate reset token
                user_id = user.get('id')
                reset_token = await self.verification_manager.create_password_reset_token(user_id)
                
                # Send reset email
                await self.email_manager.send_password_reset_email(
                    email, user.get('username'), reset_token
                )
                
                span.set_attribute("user_found", True)
                span.set_attribute("reset_token_created", True)
                span.set_attribute("email_sent", True)
                return {
                    'success': True
                }
            except Exception as e:
                logger.error(f"Forgot password error: {e}", exc_info=True)
                span.record_exception(e)
                span.set_attribute("error", str(e))
                return {
                    'success': True  # Always return success for security
                }

    async def reset_password(self, reset_token, new_password):
        """Handle password reset request"""
        with optional_trace_span(self.tracer, "reset_password") as span:
            try:
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
                logger.error(f"Reset password error: {e}", exc_info=True)
                span.record_exception(e)
                span.set_attribute("reset.success", False)
                span.set_attribute("reset.error", str(e))
                return {
                    'success': False,
                    'error': "Password reset failed"
                }

    async def update_profile(self, user_id, profile_data):
        """Handle profile update request"""
        with optional_trace_span(self.tracer, "update_profile") as span:
            span.set_attribute("user_id", str(user_id))
            
            try:
                # Validate username uniqueness if changing
                if profile_data.get('username'):
                    existing_user = await self.db.get_user_by_username(profile_data['username'])
                    if existing_user and existing_user.get('id') != user_id:
                        span.set_attribute("update.success", False)
                        span.set_attribute("update.error", "Username already exists")
                        return {
                            'success': False,
                            'error': "Username already exists"
                        }
                
                # Validate email uniqueness if changing
                if profile_data.get('email'):
                    existing_email = await self.db.get_user_by_email(profile_data['email'])
                    if existing_email and existing_email.get('id') != user_id:
                        span.set_attribute("update.success", False)
                        span.set_attribute("update.error", "Email already exists")
                        return {
                            'success': False,
                            'error': "Email already exists"
                        }
                
                # Update profile in database
                await self.db.update_user_profile(user_id, profile_data)
                
                span.set_attribute("update.success", True)
                return {
                    'success': True,
                    'message': "Profile updated successfully"
                }
            except Exception as e:
                logger.error(f"Profile update error: {e}", exc_info=True)
                span.record_exception(e)
                span.set_attribute("update.success", False)
                span.set_attribute("update.error", str(e))
                return {
                    'success': False,
                    'error': "Profile update failed"
                }

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
                logger.error(f"Feedback submission error: {e}", exc_info=True)
                span.record_exception(e)
                span.set_attribute("feedback.success", False)
                span.set_attribute("feedback.error", str(e))
                return {
                    'success': False,
                    'error': "Feedback submission failed"
                }
            
    async def _hash_password(self, password):
        """Generate a secure password hash"""
        # Use bcrypt through the PostgreSQL crypt function
        async with self.db.pool.acquire() as conn:
            query = "SELECT crypt($1, gen_salt('bf'))"
            return await conn.fetchval(query, password)
        
        
    async def verify_email(self, user_id, verification_code):
        """Handle email verification request"""
        with optional_trace_span(self.tracer, "verify_email") as span:
            span.set_attribute("user_id", str(user_id))
            
            try:
                # Get user info
                user = await self.db.get_user_by_id(user_id)
                
                if not user:
                    span.set_attribute("verification.success", False)
                    span.set_attribute("verification.error", "User not found")
                    return {
                        'success': False,
                        'error': "User not found"
                    }
                
                if user.get('email_verified'):
                    span.set_attribute("verification.success", False)
                    span.set_attribute("verification.error", "Email already verified")
                    return {
                        'success': False,
                        'error': "Email already verified"
                    }
                
                # Verify code
                is_valid = await self.verification_manager.verify_email_code(user_id, verification_code)
                
                if not is_valid:
                    span.set_attribute("verification.success", False)
                    span.set_attribute("verification.error", "Invalid or expired verification code")
                    return {
                        'success': False,
                        'error': "Invalid or expired verification code"
                    }
                
                span.set_attribute("verification.success", True)
                return {
                    'success': True,
                    'message': "Email verified successfully"
                }
            except Exception as e:
                logger.error(f"Email verification error: {e}", exc_info=True)
                span.record_exception(e)
                span.set_attribute("verification.success", False)
                span.set_attribute("verification.error", str(e))
                return {
                    'success': False,
                    'error': "Email verification failed"
                }
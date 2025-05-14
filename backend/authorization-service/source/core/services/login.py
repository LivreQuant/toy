# backend/authorization-service/source/core/services/login.py

import time
from source.core.base_manager import BaseManager
from source.utils.tracing import optional_trace_span
from source.utils.metrics import (
    track_login_attempt,
    track_login_duration,
    track_token_issued
)


class LoginService(BaseManager):
    """Service for handling user authentication"""

    def __init__(self, db_manager, token_service):
        super().__init__(db_manager)
        self.token_service = token_service

    async def login(self, username, password):
        """Authenticate a user and generate tokens"""
        with optional_trace_span(self.tracer, "login") as span:
            span.set_attribute("username", username)
            start_time = time.time()

            self.logger.debug(f"Login attempt for username: {username}")

            try:
                # Verify username and password
                self.logger.debug("Calling verify_password")
                user = await self.db.verify_password(username, password)
                self.logger.debug(f"verify_password returned: {user}")

                if not user:
                    # Use metrics tracking
                    self.logger.debug("Authentication failed: No user data returned")
                    track_login_attempt(username, False)
                    track_login_duration(start_time, False)

                    span.set_attribute("login.success", False)
                    span.set_attribute("login.error", "Invalid username or password")
                    return {
                        'success': False,
                        'error': "Invalid username or password"
                    }

                self.logger.debug(f"User authenticated successfully: {user}")

                # Check email verification status
                user_details = await self.db.get_user_by_id(user['user_id'])
                if user_details and not user_details.get('email_verified', False):
                    track_login_attempt(username, False)
                    track_login_duration(start_time, False)
                    
                    span.set_attribute("login.success", False)
                    span.set_attribute("login.error", "Email not verified")
                    
                    # UPDATED: Include email address in the response
                    return {
                        'success': False,
                        'error': "Email verification required",
                        'requiresVerification': True,
                        'userId': str(user['user_id']),
                        'email': user_details.get('email')
                    }

                self.logger.debug(f"User email verified successfully: {user}")

                # Track successful login
                track_login_attempt(username, True)
                track_login_duration(start_time, True)

                # Generate JWT tokens
                self.logger.debug("Generating JWT tokens")
                tokens = self.token_service.token_manager.generate_tokens(
                    user['user_id'],
                    user.get('user_role', 'user')
                )
                self.logger.debug("Tokens generated successfully")

                # Track token issuance
                track_token_issued('access', user.get('user_role', 'user'))
                track_token_issued('refresh', user.get('user_role', 'user'))

                return {
                    'success': True,
                    'accessToken': tokens['accessToken'],
                    'refreshToken': tokens['refreshToken'],
                    'expiresIn': tokens['expiresIn'],
                    'userId': str(user['user_id']),
                    'userRole': user.get('user_role', 'user')
                }

            except Exception as e:
                # Track login failure due to exception
                self.logger.error(f"Login error: {e}", exc_info=True)
                track_login_attempt(username, False)
                track_login_duration(start_time, False)

                span.record_exception(e)
                return {
                    'success': False,
                    'error': "Authentication service error"
                }
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
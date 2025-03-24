# source/core/auth_manager.py
import logging
import asyncio
import threading
import time
import datetime

from source.core.token_manager import TokenManager

logger = logging.getLogger('auth_manager')


class AuthManager:
    def __init__(self, db_manager):
        self.db = db_manager
        self.token_manager = TokenManager()

        # Start a background task to clean up expired tokens periodically
        self.cleanup_thread = threading.Thread(target=self._cleanup_expired_tokens, daemon=True)
        self.cleanup_thread.start()

    def _cleanup_expired_tokens(self):
        """Background task to clean up expired tokens"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        while True:
            try:
                # Run cleanup every 6 hours
                time.sleep(6 * 60 * 60)
                logger.info("Running expired token cleanup")
                asyncio.run_coroutine_threadsafe(self.db.cleanup_expired_tokens(), loop)
            except Exception as e:
                logger.error(f"Error in token cleanup: {e}")

    async def login(self, username, password):
        """Handle login request"""
        try:
            # Verify username and password
            user = await self.db.verify_password(username, password)

            if not user:
                return {
                    'success': False,
                    'error': "Invalid username or password"
                }

            # Generate JWT tokens
            tokens = self.token_manager.generate_tokens(user['user_id'], user.get('role', 'user'))

            # Save refresh token to database
            refresh_token_hash = self.token_manager.hash_token(tokens['refreshToken'])
            refresh_token_expires = datetime.datetime.fromtimestamp(
                time.time() + self.token_manager.refresh_token_expiry)
            await self.db.save_refresh_token(user['user_id'], refresh_token_hash, refresh_token_expires)

            # Return tokens
            return {
                'success': True,
                'accessToken': tokens['accessToken'],
                'refreshToken': tokens['refreshToken'],
                'expiresIn': tokens['expiresIn']
            }
        except Exception as e:
            logger.error(f"Login error: {e}")
            return {
                'success': False,
                'error': "Authentication service error"
            }

    async def logout(self, access_token, refresh_token=None, logout_all=False):
        """Handle logout request"""
        try:
            # Validate access token to get user_id
            token_data = self.token_manager.validate_access_token(access_token)
            user_id = token_data.get('user_id') if token_data.get('valid') else None

            if refresh_token:
                # Revoke the specific refresh token
                refresh_token_hash = self.token_manager.hash_token(refresh_token)
                await self.db.revoke_refresh_token(refresh_token_hash)
                logger.info(f"Revoked refresh token for user {user_id}")

            if user_id and logout_all:
                # Revoke all user's refresh tokens
                await self.db.revoke_all_user_tokens(user_id)
                logger.info(f"Revoked all refresh tokens for user {user_id}")

            return {
                'success': True
            }
        except Exception as e:
            logger.error(f"Logout error: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    async def refresh_token(self, refresh_token):
        """Handle token refresh request"""
        try:
            # Validate refresh token
            validation = self.token_manager.validate_refresh_token(refresh_token)

            if not validation.get('valid'):
                return {
                    'success': False,
                    'error': validation.get('error', 'Invalid refresh token')
                }

            user_id = validation.get('user_id')

            # Check if token exists in database
            token_hash = self.token_manager.hash_token(refresh_token)
            token_record = await self.db.get_refresh_token(token_hash)

            if not token_record or token_record.get('is_revoked'):
                logger.warning(f"Refresh token not found or revoked for user {user_id}")
                return {
                    'success': False,
                    'error': "Invalid refresh token"
                }

            # Get user info
            user = await self.db.get_user_by_id(user_id)

            if not user or not user.get('is_active', False):
                logger.warning(f"User inactive or not found: {user_id}")
                return {
                    'success': False,
                    'error': "User account inactive or not found"
                }

            # Generate new tokens
            role = user.get('role', 'user')
            tokens = self.token_manager.generate_tokens(user_id, role)

            # Revoke old refresh token
            await self.db.revoke_refresh_token(token_hash)

            # Save new refresh token
            new_token_hash = self.token_manager.hash_token(tokens['refreshToken'])
            refresh_token_expires = datetime.datetime.fromtimestamp(
                time.time() + self.token_manager.refresh_token_expiry)
            await self.db.save_refresh_token(user_id, new_token_hash, refresh_token_expires)

            logger.info(f"Refreshed token for user {user_id}")

            return {
                'success': True,
                'accessToken': tokens['accessToken'],
                'refreshToken': tokens['refreshToken'],
                'expiresIn': tokens['expiresIn']
            }
        except Exception as e:
            logger.error(f"Token refresh error: {e}")
            return {
                'success': False,
                'error': "Authentication service error"
            }

    async def validate_token(self, token):
        """Validate an access token"""
        try:
            # Verify JWT token
            validation = self.token_manager.validate_access_token(token)

            if not validation.get('valid'):
                return {
                    'valid': False,
                    'error': validation.get('error', 'Invalid token')
                }

            user_id = validation.get('user_id')

            # Get user info
            user = await self.db.get_user_by_id(user_id)

            if not user or not user.get('is_active', False):
                return {
                    'valid': False,
                    'error': 'User account inactive or not found'
                }

            return {
                'valid': True,
                'userId': str(user_id),
                'role': validation.get('role', 'user')
            }
        except Exception as e:
            logger.error(f"Token validation error: {e}")
            return {
                'valid': False,
                'error': 'Token validation failed'
            }

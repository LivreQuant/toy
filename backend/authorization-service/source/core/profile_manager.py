# source/core/profile_manager.py
from source.core.base_manager import BaseManager
from source.utils.tracing import optional_trace_span
from source.utils.metrics import track_profile_update


class ProfileManager(BaseManager):
    def __init__(self, db_manager):
        super().__init__(db_manager)

    async def get_user_profile(self, user_id):
        """Get a user's complete profile information"""
        with optional_trace_span(self.tracer, "get_user_profile") as span:
            span.set_attribute("user_id", str(user_id))

            try:
                # Get basic user info
                user_data = await self.db.get_user_by_id(user_id)

                if not user_data:
                    span.set_attribute("profile.found", False)
                    span.set_attribute("error", "User not found")
                    return None

                # Get profile data
                profile_data = await self.db.get_user_profile(user_id)

                # Combine user and profile data
                combined_profile = {
                    'user_id': user_id,
                    'username': user_data.get('username'),
                    'email': user_data.get('email'),
                    'first_name': user_data.get('first_name'),
                    'last_name': user_data.get('last_name'),
                    'email_verified': user_data.get('email_verified', False),
                    'is_active': user_data.get('is_active', True),
                    'user_role': user_data.get('user_role', 'user'),
                    'created_at': user_data.get('created_at'),
                    'last_login': user_data.get('last_login'),
                }

                # Add profile data if it exists
                if profile_data:
                    combined_profile.update({
                        'display_name': profile_data.get('display_name'),
                        'bio': profile_data.get('bio'),
                        'profile_picture_url': profile_data.get('profile_picture_url'),
                        'preferences': profile_data.get('preferences', {}),
                        'profile_updated_at': profile_data.get('updated_at')
                    })

                span.set_attribute("profile.found", True)
                return combined_profile
            except Exception as e:
                self.logger.error(f"Error getting user profile: {e}", exc_info=True)
                span.record_exception(e)
                span.set_attribute("error", str(e))
                return None

    async def update_profile(self, user_id, profile_data):
        """Update user profile data"""
        with optional_trace_span(self.tracer, "update_profile") as span:
            span.set_attribute("user_id", str(user_id))

            try:
                # Check if user exists
                user = await self.db.get_user_by_id(user_id)

                if not user:
                    track_profile_update(False)
                    span.set_attribute("update.success", False)
                    span.set_attribute("error", "User not found")
                    return {
                        'success': False,
                        'error': "User not found"
                    }

                # Validate username uniqueness if changing
                if profile_data.get('username') and profile_data['username'] != user.get('username'):
                    existing_user = await self.db.get_user_by_username(profile_data['username'])
                    if existing_user and existing_user.get('id') != user_id:
                        track_profile_update(False)
                        span.set_attribute("update.success", False)
                        span.set_attribute("error", "Username already exists")
                        return {
                            'success': False,
                            'error': "Username already exists"
                        }

                # Validate email uniqueness if changing
                if profile_data.get('email') and profile_data['email'] != user.get('email'):
                    existing_email = await self.db.get_user_by_email(profile_data['email'])
                    if existing_email and existing_email.get('id') != user_id:
                        track_profile_update(False)
                        span.set_attribute("update.success", False)
                        span.set_attribute("error", "Email already exists")
                        return {
                            'success': False,
                            'error': "Email already exists"
                        }

                    # If email is changing, reset verification status
                    if 'email_verified' not in profile_data:
                        profile_data['email_verified'] = False

                # Track which fields are being updated
                for field in profile_data:
                    if profile_data[field] is not None:
                        span.set_attribute(f"update.field.{field}", True)

                # Update profile in database
                await self.db.update_user_profile(user_id, profile_data)

                # Track metric
                track_profile_update(True)
                span.set_attribute("update.success", True)

                return {
                    'success': True,
                    'message': "Profile updated successfully"
                }
            except Exception as e:
                self.logger.error(f"Profile update error: {e}", exc_info=True)
                track_profile_update(False)
                span.record_exception(e)
                span.set_attribute("update.success", False)
                span.set_attribute("error", str(e))
                return {
                    'success': False,
                    'error': "Profile update failed"
                }

    async def update_preferences(self, user_id, preferences):
        """Update only user preferences"""
        with optional_trace_span(self.tracer, "update_preferences") as span:
            span.set_attribute("user_id", str(user_id))

            try:
                # Check if user exists
                user = await self.db.get_user_by_id(user_id)

                if not user:
                    span.set_attribute("update.success", False)
                    span.set_attribute("error", "User not found")
                    return {
                        'success': False,
                        'error': "User not found"
                    }

                # Update only preferences
                profile_data = {
                    'preferences': preferences
                }

                # Update profile in database
                await self.db.update_user_profile(user_id, profile_data)

                span.set_attribute("update.success", True)
                return {
                    'success': True,
                    'message': "Preferences updated successfully"
                }
            except Exception as e:
                self.logger.error(f"Preferences update error: {e}", exc_info=True)
                span.record_exception(e)
                span.set_attribute("update.success", False)
                span.set_attribute("error", str(e))
                return {
                    'success': False,
                    'error': "Preferences update failed"
                }

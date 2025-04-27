# source/db/profile_db.py
import logging
from opentelemetry import trace

from source.utils.tracing import optional_trace_span
from source.db.base_manager import BaseDatabaseManager

logger = logging.getLogger('profile_db')

class ProfileDatabaseManager(BaseDatabaseManager):
    async def get_user_profile(self, user_id):
        """Get user profile data"""
        with optional_trace_span(self.tracer, "db_get_user_profile") as span:
            span.set_attribute("user_id", str(user_id))
            
            if not self.pool:
                await self.connect()

            query = """
                SELECT user_id, display_name, bio, profile_picture_url, 
                       preferences, metadata, updated_at
                FROM auth.user_profiles
                WHERE user_id = $1
            """
            span.set_attribute("db.statement", query)

            try:
                async with self.pool.acquire() as conn:
                    row = await conn.fetchrow(query, user_id)
                    result = dict(row) if row else None
                    span.set_attribute("success", result is not None)
                    span.set_attribute("profile_found", result is not None)
                    return result
            except Exception as e:
                span.record_exception(e)
                span.set_attribute("success", False)
                span.set_attribute("error", str(e))
                logger.error(f"Error getting user profile: {e}")
                return None

    async def update_user_profile(self, user_id, profile_data):
        """Update user profile"""
        with optional_trace_span(self.tracer, "db_update_user_profile") as span:
            span.set_attribute("user_id", str(user_id))
            
            if not self.pool:
                await self.connect()

            # First update user table
            user_query = """
                UPDATE auth.users
                SET username = COALESCE($2, username),
                    email = COALESCE($3, email),
                    first_name = COALESCE($4, first_name),
                    last_name = COALESCE($5, last_name),
                    email_verified = COALESCE($6, email_verified)
                WHERE id = $1
            """
            span.set_attribute("db.statement.user", user_query)
            
            # Then update profile table
            profile_query = """
                UPDATE auth.user_profiles
                SET display_name = COALESCE($2, display_name),
                    bio = COALESCE($3, bio),
                    profile_picture_url = COALESCE($4, profile_picture_url),
                    preferences = COALESCE(preferences || $5, preferences),
                    updated_at = NOW()
                WHERE user_id = $1
            """
            span.set_attribute("db.statement.profile", profile_query)

            try:
                async with self.pool.acquire() as conn:
                    # Start transaction
                    async with conn.transaction():
                        # Update user data
                        await conn.execute(
                            user_query, 
                            user_id,
                            profile_data.get('username'),
                            profile_data.get('email'),
                            profile_data.get('first_name'),
                            profile_data.get('last_name'),
                            profile_data.get('email_verified')
                        )
                        
                        # Update profile data
                        await conn.execute(
                            profile_query,
                            user_id,
                            profile_data.get('display_name'),
                            profile_data.get('bio'),
                            profile_data.get('profile_picture_url'),
                            profile_data.get('preferences', {})
                        )
                    
                    span.set_attribute("success", True)
            except Exception as e:
                span.record_exception(e)
                span.set_attribute("success", False)
                span.set_attribute("error", str(e))
                raise
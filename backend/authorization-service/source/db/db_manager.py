from source.db.base_manager import BaseDatabaseManager
from source.db.handlers.user import UserDatabaseManager
from source.db.handlers.auth import AuthDatabaseManager
from source.db.handlers.verification import VerificationDatabaseManager
from source.db.handlers.password_reset import PasswordResetDatabaseManager
from source.db.handlers.feedback import FeedbackDatabaseManager


class DatabaseManager(BaseDatabaseManager):
    """
    Unified database manager that combines all database operations using composition.

    This class inherits only from BaseDatabaseManager to provide core connection
    functionality and then uses composition to include the functionality of all
    specialized database handlers.
    """

    def __init__(self):
        """Initialize the database manager."""
        super().__init__()
        self.user = UserDatabaseManager()
        self.auth = AuthDatabaseManager()
        self.verification = VerificationDatabaseManager()
        self.password_reset = PasswordResetDatabaseManager()
        self.feedback = FeedbackDatabaseManager()

        # Share the connection pool with all handlers
        for handler in [self.user, self.auth, self.verification,
                        self.password_reset, self.feedback]:
            handler.pool = None  # Will be set when connected

    async def connect(self):
        """Create the database connection pool and share it with handlers."""
        await super().connect()

        # Share the connection pool with all handlers
        for handler in [self.user, self.auth, self.verification,
                        self.password_reset, self.feedback]:
            handler.pool = self.pool

    async def initialize(self):
        """Fully initialize the database manager by establishing a connection."""
        await self.connect()
        return self

    # Forward all methods from specialized managers
    # User methods
    async def get_user_by_username(self, username):
        return await self.user.get_user_by_username(username)

    async def get_user_by_id(self, user_id):
        return await self.user.get_user_by_id(user_id)

    async def get_user_by_email(self, email):
        return await self.user.get_user_by_email(email)

    async def create_user(self, username, email, password_hash):
        return await self.user.create_user(username, email, password_hash)

    async def verify_password(self, username, password):
        return await self.user.verify_password(username, password)

    async def update_password(self, user_id, new_password_hash):
        return await self.user.update_password(user_id, new_password_hash)

    # Auth methods
    async def save_refresh_token(self, user_id, token_hash, expires_at):
        return await self.auth.save_refresh_token(user_id, token_hash, expires_at)

    async def get_refresh_token(self, token_hash):
        return await self.auth.get_refresh_token(token_hash)

    async def revoke_refresh_token(self, token_hash):
        return await self.auth.revoke_refresh_token(token_hash)

    async def revoke_all_user_tokens(self, user_id):
        return await self.auth.revoke_all_user_tokens(user_id)

    async def cleanup_expired_tokens(self):
        return await self.auth.cleanup_expired_tokens()

    # Verification methods
    async def update_verification_code(self, user_id, code, expires_at):
        return await self.verification.update_verification_code(user_id, code, expires_at)

    async def mark_email_verified(self, user_id):
        return await self.verification.mark_email_verified(user_id)

    # Password reset methods
    async def create_password_reset_token(self, user_id, token_hash, expires_at):
        return await self.password_reset.create_password_reset_token(user_id, token_hash, expires_at)

    async def get_password_reset_token(self, token_hash):
        return await self.password_reset.get_password_reset_token(token_hash)

    async def mark_reset_token_used(self, token_hash):
        return await self.password_reset.mark_reset_token_used(token_hash)

    async def cleanup_expired_reset_tokens(self):
        return await self.password_reset.cleanup_expired_reset_tokens()

    # Feedback methods
    async def save_feedback(self, user_id, feedback_type, title, content):
        return await self.feedback.save_feedback(user_id, feedback_type, title, content)

# source/core/auth_manager.py
from source.core.base_manager import BaseManager

from source.core.services.login import LoginService
from source.core.services.token import TokenService
from source.core.services.signup import SignupService
from source.core.services.password import PasswordService
from source.core.services.feedback import FeedbackService


class AuthManager(BaseManager):
    """
    Core authentication manager that delegates to specialized service classes.
    This manager acts as a facade for various authentication services.
    """

    def __init__(self, db_manager):
        super().__init__(db_manager)
        # Initialize service classes
        self.token_service = TokenService(db_manager)
        self.login_service = LoginService(db_manager, self.token_service)
        self.signup_service = SignupService(db_manager)
        self.password_service = PasswordService(db_manager)
        self.feedback_service = FeedbackService(db_manager)
        # These will be set via dependency injection
        self.email_manager = None
        self.verification_manager = None

    async def initialize(self):
        """Initialize all services"""
        await super().initialize()

        # Check dependencies
        if not self.email_manager:
            self.logger.warning("EmailManager dependency not registered")
        else:
            self.signup_service.email_manager = self.email_manager
            self.password_service.email_manager = self.email_manager

        if not self.verification_manager:
            self.logger.warning("VerificationManager dependency not registered")
        else:
            self.signup_service.verification_manager = self.verification_manager
            self.password_service.verification_manager = self.verification_manager

        # Initialize token cleanup process
        await self.token_service.initialize()
        return self

    async def cleanup(self):
        """Clean up all services"""
        self.logger.info("Cleaning up AuthManager...")
        await self.token_service.cleanup()
        await super().cleanup()
        return self

    # Delegating methods to appropriate services

    async def login(self, username, password):
        """Authenticate a user and generate tokens"""
        return await self.login_service.login(username, password)

    async def logout(self, access_token, refresh_token=None, logout_all=False):
        """Handle logout request"""
        return await self.token_service.logout(access_token, refresh_token, logout_all)

    async def refresh_token(self, refresh_token):
        """Handle token refresh request"""
        return await self.token_service.refresh_token(refresh_token)

    async def validate_token(self, token):
        """Validate an access token"""
        return await self.token_service.validate_token(token)

    async def signup(self, username, email, password):
        """Handle signup request"""
        return await self.signup_service.signup(username, email, password)

    async def verify_email(self, user_id, verification_code):
        """Handle email verification request"""
        return await self.signup_service.verify_email(user_id, verification_code)

    async def resend_verification(self, user_id):
        """Resend verification email"""
        return await self.signup_service.resend_verification(user_id)

    async def forgot_username(self, email):
        """Handle forgot username request"""
        return await self.password_service.forgot_username(email)

    async def forgot_password(self, email):
        """Handle forgot password request"""
        return await self.password_service.forgot_password(email)

    async def reset_password(self, reset_token, new_password):
        """Handle password reset request"""
        return await self.password_service.reset_password(reset_token, new_password)

    async def submit_feedback(self, user_id, feedback_type, title, content):
        """Handle feedback submission"""
        return await self.feedback_service.submit_feedback(user_id, feedback_type, title, content)

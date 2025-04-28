# source/core/verification_manager.py
import random
import string
import secrets
import hashlib
from datetime import datetime, timedelta

from source.core.base_manager import BaseManager
from source.utils.tracing import optional_trace_span


class VerificationManager(BaseManager):
    def __init__(self, db_manager):
        super().__init__(db_manager)
        self.code_length = 6
        self.code_expiry = 3600  # 1 hour in seconds

    def generate_verification_code(self):
        """Generate a numeric verification code"""
        with optional_trace_span(self.tracer, "generate_verification_code") as span:
            # Generate a 6-digit code
            code = ''.join(random.choices(string.digits, k=self.code_length))
            span.set_attribute("code_length", self.code_length)
            return code

    def generate_token(self):
        """Generate a secure token for password reset"""
        with optional_trace_span(self.tracer, "generate_token") as span:
            token = secrets.token_urlsafe(32)
            span.set_attribute("token_length", len(token))
            return token

    def hash_token(self, token):
        """Hash a token for storage"""
        with optional_trace_span(self.tracer, "hash_token") as span:
            hash_obj = hashlib.sha256(token.encode())
            hashed = hash_obj.hexdigest()
            span.set_attribute("hash_length", len(hashed))
            return hashed

    async def create_email_verification(self, user_id, email):
        """Create and store email verification code"""
        with optional_trace_span(self.tracer, "create_email_verification") as span:
            span.set_attribute("user_id", str(user_id))

            # Generate verification code
            code = self.generate_verification_code()
            expires_at = datetime.utcnow() + timedelta(seconds=self.code_expiry)

            # Store verification code
            await self.db.update_verification_code(user_id, code, expires_at)

            span.set_attribute("verification_created", True)
            return code

    async def verify_email_code(self, user_id, code):
        """Verify an email verification code"""
        with optional_trace_span(self.tracer, "verify_email_code") as span:
            span.set_attribute("user_id", str(user_id))

            # Get user verification info
            user = await self.db.get_user_by_id(user_id)

            if not user:
                span.set_attribute("verification_success", False)
                span.set_attribute("error", "User not found")
                return False

            # Check if code matches and is not expired
            if (user.get('verification_code') == code and
                    user.get('verification_sent_at') and
                    (datetime.utcnow() - user['verification_sent_at']).total_seconds() < self.code_expiry):
                # Mark email as verified
                await self.db.mark_email_verified(user_id)
                span.set_attribute("verification_success", True)
                return True

            span.set_attribute("verification_success", False)
            return False

    async def create_password_reset_token(self, user_id):
        """Create a password reset token"""
        with optional_trace_span(self.tracer, "create_password_reset_token") as span:
            span.set_attribute("user_id", str(user_id))

            # Generate token
            token = self.generate_token()
            token_hash = self.hash_token(token)

            # Token expires in 24 hours
            expires_at = datetime.utcnow() + timedelta(hours=24)

            # Store token hash
            await self.db.create_password_reset_token(user_id, token_hash, expires_at)

            span.set_attribute("token_created", True)
            return token

    async def verify_password_reset_token(self, token):
        """Verify a password reset token"""
        with optional_trace_span(self.tracer, "verify_password_reset_token") as span:
            # Hash the token
            token_hash = self.hash_token(token)
            span.set_attribute("token_hash_length", len(token_hash))

            # Check if token exists and is valid
            token_data = await self.db.get_password_reset_token(token_hash)

            if not token_data:
                span.set_attribute("token_valid", False)
                span.set_attribute("error", "Token not found")
                return None

            if token_data.get('is_used'):
                span.set_attribute("token_valid", False)
                span.set_attribute("error", "Token already used")
                return None

            if token_data.get('expires_at') < datetime.utcnow():
                span.set_attribute("token_valid", False)
                span.set_attribute("error", "Token expired")
                return None

            span.set_attribute("token_valid", True)
            return token_data.get('user_id')

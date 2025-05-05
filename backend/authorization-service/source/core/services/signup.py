# source/core/services/signup_service.py
from source.core.base_manager import BaseManager
from source.utils.tracing import optional_trace_span


class SignupService(BaseManager):
    """Service for handling user registration and verification"""

    def __init__(self, db_manager):
        super().__init__(db_manager)
        # These will be set via dependency injection
        self.email_manager = None
        self.verification_manager = None

    async def signup(self, username, email, password):
        """Handle user registration"""
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
                self.logger.info(f"Created user with ID: {user_id}")

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
                self.logger.error(f"Signup error: {e}", exc_info=True)
                span.record_exception(e)
                span.set_attribute("signup.success", False)
                span.set_attribute("signup.error", str(e))
                return {
                    'success': False,
                    'error': "Registration failed"
                }

    async def verify_email(self, user_id, verification_code):
        """Handle email verification request"""
        with optional_trace_span(self.tracer, "verify_email") as span:
            span.set_attribute("user_id", str(user_id))
            self.logger.info(f"Email verification request for user_id: {user_id}")
            self.logger.info(f"Verification code provided: '{verification_code}' of type {type(verification_code)}")

            try:
                # Get user info
                user = await self.db.get_user_by_id(user_id)
                
                if not user:
                    self.logger.error(f"User not found with ID: {user_id}")
                    span.set_attribute("verification.success", False)
                    span.set_attribute("verification.error", "User not found")
                    return {
                        'success': False,
                        'error': "User not found"
                    }

                self.logger.info(f"User found: {user.get('id')}, username: {user.get('username')}")
                
                if user.get('email_verified'):
                    self.logger.info(f"Email already verified for user {user_id}")
                    span.set_attribute("verification.success", False)
                    span.set_attribute("verification.error", "Email already verified")
                    return {
                        'success': False,
                        'error': "Email already verified"
                    }

                # Verify code
                self.logger.info(f"Calling verification_manager.verify_email_code for user {user_id}")
                is_valid = await self.verification_manager.verify_email_code(user_id, verification_code)
                self.logger.info(f"Verification result for user {user_id}: {is_valid}")

                if not is_valid:
                    self.logger.warning(f"Invalid or expired verification code for user {user_id}")
                    span.set_attribute("verification.success", False)
                    span.set_attribute("verification.error", "Invalid or expired verification code")
                    return {
                        'success': False,
                        'error': "Invalid or expired verification code"
                    }

                self.logger.info(f"Email verification successful for user {user_id}")
                span.set_attribute("verification.success", True)
                return {
                    'success': True,
                    'message': "Email verified successfully"
                }
            except Exception as e:
                self.logger.error(f"Email verification error for user {user_id}: {e}", exc_info=True)
                span.record_exception(e)
                span.set_attribute("verification.success", False)
                span.set_attribute("verification.error", str(e))
                return {
                    'success': False,
                    'error': "Email verification failed"
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
                self.logger.error(f"Resend verification error: {e}", exc_info=True)
                span.record_exception(e)
                span.set_attribute("resend.success", False)
                span.set_attribute("resend.error", str(e))
                return {
                    'success': False,
                    'error': "Failed to resend verification email"
                }

    async def _hash_password(self, password):
        """Generate a secure password hash"""
        # Use bcrypt through the PostgreSQL crypt function
        async with self.db.pool.acquire() as conn:
            query = "SELECT crypt($1, gen_salt('bf'))"
            return await conn.fetchval(query, password)

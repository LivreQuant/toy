# source/core/token_manager.py
import jwt
import uuid
import datetime
import os
import hashlib
import logging
from opentelemetry import trace

from source.utils.tracing import optional_trace_span

logger = logging.getLogger('token_manager')


class TokenManager:
    def __init__(self):
        # Load secrets from environment or secure storage
        self.jwt_secret = os.getenv('JWT_SECRET', 'dev-secret-key')
        self.refresh_secret = os.getenv('JWT_REFRESH_SECRET', 'dev-refresh-secret-key')
        self.access_token_expiry = int(os.getenv('ACCESS_TOKEN_EXPIRY', '3600'))  # 1 hour
        self.refresh_token_expiry = int(os.getenv('REFRESH_TOKEN_EXPIRY', '2592000'))  # 30 days
        self.tracer = trace.get_tracer("token_manager")

    def generate_tokens(self, user_id, user_role='user'):
        """Generate access and refresh tokens"""
        with optional_trace_span(self.tracer, "generate_tokens") as span:
            span.set_attribute("user.id", str(user_id))
            span.set_attribute("user.role", user_role)
            
            # Generate access token
            access_token_expires = datetime.datetime.utcnow() + datetime.timedelta(seconds=self.access_token_expiry)
            access_token_payload = {
                'user_id': user_id,
                'user_role': user_role,
                'exp': access_token_expires,
                'iat': datetime.datetime.utcnow(),
                'jti': str(uuid.uuid4()),
                'token_type': 'access'
            }
            access_token = jwt.encode(access_token_payload, self.jwt_secret, algorithm='HS256')
            span.set_attribute("access_token.jti", access_token_payload['jti'])

            # Generate refresh token
            refresh_token_expires = datetime.datetime.utcnow() + datetime.timedelta(seconds=self.refresh_token_expiry)
            refresh_token_payload = {
                'user_id': user_id,
                'exp': refresh_token_expires,
                'iat': datetime.datetime.utcnow(),
                'jti': str(uuid.uuid4()),
                'token_type': 'refresh'
            }
            refresh_token = jwt.encode(refresh_token_payload, self.refresh_secret, algorithm='HS256')
            span.set_attribute("refresh_token.jti", refresh_token_payload['jti'])

            return {
                'accessToken': access_token,
                'refreshToken': refresh_token,
                'expiresIn': self.access_token_expiry,
                'expires_at': int(access_token_expires.timestamp())
            }

    def validate_access_token(self, token):
        """Validate an access token"""
        with optional_trace_span(self.tracer, "validate_access_token") as span:
            try:
                payload = jwt.decode(token, self.jwt_secret, algorithms=['HS256'])

                # Check token type for additional security
                if payload.get('token_type') != 'access':
                    logger.warning(f"Wrong token type: {payload.get('token_type')}")
                    span.set_attribute("error", "Wrong token type")
                    span.set_attribute("valid", False)
                    return {'valid': False}

                span.set_attribute("user.id", str(payload.get('user_id')))
                span.set_attribute("user.role", payload.get('user_role', 'user'))
                span.set_attribute("valid", True)
                
                return {
                    'valid': True,
                    'user_id': payload.get('user_id'),
                    'user_role': payload.get('user_role', 'user')
                }
            except jwt.ExpiredSignatureError:
                logger.warning(f"Token expired: {token[:10]}...")
                span.set_attribute("error", "Token expired")
                span.set_attribute("valid", False)
                return {'valid': False, 'error': 'Token expired'}
            except jwt.InvalidTokenError as e:
                logger.warning(f"Invalid token: {e}")
                span.set_attribute("error", str(e))
                span.set_attribute("valid", False)
                return {'valid': False, 'error': str(e)}
            except Exception as e:
                logger.error(f"Token validation error: {e}")
                span.record_exception(e)
                span.set_attribute("error", str(e))
                span.set_attribute("valid", False)
                return {'valid': False, 'error': 'Validation error'}

    def validate_refresh_token(self, token):
        """Validate a refresh token"""
        with optional_trace_span(self.tracer, "validate_refresh_token") as span:
            try:
                payload = jwt.decode(token, self.refresh_secret, algorithms=['HS256'])

                # Check token type
                if payload.get('token_type') != 'refresh':
                    logger.warning(f"Wrong token type for refresh: {payload.get('token_type')}")
                    span.set_attribute("error", "Wrong token type")
                    span.set_attribute("valid", False)
                    return {'valid': False}

                span.set_attribute("user.id", str(payload.get('user_id')))
                span.set_attribute("valid", True)
                
                return {
                    'valid': True,
                    'user_id': payload.get('user_id')
                }
            except jwt.ExpiredSignatureError:
                span.set_attribute("error", "Refresh token expired")
                span.set_attribute("valid", False)
                return {'valid': False, 'error': 'Refresh token expired'}
            except jwt.InvalidTokenError as e:
                span.set_attribute("error", str(e))
                span.set_attribute("valid", False)
                return {'valid': False, 'error': str(e)}
            except Exception as e:
                logger.error(f"Refresh token validation error: {e}")
                span.record_exception(e)
                span.set_attribute("error", str(e))
                span.set_attribute("valid", False)
                return {'valid': False, 'error': 'Validation error'}

    def hash_token(self, token):
        """Create a secure hash of a token for storage"""
        with optional_trace_span(self.tracer, "hash_token") as span:
            hashed = hashlib.sha256(token.encode()).hexdigest()
            span.set_attribute("hash_length", len(hashed))
            return hashed

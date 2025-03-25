# source/core/token_manager.py
import jwt
import uuid
import datetime
import os
import hashlib
import logging

logger = logging.getLogger('token_manager')


class TokenManager:
    def __init__(self):
        # Load secrets from environment or secure storage
        self.jwt_secret = os.getenv('JWT_SECRET', 'dev-secret-key')
        self.refresh_secret = os.getenv('JWT_REFRESH_SECRET', 'dev-refresh-secret-key')
        self.access_token_expiry = int(os.getenv('ACCESS_TOKEN_EXPIRY', '3600'))  # 1 hour
        self.refresh_token_expiry = int(os.getenv('REFRESH_TOKEN_EXPIRY', '2592000'))  # 30 days

    def generate_tokens(self, user_id, user_role='user'):
        """Generate access and refresh tokens"""
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

        return {
            'accessToken': access_token,
            'refreshToken': refresh_token,
            'expiresIn': self.access_token_expiry,
            'expires_at': int(access_token_expires.timestamp())
        }

    def validate_access_token(self, token):
        """Validate an access token"""
        try:
            payload = jwt.decode(token, self.jwt_secret, algorithms=['HS256'])

            # Check token type for additional security
            if payload.get('token_type') != 'access':
                logger.warning(f"Wrong token type: {payload.get('token_type')}")
                return {'valid': False}

            return {
                'valid': True,
                'user_id': payload.get('user_id'),
                'user_role': payload.get('user_role', 'user')
            }
        except jwt.ExpiredSignatureError:
            logger.warning(f"Token expired: {token[:10]}...")
            return {'valid': False, 'error': 'Token expired'}
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid token: {e}")
            return {'valid': False, 'error': str(e)}
        except Exception as e:
            logger.error(f"Token validation error: {e}")
            return {'valid': False, 'error': 'Validation error'}

    def validate_refresh_token(self, token):
        """Validate a refresh token"""
        try:
            payload = jwt.decode(token, self.refresh_secret, algorithms=['HS256'])

            # Check token type
            if payload.get('token_type') != 'refresh':
                logger.warning(f"Wrong token type for refresh: {payload.get('token_type')}")
                return {'valid': False}

            return {
                'valid': True,
                'user_id': payload.get('user_id')
            }
        except jwt.ExpiredSignatureError:
            return {'valid': False, 'error': 'Refresh token expired'}
        except jwt.InvalidTokenError as e:
            return {'valid': False, 'error': str(e)}
        except Exception as e:
            logger.error(f"Refresh token validation error: {e}")
            return {'valid': False, 'error': 'Validation error'}

    def hash_token(self, token):
        """Create a secure hash of a token for storage"""
        return hashlib.sha256(token.encode()).hexdigest()

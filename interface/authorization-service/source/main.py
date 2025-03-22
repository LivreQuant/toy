# interface/authorization-service/source/main.py
import os
import jwt
import uuid
import datetime
import logging
import grpc
import time
from concurrent import futures
import psycopg2
from psycopg2.extras import DictCursor
import hashlib

# Import gRPC generated code
import auth_pb2
import auth_pb2_grpc

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('auth_service')

# Configuration from environment variables
JWT_SECRET = os.getenv('JWT_SECRET', 'dev-secret-key')
JWT_REFRESH_SECRET = os.getenv('JWT_REFRESH_SECRET', 'dev-refresh-secret-key')
ACCESS_TOKEN_EXPIRY = int(os.getenv('ACCESS_TOKEN_EXPIRY', '3600'))  # 1 hour in seconds
REFRESH_TOKEN_EXPIRY = int(os.getenv('REFRESH_TOKEN_EXPIRY', '2592000'))  # 30 days in seconds

# Database config
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'postgres'),
    'port': os.getenv('DB_PORT', '5432'),
    'dbname': os.getenv('DB_NAME', 'opentp'),
    'user': os.getenv('DB_USER', 'opentp'),
    'password': os.getenv('DB_PASSWORD', 'samaral')
}

class DatabaseManager:
    def __init__(self):
        self.db_config = DB_CONFIG
        self.connection = None
        self.connect()
    
    def connect(self):
        try:
            self.connection = psycopg2.connect(**self.db_config)
            self.connection.autocommit = True
            logger.info("Database connection established")
        except Exception as e:
            logger.error(f"Database connection failed: {e}")
            raise
    
    def execute(self, query, params=None, fetch=False):
        try:
            with self.connection.cursor(cursor_factory=DictCursor) as cursor:
                cursor.execute(query, params or ())
                if fetch:
                    return cursor.fetchall()
                return None
        except (psycopg2.OperationalError, psycopg2.InterfaceError) as e:
            # Connection may have timed out, try to reconnect
            logger.warning(f"Database connection error, attempting to reconnect: {e}")
            self.connect()
            
            # Retry once with new connection
            with self.connection.cursor(cursor_factory=DictCursor) as cursor:
                cursor.execute(query, params or ())
                if fetch:
                    return cursor.fetchall()
                return None
    
    def close(self):
        if self.connection:
            self.connection.close()
            logger.info("Database connection closed")

    def get_user_by_username(self, username):
        query = """
            SELECT id, username, password_hash, is_active, role
            FROM auth.users
            WHERE username = %s
        """
        result = self.execute(query, (username,), fetch=True)
        return dict(result[0]) if result else None
    
    def get_user_by_id(self, user_id):
        query = """
            SELECT id, username, is_active, role
            FROM auth.users
            WHERE id = %s
        """
        result = self.execute(query, (user_id,), fetch=True)
        return dict(result[0]) if result else None
    
    def save_refresh_token(self, user_id, token_hash, expires_at):
        query = """
            INSERT INTO auth.refresh_tokens
            (user_id, token_hash, expires_at, created_at)
            VALUES (%s, %s, %s, NOW())
        """
        self.execute(query, (user_id, token_hash, expires_at))
    
    def get_refresh_token(self, token_hash):
        query = """
            SELECT user_id, expires_at
            FROM auth.refresh_tokens
            WHERE token_hash = %s AND expires_at > NOW() AND is_revoked = FALSE
        """
        result = self.execute(query, (token_hash,), fetch=True)
        return dict(result[0]) if result else None
    
    def revoke_refresh_token(self, token_hash):
        query = """
            UPDATE auth.refresh_tokens
            SET is_revoked = TRUE
            WHERE token_hash = %s
        """
        self.execute(query, (token_hash,))
    
    def revoke_all_user_tokens(self, user_id):
        query = """
            UPDATE auth.refresh_tokens
            SET is_revoked = TRUE
            WHERE user_id = %s
        """
        self.execute(query, (user_id,))
    
    def verify_password(self, username, password):
        query = """
            SELECT * FROM auth.verify_password(%s, %s)
        """
        result = self.execute(query, (username, password), fetch=True)
        return dict(result[0]) if result else None
    
    def cleanup_expired_tokens(self):
        query = """
            DELETE FROM auth.refresh_tokens
            WHERE expires_at < NOW() OR is_revoked = TRUE
        """
        self.execute(query)

# First, let's create or update the necessary database schema
def ensure_db_schema(db):
    # Check if refresh_tokens table exists and create if not
    schema_query = """
    DO $$
    BEGIN
        -- Create refresh_tokens table if it doesn't exist
        IF NOT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_schema = 'auth' AND table_name = 'refresh_tokens'
        ) THEN
            CREATE TABLE auth.refresh_tokens (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
                token_hash TEXT NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
                is_revoked BOOLEAN DEFAULT FALSE,
                CONSTRAINT unique_token UNIQUE (token_hash)
            );
            
            -- Add index for token lookup
            CREATE INDEX idx_refresh_token_hash ON auth.refresh_tokens(token_hash);
            
            -- Add index for user_id for faster revocation
            CREATE INDEX idx_refresh_token_user_id ON auth.refresh_tokens(user_id);
        END IF;
        
        -- Add cleanup function if it doesn't exist
        IF NOT EXISTS (
            SELECT FROM pg_proc 
            WHERE proname = 'cleanup_expired_tokens' AND pronamespace = 'auth'::regnamespace
        ) THEN
            CREATE OR REPLACE FUNCTION auth.cleanup_expired_tokens()
            RETURNS void AS $$
            BEGIN
                DELETE FROM auth.refresh_tokens 
                WHERE expires_at < NOW() OR is_revoked = TRUE;
            END;
            $$ LANGUAGE plpgsql;
        END IF;
    END
    $$;
    """
    db.execute(schema_query)
    logger.info("Database schema verified")

class AuthServicer(auth_pb2_grpc.AuthServiceServicer):
    def __init__(self, db_manager):
        self.db = db_manager
        ensure_db_schema(self.db)
        
        # Start a background task to clean up expired tokens periodically
        self.cleanup_thread = threading.Thread(target=self._cleanup_expired_tokens, daemon=True)
        self.cleanup_thread.start()
    
    def _cleanup_expired_tokens(self):
        """Background task to clean up expired tokens"""
        while True:
            try:
                # Run cleanup every 6 hours
                time.sleep(6 * 60 * 60)
                logger.info("Running expired token cleanup")
                self.db.cleanup_expired_tokens()
            except Exception as e:
                logger.error(f"Error in token cleanup: {e}")
    
    def Login(self, request, context):
        username = request.username
        password = request.password
        
        try:
            # Verify username and password
            user = self.db.verify_password(username, password)
            
            if not user:
                return auth_pb2.LoginResponse(
                    success=False,
                    error_message="Invalid username or password"
                )
            
            # Generate JWT tokens
            access_token, refresh_token, expires_at = self._generate_tokens(user['user_id'], user['role'])
            
            # Hash refresh token before storing
            refresh_token_hash = self._hash_token(refresh_token)
            
            # Save refresh token to database
            refresh_token_expires = datetime.datetime.now() + datetime.timedelta(seconds=REFRESH_TOKEN_EXPIRY)
            self.db.save_refresh_token(user['user_id'], refresh_token_hash, refresh_token_expires)
            
            return auth_pb2.LoginResponse(
                success=True,
                access_token=access_token,
                refresh_token=refresh_token,
                expires_in=ACCESS_TOKEN_EXPIRY
            )
        except Exception as e:
            logger.error(f"Login error: {e}")
            return auth_pb2.LoginResponse(
                success=False,
                error_message="Authentication service error"
            )
    
    def Logout(self, request, context):
        try:
            # Get metadata
            metadata = dict(context.invocation_metadata())
            refresh_token = metadata.get('refresh_token')
            
            # Decode token without verification to get user_id
            try:
                token_data = jwt.decode(
                    request.token, 
                    options={"verify_signature": False}
                )
                user_id = token_data.get('user_id')
            except:
                user_id = None
            
            # Check if we should revoke all sessions for this user
            revoke_all = metadata.get('logout_all_sessions') == 'true'
            
            if refresh_token:
                # Revoke the specific refresh token
                refresh_token_hash = self._hash_token(refresh_token)
                self.db.revoke_refresh_token(refresh_token_hash)
                logger.info(f"Revoked refresh token for user {user_id}")
            elif user_id and revoke_all:
                # Revoke all user's refresh tokens
                self.db.revoke_all_user_tokens(user_id)
                logger.info(f"Revoked all refresh tokens for user {user_id}")
            
            return auth_pb2.LogoutResponse(success=True)
        except Exception as e:
            logger.error(f"Logout error: {e}")
            return auth_pb2.LogoutResponse(success=False)
    
    def ValidateToken(self, request, context):
        token = request.token
        
        try:
            # Verify JWT token
            payload = jwt.decode(token, JWT_SECRET, algorithms=['HS256'])
            
            # Get user info
            user_id = payload.get('user_id')
            user = self.db.get_user_by_id(user_id)
            
            if not user or not user.get('is_active', False):
                return auth_pb2.ValidateTokenResponse(valid=False)
            
            return auth_pb2.ValidateTokenResponse(
                valid=True,
                user_id=str(user_id)
            )
        except jwt.ExpiredSignatureError:
            logger.warning(f"Token expired: {token[:10]}...")
            return auth_pb2.ValidateTokenResponse(valid=False)
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid token: {e}")
            return auth_pb2.ValidateTokenResponse(valid=False)
        except Exception as e:
            logger.error(f"Token validation error: {e}")
            return auth_pb2.ValidateTokenResponse(valid=False)
    
    def RefreshToken(self, request, context):
        refresh_token = request.refresh_token
        
        try:
            # Verify refresh token
            try:
                refresh_payload = jwt.decode(refresh_token, JWT_REFRESH_SECRET, algorithms=['HS256'])
                user_id = refresh_payload.get('user_id')
                
                if not user_id:
                    return auth_pb2.RefreshTokenResponse(
                        success=False,
                        error_message="Invalid refresh token"
                    )
            except jwt.ExpiredSignatureError:
                return auth_pb2.RefreshTokenResponse(
                    success=False,
                    error_message="Refresh token expired"
                )
            except jwt.InvalidTokenError:
                return auth_pb2.RefreshTokenResponse(
                    success=False,
                    error_message="Invalid refresh token"
                )
            
            # Hash token and check if it exists in database
            token_hash = self._hash_token(refresh_token)
            token_record = self.db.get_refresh_token(token_hash)
            
            if not token_record:
                logger.warning(f"Refresh token not found or revoked for user {user_id}")
                return auth_pb2.RefreshTokenResponse(
                    success=False,
                    error_message="Invalid refresh token"
                )
            
            # Get user info
            user = self.db.get_user_by_id(user_id)
            
            if not user or not user.get('is_active', False):
                logger.warning(f"User inactive or not found: {user_id}")
                return auth_pb2.RefreshTokenResponse(
                    success=False,
                    error_message="User account inactive or not found"
                )
            
            # Generate new tokens
            role = user.get('role', 'user')
            access_token, new_refresh_token, expires_at = self._generate_tokens(user_id, role)
            
            # Revoke old refresh token
            self.db.revoke_refresh_token(token_hash)
            
            # Save new refresh token
            new_token_hash = self._hash_token(new_refresh_token)
            refresh_token_expires = datetime.datetime.now() + datetime.timedelta(seconds=REFRESH_TOKEN_EXPIRY)
            self.db.save_refresh_token(user_id, new_token_hash, refresh_token_expires)
            
            logger.info(f"Refreshed token for user {user_id}")
            
            return auth_pb2.RefreshTokenResponse(
                success=True,
                access_token=access_token,
                refresh_token=new_refresh_token,
                expires_in=ACCESS_TOKEN_EXPIRY
            )
        except Exception as e:
            logger.error(f"Token refresh error: {e}")
            return auth_pb2.RefreshTokenResponse(
                success=False,
                error_message="Authentication service error"
            )
    
    def _generate_tokens(self, user_id, role):
        # Generate access token
        access_token_expires = datetime.datetime.utcnow() + datetime.timedelta(seconds=ACCESS_TOKEN_EXPIRY)
        access_token_payload = {
            'user_id': user_id,
            'role': role,
            'exp': access_token_expires,
            'iat': datetime.datetime.utcnow(),
            'jti': str(uuid.uuid4())
        }
        access_token = jwt.encode(access_token_payload, JWT_SECRET, algorithm='HS256')
        
        # Generate refresh token
        refresh_token_payload = {
            'user_id': user_id,
            'type': 'refresh',
            'exp': datetime.datetime.utcnow() + datetime.timedelta(seconds=REFRESH_TOKEN_EXPIRY),
            'jti': str(uuid.uuid4())
        }
        refresh_token = jwt.encode(refresh_token_payload, JWT_REFRESH_SECRET, algorithm='HS256')
        
        return access_token, refresh_token, int(access_token_expires.timestamp())
    
    def _hash_token(self, token):
        # Hash the token before storing in database for security
        return hashlib.sha256(token.encode()).hexdigest()

def serve():
    # Create database manager
    db_manager = DatabaseManager()
       
    # Load server credentials
    server_key = open('certs/server.key', 'rb').read()
    server_cert = open('certs/server.crt', 'rb').read()
    ca_cert = open('certs/ca.crt', 'rb').read()
    
    # Create server credentials
    server_credentials = grpc.ssl_server_credentials(
        [(server_key, server_cert)],
        root_certificates=ca_cert,
        require_client_auth=True  # Require mutual TLS
    )
    
    # Create gRPC server
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    
    # Add servicer
    auth_servicer = AuthServicer(db_manager)
    auth_pb2_grpc.add_AuthServiceServicer_to_server(auth_servicer, server)
    
    # Start server
    port = os.getenv('GRPC_PORT', '50051')
    server.add_insecure_port(f'[::]:{port}', server_credentials)
    server.start()
    
    logger.info(f"Auth service started on port {port}")
    
    try:
        # Keep server alive
        server.wait_for_termination()
    except KeyboardInterrupt:
        # Clean shutdown
        server.stop(0)
        db_manager.close()
        logger.info("Auth service stopped")

if __name__ == '__main__':
    serve()
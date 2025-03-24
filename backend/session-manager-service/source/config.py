import os
import logging

# Configure logging
def setup_logging():
    """Configure logging for the application"""
    log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    
    logging.basicConfig(
        level=getattr(logging, log_level),
        format=log_format
    )

# Service configuration
class Config:
    """Application configuration"""
    # Core settings
    HOST = os.getenv('HOST', '0.0.0.0')
    PORT = int(os.getenv('PORT', '8080'))
    
    # Database configuration
    DB_HOST = os.getenv('DB_HOST', 'postgres')
    DB_PORT = int(os.getenv('DB_PORT', '5432'))
    DB_NAME = os.getenv('DB_NAME', 'opentp')
    DB_USER = os.getenv('DB_USER', 'opentp')
    DB_PASSWORD = os.getenv('DB_PASSWORD', 'samaral')
    DB_MIN_CONNECTIONS = int(os.getenv('DB_MIN_CONNECTIONS', '1'))
    DB_MAX_CONNECTIONS = int(os.getenv('DB_MAX_CONNECTIONS', '10'))
    
    # Service endpoints - Updated to use REST for auth service
    AUTH_SERVICE_URL = os.getenv('AUTH_SERVICE_URL', 'http://auth-service:8000')
    EXCHANGE_MANAGER_SERVICE = os.getenv('EXCHANGE_MANAGER_SERVICE', 'exchange-manager-service:50053')
    
    # Session settings
    SESSION_TIMEOUT_SECONDS = int(os.getenv('SESSION_TIMEOUT_SECONDS', '3600'))  # 1 hour
    SESSION_EXTENSION_THRESHOLD = int(os.getenv('SESSION_EXTENSION_THRESHOLD', '1800'))  # 30 minutes
    
    # WebSocket settings
    WEBSOCKET_HEARTBEAT_INTERVAL = int(os.getenv('WEBSOCKET_HEARTBEAT_INTERVAL', '10'))  # 10 seconds
    
    # SSE settings
    SSE_KEEPALIVE_INTERVAL = int(os.getenv('SSE_KEEPALIVE_INTERVAL', '15'))  # 15 seconds
    
    # Kubernetes settings
    KUBERNETES_NAMESPACE = os.getenv('KUBERNETES_NAMESPACE', 'default')
    POD_NAME = os.getenv('POD_NAME', os.getenv('HOSTNAME', 'unknown'))

# Create config instance
config = Config()
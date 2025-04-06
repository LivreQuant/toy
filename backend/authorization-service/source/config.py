# source/config.py
import os


class Config:
    # Environment
    ENVIRONMENT = os.getenv('ENVIRONMENT', 'development')

    # Database Configuration
    DB_CONFIG = {
        'host': os.getenv('DB_HOST', 'postgres'),
        'port': int(os.getenv('DB_PORT', '5432')),
        'database': os.getenv('DB_NAME', 'opentp'),
        'user': os.getenv('DB_USER', 'opentp'),
        'password': os.getenv('DB_PASSWORD', 'samaral')
    }
    DB_MIN_CONNECTIONS = int(os.getenv('DB_MIN_CONNECTIONS', '1'))
    DB_MAX_CONNECTIONS = int(os.getenv('DB_MAX_CONNECTIONS', '10'))

    # Tracing Configuration
    ENABLE_TRACING = os.getenv('ENABLE_TRACING', 'true').lower() == 'true'

    # Service Configuration
    REST_PORT = int(os.getenv('REST_PORT', '8001'))
    AUTH_SERVICE_URL = os.getenv('AUTH_SERVICE_URL', 'http://auth-service:8000')

    # JWT Configuration
    JWT_SECRET = os.getenv('JWT_SECRET', 'dev-secret-key')
    JWT_REFRESH_SECRET = os.getenv('JWT_REFRESH_SECRET', 'dev-refresh-secret-key')
    ACCESS_TOKEN_EXPIRY = int(os.getenv('ACCESS_TOKEN_EXPIRY', '3600'))  # 1 hour default
    REFRESH_TOKEN_EXPIRY = int(os.getenv('REFRESH_TOKEN_EXPIRY', '2592000'))  # 30 days default

    # Security
    TOKEN_CLEANUP_INTERVAL = int(os.getenv('TOKEN_CLEANUP_INTERVAL', '21600'))  # 6 hours default

    # Logging
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')

    # Cookie settings
    COOKIE_SECURE = ENVIRONMENT == 'production'
    COOKIE_HTTPONLY = True
    COOKIE_SAMESITE = 'Strict'
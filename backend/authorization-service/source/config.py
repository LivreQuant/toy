# source/config.py
import os
from pathlib import Path
import logging
from dotenv import load_dotenv

# Setup logging
logger = logging.getLogger('config')

# Determine environment
ENV = os.environ.get('ENVIRONMENT', 'development')
IS_PRODUCTION = ENV == 'production'

# Load environment variables from files in development
if not IS_PRODUCTION:
    # Try to load from .env.local first, then fall back to .env
    env_path = Path('.') / '.env.local'
    if not env_path.exists():
        env_path = Path('.') / '.env'
    
    # Load the env file if it exists
    if env_path.exists():
        logger.info(f"Loading environment from {env_path}")
        load_dotenv(dotenv_path=env_path)
    else:
        logger.warning("No .env file found, using system environment variables")


class Config:
    # Environment
    ENVIRONMENT = ENV

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

    # API Keys and Secrets
    MAILGUN_API_KEY = os.getenv('MAILGUN_API_KEY', '')
    MAILGUN_DOMAIN = os.getenv('MAILGUN_DOMAIN', '')
    MAILGUN_SENDER = os.getenv('MAILGUN_SENDER', '')

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
    COOKIE_SECURE = IS_PRODUCTION
    COOKIE_HTTPONLY = True
    COOKIE_SAMESITE = 'Strict'
    
    @classmethod
    def validate_config(cls):
        """Validate critical configuration settings"""
        is_valid = True
        
        # In production, ensure we have real secrets, not defaults
        if IS_PRODUCTION:
            if cls.JWT_SECRET == 'dev-secret-key':
                logger.error("PRODUCTION WARNING: Using default JWT_SECRET")
                is_valid = False
                
            if cls.JWT_REFRESH_SECRET == 'dev-refresh-secret-key':
                logger.error("PRODUCTION WARNING: Using default JWT_REFRESH_SECRET")
                is_valid = False
                
            if not cls.MAILGUN_API_KEY:
                logger.error("PRODUCTION WARNING: MAILGUN_API_KEY not set")
                is_valid = False
        
        return is_valid


# Validate configuration
Config.validate_config()
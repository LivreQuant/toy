# backend/fund-service/source/config.py
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class Config:
    """Application configuration."""

    # Environment
    environment = os.getenv('ENVIRONMENT', 'development')

    # Server settings
    rest_port = int(os.getenv('REST_PORT', '8001'))
    host = os.getenv('HOST', '0.0.0.0')

    # Database Configuration
    db_host = os.getenv('DB_HOST', 'postgres')
    db_port = int(os.getenv('DB_PORT', '5432'))
    db_name = os.getenv('DB_NAME', 'opentp')
    db_user = os.getenv('DB_USER', 'opentp')
    db_password = os.getenv('DB_PASSWORD', 'samaral')
    db_min_connections = int(os.getenv('DB_MIN_CONNECTIONS', '10'))
    db_max_connections = int(os.getenv('DB_MAX_CONNECTIONS', '100'))

    # Authentication Service
    auth_service_url = os.getenv('AUTH_SERVICE_URL', 'http://auth-service:8000')
    
    # Logging
    log_level = os.getenv('LOG_LEVEL', 'INFO')

    # Performance settings
    request_timeout = int(os.getenv('REQUEST_TIMEOUT', '30'))

    # Feature flags
    enable_metrics = os.getenv('ENABLE_METRICS', 'true').lower() == 'true'
    enable_tracing = os.getenv('ENABLE_TRACING', 'true').lower() == 'true'

    # Crypto/Blockchain Configuration
    
    # Algorand node connection
    algod_token = os.getenv('ALGOD_TOKEN', 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa')
    algod_server = os.getenv('ALGOD_SERVER', 'http://localhost')
    algod_port = os.getenv('ALGOD_PORT', '4001')

    indexer_token = os.getenv('INDEXER_TOKEN', 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa')
    indexer_server = os.getenv('INDEXER_SERVER', 'http://localhost')
    indexer_port = os.getenv('INDEXER_PORT', '8980')

    # Admin wallet (deployer)
    admin_mnemonic = os.getenv('ADMIN_MNEMONIC')

    # Security settings
    secret_pass_phrase = os.getenv('SECRET_PASS_PHRASE')
    encrypt_wallets = True if secret_pass_phrase else False
    encrypt_private_keys = True if secret_pass_phrase else False

    # Smart contract settings
    default_funding_amount = 1_000_000  # 1 Algo in microAlgos

    # Default parameters
    default_params_str = "region:NA|asset_class:EQUITIES|instrument_class:STOCKS"

    @property
    def db_connection_string(self) -> str:
        """Get PostgreSQL connection string"""
        return f"postgres://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"

    @property
    def is_production(self) -> bool:
        """Check if running in production environment"""
        return self.environment.lower() == 'production'


# Create global instance
config = Config()
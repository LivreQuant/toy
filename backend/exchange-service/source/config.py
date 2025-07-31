# source/config.py
import os
from dataclasses import dataclass
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


@dataclass
class DatabaseConfig:
    """Database configuration"""
    host: str
    port: int
    database: str
    user: str
    password: str
    min_connections: int
    max_connections: int

    @property
    def connection_string(self) -> str:
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"


class Config:
    """Application configuration."""

    def __init__(self):
        self.environment = os.getenv('ENVIRONMENT', 'development')

        # FORCE the data directory to be relative to project root, not source/
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.data_directory = os.path.join(project_root, 'data')

        self.log_level = os.getenv('LOG_LEVEL', 'INFO')

        # Database configuration
        self.database = self._get_database_config()

        # SIMPLE RULE: Production = Database, Development = Files
        if self.is_production:
            self.use_database_storage = True
        else:
            self.use_database_storage = False

        # Log the configuration
        print(f"🔧 Environment: {self.environment}")
        print(f"🔧 Storage: {'DATABASE' if self.use_database_storage else 'FILES'}")

        # Rest of config...
        self.rest_port = int(os.getenv('REST_PORT', '8001'))
        self.host = os.getenv('HOST', '0.0.0.0')
        self.auth_service_url = os.getenv('AUTH_SERVICE_URL', 'http://auth-service:8000')
        self.request_timeout = int(os.getenv('REQUEST_TIMEOUT', '30'))
        self.enable_metrics = os.getenv('ENABLE_METRICS', 'true').lower() == 'true'
        self.enable_tracing = os.getenv('ENABLE_TRACING', 'true').lower() == 'true'

        self.algod_token = os.getenv('ALGOD_TOKEN', 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa')
        self.algod_server = os.getenv('ALGOD_SERVER', 'http://localhost')
        self.algod_port = os.getenv('ALGOD_PORT', '4001')
        self.indexer_token = os.getenv('INDEXER_TOKEN', 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa')
        self.indexer_server = os.getenv('INDEXER_SERVER', 'http://localhost')
        self.indexer_port = os.getenv('INDEXER_PORT', '8980')
        self.admin_mnemonic = os.getenv('ADMIN_MNEMONIC')
        self.secret_pass_phrase = os.getenv('SECRET_PASS_PHRASE')
        self.encrypt_wallets = True if self.secret_pass_phrase else False
        self.encrypt_private_keys = True if self.secret_pass_phrase else False
        self.default_funding_amount = 1_000_000
        self.default_params_str = "region:NA|asset_class:EQUITIES|instrument_class:STOCKS"

    def _get_database_config(self) -> DatabaseConfig:
        """Get database configuration"""
        return DatabaseConfig(
            host=os.getenv('DB_HOST', 'localhost'),
            port=int(os.getenv('DB_PORT', '5432')),
            database=os.getenv('DB_NAME', 'opentp'),
            user=os.getenv('DB_USER', 'opentp'),
            password=os.getenv('DB_PASSWORD', 'samaral'),
            min_connections=int(os.getenv('DB_MIN_CONNECTIONS', '5')),
            max_connections=int(os.getenv('DB_MAX_CONNECTIONS', '20'))
        )

    @property
    def db_connection_string(self) -> str:
        """Get database connection string for backward compatibility"""
        return self.database.connection_string

    @property
    def is_development(self) -> bool:
        """Check if running in development environment"""
        return self.environment.lower() == 'development'

    @property
    def is_production(self) -> bool:
        """Check if running in production environment"""
        return self.environment.lower() == 'production'


# Global configuration instance
app_config = Config()
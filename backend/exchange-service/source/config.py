# source/config.py - Updated to integrate with new architecture
import os
from dataclasses import dataclass
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from typing import List

# Load environment variables
load_dotenv()


class SimulatorConfig(BaseModel):
    """Simulator configuration for backward compatibility and user management"""
    user_id: str = Field(default=os.getenv('USER_ID', 'test'))
    desk_id: str = Field(default=os.getenv('DESK_ID', 'test'))
    default_symbols: List[str] = Field(default=['AAPL', 'GOOGL', 'MSFT', 'AMZN'])
    initial_cash: float = Field(default=100_000.0)


class ServerConfig(BaseModel):
    host: str = Field(default="0.0.0.0")
    grpc_port: int = Field(default=50055)
    http_port: int = Field(default=50056)


class MetricsConfig(BaseModel):
    enabled: bool = Field(default=True)
    port: int = Field(default=9090)


class TracingConfig(BaseModel):
    enabled: bool = Field(default=True)
    service_name: str = Field(default="exchange-simulator")
    otlp_endpoint: str = Field(default="http://jaeger-collector:4317")  # Updated to OTLP


class DatabaseConfig(BaseModel):
    host: str = Field(default=os.getenv('DB_HOST', 'postgres'))
    port: int = Field(default=int(os.getenv('DB_PORT', '5432')))
    database: str = Field(default=os.getenv('DB_NAME', 'opentp'))
    user: str = Field(default=os.getenv('DB_USER', 'opentp'))
    password: str = Field(default=os.getenv('DB_PASSWORD', 'samaral'))
    min_connections: int = Field(default=1)
    max_connections: int = Field(default=5)

    @property
    def connection_string(self) -> str:
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"


class MarketDataConfig(BaseModel):
    service_url: str = Field(default=os.getenv('MARKET_DATA_SERVICE_URL', 'market-data-service:50060'))


class ConvictionExchangeConfig(BaseModel):  # Renamed from OrderExchangeConfig
    service_url: str = Field(default=os.getenv('CONVICTION_EXCHANGE_SERVICE_URL', 'conviction-exchange-service:50057'))


class Config:
    """Application configuration - enhanced to support both old and new architectures."""

    def __init__(self):
        self.environment = os.getenv('ENVIRONMENT', 'development')

        # FORCE the data directory to be relative to project root, not source/
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.data_directory = os.path.join(project_root, 'data')

        self.log_level = os.getenv('LOG_LEVEL', 'INFO')

        # Add simulator config for backward compatibility
        self.simulator = SimulatorConfig()
        self.server = ServerConfig()
        self.metrics = MetricsConfig()
        self.tracing = TracingConfig()

        # Database configuration
        self.database = self._get_database_config()
        self.db = self.database  # Backward compatibility

        # Market data and conviction exchange
        self.market_data = MarketDataConfig()
        self.conviction_exchange = ConvictionExchangeConfig()
        self.order_exchange = self.conviction_exchange  # Backward compatibility

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

    @classmethod
    def from_env(cls):
        """Create config from environment variables - backward compatibility method"""
        return cls()


# Global configuration instances for backward compatibility
app_config = Config()
config = app_config  # For old-style access pattern
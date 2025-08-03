# source/config.py - Simple configuration without overcomplicated BS
import os
from dataclasses import dataclass
from pydantic import BaseModel, Field
from typing import List


class SimulatorConfig(BaseModel):
    user_id: str = Field(default=os.getenv('USER_ID', 'test'))
    desk_id: str = Field(default=os.getenv('DESK_ID', 'test'))
    default_symbols: List[str] = Field(default=['AAPL', 'GOOGL', 'MSFT', 'AMZN'])
    initial_cash: float = Field(default=100_000.0)


class ServerConfig(BaseModel):
    host: str = Field(default=os.getenv('HOST', '0.0.0.0'))
    grpc_port: int = Field(default=int(os.getenv('GRPC_SERVICE_PORT', '50055')))
    http_port: int = Field(default=int(os.getenv('HEALTH_SERVICE_PORT', '50056')))


class DatabaseConfig(BaseModel):
    host: str = Field(default=os.getenv('DB_HOST', 'postgres'))
    port: int = Field(default=int(os.getenv('DB_PORT', '5432')))
    database: str = Field(default=os.getenv('DB_NAME', 'opentp'))
    user: str = Field(default=os.getenv('DB_USER', 'opentp'))
    password: str = Field(default=os.getenv('DB_PASSWORD', 'samaral'))
    min_connections: int = Field(default=int(os.getenv('DB_MIN_CONNECTIONS', '5')))
    max_connections: int = Field(default=int(os.getenv('DB_MAX_CONNECTIONS', '20')))

    @property
    def connection_string(self) -> str:
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"


class Config:
    """Simple, clean configuration class"""

    def __init__(self):
        # Core settings
        self.environment = os.getenv('ENVIRONMENT', 'development')
        self.log_level = os.getenv('LOG_LEVEL', 'INFO')
        
        # Data directory
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.data_directory = os.path.join(project_root, 'data')

        # Component configs
        self.simulator = SimulatorConfig()
        self.server = ServerConfig()
        self.database = DatabaseConfig()

        # Storage strategy
        self.use_database_storage = self.is_production

        # Exchange configuration
        self.exch_id = os.getenv('EXCH_ID', '123e4567-e89b-12d3-a456-426614174000')
        self.exchange_type = os.getenv('EXCHANGE_TYPE', 'US_EQUITIES')

        # Service configuration
        self.host = os.getenv('HOST', '0.0.0.0')
        self.grpc_service_port = int(os.getenv('GRPC_SERVICE_PORT', '50055'))
        self.health_service_port = int(os.getenv('HEALTH_SERVICE_PORT', '50056'))
        
        # Feature flags
        self.enable_metrics = os.getenv('ENABLE_METRICS', 'true').lower() == 'true'
        self.enable_tracing = os.getenv('ENABLE_TRACING', 'true').lower() == 'true'
        self.enable_session_service = os.getenv('ENABLE_SESSION_SERVICE', 'true').lower() == 'true'
        self.enable_conviction_service = os.getenv('ENABLE_CONVICTION_SERVICE', 'false').lower() == 'true'

        # Service URLs
        self.market_data_service_url = os.getenv('MARKET_DATA_SERVICE_URL', 'localhost:50060')
        self.auth_service_url = os.getenv('AUTH_SERVICE_URL', 'http://auth-service:8000')

        # Backward compatibility
        self.db = self.database
        self.rest_port = self.health_service_port

        print(f"🔧 Environment: {self.environment}")
        print(f"🔧 Storage: {'DATABASE' if self.use_database_storage else 'FILES'}")

    @property
    def db_connection_string(self) -> str:
        return self.database.connection_string

    @property
    def is_development(self) -> bool:
        return self.environment.lower() == 'development'

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == 'production'

    @classmethod
    def from_env(cls):
        return cls()


# Global config instance
app_config = Config()
config = app_config
import os
import random
from typing import List
from pydantic import BaseModel, Field

class SimulatorConfig(BaseModel):
    default_symbols: List[str] = Field(default_factory=lambda: ['AAPL', 'GOOGL', 'MSFT', 'AMZN', 'TSLA'])
    initial_cash: float = Field(default=100000.0)
    min_price: float = Field(default=50.0)
    max_price: float = Field(default=1000.0)
    volatility: float = Field(default=0.02)

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
    jaeger_endpoint: str = Field(default="http://jaeger-collector:14268/api/traces")

class DatabaseConfig(BaseModel):
    host: str = Field(default=os.getenv('DB_HOST', 'postgres'))
    port: int = Field(default=int(os.getenv('DB_PORT', '5432')))
    database: str = Field(default=os.getenv('DB_NAME', 'opentp'))
    user: str = Field(default=os.getenv('DB_USER', 'opentp'))
    password: str = Field(default=os.getenv('DB_PASSWORD', 'samaral'))
    min_connections: int = Field(default=1)
    max_connections: int = Field(default=5)

class Config(BaseModel):
    simulator: SimulatorConfig = Field(default_factory=SimulatorConfig)
    server: ServerConfig = Field(default_factory=ServerConfig)
    metrics: MetricsConfig = Field(default_factory=MetricsConfig)
    tracing: TracingConfig = Field(default_factory=TracingConfig)
    db: DatabaseConfig = Field(default_factory=DatabaseConfig)  # Add database config
    log_level: str = Field(default="INFO")
    environment: str = Field(default="development")
    
    @classmethod
    def from_env(cls):
        return cls(
            log_level=os.getenv('LOG_LEVEL', 'INFO'),
            environment=os.getenv('ENVIRONMENT', 'development'),
            db=DatabaseConfig()  # Initialize with values from environment
        )

config = Config.from_env()
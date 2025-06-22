# source/config.py (updated)
import os
from pydantic import BaseModel, Field


class SimulatorConfig(BaseModel):
    user_id: str = Field(default=os.getenv('USER_ID', 'test'))
    desk_id: str = Field(default=os.getenv('DESK_ID', 'test'))
    default_symbols: list = Field(default=['AAPL', 'GOOGL', 'MSFT', 'AMZN'])


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


class MarketDataConfig(BaseModel):
    service_url: str = Field(default=os.getenv('MARKET_DATA_SERVICE_URL', 'market-data-service:50060'))


class OrderExchangeConfig(BaseModel):
    service_url: str = Field(default=os.getenv('ORDER_EXCHANGE_SERVICE_URL', 'order-exchange-service:50057'))


class Config(BaseModel):
    simulator: SimulatorConfig = Field(default_factory=SimulatorConfig)
    server: ServerConfig = Field(default_factory=ServerConfig)
    metrics: MetricsConfig = Field(default_factory=MetricsConfig)
    tracing: TracingConfig = Field(default_factory=TracingConfig)
    db: DatabaseConfig = Field(default_factory=DatabaseConfig)
    market_data: MarketDataConfig = Field(default_factory=MarketDataConfig)
    order_exchange: OrderExchangeConfig = Field(default_factory=OrderExchangeConfig)
    log_level: str = Field(default="INFO")
    environment: str = Field(default="development")

    @classmethod
    def from_env(cls):
        return cls(
            log_level=os.getenv('LOG_LEVEL', 'INFO'),
            environment=os.getenv('ENVIRONMENT', 'development'),
            db=DatabaseConfig(),
            market_data=MarketDataConfig(),
            tracing=TracingConfig(
                enabled=os.getenv('ENABLE_TRACING', 'true').lower() == 'true',
                otlp_endpoint=os.getenv('OTEL_EXPORTER_OTLP_ENDPOINT', 'http://jaeger-collector:4317'),
                service_name=os.getenv('OTEL_SERVICE_NAME', 'exchange-simulator')
            )
        )


config = Config.from_env()
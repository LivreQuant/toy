"""
Configuration management for the Session Service.
Loads configuration from environment variables with sensible defaults.
"""
import os
import logging
from typing import List
from pydantic import BaseModel, Field

# Log level mapping
LOG_LEVELS = {
    'DEBUG': logging.DEBUG,
    'INFO': logging.INFO,
    'WARNING': logging.WARNING,
    'ERROR': logging.ERROR,
    'CRITICAL': logging.CRITICAL
}


class DatabaseConfig(BaseModel):
    """Database connection configuration"""
    host: str = Field(default="postgres")
    port: int = Field(default=5432)
    database: str = Field(default="sessions")
    user: str = Field(default="postgres")
    password: str = Field(default="postgres")
    min_connections: int = Field(default=2)
    max_connections: int = Field(default=10)

    @property
    def connection_string(self) -> str:
        """Get PostgreSQL connection string"""
        return f"postgres://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"


class ServiceConfig(BaseModel):
    """External service endpoints"""
    auth_service_url: str = Field(default="http://auth-service:8001")
    exchange_manager_service: str = Field(default="exchange-manager-service:50055")


class ServerConfig(BaseModel):
    """Web server configuration"""
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8080)
    workers: int = Field(default=4)
    cors_allowed_origins: List[str] = Field(default=["*"])
    shutdown_timeout: int = Field(default=30) 


class SessionConfig(BaseModel):
    """Session-related configuration"""
    timeout_seconds: int = Field(default=3600)  # 1 hour
    extension_threshold: int = Field(default=1800)  # 30 minutes


class WebSocketConfig(BaseModel):
    """WebSocket configuration"""
    heartbeat_interval: int = Field(default=10)  # 10 seconds


class SimulatorConfig(BaseModel):
    """Simulator configuration"""
    max_per_user: int = Field(default=2)
    inactivity_timeout: int = Field(default=3600)  # 1 hour
    namespace: str = Field(default="default")


class KubernetesConfig(BaseModel):
    """Kubernetes configuration"""
    namespace: str = Field(default="default")
    pod_name: str = Field(default=os.getenv('HOSTNAME', 'unknown'))
    in_cluster: bool = Field(default=True)


class TracingConfig(BaseModel):
    """Tracing configuration"""
    enabled: bool = Field(default=True)
    exporter_endpoint: str = Field(default="http://jaeger-collector:14268/api/traces")
    service_name: str = Field(default="session-service")

class MetricsConfig(BaseModel):
    """Metrics configuration"""
    enabled: bool = Field(default=True)
    port: int = Field(default=9090)
    endpoint: str = Field(default="/metrics")


class Config(BaseModel):
    """Main configuration class"""
    environment: str = Field(default="development")
    log_level: str = Field(default="INFO")
    db: DatabaseConfig = Field(default_factory=DatabaseConfig)
    services: ServiceConfig = Field(default_factory=ServiceConfig)
    server: ServerConfig = Field(default_factory=ServerConfig)
    session: SessionConfig = Field(default_factory=SessionConfig)
    websocket: WebSocketConfig = Field(default_factory=WebSocketConfig)
    simulator: SimulatorConfig = Field(default_factory=SimulatorConfig)
    kubernetes: KubernetesConfig = Field(default_factory=KubernetesConfig)
    tracing: TracingConfig = Field(default_factory=TracingConfig)
    metrics: MetricsConfig = Field(default_factory=MetricsConfig)

    @classmethod
    def from_env(cls) -> 'Config':
        """Load configuration from environment variables"""
        return cls(
            environment=os.getenv('ENVIRONMENT', 'development'),
            log_level=os.getenv('LOG_LEVEL', 'INFO'),
            db=DatabaseConfig(
                host=os.getenv('DB_HOST', 'postgres'), #'localhost'),
                port=int(os.getenv('DB_PORT', '5432')),
                database=os.getenv('DB_NAME', 'opentp'),
                user=os.getenv('DB_USER', 'opentp'),
                password=os.getenv('DB_PASSWORD', 'samaral'),
                min_connections=int(os.getenv('DB_MIN_CONNECTIONS', '2')),
                max_connections=int(os.getenv('DB_MAX_CONNECTIONS', '10'))
            ),
            services=ServiceConfig(
                auth_service_url=os.getenv('AUTH_SERVICE_URL', 'http://auth-service:8000'),
                exchange_manager_service=os.getenv('EXCHANGE_MANAGER_SERVICE', 'exchange-manager-service:50055')
            ),
            server=ServerConfig(
                host=os.getenv('HOST', '0.0.0.0'),
                port=int(os.getenv('PORT', '8080')),
                workers=int(os.getenv('WORKERS', '4')),
                cors_allowed_origins=os.getenv('CORS_ALLOWED_ORIGINS', '*').split(',')
            ),
            session=SessionConfig(
                timeout_seconds=int(os.getenv('SESSION_TIMEOUT_SECONDS', '3600')),
                extension_threshold=int(os.getenv('SESSION_EXTENSION_THRESHOLD', '1800'))
            ),
            websocket=WebSocketConfig(
                heartbeat_interval=int(os.getenv('WEBSOCKET_HEARTBEAT_INTERVAL', '10'))
            ),
            simulator=SimulatorConfig(
                max_per_user=int(os.getenv('MAX_SIMULATORS_PER_USER', '1')),
                namespace=os.getenv('SIMULATOR_NAMESPACE', 'default')
            ),
            kubernetes=KubernetesConfig(
                namespace=os.getenv('KUBERNETES_NAMESPACE', 'default'),
                pod_name=os.getenv('POD_NAME', os.getenv('HOSTNAME', 'unknown')),
                in_cluster=os.getenv('K8S_IN_CLUSTER', 'true').lower() == 'true'
            ),
            tracing=TracingConfig(
                enabled=os.getenv('ENABLE_TRACING', 'true').lower() == 'true',
                exporter_endpoint=os.getenv('OTEL_EXPORTER_JAEGER_ENDPOINT', 'http://jaeger-collector:14268/api/traces'),
                service_name=os.getenv('OTEL_SERVICE_NAME', 'session-service')
            ),
            metrics=MetricsConfig(
                enabled=os.getenv('ENABLE_METRICS', 'true').lower() == 'true',
                port=int(os.getenv('METRICS_PORT', '9090')),
                endpoint=os.getenv('METRICS_ENDPOINT', '/metrics')
            ),
        )


# Create global config instance
config = Config.from_env()

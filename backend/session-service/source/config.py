"""
Configuration management for the Session Service.
Loads configuration from environment variables with sensible defaults.
"""
import os
import logging
from typing import List, Optional
from pydantic import BaseModel, Field

# Log level mapping
LOG_LEVELS = {
    'DEBUG': logging.DEBUG,
    'INFO': logging.INFO,
    'WARNING': logging.WARNING,
    'ERROR': logging.ERROR,
    'CRITICAL': logging.CRITICAL
}


class StateManagementConfig(BaseModel):
    """Service state management configuration"""
    ready_file_path: str = Field(default="/tmp/session_service_ready")
    health_check_path: str = Field(default="/health")
    readiness_check_path: str = Field(default="/ready")
    active_lock_file_path: str = Field(default="/tmp/session_service_active")
    reset_on_startup: bool = Field(default=True)


class DatabaseConfig(BaseModel):
    """Database connection configuration"""
    host: str = Field(default="postgres")
    port: int = Field(default=5432)
    database: str = Field(default="sessions")
    user: str = Field(default="postgres")
    password: str = Field(default="postgres")
    min_connections: int = Field(default=2)
    max_connections: int = Field(default=10)
    max_retries: int = Field(default=5)
    retry_delay: int = Field(default=1)


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
    secure: bool = Field(default=False)  # New field for secure WebSocket
    ssl_cert_path: Optional[str] = Field(default=None)
    ssl_key_path: Optional[str] = Field(default=None)


class SimulatorConfig(BaseModel):
    """Simplified simulator configuration - connection only"""
    connection_timeout: int = Field(default=30)  # Seconds to wait for connection
    heartbeat_interval: int = Field(default=10)  # Heartbeat frequency
    max_reconnect_attempts: int = Field(default=0)  # 0 = infinite retries
    reconnect_delay: int = Field(default=5)  # Seconds between reconnection attempts
    connection_retry_backoff: float = Field(default=1.5)  # Exponential backoff multiplier
    max_retry_delay: int = Field(default=60)  # Maximum delay between retries


class KubernetesConfig(BaseModel):
    """Minimal Kubernetes configuration - only for identification"""
    namespace: str = Field(default="default")
    pod_name: str = Field(default=os.getenv('HOSTNAME', 'unknown'))


class TracingConfig(BaseModel):
    """Tracing configuration"""
    enabled: bool = Field(default=True)
    exporter_endpoint: str = Field(default="http://jaeger-collector:4317")  # Changed to gRPC port
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
    state_management: StateManagementConfig = Field(default_factory=StateManagementConfig)

    @classmethod
    def from_env(cls) -> 'Config':
        """Load configuration from environment variables"""
        return cls(
            environment=os.getenv('ENVIRONMENT', 'development'),
            log_level=os.getenv('LOG_LEVEL', 'INFO'),
            db=DatabaseConfig(
                host=os.getenv('DB_HOST', 'postgres'),  # 'localhost'),
                port=int(os.getenv('DB_PORT', '5432')),
                database=os.getenv('DB_NAME', 'opentp'),
                user=os.getenv('DB_USER', 'opentp'),
                password=os.getenv('DB_PASSWORD', 'samaral'),
                min_connections=int(os.getenv('DB_MIN_CONNECTIONS', '2')),
                max_connections=int(os.getenv('DB_MAX_CONNECTIONS', '10')),
                max_retries=int(os.getenv('DB_MAX_RETRIES', '5')),
                retry_delay=int(os.getenv('DB_RETRY_DELAY', '1'))
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
                heartbeat_interval=int(os.getenv('WS_HEARTBEAT_INTERVAL', '10')),
                secure=os.getenv('WS_SECURE', 'false').lower() == 'true',
                ssl_cert_path=os.getenv('WS_SSL_CERT_PATH'),
                ssl_key_path=os.getenv('WS_SSL_KEY_PATH')
            ),
            simulator=SimulatorConfig(
                connection_timeout=int(os.getenv('SIMULATOR_CONNECTION_TIMEOUT', '30')),
                heartbeat_interval=int(os.getenv('SIMULATOR_HEARTBEAT_INTERVAL', '10')),
                max_reconnect_attempts=int(os.getenv('SIMULATOR_MAX_RECONNECT_ATTEMPTS', '0')),
                reconnect_delay=int(os.getenv('SIMULATOR_RECONNECT_DELAY', '5')),
                connection_retry_backoff=float(os.getenv('SIMULATOR_RETRY_BACKOFF', '1.5')),
                max_retry_delay=int(os.getenv('SIMULATOR_MAX_RETRY_DELAY', '60'))
            ),
            kubernetes=KubernetesConfig(
                namespace=os.getenv('KUBERNETES_NAMESPACE', 'default'),
                pod_name=os.getenv('POD_NAME', os.getenv('HOSTNAME', 'unknown'))
            ),
            tracing=TracingConfig(
                enabled=os.getenv('ENABLE_TRACING', 'false').lower() == 'true',
                exporter_endpoint=os.getenv('OTEL_EXPORTER_OTLP_ENDPOINT', 'http://jaeger-collector:4317'),  # Use standard OTLP env var
                service_name=os.getenv('OTEL_SERVICE_NAME', 'session-service')
            ),
            metrics=MetricsConfig(
                enabled=os.getenv('ENABLE_METRICS', 'true').lower() == 'true',
                port=int(os.getenv('METRICS_PORT', '9090')),
                endpoint=os.getenv('METRICS_ENDPOINT', '/metrics')
            ),
            state_management=StateManagementConfig(
                ready_file_path=os.getenv('READY_FILE_PATH', '/tmp/session_service_ready'),
                health_check_path=os.getenv('HEALTH_CHECK_PATH', '/health'),
                readiness_check_path=os.getenv('READINESS_CHECK_PATH', '/readiness'),
                active_lock_file_path=os.getenv('ACTIVE_LOCK_FILE_PATH', '/tmp/session_service_active'),
                reset_on_startup=os.getenv('RESET_ON_STARTUP', 'true').lower() == 'true'
            )
        )


# Create global config instance
config = Config.from_env()

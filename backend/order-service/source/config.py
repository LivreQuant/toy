import os
from typing import Dict, Any

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
    db_min_connections = int(os.getenv('DB_MIN_CONNECTIONS', '2'))
    db_max_connections = int(os.getenv('DB_MAX_CONNECTIONS', '20'))
    
    # Redis Configuration
    redis_host = os.getenv('REDIS_HOST', 'redis')
    redis_port = int(os.getenv('REDIS_PORT', '6379'))
    redis_db = int(os.getenv('REDIS_DB', '0'))
    redis_password = os.getenv('REDIS_PASSWORD', None)
    
    # Service URLs
    auth_service_url = os.getenv('AUTH_SERVICE_URL', 'http://auth-service:8000')
    
    # Logging
    log_level = os.getenv('LOG_LEVEL', 'INFO')
    
    # Performance settings
    request_timeout = int(os.getenv('REQUEST_TIMEOUT', '30'))
    
    # Feature flags
    enable_metrics = os.getenv('ENABLE_METRICS', 'true').lower() == 'true'
    
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
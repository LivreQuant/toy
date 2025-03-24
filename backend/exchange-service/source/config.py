import os
from typing import Dict, Any

class Config:
    """Application configuration."""
    
    # Environment
    environment = os.getenv('ENVIRONMENT', 'development')
    
    # Server settings
    port = int(os.getenv('PORT', '50055'))
    host = os.getenv('HOST', '0.0.0.0')
    
    # Simulator settings
    inactivity_timeout_seconds = int(os.getenv('INACTIVITY_TIMEOUT_SECONDS', '300'))
    auto_terminate = os.getenv('AUTO_TERMINATE', 'true').lower() == 'true'
    
    # Market data settings
    default_symbols = os.getenv('DEFAULT_SYMBOLS', 'AAPL,MSFT,GOOGL,AMZN,TSLA').split(',')
    default_initial_cash = float(os.getenv('DEFAULT_INITIAL_CASH', '100000.0'))
    market_update_interval_seconds = float(os.getenv('MARKET_UPDATE_INTERVAL_SECONDS', '1.0'))
    
    # Performance settings
    max_worker_threads = int(os.getenv('MAX_WORKER_THREADS', '10'))
    
    # Logging
    log_level = os.getenv('LOG_LEVEL', 'INFO')
    
    # Feature flags
    enable_metrics = os.getenv('ENABLE_METRICS', 'true').lower() == 'true'
    
    @property
    def is_production(self) -> bool:
        """Check if running in production environment"""
        return self.environment.lower() == 'production'

# Create global instance
config = Config()
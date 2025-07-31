# source/config.py
import os
from typing import Dict, Any
from dataclasses import dataclass
import json

@dataclass
class DatabaseConfig:
    host: str = os.getenv('DB_HOST', 'opentp')
    port: int = int(os.getenv('DB_PORT', '5432'))
    database: str = os.getenv('DB_NAME', 'exch_us_equity')
    user: str = os.getenv('DB_USER', 'opentp')
    password: str = os.getenv('DB_PASSWORD', 'samaral')
    min_connections: int = 1
    max_connections: int = 10


class Config:
    """Configuration for market data service"""
    
    # Service configuration
    API_HOST: str = os.getenv("API_HOST", "0.0.0.0")
    API_PORT: int = int(os.getenv("API_PORT", "50060"))
    
    # Market data configuration - now loaded from JSON config
    CONFIG_FILE: str = os.getenv("CONFIG_FILE", "test_0.json")
    
    # Database configuration
    db: DatabaseConfig = DatabaseConfig()
    
    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    
    def load_market_config(self) -> Dict[str, Any]:
        """Load market data configuration from JSON file"""
        import sys
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(os.path.dirname(current_dir))
        
        # Try multiple locations for config file
        search_paths = [
            self.CONFIG_FILE,  # Direct path
            os.path.join(current_dir, self.CONFIG_FILE),
            os.path.join(project_root, "tests", self.CONFIG_FILE),
        ]
        
        for path in search_paths:
            if os.path.isfile(path):
                with open(path, 'r') as f:
                    return json.load(f)
        
        # Fallback default config
        return {
            "config_name": "Default Config",
            "timezone": "America/New_York",
            "start_time": "2024-01-01T09:30:00",
            "time_increment_minutes": 1,
            "server_port": 50060,
            "equity": [
                {"symbol": "AAPL", "starting_price": 190.0, "price_change_per_minute": 0.01, 
                 "base_volume": 10000, "trade_count": 100, "currency": "USD", 
                 "vwas": 0.01, "vwav": 0.01, "exchange": "NASDAQ"},
                {"symbol": "GOOGL", "starting_price": 160.0, "price_change_per_minute": 0.02,
                 "base_volume": 5000, "trade_count": 50, "currency": "USD",
                 "vwas": 0.01, "vwav": 0.01, "exchange": "NASDAQ"}
            ],
            "fx": [
                {"from_currency": "USD", "to_currency": "EUR", "starting_rate": 0.85, "rate_change_per_minute": 0.0001}
            ]
        }

config = Config()
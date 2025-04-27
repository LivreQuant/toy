# source/config.py
import os
from typing import List
from dataclasses import dataclass

@dataclass
class DatabaseConfig:
    host: str = os.getenv('DB_HOST', 'postgres')
    port: int = int(os.getenv('DB_PORT', '5432'))
    database: str = os.getenv('DB_NAME', 'marketdata')
    user: str = os.getenv('DB_USER', 'postgres')
    password: str = os.getenv('DB_PASSWORD', 'postgres')
    min_connections: int = 1
    max_connections: int = 5


class Config:
    """Configuration for market data service"""
    
    # Service configuration
    API_HOST: str = os.getenv("API_HOST", "0.0.0.0")
    API_PORT: int = int(os.getenv("API_PORT", "50060"))
    
    # Market data configuration
    SYMBOLS: List[str] = os.getenv("SYMBOLS", "AAPL,GOOGL,MSFT,AMZN,TSLA,FB").split(",")
    UPDATE_INTERVAL: int = int(os.getenv("UPDATE_INTERVAL", "60"))  # Seconds
    
    # Database configuration
    db: DatabaseConfig = DatabaseConfig()
    
    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")


config = Config()
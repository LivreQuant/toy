# source/config.py
import os
from typing import List


class Config:
    """Configuration for market data distributor service"""
    
    # Service configuration
    API_HOST: str = os.getenv("API_HOST", "0.0.0.0")
    API_PORT: int = int(os.getenv("API_PORT", "50060"))
    
    # Market data configuration
    SYMBOLS: List[str] = os.getenv("SYMBOLS", "AAPL,GOOGL,MSFT,AMZN,TSLA,FB").split(",")
    UPDATE_INTERVAL: int = int(os.getenv("UPDATE_INTERVAL", "60"))  # Seconds
    
    # Service operating hours
    STARTUP_HOUR: int = int(os.getenv("STARTUP_HOUR", "3"))  # 3 AM
    SHUTDOWN_HOUR: int = int(os.getenv("SHUTDOWN_HOUR", "20"))  # 8 PM
    
    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    
    # Exchange simulator service discovery
    EXCHANGE_SERVICE_NAME: str = os.getenv("EXCHANGE_SERVICE_NAME", "exchange-simulator")
    EXCHANGE_SERVICE_PORT: int = int(os.getenv("EXCHANGE_SERVICE_PORT", "50055"))


config = Config()

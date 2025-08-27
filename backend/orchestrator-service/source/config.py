# source/config.py
import os
from typing import Optional
from datetime import time
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Config:
    """Application configuration"""
    
    # Database Configuration
    DATABASE_HOST: str = os.getenv("DATABASE_HOST", "localhost")
    DATABASE_PORT: int = int(os.getenv("DATABASE_PORT", "5432"))
    DATABASE_NAME: str = os.getenv("DATABASE_NAME", "trading_db")
    DATABASE_USER: str = os.getenv("DATABASE_USER", "trading_user")
    DATABASE_PASSWORD: str = os.getenv("DATABASE_PASSWORD", "")
    DATABASE_MIN_CONNECTIONS: int = int(os.getenv("DATABASE_MIN_CONNECTIONS", "5"))
    DATABASE_MAX_CONNECTIONS: int = int(os.getenv("DATABASE_MAX_CONNECTIONS", "20"))
    
    @property
    def database_url(self) -> str:
        """Get database connection URL"""
        return f"postgresql://{self.DATABASE_USER}:{self.DATABASE_PASSWORD}@{self.DATABASE_HOST}:{self.DATABASE_PORT}/{self.DATABASE_NAME}"
    
    # Orchestrator Configuration
    MARKET_TIMEZONE: str = os.getenv("MARKET_TIMEZONE", "America/New_York")
    SOD_TIME: str = os.getenv("SOD_TIME", "06:00")
    EOD_TIME: str = os.getenv("EOD_TIME", "18:00")
    SCHEDULER_CHECK_INTERVAL: int = int(os.getenv("SCHEDULER_CHECK_INTERVAL", "60"))
    
    @property
    def sod_time(self) -> time:
        """Get SOD time as time object"""
        hour, minute = map(int, self.SOD_TIME.split(":"))
        return time(hour, minute)
    
    @property
    def eod_time(self) -> time:
        """Get EOD time as time object"""
        hour, minute = map(int, self.EOD_TIME.split(":"))
        return time(hour, minute)
    
    # Kubernetes Configuration
    K8S_NAMESPACE: str = os.getenv("K8S_NAMESPACE", "trading")
    K8S_CONFIG_PATH: Optional[str] = os.getenv("K8S_CONFIG_PATH")
    
    # Logging Configuration
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FORMAT: str = os.getenv("LOG_FORMAT", "%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    
    # Environment
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    DEBUG_MODE: bool = os.getenv("DEBUG_MODE", "false").lower() == "true"
    
    @property
    def is_development(self) -> bool:
        return self.ENVIRONMENT.lower() == "development"
    
    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT.lower() == "production"


# Global config instance
config = Config()


def get_config() -> Config:
    """Get application configuration"""
    return config
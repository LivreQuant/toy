"""
Configuration management for the Risk Model Service.
Loads configuration from environment variables with sensible defaults.
"""
import os
import logging
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
    driver: str = Field(default="{ODBC Driver 17 for SQL Server}")
    server: str = Field(default="localhost")
    database: str = Field(default="risk_models")
    username: str = Field(default="sa")
    password: str = Field(default="your_password")
    table: str = Field(default="exch_us_equity.risk_factor_data")

    @property
    def connection_string(self) -> str:
        """Get SQL Server connection string"""
        return f'DRIVER={self.driver};SERVER={self.server};DATABASE={self.database};UID={self.username};PWD={self.password}'


class Config(BaseModel):
    """Main configuration class"""
    environment: str = Field(default="development")
    log_level: str = Field(default="INFO")
    db: DatabaseConfig = Field(default_factory=DatabaseConfig)

    @classmethod
    def from_env(cls) -> 'Config':
        """Load configuration from environment variables"""
        return cls(
            environment=os.getenv('ENVIRONMENT', 'development'),
            log_level=os.getenv('LOG_LEVEL', 'INFO'),
            db=DatabaseConfig(
                driver=os.getenv('DB_DRIVER', '{ODBC Driver 17 for SQL Server}'),
                server=os.getenv('DB_SERVER', 'localhost'),
                database=os.getenv('DB_DATABASE', 'risk_models'),
                username=os.getenv('DB_USERNAME', 'sa'),
                password=os.getenv('DB_PASSWORD', 'your_password'),
                table=os.getenv('DB_TABLE', 'exch_us_equity.risk_factor_data')
            )
        )


# Create global config instance
config = Config.from_env()
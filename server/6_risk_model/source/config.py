"""
Configuration management for the Risk Model Service.
Loads configuration from environment variables with sensible defaults.
"""
import os
import logging
import pandas as pd
from datetime import datetime
from pathlib import Path
from typing import Optional
from pydantic import BaseModel, Field
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Log level mapping
LOG_LEVELS = {
    'DEBUG': logging.DEBUG,
    'INFO': logging.INFO,
    'WARNING': logging.WARNING,
    'ERROR': logging.ERROR,
    'CRITICAL': logging.CRITICAL
}


class MasterDataConfig(BaseModel):
    """Configuration for master data directory"""
    master_dir: str = Field(default="data/master")


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
    master_data: MasterDataConfig = Field(default_factory=MasterDataConfig)
    db: DatabaseConfig = Field(default_factory=DatabaseConfig)
    output_dir: str = Field(default="output")

    # Master data cache
    _master_data: Optional[pd.DataFrame] = None

    @classmethod
    def from_env(cls) -> 'Config':
        """Load configuration from environment variables"""
        return cls(
            environment=os.getenv('ENVIRONMENT'),
            log_level=os.getenv('LOG_LEVEL'),
            output_dir=os.getenv('OUTPUT_DIR'),
            master_data=MasterDataConfig(
                master_dir=os.getenv('MASTER_DIR')
            ),
            db=DatabaseConfig(
                driver=os.getenv('DB_DRIVER', '{ODBC Driver 17 for SQL Server}'),
                server=os.getenv('DB_SERVER', 'localhost'),
                database=os.getenv('DB_DATABASE', 'risk_models'),
                username=os.getenv('DB_USERNAME', 'sa'),
                password=os.getenv('DB_PASSWORD', 'your_password'),
                table=os.getenv('DB_TABLE', 'exch_us_equity.risk_factor_data')
            )
        )

    def get_ymd(self) -> str:
        ymd = datetime.strftime(datetime.today(), "%Y%m%d")
        return ymd

    def get_master_dir(self) -> Path:
        """Get master data directory path"""
        return Path(os.path.join(self.master_data.master_dir, self.get_ymd(), "data"))

    def get_output_dir(self) -> Path:
        """Get output directory path"""
        return Path(os.path.join(self.output_dir, self.get_ymd()))

    def load_master_file(self) -> pd.DataFrame:
        """Load a specific master file"""
        try:
            master_path = self.get_master_dir()

            if not master_path.exists():
                logging.error(f"Master directory does not exist: {master_path}")
                raise ValueError(f"Master directory not found: {master_path}")

            # Find master files
            master_files = list(master_path.glob("*MASTER_UPDATED.csv"))

            if not master_files:
                logging.error(f"No MASTER_UPDATED.csv files found in: {master_path}")
                # List what files ARE there for debugging
                all_files = list(master_path.glob("*.csv"))
                logging.error(f"Available CSV files: {[f.name for f in all_files]}")
                raise ValueError("No MASTER_UPDATED.csv file found")

            master_file = master_files[0]  # Take the first one

            df = pd.read_csv(master_file, dtype=str, keep_default_na=False, na_values=[], sep="|")
            logging.info(f"Loaded master file: {master_file} with {len(df)} records")
            return df

        except Exception as e:
            logging.error(f"Failed to load master file: {e}")
            raise


# Create global config instance
config = Config.from_env()
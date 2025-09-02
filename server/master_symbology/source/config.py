import os
from pathlib import Path
from dotenv import load_dotenv
from datetime import datetime
import glob

class MasterSymbologyConfig:
    def __init__(self, env_file_path=None):
        """Initialize configuration with environment variables"""
        if env_file_path is None:
            # Look for .env file in current directory or parent directories
            current_dir = Path(__file__).parent
            for parent in [current_dir] + list(current_dir.parents):
                env_path = parent / '.env'
                if env_path.exists():
                    env_file_path = env_path
                    break

        if env_file_path:
            load_dotenv(env_file_path)

        ymd = datetime.strftime(datetime.today(), "%Y%m%d")
        prv_ymd = sorted(glob.glob(os.path.join(os.getenv('SOURCE_DIR'), '*')))[-2]

        # Main directories

        self.source_dir = os.path.join(os.getenv('SOURCE_DIR'), ymd)
        self.prv_source_dir = os.path.join(os.getenv('SOURCE_DIR'), prv_ymd)
        self.save_dir = os.path.join(os.getenv('SAVE_DIR'), ymd)

        # Output directories (derived from SAVE_DIR)
        self.data_dir = os.path.join(self.save_dir, 'data')
        self.debug_dir = os.path.join(self.save_dir, 'debug')

        # Provider-specific data paths (derived from SOURCE_DIR)
        self.alpaca_data_path = os.path.join(self.source_dir, 'alpaca')  # UPDATE
        self.alphavantage_data_path = os.path.join(self.source_dir, 'alphavantage')  # UPDATE
        self.eodhd_data_path = os.path.join(self.source_dir, 'eodhd')  # UPDATE
        self.financedatabase_data_path = os.path.join(self.source_dir, 'finance_db')  # UPDATE
        self.fmp_data_path = os.path.join(self.source_dir, 'fmp')
        self.intrinio_data_path = os.path.join(self.source_dir, 'intrinio')
        self.nasdaq_data_path = os.path.join(self.source_dir, 'nasdaq')  # UPDATE
        self.nyse_data_path = os.path.join(self.source_dir, 'nyse')  # UPDATE
        self.polygon_data_path = os.path.join(self.source_dir, 'poly', 'details')
        self.sharadar_data_path = os.path.join(self.prv_source_dir, 'sharadar')

        # API Keys
        self.alphavantage_api_key = os.getenv('ALPHAVANTAGE_API_KEY')
        self.eodhd_api_key = os.getenv('EODHD_API_KEY')
        self.alpaca_api_key = os.getenv('ALPACA_API_KEY_ID')
        self.alpaca_secret_key = os.getenv('ALPACA_SECRET_KEY')

        # File names (with defaults)
        self.intrinio_securities_file = os.getenv('INTRINIO_SECURITIES_FILE', 'all_securities_active_T_delisted_F.json')
        self.intrinio_exchange_file = os.getenv('INTRINIO_EXCHANGE_FILE',
                                                'stock_exchange_securities_identifier_USCOMP.json')
        self.fmp_nasdaq_file = os.getenv('FMP_NASDAQ_FILE', 'NASDAQ.json')
        self.fmp_nyse_file = os.getenv('FMP_NYSE_FILE', 'NYSE.json')
        self.fmp_symbol_list_file = os.getenv('FMP_SYMBOL_LIST_FILE', 'symbol_list.json')

    def ensure_directories(self):
        """Create all necessary directories if they don't exist"""
        directories = [
            self.data_dir,
            self.debug_dir,

            self.alpaca_data_path,
            self.alphavantage_data_path,
            self.eodhd_data_path,
            self.financedatabase_data_path,
            self.fmp_data_path,
            self.intrinio_data_path,
            self.nasdaq_data_path,
            self.nyse_data_path,
            self.polygon_data_path,
            self.sharadar_data_path,
        ]

        for directory in directories:
            os.makedirs(directory, exist_ok=True)

    def get_provider_data_path(self, provider_name):
        """Get the data path for a specific provider"""
        provider_paths = {
            'alpaca': self.alpaca_data_path,
            'alphavantage': self.alphavantage_data_path,
            'eodhd': self.eodhd_data_path,
            'finance_db': self.financedatabase_data_path,
            'fmp': self.fmp_data_path,
            'intrinio': self.intrinio_data_path,
            'nasdaq': self.nasdaq_data_path,
            'nyse': self.nyse_data_path,
            'polygon': self.polygon_data_path,
            'sharadar': self.sharadar_data_path,
        }
        return provider_paths.get(provider_name.lower())


# Global configuration instance
config = MasterSymbologyConfig()

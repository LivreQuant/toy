import os
from pathlib import Path
from dotenv import load_dotenv

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
        
        # Data directories
        self.data_dir = self._get_abs_path('DATA_DIR', './data')
        self.debug_dir = self._get_abs_path('DEBUG_DIR', './debug')
        self.comparison_dir = self._get_abs_path('COMPARISON_DIR', './comparisons')
        self.example_dir = self._get_abs_path('EXAMPLE_DIR', './example')
        
        # Provider-specific data paths
        self.intrinio_data_path = self._get_abs_path('INTRINIO_DATA_PATH', './example/intrinio')
        self.fmp_data_path = self._get_abs_path('FMP_DATA_PATH', './example/fmp')
        self.sharadar_data_path = self._get_abs_path('SHARADAR_DATA_PATH', './example/sharadar')
        self.polygon_data_path = self._get_abs_path('POLYGON_DATA_PATH', './example/poly')
        self.nasdaq_data_path = self._get_abs_path('NASDAQ_DATA_PATH', './example/nasdaq')
        self.nyse_data_path = self._get_abs_path('NYSE_DATA_PATH', './example/nyse')
        self.financedatabase_data_path = self._get_abs_path('FINANCEDATABASE_DATA_PATH', './example/finance_db')
        
        # API Keys
        self.alphavantage_api_key = os.getenv('ALPHAVANTAGE_API_KEY')
        self.eodhd_api_key = os.getenv('EODHD_API_KEY')
        self.alpaca_api_key = os.getenv('ALPACA_API_KEY')
        self.alpaca_secret_key = os.getenv('ALPACA_SECRET_KEY')
        
        # File names
        self.intrinio_securities_file = os.getenv('INTRINIO_SECURITIES_FILE', 'all_securities_active_T_delisted_F.json')
        self.intrinio_exchange_file = os.getenv('INTRINIO_EXCHANGE_FILE', 'stock_exchange_securities_identifier_USCOMP.json')
        self.fmp_nasdaq_file = os.getenv('FMP_NASDAQ_FILE', 'NASDAQ.json')
        self.fmp_nyse_file = os.getenv('FMP_NYSE_FILE', 'NYSE.json')
        self.fmp_symbol_list_file = os.getenv('FMP_SYMBOL_LIST_FILE', 'symbol_list.json')
        self.sharadar_default_file = os.getenv('SHARADAR_DEFAULT_FILE', '20250826.csv')
    
    def _get_abs_path(self, env_var, default_path):
        """Get absolute path from environment variable or default"""
        path = os.getenv(env_var, default_path)
        if os.path.isabs(path):
            return path
        return os.path.abspath(os.path.join(os.path.dirname(__file__), path))
    
    def ensure_directories(self):
        """Create all necessary directories if they don't exist"""
        directories = [
            self.data_dir, self.debug_dir, self.comparison_dir, self.example_dir,
            self.intrinio_data_path, self.fmp_data_path, self.sharadar_data_path,
            self.polygon_data_path, self.nasdaq_data_path, self.nyse_data_path,
            self.financedatabase_data_path
        ]
        
        for directory in directories:
            os.makedirs(directory, exist_ok=True)

# Global configuration instance
config = MasterSymbologyConfig()
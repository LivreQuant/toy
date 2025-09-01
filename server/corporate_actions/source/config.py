import os
from pathlib import Path
from dotenv import load_dotenv

class CorporateActionsConfig:
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
        self.example_dir = self._get_abs_path('EXAMPLE_DIR', './example')
        self.master_files_dir = self._get_abs_path('MASTER_FILES_DIR', './example/master')
        
        # History analysis patterns
        self.sharadar_ca_pattern = os.getenv('SHARADAR_CA_PATTERN', 
                                           '/media/samaral/Horse1/market/US_EQUITY/live/corporate_actions/*/sharadar/*.csv')
        self.alpaca_ca_pattern = os.getenv('ALPACA_CA_PATTERN',
                                         '/media/samaral/Horse1/market/US_EQUITY/live/corporate_actions/*/alpaca/*.json')
        self.poly_dividends_pattern = os.getenv('POLY_DIVIDENDS_PATTERN',
                                              '/media/samaral/Horse1/market/US_EQUITY/live/corporate_actions/*/poly/dividends.json')
        self.poly_splits_pattern = os.getenv('POLY_SPLITS_PATTERN',
                                           '/media/samaral/Horse1/market/US_EQUITY/live/corporate_actions/*/poly/splits.json')
        
        # Default file names
        self.unified_cash_dividends_file = os.getenv('UNIFIED_CASH_DIVIDENDS_FILE', 'unified_cash_dividends_{timestamp}.csv')
        self.unified_stock_dividends_file = os.getenv('UNIFIED_STOCK_DIVIDENDS_FILE', 'unified_stock_dividends_{timestamp}.csv')
        self.unified_stock_splits_file = os.getenv('UNIFIED_STOCK_SPLITS_FILE', 'unified_stock_splits_{timestamp}.csv')
        self.unified_mergers_file = os.getenv('UNIFIED_MERGERS_FILE', 'unified_mergers_{timestamp}.csv')
        self.unified_spinoffs_file = os.getenv('UNIFIED_SPINOFFS_FILE', 'unified_spinoffs_{timestamp}.csv')
        self.unified_symbol_changes_file = os.getenv('UNIFIED_SYMBOL_CHANGES_FILE', 'unified_symbol_changes_{timestamp}.csv')
        self.unified_ipos_file = os.getenv('UNIFIED_IPOS_FILE', 'unified_ipos_{timestamp}.csv')
        self.unified_rights_file = os.getenv('UNIFIED_RIGHTS_FILE', 'unified_rights_offerings_{timestamp}.csv')
        
        # Schema analysis output files
        self.sharadar_schema_file = os.getenv('SHARADAR_SCHEMA_FILE', 'schema_analysis_SHARADAR.json')
        self.alpaca_schema_file = os.getenv('ALPACA_SCHEMA_FILE', 'schema_analysis_ALPACA.json')
        self.poly_schema_file = os.getenv('POLY_SCHEMA_FILE', 'schema_analysis_POLY.json')
    
    def _get_abs_path(self, env_var, default_path):
        """Get absolute path from environment variable or default"""
        path = os.getenv(env_var, default_path)
        if os.path.isabs(path):
            return path
        return os.path.abspath(os.path.join(os.path.dirname(__file__), path))
    
    def ensure_directories(self):
        """Create all necessary directories if they don't exist"""
        directories = [
            self.data_dir, self.debug_dir, self.example_dir, self.master_files_dir
        ]
        
        for directory in directories:
            os.makedirs(directory, exist_ok=True)
    
    def get_unified_filename(self, file_template, timestamp=None):
        """Get unified filename with timestamp"""
        from datetime import datetime
        if timestamp is None:
            timestamp = datetime.now().strftime("%Y%m%d")
        return file_template.format(timestamp=timestamp)

# Global configuration instance
config = CorporateActionsConfig()
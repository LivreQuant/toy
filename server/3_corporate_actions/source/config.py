import os
from datetime import datetime
import glob
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

        ymd = datetime.strftime(datetime.today(), "%Y%m%d")
        prv_ymd = os.path.basename(sorted(glob.glob(os.path.join(os.getenv('SOURCE_CA_DIR'), '*')))[-2])

        self.source_symbols_dir = os.path.join(os.getenv('SOURCE_SYMBOLS_DIR'), ymd)
        self.source_ca_dir = os.path.join(os.getenv('SOURCE_CA_DIR'), ymd)
        self.source_ca_prv_dir = os.path.join(os.getenv('SOURCE_CA_DIR'), prv_ymd)

        self.master_files_dir = os.path.join(os.getenv('MASTER_FILES_DIR'), ymd, 'data')
        self.master_files_prv_dir = os.path.join(os.getenv('MASTER_FILES_DIR'), prv_ymd, 'data')
        self.corporate_actions_dir = os.path.join(os.getenv('CORPORATE_ACTIONS_DIR'), ymd)

        # Data directories
        self.data_dir = os.path.join(self.corporate_actions_dir, './data')
        self.debug_dir = os.path.join(self.corporate_actions_dir, './debug')

        # Default file names
        self.unified_cash_dividends_file = os.getenv('UNIFIED_CASH_DIVIDENDS_FILE')
        self.unified_delisting_file = os.getenv('UNIFIED_DELISTING_FILE')
        self.unified_ipos_file = os.getenv('UNIFIED_IPOS_FILE')
        self.unified_mergers_file = os.getenv('UNIFIED_MERGERS_FILE')
        self.unified_rights_file = os.getenv('UNIFIED_RIGHTS_FILE')
        self.unified_spinoffs_file = os.getenv('UNIFIED_SPINOFFS_FILE')
        self.unified_stock_splits_file = os.getenv('UNIFIED_STOCK_SPLITS_FILE')
        self.unified_stock_dividends_file = os.getenv('UNIFIED_STOCK_DIVIDENDS_FILE')
        self.unified_symbol_changes_file = os.getenv('UNIFIED_SYMBOL_CHANGES_FILE')

        # Schema analysis output files
        self.alpaca_schema_file = os.getenv('ALPACA_SCHEMA_FILE')
        self.fmp_schema_file = os.getenv('FMP_SCHEMA_FILE')
        self.poly_schema_file = os.getenv('POLY_SCHEMA_FILE')
        self.sharadar_schema_file = os.getenv('SHARADAR_SCHEMA_FILE')

    def ensure_directories(self):
        """Create all necessary directories if they don't exist"""
        directories = [
            self.data_dir, self.debug_dir, self.master_files_dir, self.master_files_prv_dir, self.corporate_actions_dir
        ]

        for directory in directories:
            os.makedirs(directory, exist_ok=True)


# Global configuration instance
config = CorporateActionsConfig()

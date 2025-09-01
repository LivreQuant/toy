import pandas as pd
from typing import Dict, Optional
import logging
from source.config import config

logger = logging.getLogger(__name__)


class SymbolMapper:
    """Maps symbols from different sources to master symbols."""

    def __init__(self, master_csv_path: str = None):
        if master_csv_path is None:
            # Use default master file from config
            import glob
            master_files = glob.glob(os.path.join(config.master_files_dir, '*.csv'))
            if not master_files:
                raise FileNotFoundError(f"No master CSV files found in {config.master_files_dir}")
            master_csv_path = max(master_files)
            
        self.master_df = pd.read_csv(master_csv_path, sep='|')
        self.source_mappings = {
            'alpaca': 'al_symbol',
            'poly': 'pl_symbol',
            'fmp': 'fp_symbol',
            'sharadar': 'sh_symbol'
        }

        # Create lookup dictionaries for fast mapping
        self.lookup_tables = {}
        for source, column in self.source_mappings.items():
            if column in self.master_df.columns:
                # Create mapping from source symbol to master symbol
                mapping = self.master_df[self.master_df[column].notna()].set_index(column)['symbol'].to_dict()
                self.lookup_tables[source] = mapping
            else:
                logger.warning(f"Column {column} not found in master CSV for source {source}")
                self.lookup_tables[source] = {}

    def map_to_master_symbol(self, source: str, source_symbol: str) -> Optional[str]:
        """Map a source symbol to master symbol."""
        if source not in self.lookup_tables:
            return None
        return self.lookup_tables[source].get(source_symbol)

    def get_symbol_info(self, master_symbol: str) -> Dict:
        """Get full symbol information from master CSV."""
        row = self.master_df[self.master_df['symbol'] == master_symbol]
        if row.empty:
            return {}
        return row.iloc[0].to_dict()
# db/symbol_manager.py
from source.db.base_manager import BaseManager
from typing import List
import pandas as pd
from source.config import config
import logging


class SymbolManager(BaseManager):
    """
    Manages retrieving the universe of symbols from the master file.
    """

    def __init__(self):
        """
        Initializes the symbol manager and loads the master file.
        """
        super().__init__()
        self.master_data = config.load_master_file()

    def get_universe(self) -> pd.DataFrame:
        """
        Retrieves the universe of symbols from the master file.

        Returns:
            List[str]: A list of security symbols.
        """
        if self.master_data.empty:
            logging.error("Master data is empty")
            raise ValueError("No Master data")

        return self.master_data

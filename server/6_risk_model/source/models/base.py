# models/base.py
import logging
from abc import ABC, abstractmethod
import os
from pathlib import Path
from datetime import date
from typing import List, Dict, Any
from source.config import config
import pandas as pd


class BaseRiskModel(ABC):
    """
    Abstract base class for all risk models.
    """

    def __init__(self, model: str, symbols: List[str]):
        """
        Initializes the base risk model with a name and a list of symbols.

        Args:
            model (str): The name of the risk model (e.g., 'RANDOM', 'BASIC').
            symbols (List[str]): A list of security symbols to generate data for.
        """
        self.model = model
        self.symbols = symbols
        self.exposures = pd.DataFrame()

    @abstractmethod
    def generate_exposures(self, date: date) -> List[Dict[str, Any]]:
        """
        Generates risk factor data for a specific date.

        Args:
            date (date): The date for which to generate the data.

        Returns:
            List[Dict[str, Any]]: A list of dictionaries containing the risk factor data.
        """
        pass

    def save_file(self) -> None:
        """
        Saves the generated exposures to a CSV file.

        Args:
            output_dir (str): Base output directory path. Defaults to "OUTPUT_DIR".
        """
        if not self.exposures:
            logging.warning("No exposures data to save. Run generate_exposures() first.")
            return

        try:
            # Create the output directory structure: OUTPUT_DIR/model_name/
            model_dir = Path(os.path.join(config.get_output_dir(), config.get_ymd(), self.model.lower()))
            model_dir.mkdir(parents=True, exist_ok=True)

            # Create the output file path
            output_file = model_dir / "exposures.csv"

            # Convert exposures to DataFrame and save to CSV
            df = pd.DataFrame(self.exposures)
            df.to_csv(output_file, index=False)

            logging.info(f"Exposures saved successfully to: {output_file}")
            logging.info(f"Saved {len(df)} rows of exposure data.")

        except Exception as e:
            logging.error(f"Failed to save exposures file: {e}")
            raise
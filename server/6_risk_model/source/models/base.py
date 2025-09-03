# models/base.py
from abc import ABC, abstractmethod
from datetime import date
from typing import List, Dict, Any

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

    @abstractmethod
    def generate_data(self, date: date) -> List[Dict[str, Any]]:
        """
        Generates risk factor data for a specific date.

        Args:
            date (date): The date for which to generate the data.

        Returns:
            List[Dict[str, Any]]: A list of dictionaries containing the risk factor data.
        """
        pass
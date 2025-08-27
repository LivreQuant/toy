
# models/random.py
from models.base import BaseRiskModel
from datetime import date
from typing import List, Dict, Any
import random

class RandomRiskModel(BaseRiskModel):
    """
    Generates random risk factor data.
    """
    def __init__(self, model: str, symbols: List[str]):
        """
        Initializes the Random risk model.

        Args:
            model (str): The name of the risk model.
            symbols (List[str]): A list of security symbols.
        """
        super().__init__(model, symbols)
        self.factor_types_cum_eq_1 = {
            "Currency": ["USD"],
            "Sector": ["Tech", "Finance", "Healthcare"]
        }

        self.factor_types_cum_neq_1 = {
            "Style": ["Market", "Momentum", "Value"],
        }

    def generate_data(self, date: date) -> List[Dict[str, Any]]:
        """
        Generates random risk factor data for the given symbols and date.
        For factors where the cumulative sum must equal one, it generates non-negative
        values that sum to 1. For other factors, it generates random values.

        Args:
            date (date): The date for which to generate the data.

        Returns:
            List[Dict[str, Any]]: A list of dictionaries with the generated data.
        """
        data = []
        for symbol in self.symbols:
            # Generate factors where the cumulative sum must equal 1 and values are non-negative
            for factor_type, factor_names in self.factor_types_cum_eq_1.items():
                num_factors = len(factor_names)
                # Generate num_factors-1 random points between 0 and 1
                random_points = sorted([random.uniform(0, 1) for _ in range(num_factors - 1)])
                
                # Use the sorted points to create values that sum to 1
                values_to_sum = [random_points[0]]
                for i in range(num_factors - 2):
                    values_to_sum.append(random_points[i+1] - random_points[i])
                values_to_sum.append(1 - random_points[-1])
                
                for factor_name, value in zip(factor_names, values_to_sum):
                    row = {
                        "date": date,
                        "model": self.model,
                        "factor1": factor_type, # Maps 'type' to 'factor1'
                        "factor2": factor_name, # Maps 'name' to 'factor2'
                        "factor3": "",          # Unused for now
                        "symbol": symbol,
                        "type": factor_type,
                        "name": factor_name,
                        "value": round(value, 6)
                    }
                    data.append(row)

            # Generate factors where the cumulative sum does not have to equal 1
            for factor_type, factor_names in self.factor_types_cum_neq_1.items():
                for factor_name in factor_names:
                    value = round(random.uniform(-1.0, 1.0), 6)  # Random value between -1 and 1
                    row = {
                        "date": date,
                        "model": self.model,
                        "factor1": factor_type, # Maps 'type' to 'factor1'
                        "factor2": factor_name, # Maps 'name' to 'factor2'
                        "factor3": "",          # Unused for now
                        "symbol": symbol,
                        "type": factor_type,
                        "name": factor_name,
                        "value": value
                    }
                    data.append(row)
        return data

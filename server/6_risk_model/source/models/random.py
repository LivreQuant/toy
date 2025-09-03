# models/random.py
from source.models.base import BaseRiskModel
from datetime import date
from typing import List, Dict, Any
import random
import pandas as pd
import logging
from source.config import config


class RandomRiskModel(BaseRiskModel):
    """
    Generates random risk factor data based on master file universe.
    ALL risk model structure and factor definitions are contained here.
    """

    def __init__(self, model: str, symbols: List[str]):
        """
        Initializes the Random risk model.

        Args:
            model (str): The name of the risk model.
            symbols (List[str]): A list of security symbols.
        """
        super().__init__(model, symbols)

        # Load master data to determine universe and factor structure
        self.master_data = config.load_master_file()

        # Define Style factors (random values between -1 and 1)
        self.style_factors = [
            "Market",  # Market beta exposure
            "Momentum",  # Price momentum
            "Liquidity",  # Trading liquidity
            "Value",  # Value vs growth
            "Quality",  # Financial quality
            "Size",  # Market capitalization
            "Volatility",  # Historical volatility
            "Profitability",  # Earnings quality
            "Growth",  # Revenue/earnings growth
            "Leverage"  # Financial leverage
        ]

        # Extract sector, country, and currency factors from master data
        self.sector_factors = self._extract_sectors()
        self.country_factors = self._extract_countries()
        self.currency_factors = self._extract_currencies()

        # Define factor types that must sum to 1 (allocation/exposure factors)
        self.factor_types_cum_eq_1 = {}
        if self.sector_factors:
            self.factor_types_cum_eq_1["Sector"] = self.sector_factors
        if self.country_factors:
            self.factor_types_cum_eq_1["Country"] = self.country_factors
        if self.currency_factors:
            self.factor_types_cum_eq_1["Currency"] = self.currency_factors

        # Define factor types that can be random values between -1 and 1
        self.factor_types_cum_neq_1 = {
            "Style": self.style_factors
        }

        logging.info(f"Random Risk Model initialized:")
        logging.info(f"  Style factors: {len(self.style_factors)}")
        logging.info(f"  Sector factors: {len(self.sector_factors)}")
        logging.info(f"  Country factors: {len(self.country_factors)}")
        logging.info(f"  Currency factors: {len(self.currency_factors)}")

        self.exposures = pd.DataFrame()

    def _extract_sectors(self) -> List[str]:
        """Extract unique sectors from master data"""
        if self.master_data.empty:
            return ["Technology", "Finance", "Healthcare"]  # Default fallback

        # Try common sector column names
        sector_columns = ["SECTOR", "Sector", "sector", "GICS_SECTOR", "Industry"]

        for col in sector_columns:
            if col in self.master_data.columns:
                sectors = self.master_data[col].dropna().unique().tolist()
                if sectors:
                    logging.info(f"Found sectors in column '{col}': {sectors}")
                    return sorted(sectors)

        logging.warning("No sector column found in master data, using defaults")
        return ["Technology", "Finance", "Healthcare"]

    def _extract_countries(self) -> List[str]:
        """Extract unique countries from master data"""
        if self.master_data.empty:
            return ["USA"]  # Default fallback

        # Try common country column names
        country_columns = ["COUNTRY", "Country", "country", "LOCATION", "Location"]

        for col in country_columns:
            if col in self.master_data.columns:
                countries = self.master_data[col].dropna().unique().tolist()
                if countries:
                    logging.info(f"Found countries in column '{col}': {countries}")
                    return sorted(countries)

        logging.warning("No country column found in master data, using defaults")
        return ["USA"]

    def _extract_currencies(self) -> List[str]:
        """Extract unique currencies from master data"""
        if self.master_data.empty:
            return ["USD"]  # Default fallback

        # Try common currency column names
        currency_columns = ["CURRENCY", "Currency", "currency", "CCY", "Ccy"]

        for col in currency_columns:
            if col in self.master_data.columns:
                currencies = self.master_data[col].dropna().unique().tolist()
                if currencies:
                    logging.info(f"Found currencies in column '{col}': {currencies}")
                    return sorted(currencies)

        logging.warning("No currency column found in master data, using defaults")
        return ["USD"]

    def get_symbol_sector(self, symbol: str) -> str:
        """Get sector for a specific symbol from master data"""
        if self.master_data.empty:
            return random.choice(self.sector_factors)

        # Try to find the symbol in master data
        symbol_columns = ["SYMBOL", "Symbol", "symbol", "TICKER", "Ticker"]
        sector_columns = ["SECTOR", "Sector", "sector", "GICS_SECTOR", "Industry"]

        symbol_col = None
        sector_col = None

        for col in symbol_columns:
            if col in self.master_data.columns:
                symbol_col = col
                break

        for col in sector_columns:
            if col in self.master_data.columns:
                sector_col = col
                break

        if symbol_col and sector_col:
            symbol_data = self.master_data[self.master_data[symbol_col] == symbol]
            if not symbol_data.empty:
                sector = symbol_data[sector_col].iloc[0]
                if pd.notna(sector):
                    return sector

        # Fallback to random sector
        return random.choice(self.sector_factors)

    def get_symbol_country(self, symbol: str) -> str:
        """Get country for a specific symbol from master data"""
        if self.master_data.empty:
            return random.choice(self.country_factors)

        # Similar logic as get_symbol_sector but for country
        symbol_columns = ["SYMBOL", "Symbol", "symbol", "TICKER", "Ticker"]
        country_columns = ["COUNTRY", "Country", "country", "LOCATION", "Location"]

        symbol_col = None
        country_col = None

        for col in symbol_columns:
            if col in self.master_data.columns:
                symbol_col = col
                break

        for col in country_columns:
            if col in self.master_data.columns:
                country_col = col
                break

        if symbol_col and country_col:
            symbol_data = self.master_data[self.master_data[symbol_col] == symbol]
            if not symbol_data.empty:
                country = symbol_data[country_col].iloc[0]
                if pd.notna(country):
                    return country

        return random.choice(self.country_factors)

    def get_symbol_currency(self, symbol: str) -> str:
        """Get currency for a specific symbol from master data"""
        if self.master_data.empty:
            return random.choice(self.currency_factors)

        # Similar logic as get_symbol_sector but for currency
        symbol_columns = ["SYMBOL", "Symbol", "symbol", "TICKER", "Ticker"]
        currency_columns = ["CURRENCY", "Currency", "currency", "CCY", "Ccy"]

        symbol_col = None
        currency_col = None

        for col in symbol_columns:
            if col in self.master_data.columns:
                symbol_col = col
                break

        for col in currency_columns:
            if col in self.master_data.columns:
                currency_col = col
                break

        if symbol_col and currency_col:
            symbol_data = self.master_data[self.master_data[symbol_col] == symbol]
            if not symbol_data.empty:
                currency = symbol_data[currency_col].iloc[0]
                if pd.notna(currency):
                    return currency

        return random.choice(self.currency_factors)

    def generate_exposures(self, date: date) -> List[Dict[str, Any]]:
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
                if factor_type == "Sector":
                    # For sectors, assign 1.0 to the symbol's actual sector, 0.0 to others
                    symbol_sector = self.get_symbol_sector(symbol)
                    for factor_name in factor_names:
                        value = 1.0 if factor_name == symbol_sector else 0.0
                        row = {
                            "date": date,
                            "model": self.model,
                            "factor1": factor_type,
                            "factor2": factor_name,
                            "factor3": "",
                            "symbol": symbol,
                            "type": factor_type,
                            "name": factor_name,
                            "value": round(value, 6)
                        }
                        data.append(row)

                elif factor_type == "Country":
                    # For countries, assign 1.0 to the symbol's actual country, 0.0 to others
                    symbol_country = self.get_symbol_country(symbol)
                    for factor_name in factor_names:
                        value = 1.0 if factor_name == symbol_country else 0.0
                        row = {
                            "date": date,
                            "model": self.model,
                            "factor1": factor_type,
                            "factor2": factor_name,
                            "factor3": "",
                            "symbol": symbol,
                            "type": factor_type,
                            "name": factor_name,
                            "value": round(value, 6)
                        }
                        data.append(row)

                elif factor_type == "Currency":
                    # For currencies, assign 1.0 to the symbol's actual currency, 0.0 to others
                    symbol_currency = self.get_symbol_currency(symbol)
                    for factor_name in factor_names:
                        value = 1.0 if factor_name == symbol_currency else 0.0
                        row = {
                            "date": date,
                            "model": self.model,
                            "factor1": factor_type,
                            "factor2": factor_name,
                            "factor3": "",
                            "symbol": symbol,
                            "type": factor_type,
                            "name": factor_name,
                            "value": round(value, 6)
                        }
                        data.append(row)

                else:
                    # For other factor types, generate random values that sum to 1
                    num_factors = len(factor_names)
                    random_points = sorted([random.uniform(0, 1) for _ in range(num_factors - 1)])

                    values_to_sum = [random_points[0]]
                    for i in range(num_factors - 2):
                        values_to_sum.append(random_points[i + 1] - random_points[i])
                    values_to_sum.append(1 - random_points[-1])

                    for factor_name, value in zip(factor_names, values_to_sum):
                        row = {
                            "date": date,
                            "model": self.model,
                            "factor1": factor_type,
                            "factor2": factor_name,
                            "factor3": "",
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
                        "factor1": factor_type,
                        "factor2": factor_name,
                        "factor3": "",
                        "symbol": symbol,
                        "type": factor_type,
                        "name": factor_name,
                        "value": value
                    }
                    data.append(row)

        self.exposures = data
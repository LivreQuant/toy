from source.models.base import BaseRiskModel
from datetime import date
from typing import List, Dict, Any
import random
import pandas as pd
import logging

from source.utils.update_sectors import update_sectors
from source.utils.update_regions import update_regions
from source.utils.update_mktcap import update_mktcap
from source.utils.update_currencies import update_currencies


class RandomRiskModel(BaseRiskModel):
    """
    Generates random risk factor data based on master file universe.
    ALL risk model structure and factor definitions are contained here.
    """

    def __init__(self, model: str, master_data: pd.DataFrame):
        """
        Initializes the Random risk model.

        Args:
            model (str): The name of the risk model.
            symbol_manager (SymbolManager): Symbol manager containing master data.
        """
        super().__init__(model, master_data)

        # Get the master data from symbol manager and update all mappings
        self.master_data = update_sectors(master_data)
        self.master_data = update_regions(self.master_data)

        test_symbol = self.master_data[self.master_data['symbol'] == 'ADAM']
        if not test_symbol.empty:
            print(
                f"ADAM after currency update - Region: {test_symbol['region'].iloc[0]}, Currency: {test_symbol['currency'].iloc[0]}")

        self.master_data = update_mktcap(self.master_data)

        test_symbol = self.master_data[self.master_data['symbol'] == 'ADAM']
        if not test_symbol.empty:
            print(
                f"ADAM after currency update - Region: {test_symbol['region'].iloc[0]}, Currency: {test_symbol['currency'].iloc[0]}")

        self.master_data = update_currencies(self.master_data)

        # Debug: Check a specific symbol
        test_symbol = self.master_data[self.master_data['symbol'] == 'ADAM']
        if not test_symbol.empty:
            print(
                f"ADAM after currency update - Region: {test_symbol['region'].iloc[0]}, Currency: {test_symbol['currency'].iloc[0]}")

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

        # Extract sector, region, currency, and market cap factors from master data
        self.sector_factors = self._extract_sectors()
        self.region_factors = self._extract_regions()
        self.currency_factors = self._extract_currencies()
        self.mktcap_factors = self._extract_mktcaps()

        # Define factor types that must sum to 1 (allocation/exposure factors)
        self.factor_types_cum_eq_1 = {}
        if self.sector_factors:
            self.factor_types_cum_eq_1["Sector"] = self.sector_factors
        if self.region_factors:
            self.factor_types_cum_eq_1["Region"] = self.region_factors
        if self.currency_factors:
            self.factor_types_cum_eq_1["Currency"] = self.currency_factors
        if self.mktcap_factors:
            self.factor_types_cum_eq_1["MarketCap"] = self.mktcap_factors

        # Define factor types that can be random values between -1 and 1
        self.factor_types_cum_neq_1 = {
            "Style": self.style_factors
        }

        logging.info(f"Random Risk Model initialized:")
        logging.info(f"  Style factors: {len(self.style_factors)}")
        logging.info(f"  Sector factors: {len(self.sector_factors)}")
        logging.info(f"  Region factors: {len(self.region_factors)}")
        logging.info(f"  Currency factors: {len(self.currency_factors)}")
        logging.info(f"  Market Cap factors: {len(self.mktcap_factors)}")

        self.exposures = pd.DataFrame()

    def _extract_sectors(self) -> List[str]:
        """Extract unique sectors from master data"""
        # Try common sector column names
        sector_columns = ["sector"]

        for col in sector_columns:
            if col in self.master_data.columns:
                sectors = self.master_data[col].dropna().unique().tolist()
                if sectors:
                    # Get sector counts
                    sector_counts = self.master_data[col].value_counts()

                    logging.info(f"Found sectors in column '{col}':")
                    for sector, count in sector_counts.items():
                        logging.info(f"  {sector}: {count}")

                    return sorted(sectors)

        raise ValueError("No sector column found in master data")

    def _extract_regions(self) -> List[str]:
        """Extract unique regions from master data"""
        # Try common region column names
        region_columns = ["region"]

        for col in region_columns:
            if col in self.master_data.columns:
                regions = self.master_data[col].dropna().unique().tolist()
                if regions:
                    # Get region counts
                    region_counts = self.master_data[col].value_counts()

                    logging.info(f"Found regions in column '{col}':")
                    for region, count in region_counts.items():
                        logging.info(f"  {region}: {count}")

                    return sorted(regions)

        raise ValueError("No region column found in master data")

    def _extract_currencies(self) -> List[str]:
        """Extract unique currencies from master data"""
        # Try common currency column names
        currency_columns = ["currency"]

        for col in currency_columns:
            if col in self.master_data.columns:
                currencies = self.master_data[col].dropna().unique().tolist()
                if currencies:
                    # Get currency counts (including empty strings)
                    currency_counts = self.master_data[col].value_counts(dropna=False)

                    logging.info(f"Found currencies in column '{col}':")
                    for currency, count in currency_counts.items():
                        if pd.isna(currency) or currency == '':
                            logging.info(f"  UNKNOWN: {count}")
                        else:
                            logging.info(f"  {currency}: {count}")

                    if currencies:
                        return sorted(currencies)

        raise ValueError("No currency column found in master data")

    def _extract_mktcaps(self) -> List[str]:
        """Extract unique market cap scales from master data"""
        # Try common market cap column names
        mktcap_columns = ["scalemarketcap"]

        for col in mktcap_columns:
            if col in self.master_data.columns:
                mktcaps = self.master_data[col].dropna().unique().tolist()
                if mktcaps:
                    # Get market cap counts
                    mktcap_counts = self.master_data[col].value_counts()

                    logging.info(f"Found market cap scales in column '{col}':")
                    for mktcap, count in mktcap_counts.items():
                        logging.info(f"  {mktcap}: {count}")

                    return sorted(mktcaps)

        raise ValueError("No market cap scale column found in master data")

    def get_symbol_sector(self, symbol: str) -> str:
        """Get sector for a specific symbol from master data"""
        # Try to find the symbol in master data
        symbol_columns = ["symbol"]
        sector_columns = ["sector"]

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
                if pd.notna(sector) and sector != 'UNKNOWN':
                    return sector

        # Fallback to random sector
        return 'UNKNOWN'

    def get_symbol_region(self, symbol: str) -> str:
        """Get region for a specific symbol from master data"""
        if self.master_data.empty:
            return random.choice(self.region_factors)

        # Similar logic as get_symbol_sector but for region
        symbol_columns = ["symbol"]
        region_columns = ["region"]

        symbol_col = None
        region_col = None

        for col in symbol_columns:
            if col in self.master_data.columns:
                symbol_col = col
                break

        for col in region_columns:
            if col in self.master_data.columns:
                region_col = col
                break

        if symbol_col and region_col:
            symbol_data = self.master_data[self.master_data[symbol_col] == symbol]
            if not symbol_data.empty:
                region = symbol_data[region_col].iloc[0]
                if pd.notna(region) and region != 'UNKNOWN':
                    return region

        return 'UNKNOWN'

    def get_symbol_currency(self, symbol: str) -> str:
        """Get currency for a specific symbol from master data"""
        # Similar logic as get_symbol_sector but for currency
        symbol_columns = ["symbol"]
        currency_columns = ["currency"]

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
                if pd.notna(currency) and currency != 'UNKNOWN':
                    return currency

        return 'UNKNOWN'

    def get_symbol_mktcap(self, symbol: str) -> str:
        """Get market cap scale for a specific symbol from master data"""
        # Similar logic as get_symbol_sector but for market cap scale
        symbol_columns = ["symbol"]
        mktcap_columns = ["scalemarketcap"]

        symbol_col = None
        mktcap_col = None

        for col in symbol_columns:
            if col in self.master_data.columns:
                symbol_col = col
                break

        for col in mktcap_columns:
            if col in self.master_data.columns:
                mktcap_col = col
                break

        if symbol_col and mktcap_col:
            symbol_data = self.master_data[self.master_data[symbol_col] == symbol]
            if not symbol_data.empty:
                mktcap = symbol_data[mktcap_col].iloc[0]
                if pd.notna(mktcap) and mktcap != 'UNKNOWN':
                    return mktcap

        return 'UNKNOWN'

    def _get_symbols_from_master_data(self) -> List[str]:
        """Extract symbols from master data"""
        # Try common symbol column names
        symbol_columns = ["symbol"]

        for col in symbol_columns:
            if col in self.master_data.columns:
                symbols = self.master_data[col].dropna().unique().tolist()
                if symbols:
                    logging.info(f"Found {len(symbols)} symbols in column '{col}'")
                    return symbols

        logging.warning("No symbol column found in master data")
        return []

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

        # Get symbols from master data
        symbols = self._get_symbols_from_master_data()

        if not symbols:
            logging.error("No symbols found in master data")
            return data

        for symbol in symbols:
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
                            "symbol": symbol,
                            "factor1": factor_type,
                            "factor2": factor_name,
                            "factor3": "",
                            "value": round(value, 6)
                        }
                        data.append(row)

                elif factor_type == "Region":
                    # For regions, assign 1.0 to the symbol's actual region, 0.0 to others
                    symbol_region = self.get_symbol_region(symbol)
                    for factor_name in factor_names:
                        value = 1.0 if factor_name == symbol_region else 0.0
                        row = {
                            "date": date,
                            "model": self.model,
                            "symbol": symbol,
                            "factor1": factor_type,
                            "factor2": factor_name,
                            "factor3": "",
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
                            "symbol": symbol,
                            "factor1": factor_type,
                            "factor2": factor_name,
                            "factor3": "",
                            "value": round(value, 6)
                        }
                        data.append(row)

                elif factor_type == "MarketCap":
                    # For market cap, assign 1.0 to the symbol's actual market cap scale, 0.0 to others
                    symbol_mktcap = self.get_symbol_mktcap(symbol)
                    for factor_name in factor_names:
                        value = 1.0 if factor_name == symbol_mktcap else 0.0
                        row = {
                            "date": date,
                            "model": self.model,
                            "symbol": symbol,
                            "factor1": factor_type,
                            "factor2": factor_name,
                            "factor3": "",
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
                            "symbol": symbol,
                            "factor1": factor_type,
                            "factor2": factor_name,
                            "factor3": "",
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
                        "symbol": symbol,
                        "factor1": factor_type,
                        "factor2": factor_name,
                        "factor3": "",
                        "value": value
                    }
                    data.append(row)

        # Filter out zero exposures for cleaner output
        data = [row for row in data if row['value'] != 0.0]

        self.exposures = data

        logging.info(f"Generated {len(data)} non-zero exposure records for {len(symbols)} symbols")
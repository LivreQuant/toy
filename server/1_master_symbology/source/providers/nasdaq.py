import pandas as pd
import requests
import os
from source.providers.utils import standardize
from source.config import config

from pathlib import Path

csv_path = Path(__file__).parent / "../standards/types.csv"
df_types = pd.read_csv(csv_path, dtype=str, keep_default_na=False, na_values=[])

OLD_COLUMNS = ['Symbol', 'exchange', 'Security Name', 'Financial Status', 'Round Lot Size', 'ETF']
NEW_COLUMNS = ['na_symbol', 'exchange', 'na_name', 'na_status', 'na_lot', 'na_etf']


def load_nasdaq_data():
    """
    Fetches NASDAQ listed symbols and loads them into a pandas DataFrame using requests.
    Caches the data to a local file.
    """
    # Ensure data directory exists
    os.makedirs(config.nasdaq_data_path, exist_ok=True)
    file_path = os.path.join(config.nasdaq_data_path, f"NASDAQ.csv")

    # Check if the cached file exists
    if os.path.exists(file_path):
        print(f"Loading data from cached file: {file_path}")
        df = pd.read_csv(file_path, dtype=str, keep_default_na=False, na_values=[])

        """
        # Normalize symbols (e.g., upper case) to catch duplicates
        df["symbol_norm"] = df["Symbol"].str.upper()

        # Count uppercase letters (e.g., TpC vs TPC)
        df["uppercase_count"] = df["Symbol"].str.count(r"[A-Z]")

        # For each group, keep the one with the most uppercase letters (keep TPC)
        df = (
            df.sort_values(["symbol_norm", "uppercase_count"], ascending=[True, False])
            .drop_duplicates("symbol_norm", keep="first")
            .drop(columns=["symbol_norm", "uppercase_count"])
            .reset_index(drop=True)
        )
        """

        # Exchange
        df['exchange'] = 'XNAS'

        # Remove test
        df = df.loc[df['Test Issue'] == 'N']

        # Select and rename columns
        df = df[OLD_COLUMNS]
        df.columns = NEW_COLUMNS

        # Standardize symbol
        df['standardized_symbol'] = df['na_symbol']  # .apply(standardize)

        df = df.loc[df['exchange'].isin(['XNYS', 'XNAS'])]

        # Status
        df['na_status'] = df['na_status'].replace({
            'N': 'Normal',
            'D': 'Deficient',
            'E': "Delinquent",
            'Q': "Bankrupt",
            "G": "Bankrupt",
            "H": "Delinquent",
            "J": "Bankrupt",
            "K": "Bankrupt",
        })

        return df

    url = "https://www.nasdaqtrader.com/dynamic/symdir/nasdaqlisted.txt"
    try:
        response = requests.get(url)
        response.raise_for_status()  # Raise an exception for bad status codes
        content = response.text
        # The data is pipe-delimited
        # The first line is a header, the last line is a footer
        lines = content.splitlines()
        data = [line.split('|') for line in lines[1:-1]]
        df = pd.DataFrame(data, columns=[h.strip() for h in lines[0].split('|')])

        # Save the DataFrame to a CSV file
        df.to_csv(file_path, index=False)
        print(f"Saved data to cached file: {file_path}")

        """
        # Normalize symbols (e.g., upper case) to catch duplicates
        df["symbol_norm"] = df["Symbol"].str.upper()

        # Count uppercase letters (e.g., TpC vs TPC)
        df["uppercase_count"] = df["Symbol"].str.count(r"[A-Z]")

        # For each group, keep the one with the most uppercase letters (keep TPC)
        df = (
            df.sort_values(["symbol_norm", "uppercase_count"], ascending=[True, False])
            .drop_duplicates("symbol_norm", keep="first")
            .drop(columns=["symbol_norm", "uppercase_count"])
            .reset_index(drop=True)
        )
        """

        # Exchange
        df['exchange'] = 'XNAS'

        # Remove test
        df = df.loc[df['Test Issue'] == 'N']

        # Select and rename columns
        df = df[OLD_COLUMNS]
        df.columns = NEW_COLUMNS

        # Standardize symbol
        df['standardized_symbol'] = df['na_symbol']  # .apply(standardize)

        df = df.loc[df['exchange'].isin(['XNYS', 'XNAS'])]

        # Status
        df['na_status'] = df['na_status'].replace({
            'N': 'Normal',
            'D': 'Deficient',
            'E': "Delinquent",
            'Q': "Bankrupt",
            "G": "Bankrupt",
            "H": "Delinquent",
            "J": "Bankrupt",
            "K": "Bankrupt",
        })

        return df
    except requests.exceptions.RequestException as e:
        print(f"Error fetching NASDAQ data: {e}")
        raise ValueError("Missing NASDAQ Data")

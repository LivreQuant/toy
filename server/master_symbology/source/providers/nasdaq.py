import pandas as pd
import requests
import os
from datetime import datetime
from source.providers.utils import standardize

OLD_COLUMNS = ['Symbol', 'exchange', 'Security Name',
               #'Market Category',
               #'Test Issue',
               'Financial Status', 'Round Lot Size',
               'ETF',
               #'NextShares'
               ]

NEW_COLUMNS = ['na_symbol', 'exchange', 'na_name',
               #'na_type',
               #'na_test',
               'na_status', 'na_lot',
               'na_etf',
               #'na_next'
               ]


def load_nasdaq_data():
    """
    Fetches NASDAQ listed symbols and loads them into a pandas DataFrame using requests.
    Caches the data to a local file.
    """
    # Define the data directory and file path
    data_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data"))
    os.makedirs(data_dir, exist_ok=True)
    file_path = os.path.join(data_dir, f"{datetime.now().strftime('%Y%m%d')}_NASDAQ.csv")

    # Check if the cached file exists
    if os.path.exists(file_path):
        print(f"Loading data from cached file: {file_path}")
        df = pd.read_csv(file_path)

        # Exchange
        df['exchange'] = 'XNAS'

        # Remove test
        df = df.loc[df['Test Issue'] == 'N']

        # Select and rename columns
        df = df[OLD_COLUMNS]
        df.columns = NEW_COLUMNS

        # Standardize symbol
        df['standardized_symbol'] = df['na_symbol'].apply(standardize)

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

        # Exchange
        df['exchange'] = 'XNAS'

        # Remove test
        df = df.loc[df['Test Issue'] == 'N']

        # Select and rename columns
        df = df[OLD_COLUMNS]
        df.columns = NEW_COLUMNS

        # Standardize symbol
        df['standardized_symbol'] = df['na_symbol'].apply(standardize)

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

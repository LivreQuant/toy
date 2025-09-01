import os
import pandas as pd
import requests
from datetime import datetime
from source.providers.utils import standardize
from source.config import config

OLD_COLUMNS = ['Code', 'Exchange', 'Type', 'Name',
               'Country', 'Currency', 'Isin']

NEW_COLUMNS = ['ed_symbol', 'exchange', 'ed_type', 'ed_name',
               'ed_country', 'ed_currency', 'ed_isin']


def load_eodhd_data():
    """
    Fetches exchange symbol list from EODHD API, caches it, and returns a DataFrame.
    """
    # Ensure data directory exists
    os.makedirs(config.data_dir, exist_ok=True)
    file_path = os.path.join(config.data_dir, f"{datetime.now().strftime('%Y%m%d')}_EODHD.csv")

    # Check if the cached file exists
    if os.path.exists(file_path):
        print(f"Loading data from cached file: {file_path}")
        df = pd.read_csv(file_path)

        # Select and rename columns
        df = df[OLD_COLUMNS]
        df.columns = NEW_COLUMNS

        # Standardize symbol
        df['standardized_symbol'] = df['ed_symbol'].apply(standardize)
        df['ed_currency'] = df['ed_currency'].apply(standardize)

        # Standardize exchange
        df['exchange'] = df['exchange'].replace({
            'NASDAQ': 'XNAS',
            'NYSE': 'XNYS'
        })

        df = df.loc[df['exchange'].isin(['XNYS', 'XNAS'])]

        # Convert to Intrinio Types
        df['ed_type'] = df['ed_type'].replace({
            'Common Stock': 'EQS',
            'ETF': 'ETF',
            'Preferred Stock': 'PRF',
            'FUND': 'FND',
            'Notes': 'NTS',
            'Unit': 'UNT',
            'Mutual Fund': 'CEF',
            'BOND': 'BND'
        })

        return df

    # Get API key from config
    if not config.eodhd_api_key:
        raise ValueError("EODHD_API_KEY not found in environment variables")

    # Construct the API URL
    url = f'https://eodhd.com/api/exchange-symbol-list/US?api_token={config.eodhd_api_key}&fmt=json'

    try:
        response = requests.get(url)
        response.raise_for_status()

        # Read the JSON content into a DataFrame
        data = response.json()
        df = pd.DataFrame(data)

        # Save the DataFrame to a CSV file
        df.to_csv(file_path, index=False)
        print(f"Saved data to cached file: {file_path}")

        # Select and rename columns
        df = df[OLD_COLUMNS]
        df.columns = NEW_COLUMNS

        # Standardize symbol
        df['standardized_symbol'] = df['ed_symbol'].apply(standardize)
        df['ed_currency'] = df['ed_currency'].apply(standardize)

        # Standardize exchange
        df['exchange'] = df['exchange'].replace({
            'NASDAQ': 'XNAS',
            'NYSE': 'XNYS'
        })

        df = df.loc[df['exchange'].isin(['XNYS', 'XNAS'])]

        # Convert to Intrinio Types
        df['ed_type'] = df['ed_type'].replace({
            'Common Stock': 'EQS',
            'ETF': 'ETF',
            'Preferred Stock': 'PRF',
            'FUND': 'FND',
            'Notes': 'NTS',
            'Unit': 'UNT',
            'Mutual Fund': 'CEF',
            'BOND': 'BND'
        })

        return df

    except requests.exceptions.RequestException as e:
        print(f"Error fetching EODHD data: {e}")
        raise ValueError("Missing EODHD Data")
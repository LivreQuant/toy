import os
import pandas as pd
import requests
import io
from datetime import datetime
from source.providers.utils import standardize
from source.config import config

OLD_COLUMNS = ['symbol', 'exchange', 'name', 'status']
NEW_COLUMNS = ['av_symbol', 'exchange', 'av_name', 'av_status']


def load_alphavantage_data():
    """
    Fetches listing status from Alpha Vantage API, caches it, and returns a DataFrame.
    """
    # Ensure data directory exists
    os.makedirs(config.alphavantage_data_path, exist_ok=True)
    file_path = os.path.join(config.alphavantage_data_path, f"{datetime.now().strftime('%Y%m%d')}_AV.csv")

    # Check if the cached file exists
    if os.path.exists(file_path):
        print(f"Loading data from cached file: {file_path}")
        df = pd.read_csv(file_path)

        # Select and rename columns
        df = df[OLD_COLUMNS]
        df.columns = NEW_COLUMNS

        # Standardize symbol
        df['standardized_symbol'] = df['av_symbol'].apply(standardize)

        # Standardize exchange
        df['exchange'] = df['exchange'].replace({
            'NASDAQ': 'XNAS',
            'NYSE': 'XNYS'
        })

        df = df.loc[df['exchange'].isin(['XNYS', 'XNAS'])]

        return df

    # Get API key from config
    if not config.alphavantage_api_key:
        raise ValueError("ALPHAVANTAGE_API_KEY not found in environment variables")

    # Construct the API URL
    url = f'https://www.alphavantage.co/query?function=LISTING_STATUS&apikey={config.alphavantage_api_key}'

    try:
        response = requests.get(url)
        response.raise_for_status()

        # Read the CSV content into a DataFrame
        df = pd.read_csv(io.StringIO(response.text))

        # Save the DataFrame to a CSV file
        df.to_csv(file_path, index=False)
        print(f"Saved data to cached file: {file_path}")

        # Select and rename columns
        df = df[OLD_COLUMNS]
        df.columns = NEW_COLUMNS

        # Standardize symbol
        df['standardized_symbol'] = df['av_symbol'].apply(standardize)

        # Standardize exchange
        df['exchange'] = df['exchange'].replace({
            'NASDAQ': 'XNAS',
            'NYSE': 'XNYS'
        })

        df = df.loc[df['exchange'].isin(['XNYS', 'XNAS'])]

        return df

    except requests.exceptions.RequestException as e:
        print(f"Error fetching Alpha Vantage data: {e}")
        raise ValueError("Missing Alpha Vantage Data")
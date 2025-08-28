import os
import pandas as pd
import requests
from dotenv import load_dotenv
import io
from datetime import datetime
from source.providers.utils import standardize

OLD_COLUMNS = ['symbol', 'exchange',  # 'assetType',
               'name',
               # 'ipoDate', 'delistingDate',
               'status']

NEW_COLUMNS = ['av_symbol', 'exchange',  # 'av_type',
               'av_name',
               # 'av_ipo', 'av_delisted',
               'av_status']


def load_alphavantage_data():
    """
    Fetches listing status from Alpha Vantage API, caches it, and returns a DataFrame.
    """
    # Define the data directory and file path
    data_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data"))
    os.makedirs(data_dir, exist_ok=True)
    file_path = os.path.join(data_dir, f"{datetime.now().strftime('%Y%m%d')}_AV.csv")

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

    # Load environment variables
    load_dotenv()
    api_key = os.getenv("ALPHAVANTAGE_API_KEY")
    if not api_key:
        raise ValueError("ALPHAVANTAGE_API_KEY not found in .env file")

    # Construct the API URL
    url = f'https://www.alphavantage.co/query?function=LISTING_STATUS&apikey={api_key}'

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

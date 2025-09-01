import os
import pandas as pd
import requests
from datetime import datetime
from source.providers.utils import standardize
from source.config import config

OLD_COLUMNS = ['symbol', 'exchange', 'name', 'status', 'tradable', 'marginable',
               'maintenance_margin_requirement', 'margin_requirement_long', 'margin_requirement_short',
               'shortable', 'easy_to_borrow']

NEW_COLUMNS = ['al_symbol', 'exchange', 'al_name', 'al_status',
               'al_tradable', 'al_marginable',
               'al_maintenance_margin_requirement', 'al_margin_requirement_long', 'al_margin_requirement_short',
               'al_shortable', 'al_easy_to_borrow']



def load_alpaca_data():
    """
    Fetches assets from Alpaca API, caches them, and returns a DataFrame.
    """
    # Ensure data directory exists
    os.makedirs(config.data_dir, exist_ok=True)
    file_path = os.path.join(config.data_dir, f"{datetime.now().strftime('%Y%m%d')}_ALPACA.csv")

    # Check if the cached file exists
    if os.path.exists(file_path):
        print(f"Loading data from cached file: {file_path}")
        df = pd.read_csv(file_path)

        # Columns to keep
        df = df[OLD_COLUMNS]
        df.columns = NEW_COLUMNS

        # Standardize symbol
        df['standardized_symbol'] = df['al_symbol'].apply(standardize)

        # Standardize exchange
        df['exchange'] = df['exchange'].replace({
            'NASDAQ': 'XNAS',
            'NYSE': 'XNYS'
        })

        df = df.loc[df['exchange'].isin(['XNYS', 'XNAS'])]

        return df

    # Get API keys from config
    if not config.alpaca_api_key or not config.alpaca_secret_key:
        raise ValueError("ALPACA_API_KEY or ALPACA_SECRET_KEY not found in environment variables")

    # Construct the API URL and headers
    url = "https://paper-api.alpaca.markets/v2/assets?attributes="
    headers = {
        "accept": "application/json",
        "APCA-API-KEY-ID": config.alpaca_api_key,
        "APCA-API-SECRET-KEY": config.alpaca_secret_key
    }

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()

        # Read the JSON content into a DataFrame
        data = response.json()
        df = pd.DataFrame(data)

        # Save the DataFrame to a CSV file
        df.to_csv(file_path, index=False)
        print(f"Saved data to cached file: {file_path}")

        # Columns to keep
        df = df[OLD_COLUMNS]
        df.columns = NEW_COLUMNS

        # Standardize symbol
        df['standardized_symbol'] = df['al_symbol'].apply(standardize)

        # Standardize exchange
        df['exchange'] = df['exchange'].replace({
            'NASDAQ': 'XNAS',
            'NYSE': 'XNYS'
        })

        df = df.loc[df['exchange'].isin(['XNYS', 'XNAS'])]

        return df

    except requests.exceptions.RequestException as e:
        print(f"Error fetching Alpaca data: {e}")
        raise ValueError("Missing Alpaca Data")
    except ValueError as e:
        print(f"Error parsing Alpaca data: {e}")
        raise ValueError("Missing Alpaca Data")
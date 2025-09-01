import pandas as pd
import os
import json
from datetime import datetime
from source.providers.utils import standardize
from source.config import config

OLD_COLUMNS = ['ticker', 'primary_exchange', 'type', 'name',
               'locale', 'active', 'currency_name',
               'composite_figi', 'share_class_figi',
               'share_class_shares_outstanding',
               'cik', 'sic_code', 'sic_description',
               'address',
               'market_cap', 'description', 'homepage_url', 'branding', 'weighted_shares_outstanding']

NEW_COLUMNS = ['pl_symbol', 'exchange', 'pl_type', 'pl_name',
               'pl_locale', 'pl_status', 'pl_currency',
               'pl_composite_figi', 'pl_share_class_figi',
               'pl_share_class_shares_outstanding',
               'pl_cik', 'pl_sic_code', 'pl_sic_description',
               'pl_location',
               'pl_market_capital_2', 'pl_description', 'pl_homepage_url', 'pl_branding', 'pl_weighted_shares_outstanding']


def load_poly_data():
    """
    Loads all individual JSON symbol files from the poly directory using pandas.
    Only the 'results' key from each file is loaded.
    """
    # Ensure data directory exists
    os.makedirs(config.data_dir, exist_ok=True)
    raw_file_path = os.path.join(config.data_dir, f"{datetime.now().strftime('%Y%m%d')}_POLY_raw.csv")

    all_results = []

    # Verify polygon data path exists
    if not os.path.exists(config.polygon_data_path):
        raise FileNotFoundError(f"Polygon data directory not found: {config.polygon_data_path}")

    for filename in os.listdir(config.polygon_data_path):
        if filename.endswith(".json"):
            file_path = os.path.join(config.polygon_data_path, filename)
            with open(file_path, 'r') as f:
                try:
                    data = json.load(f)
                    if 'results' in data:
                        all_results.append(data['results'])
                except (json.JSONDecodeError, ValueError):
                    print(f"Could not decode JSON from {filename}")

    df = pd.DataFrame(all_results)

    # Save the raw DataFrame
    df.to_csv(raw_file_path, index=False)
    print(f"Saved raw Poly data to: {raw_file_path}")

    # Columns to keep
    df = df[OLD_COLUMNS]
    df.columns = NEW_COLUMNS

    # Standardize symbol
    df['standardized_symbol'] = df['pl_symbol'].apply(standardize)
    df['pl_currency'] = df['pl_currency'].apply(standardize)

    df = df.loc[df['exchange'].isin(['XNYS', 'XNAS'])]

    # Convert to Intrinio Types
    df['pl_type'] = df['pl_type'].replace({
        'CS': 'EQS',
        'ETF': 'ETF',
        'PFD': 'PRF',
        'WARRANT': 'WAR',
        'ADRC': 'DR',
        'RIGHT': 'RTS'
    })

    # Branding
    df['pl_branding'] = df['pl_branding'].str.get('logo_url')

    return df
import pandas as pd
import os
import json
from datetime import datetime
from source.providers.utils import standardize

OLD_COLUMNS = ['ticker', 'primary_exchange', 'type', 'name',
               #'market',
               'locale', 'active', 'currency_name',
               'composite_figi', 'share_class_figi',
               #'ticker_root',
               'share_class_shares_outstanding',
               'cik', 'sic_code', 'sic_description',
               'address',
               #'ticker_suffix',
               'market_cap', 'description', 'homepage_url', 'branding', 'weighted_shares_outstanding']

NEW_COLUMNS = ['pl_symbol', 'exchange', 'pl_type', 'pl_name',
               #'pl_market',
               'pl_locale', 'pl_status', 'pl_currency',
               'pl_composite_figi', 'pl_share_class_figi',
               #'pl_symbol_root',
               'pl_share_class_shares_outstanding',
               'pl_cik', 'pl_sic_code', 'pl_sic_description',
               'pl_location',
               #'pl_symbol_suffix',
               'pl_market_capital_2', 'pl_description', 'pl_homepage_url', 'pl_branding', 'pl_weighted_shares_outstanding']


def load_poly_data():
    """
    Loads all individual JSON symbol files from the poly directory using pandas.
    Only the 'results' key from each file is loaded.
    """
    # Define the data directory and file path
    data_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data"))
    os.makedirs(data_dir, exist_ok=True)
    raw_file_path = os.path.join(data_dir, f"{datetime.now().strftime('%Y%m%d')}_POLY_raw.csv")

    base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "example", "poly"))
    all_results = []

    for filename in os.listdir(base_path):
        if filename.endswith(".json"):
            file_path = os.path.join(base_path, filename)
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

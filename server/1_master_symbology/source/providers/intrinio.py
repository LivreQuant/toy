import pandas as pd
import os
from source.providers.utils import standardize
from source.config import config

OLD_COLUMNS = ['ticker_x', 'exchange_mic_x', 'code_x', 'name_x',
               'currency_x',
               'composite_ticker_x',
               'figi_x', 'composite_figi_x', 'share_class_figi_x', 'primary_listing_x']

NEW_COLUMNS = ['it_symbol', 'exchange', 'it_type', 'it_name',
               'it_currency',
               'it_composite_symbol', 'it_figi', 'it_composite_figi', 'it_share_class_figi',
               'it_primary_listing']


def load_intrinio_data():
    """
    Loads and merges Intrinio data from JSON files using pandas.
    """
    # Ensure data directory exists
    #os.makedirs(config.data_dir, exist_ok=True)
    #raw_file_path = os.path.join(config.data_dir, f"{datetime.now().strftime('%Y%m%d')}_INTRINIO_raw.csv")

    # Construct absolute paths to the data files
    securities_path = os.path.join(config.intrinio_data_path, config.intrinio_securities_file)
    stock_exchange_path = os.path.join(config.intrinio_data_path, config.intrinio_exchange_file)

    # Verify files exist
    if not os.path.exists(securities_path):
        raise FileNotFoundError(f"Securities file not found: {securities_path}")
    if not os.path.exists(stock_exchange_path):
        raise FileNotFoundError(f"Stock exchange file not found: {stock_exchange_path}")

    # Load the JSON data into pandas DataFrames
    securities_df = pd.read_json(securities_path)
    stock_exchange_df = pd.read_json(stock_exchange_path)

    # Perform an outer merge
    merged_df = pd.merge(securities_df, stock_exchange_df, on='id', how='left')

    # Save the raw merged DataFrame
    #merged_df.to_csv(raw_file_path, index=False)
    #print(f"Saved raw Intrinio data to: {raw_file_path}")

    # Columns to keep
    merged_df = merged_df[OLD_COLUMNS]
    merged_df.columns = NEW_COLUMNS

    # Standardize symbol
    merged_df['standardized_symbol'] = merged_df['it_symbol'].apply(standardize)
    merged_df['it_currency'] = merged_df['it_currency'].apply(standardize)

    merged_df = merged_df.loc[merged_df['exchange'].isin(['XNYS', 'XNAS'])]

    return merged_df
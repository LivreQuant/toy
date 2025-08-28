import pandas as pd
import os
from datetime import datetime
from source.providers.utils import standardize

"""
(symbol,
 , 
 type,
 name_x,
 marketCap,
 earningsAnnouncement,
 sharesOutstanding,
)
"""

OLD_COLUMNS = ['symbol', 'exchange_y', 'type', 'name_x',
               'marketCap', 'earningsAnnouncement', 'sharesOutstanding']
NEW_COLUMNS = ['fp_symbol', 'exchange', 'fp_type', 'fp_name',
               'fp_market_capital_1',
               'fp_earnings_announcement', 'fp_shares_outstanding']


def load_fmp_data():
    """
    Loads and merges FMP data from JSON files using pandas.
    """
    # Define the data directory and file path
    data_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data"))
    os.makedirs(data_dir, exist_ok=True)
    raw_file_path = os.path.join(data_dir, f"{datetime.now().strftime('%Y%m%d')}_FMP_raw.csv")

    # Construct absolute paths to the data files
    base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "example", "fmp"))
    nasdaq_path = os.path.join(base_path, "NASDAQ.json")
    nyse_path = os.path.join(base_path, "NYSE.json")
    symbol_list_path = os.path.join(base_path, "symbol_list.json")

    # Load the JSON data into pandas DataFrames
    nasdaq_df = pd.read_json(nasdaq_path)
    nyse_df = pd.read_json(nyse_path)
    symbol_list_df = pd.read_json(symbol_list_path)

    # Combine NASDAQ and NYSE data
    combined_df = pd.concat([nasdaq_df, nyse_df], ignore_index=True)

    # Perform a left merge
    merged_df = pd.merge(combined_df, symbol_list_df, on='symbol', how='left')

    # Save the raw merged DataFrame
    merged_df.to_csv(raw_file_path, index=False)
    print(f"Saved raw FMP data to: {raw_file_path}")

    # Select and rename columns
    merged_df = merged_df[OLD_COLUMNS]
    merged_df.columns = NEW_COLUMNS

    # Standardize symbol
    merged_df['standardized_symbol'] = merged_df['fp_symbol'].apply(standardize)

    # Standardize exchange
    merged_df['exchange'] = merged_df['exchange'].replace({
        'NASDAQ': 'XNAS',
        'New York Stock Exchange': 'XNYS'
    })

    merged_df = merged_df.loc[merged_df['exchange'].isin(['XNYS', 'XNAS'])]

    # Convert to Intrinio Types
    merged_df['fp_type'] = merged_df['fp_type'].replace({
        'stock': 'EQS',
        'etf': 'ETF',
        'fund': 'FND',
        'trust': 'TRT'
    })

    return merged_df

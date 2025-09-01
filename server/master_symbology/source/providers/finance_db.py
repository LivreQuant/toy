import financedatabase as fd
import pandas as pd
import os
from datetime import datetime
from source.providers.utils import standardize
from source.config import config

OLD_COLUMNS = ['symbol', 'market', 'name',
               'summary', 'currency',
               'sector', 'industry_group', 'industry',
               'country', 'state', 'city', 'zipcode',
               'website', 'market_cap',
               'isin', 'cusip', 'figi', 'composite_figi', 'shareclass_figi']

NEW_COLUMNS = ['fd_symbol', 'exchange', 'fd_name',
               'fd_description', 'fd_currency',
               'fd_sector', 'fd_industry_group', 'fd_industry',
               'fd_country', 'fd_state', 'fd_city', 'fd_zipcode',
               'fd_homepage_url', 'fd_scalemarketcap',
               'fd_isin', 'fd_cusip', 'fd_figi', 'fd_composite_figi', 'fd_share_class_figi']


def load_fd_data():
    # Ensure data directory exists
    os.makedirs(config.data_dir, exist_ok=True)
    raw_file_path = os.path.join(config.data_dir, f"{datetime.now().strftime('%Y%m%d')}_FD_raw.csv")

    equities = fd.Equities()
    equities.show_options(market=['New York Stock Exchange', 'NASDAQ Global Select'])
    stocks = equities.select(market=['New York Stock Exchange', 'NASDAQ Global Select'])

    df = pd.DataFrame(stocks).reset_index()

    # Save the raw DataFrame
    df.to_csv(raw_file_path, index=False)
    print(f"Saved raw FD data to: {raw_file_path}")

    # Select and rename columns
    df = df[OLD_COLUMNS]
    df.columns = NEW_COLUMNS

    # Standardize symbol
    df['standardized_symbol'] = df['fd_symbol'].apply(standardize)

    # Standardize exchange
    df['exchange'] = df['exchange'].replace({
        'NASDAQ Global Select': 'XNAS',
        'New York Stock Exchange': 'XNYS'
    })

    df = df.loc[df['exchange'].isin(['XNYS', 'XNAS'])]

    return df
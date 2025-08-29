import pandas as pd
import os
from datetime import datetime
from source.providers.utils import standardize

OLD_COLUMNS = ['ticker', 'exchange', 'category', 'name',
               'currency', 'location',  # 'isdelisted',
               'cusips',
               'siccode', 'sicsector', 'sicindustry', 'famasector', 'famaindustry',
               'sector', 'industry',
               'scalemarketcap', 'scalerevenue',
               'secfilings', 'companysite'
               ]

NEW_COLUMNS = ['sh_symbol', 'exchange', 'sh_type', 'sh_name',
               'sh_currency', 'sh_location',  # 'sh_isdelisted',
               'sh_cusips',
               'sh_sic_code', 'sh_sic_sector', 'sh_sic_industry', 'sh_fama_sector', 'sh_fama_industry',
               'sh_sector', 'sh_industry',
               'sh_scalemarketcap', 'sh_scalerevenue',
               'sh_cik', 'sh_homepage_url']


def load_sharadar_data():
    """
    Loads and merges Sharadar data from CSV files using pandas.
    """
    # Define the data directory and file path
    data_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data"))
    os.makedirs(data_dir, exist_ok=True)
    raw_file_path = os.path.join(data_dir, f"{datetime.now().strftime('%Y%m%d')}_SHARADAR_raw.csv")

    # Construct absolute paths to the data files
    base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "example", "sharadar"))
    sharadar_path = os.path.join(base_path, "20250826.csv")

    # Load the CSV data into a pandas DataFrame
    sharadar_df = pd.read_csv(sharadar_path)

    # Save the raw merged DataFrame
    sharadar_df.to_csv(raw_file_path, index=False)
    print(f"Saved raw Sharadar data to: {raw_file_path}")

    # Columns to keep
    sharadar_df = sharadar_df[OLD_COLUMNS]
    sharadar_df.columns = NEW_COLUMNS

    # Standardize symbol
    sharadar_df['standardized_symbol'] = sharadar_df['sh_symbol'].apply(standardize)
    sharadar_df['sh_currency'] = sharadar_df['sh_currency'].apply(standardize)

    sharadar_df = sharadar_df.loc[sharadar_df['exchange'].isin(['NYSE', 'NASDAQ'])]

    # Standardize exchange
    sharadar_df['exchange'] = sharadar_df['exchange'].replace({
        'NASDAQ': 'XNAS',
        'NYSE': 'XNYS'
    })

    sharadar_df = sharadar_df.loc[sharadar_df['exchange'].isin(['XNYS', 'XNAS'])]

    # Convert to Intrinio Types
    sharadar_df['sh_type'] = sharadar_df['sh_type'].replace({
        'Domestic Common Stock': 'EQS',
        'Domestic Common Stock Primary Class': 'EQS',
        'ADR Common Stock': 'DR',
        'Domestic Preferred Stock': 'EQS',
        'ADR Common Stock Primary Class': 'DR',
        'Domestic Common Stock Secondary Class': 'EQS',
        'Domestic Common Stock Warrant': 'WAR',
        'Canadian Common Stock': 'EQS',
        'ADR Common Stock Warrant': 'WAR',
        'ADR Preferred Stock': 'DR',
        'Canadian Common Stock Primary Class': 'EQS',
        'ADR Common Stock Secondary Class': 'DR',
        'Canadian Common Stock Warrant': 'WAR',
    })

    # Get cik
    sharadar_df['sh_cik'] = sharadar_df['sh_cik'].str.extract('CIK=(.*)')

    return sharadar_df

import pandas as pd
import os
from source.providers.utils import standardize
from source.config import config
import glob

OLD_COLUMNS = ['ticker', 'exchange', 'category', 'name', 'currency',
               'secfilings', 'cusips', 'siccode', 'sicsector', 'sicindustry',
               'famaindustry', 'sector', 'industry', 'scalemarketcap',
               'scalerevenue', 'location']

NEW_COLUMNS = ['sh_symbol', 'exchange', 'sh_type', 'sh_name', 'sh_currency',
               'sh_cik', 'sh_cusip', 'sh_sic_code', 'sh_sic_sector', 'sh_sic_industry',
               'sh_fama_industry', 'sh_sector', 'sh_industry', 'sh_scale_market_cap',
               'sh_scale_revenue', 'sh_location']


def load_sharadar_data():
    """
    Loads Sharadar data from CSV file using pandas.
    """
    # Ensure data directory exists
    # os.makedirs(config.data_dir, exist_ok=True)
    # raw_file_path = os.path.join(config.data_dir, f"{datetime.now().strftime('%Y%m%d')}_SHARADAR_raw.csv")

    # Construct absolute path to the data file
    sharadar_path = glob.glob(os.path.join(config.sharadar_data_path, f'*.csv'))[0]

    # Verify file exists
    if not os.path.exists(sharadar_path):
        raise FileNotFoundError(f"Sharadar file not found: {sharadar_path}")

    # Load the CSV data into a pandas DataFrame
    sharadar_df = pd.read_csv(sharadar_path)

    # Save the raw DataFrame
    # sharadar_df.to_csv(raw_file_path, index=False)
    # print(f"Saved raw Sharadar data to: {raw_file_path}")

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

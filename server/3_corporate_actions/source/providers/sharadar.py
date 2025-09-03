import pandas as pd
import os
import glob
from pathlib import Path
from source.config import config


def load_data():
    """
    Loads data from the Sharadar dataset.

    Returns:
        A pandas DataFrame containing the Sharadar data, or empty DataFrame if error occurs.
    """
    sharadar_path = glob.glob(os.path.join(config.source_ca_prv_dir, 'sharadar', '*.csv'))[0]

    if not Path(sharadar_path).exists():
        print(f"Sharadar file not found: {sharadar_path}")
        return pd.DataFrame()

    try:
        sharadar_df = pd.read_csv(sharadar_path, dtype=str, keep_default_na=False, na_values=[])
        return sharadar_df
    except pd.errors.EmptyDataError:
        print(f"Sharadar file is empty: {sharadar_path}")
        raise ValueError("Missing Sharadar Data")
    except pd.errors.ParserError as e:
        print(f"Error parsing Sharadar CSV file: {e}")
        raise ValueError("Missing Sharadar Data")
    except Exception as e:
        print(f"Error loading Sharadar data from {sharadar_path}: {e}")
        raise ValueError("Missing Sharadar Data")
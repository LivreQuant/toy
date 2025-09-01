import pandas as pd
import os
from pathlib import Path
from source.config import config


def load_data():
    """
    Loads data from the Sharadar dataset.

    Returns:
        A pandas DataFrame containing the Sharadar data, or empty DataFrame if error occurs.
    """
    sharadar_path = os.path.join(config.example_dir, 'sharadar', config.sharadar_default_ca_file)

    if not Path(sharadar_path).exists():
        print(f"Sharadar file not found: {sharadar_path}")
        return pd.DataFrame()

    try:
        sharadar_df = pd.read_csv(sharadar_path)
        return sharadar_df
    except pd.errors.EmptyDataError:
        print(f"Sharadar file is empty: {sharadar_path}")
        return pd.DataFrame()
    except pd.errors.ParserError as e:
        print(f"Error parsing Sharadar CSV file: {e}")
        return pd.DataFrame()
    except Exception as e:
        print(f"Error loading Sharadar data from {sharadar_path}: {e}")
        return pd.DataFrame()
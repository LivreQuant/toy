# server/corporate_actions/source/providers/sharadar.py

import pandas as pd
import os
from pathlib import Path

def load_data():
    """
    Loads data from the Sharadar dataset.

    Returns:
        A pandas DataFrame containing the Sharadar data, or empty DataFrame if error occurs.
    """
    base_dir = os.path.dirname(os.path.abspath(__file__))
    sharadar_path = os.path.join(base_dir, '../../examples/sharadar/20250827.csv')

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
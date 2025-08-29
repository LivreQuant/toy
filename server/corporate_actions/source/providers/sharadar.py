
import pandas as pd
import os

def load_data():
    """
    Loads data from the Sharadar dataset.

    Returns:
        A pandas DataFrame containing the Sharadar data.
    """
    base_dir = os.path.dirname(os.path.abspath(__file__))
    sharadar_path = os.path.join(base_dir, '../../examples/sharadar/20250827.csv')

    sharadar_df = pd.read_csv(sharadar_path)

    return sharadar_df

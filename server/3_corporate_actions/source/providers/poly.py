import pandas as pd
import os
from pathlib import Path
from source.config import config


def load_data():
    """
    Loads all corporate action data from the Polygon dataset.

    Returns:
        A dictionary of pandas DataFrames where keys are action types:
        - dividends: DataFrame with dividend information.
        - splits: DataFrame with stock split information.
    """
    files_to_load = {
        'dividends': os.path.join(config.source_ca_dir, 'poly', 'dividends.json'),
        'splits': os.path.join(config.source_ca_dir, 'poly', 'splits.json'),
        'ipos': os.path.join(config.source_ca_dir, 'poly', 'ipos.json')
    }

    results = {}

    for data_type, file_path in files_to_load.items():
        if Path(file_path).exists():
            try:
                results[data_type] = pd.read_json(file_path)
            except Exception as e:
                print(f"Error loading {data_type} from Polygon: {e}")
                raise ValueError("Missing POLY Data")
        else:
            print(f"File not found: {file_path}")
            raise ValueError("Missing POLY Data")

    return results

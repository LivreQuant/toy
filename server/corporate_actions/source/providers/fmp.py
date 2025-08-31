# server/corporate_actions/source/providers/fmp.py

import pandas as pd
import os
from pathlib import Path


def load_data():
    """
    Loads all corporate action data from the FMP dataset.

    Returns:
        A dictionary of pandas DataFrames where keys are action types:
        - dividends: DataFrame with dividend information.
        - splits: DataFrame with stock split information.
        - symbol_changes: DataFrame with symbol change information.
        - mergers: DataFrame with merger information.
    """
    base_dir = os.path.dirname(os.path.abspath(__file__))

    files_to_load = {
        'dividends': '../../examples/fmp/dividends.json',
        'splits': '../../examples/fmp/splits.json',
        'symbol_changes': '../../examples/fmp/symbol_change.json',
        'mergers': '../../examples/fmp/mergers.json'
    }

    results = {}

    for data_type, relative_path in files_to_load.items():
        file_path = os.path.join(base_dir, relative_path)

        if Path(file_path).exists():
            try:
                results[data_type] = pd.read_json(file_path)
            except Exception as e:
                print(f"Error loading {data_type} from FMP: {e}")
                results[data_type] = pd.DataFrame()
        else:
            print(f"File not found: {file_path}")
            results[data_type] = pd.DataFrame()

    return results
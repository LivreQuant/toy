
import pandas as pd
import os

def load_data():
    """
    Loads dividend and split data from the FMP dataset.

    Returns:
        A tuple containing two pandas DataFrames:
        - dividends: DataFrame with dividend information.
        - splits: DataFrame with stock split information.
    """
    base_dir = os.path.dirname(os.path.abspath(__file__))
    dividends_path = os.path.join(base_dir, '../../examples/fmp/dividends.json')
    splits_path = os.path.join(base_dir, '../../examples/fmp/splits.json')

    dividends = pd.read_json(dividends_path)
    splits = pd.read_json(splits_path)

    return dividends, splits

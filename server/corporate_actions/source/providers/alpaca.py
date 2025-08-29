
import pandas as pd
import os
import glob
import json

def load_data():
    """
    Loads corporate action data from the Alpaca dataset.

    Each corporate action type is loaded into its own table.

    Returns:
        A dictionary of pandas DataFrames, where each key is a corporate action
        type and the value is a DataFrame containing the data for that action.
    """
    base_dir = os.path.dirname(os.path.abspath(__file__))
    alpaca_dir = os.path.join(base_dir, '../../examples/alpaca')
    files = glob.glob(os.path.join(alpaca_dir, '*.json'))

    tables = {}

    for file in files:
        with open(file, 'r') as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                # Skip empty or invalid json files
                continue

        if not data or 'corporate_actions' not in data:
            continue

        for action_type, actions in data['corporate_actions'].items():
            if not actions:
                continue

            df = pd.DataFrame(actions)
            if action_type in tables:
                tables[action_type] = pd.concat([tables[action_type], df], ignore_index=True)
            else:
                tables[action_type] = df

    return tables

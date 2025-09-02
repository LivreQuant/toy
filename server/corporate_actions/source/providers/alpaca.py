import pandas as pd
import os
import glob
import json
from pathlib import Path
from source.config import config


def load_data():
    """
    Loads corporate action data from the Alpaca dataset.

    Each corporate action type is loaded into its own table.

    Returns:
        A dictionary of pandas DataFrames, where each key is a corporate action
        type and the value is a DataFrame containing the data for that action.
    """
    alpaca_dir = os.path.join(config.source_ca_dir, 'alpaca')

    # Check if the alpaca directory exists
    if not Path(alpaca_dir).exists():
        print(f"Alpaca directory not found: {alpaca_dir}")
        return {}

    files = glob.glob(os.path.join(alpaca_dir, '*.json'))

    if not files:
        print(f"No JSON files found in Alpaca directory: {alpaca_dir}")
        return {}

    tables = {}

    for file in files:
        try:
            with open(file, 'r') as f:
                try:
                    data = json.load(f)
                except json.JSONDecodeError as e:
                    print(f"Error parsing JSON file {file}: {e}")
                    continue
                except Exception as e:
                    print(f"Error reading file {file}: {e}")
                    continue

            if not data or 'corporate_actions' not in data:
                print(f"No corporate_actions data found in file: {file}")
                continue

            for action_type, actions in data['corporate_actions'].items():
                if not actions:
                    continue

                try:
                    df = pd.DataFrame(actions)
                    if action_type in tables:
                        tables[action_type] = pd.concat([tables[action_type], df], ignore_index=True)
                    else:
                        tables[action_type] = df
                except Exception as e:
                    print(f"Error creating DataFrame for {action_type} from file {file}: {e}")
                    continue

        except Exception as e:
            print(f"Error processing file {file}: {e}")
            continue

    return tables
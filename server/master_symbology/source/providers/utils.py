import re
import pandas as pd
from functools import reduce


def average_or_keep(row):
    val1 = row['market_capital_1']
    val2 = row['market_capital_2']

    # Check if both values are not None/NaN
    if pd.notna(val1) and pd.notna(val2):
        return round((val1 + val2) / 2)

    # If only one is not None/NaN, return that value
    elif pd.notna(val1):
        return round(val1)

    elif pd.notna(val2):
        return round(val2)

    # If both are None/NaN, return None
    else:
        return None

def standardize(symbol):
    if not isinstance(symbol, str):
        return None
    return re.sub(r'[^A-Z]', '', symbol.upper())


def consolidate_column(df, base_variable, priority_map):
    """
     Consolidates a column based on a priority map.

     Args:
        df (pd.DataFrame): The merged DataFrame.
        base_variable (str): The base name of the column to consolidate (e.g., 'name').
        priority_map (list): A list of tuples, where each tuple is (table_indicator, col_prefix).
        The order of the list defines the priority.

    Returns:
        pd.Series: The consolidated column.
      """
    consolidated = pd.Series(index=df.index, dtype=object)

    for table_indicator, col_prefix in priority_map:
        indicator_col = f"_in_{table_indicator}"
        source_col = f"{col_prefix}_{base_variable}"

        if indicator_col in df.columns and source_col in df.columns:
            mask = (df[indicator_col] == 1) & (consolidated.isnull())
            consolidated.loc[mask] = df.loc[mask, source_col]

    return consolidated


def merge_and_prioritize(dataframes, priorities, required_tables, merge_keys=['ix1', 'ix2']):
    """
    Merges a list of DataFrames based on a common set of keys, calculates a confidence score,
    and prioritizes columns based on a given order.

    Args:
        dataframes (dict): A dictionary of pandas DataFrames, with keys as table names.
        priorities (list): A list of table names in descending order of priority.
        required_tables (list): A list of table names that are required for a non-zero confidence score.
        merge_keys (list): A list of column names to merge on.

    Returns:
        pandas.DataFrame: The merged and prioritized DataFrame.
    """
    # Add indicator columns to each DataFrame
    for name, df in dataframes.items():
        df[f'_in_{name}'] = 1

    # Merge all dataframes
    merged_df = reduce(lambda left, right: pd.merge(left, right, on=merge_keys, how='outer'), dataframes.values())

    # Calculate confidence score
    indicator_cols = [f'_in_{name}' for name in dataframes.keys()]
    merged_df['confidence_score'] = merged_df[indicator_cols].sum(axis=1)

    # Fill NaNs in indicator columns with 0
    for col in indicator_cols:
        merged_df[col] = merged_df[col].fillna(0)

    # Set confidence to zero if not in required tables
    required_indicator_cols = [f'_in_{name}' for name in required_tables]
    required_condition = merged_df[required_indicator_cols].sum(axis=1) > 0
    merged_df.loc[~required_condition, 'confidence_score'] = 0

    # Prioritize columns
    # Create a new DataFrame to hold the prioritized data
    final_df = merged_df[merge_keys + indicator_cols + ['confidence_score']].copy()

    # Get all columns to be prioritized (all columns except keys and indicators)
    value_cols = [col for col in merged_df.columns if
                  col not in merge_keys and not col.startswith('_in_') and col != 'confidence_score']

    for col in value_cols:
        # Start with an empty series
        final_col = pd.Series(index=merged_df.index, dtype=merged_df[col].dtype)
        for name in priorities:
            # The column name in the merged_df will have a suffix if it's not from the first table
            # This logic needs to be more robust to handle suffixes
            # For now, we assume simple column names, which is incorrect for a real merge
            # This is a placeholder for a more complex column resolution logic
            if col in dataframes[name].columns:
                final_col = final_col.combine_first(merged_df[col])  # This is a simplified example
        final_df[col] = final_col

    # Define the base variables to be consolidated
    base_variables = {re.sub(r'^[a-z]{2}_', '', col) for col in final_df.columns if re.match(r'^[a-z]{2}_',
                                                                                             col)}

    # Define the mapping from table names to column prefixes
    prefix_map = {
        't1': 'na',
        't2': 'ny',
        't3': 'it',
        't4': 'ed',
        't5': 'pl',
        't6': 'fp',
        't7': 'av',
        't8': 'al'
    }

    # Create the priority map for consolidation
    priority_map = [(table, prefix_map.get(table)) for table in priorities if table in prefix_map]

    # Consolidate each base variable
    for base_variable in base_variables:
        final_df[base_variable] = consolidate_column(merged_df, base_variable, priority_map)

    return final_df, base_variables

import pandas as pd
import numpy as np
from collections import defaultdict


def update_mktcap(df):
    """
    Update market cap scale information using both scalemarketcap (string) and market_capital (float).

    Priority order:
    1. Use existing 'scalemarketcap' if available and not null
    2. Create bins from market_capital values where scalemarketcap is known
    3. Map market_capital values to scalemarketcap categories using these bins
    4. Otherwise, set to "UNKNOWN"

    Args:
        df (pd.DataFrame): DataFrame containing scalemarketcap and/or market_capital columns

    Returns:
        pd.DataFrame: DataFrame with cleaned 'scalemarketcap' column
    """
    # Create a copy to avoid modifying the original DataFrame
    result_df = df.copy()

    # Initialize scalemarketcap column if it doesn't exist
    if 'scalemarketcap' not in result_df.columns:
        result_df['scalemarketcap'] = None

    # Check if market_capital column exists
    if 'market_capital' not in result_df.columns:
        result_df['scalemarketcap'] = result_df['scalemarketcap'].fillna("UNKNOWN")
        result_df['scalemarketcap'] = result_df['scalemarketcap'].replace('', "UNKNOWN")
        return result_df

    # Clean market_capital column - convert to numeric, handle errors
    result_df['market_capital'] = pd.to_numeric(result_df['market_capital'], errors='coerce')

    # Step 1: Get records that have both scalemarketcap and market_capital
    valid_records = result_df[
        (result_df['scalemarketcap'].notna()) &
        (result_df['scalemarketcap'] != '') &
        (result_df['scalemarketcap'] != 'UNKNOWN') &
        (result_df['market_capital'].notna()) &
        (result_df['market_capital'] > 0)  # Only positive market caps
        ]

    if len(valid_records) == 0:
        # No valid mapping data available
        result_df['scalemarketcap'] = result_df['scalemarketcap'].fillna("UNKNOWN")
        result_df['scalemarketcap'] = result_df['scalemarketcap'].replace('', "UNKNOWN")
        print("No valid scalemarketcap to market_capital mappings found")
        return result_df

    # Step 2: Create bins for each scalemarketcap category
    scale_bins = {}

    # Group by scalemarketcap and get market_capital ranges
    for scale_category in valid_records['scalemarketcap'].unique():
        category_data = valid_records[valid_records['scalemarketcap'] == scale_category]
        market_caps = category_data['market_capital'].values

        if len(market_caps) > 0:
            try:
                scale_bins[scale_category] = {
                    'min': float(np.min(market_caps)),
                    'max': float(np.max(market_caps)),
                    'median': float(np.median(market_caps)),
                    'count': len(market_caps)
                }
            except (TypeError, ValueError) as e:
                print(f"Error processing market caps for category {scale_category}: {e}")
                continue

    if not scale_bins:
        # No valid bins created
        result_df['scalemarketcap'] = result_df['scalemarketcap'].fillna("UNKNOWN")
        result_df['scalemarketcap'] = result_df['scalemarketcap'].replace('', "UNKNOWN")
        print("No valid market cap bins could be created")
        return result_df

    # Step 3: Create non-overlapping bins by sorting categories by median market cap
    sorted_categories = sorted(scale_bins.keys(), key=lambda x: scale_bins[x]['median'])

    # Create bin boundaries
    bin_boundaries = []
    category_mapping = {}

    for i, category in enumerate(sorted_categories):
        try:
            if i == 0:
                # First category: 0 to midpoint with next category
                if len(sorted_categories) > 1:
                    next_median = scale_bins[sorted_categories[i + 1]]['median']
                    upper_bound = (scale_bins[category]['median'] + next_median) / 2.0
                else:
                    upper_bound = float('inf')
                bin_boundaries.append((0.0, upper_bound))
                category_mapping[(0.0, upper_bound)] = category
            elif i == len(sorted_categories) - 1:
                # Last category: previous boundary to infinity
                lower_bound = bin_boundaries[-1][1]
                bin_boundaries.append((lower_bound, float('inf')))
                category_mapping[(lower_bound, float('inf'))] = category
            else:
                # Middle categories: previous boundary to midpoint with next category
                lower_bound = bin_boundaries[-1][1]
                next_median = scale_bins[sorted_categories[i + 1]]['median']
                upper_bound = (scale_bins[category]['median'] + next_median) / 2.0
                bin_boundaries.append((lower_bound, upper_bound))
                category_mapping[(lower_bound, upper_bound)] = category
        except (TypeError, ValueError, ZeroDivisionError) as e:
            print(f"Error creating bins for category {category}: {e}")
            continue

    # Log the bin boundaries
    print("Market Cap Bins Created:")
    for category in sorted_categories:
        if category in [v for v in category_mapping.values()]:
            bounds = [k for k, v in category_mapping.items() if v == category][0]
            print(
                f"  {category}: ${bounds[0]:,.0f} - ${bounds[1]:,.0f} (median: ${scale_bins[category]['median']:,.0f}, count: {scale_bins[category]['count']})")

    # Step 4: Apply mapping to fill missing scalemarketcap values
    filled_count = 0

    for idx, row in result_df.iterrows():
        current_scale = row.get('scalemarketcap')
        current_mktcap = row.get('market_capital')

        # Skip if we already have a valid scalemarketcap
        if (pd.notna(current_scale) and
                current_scale != '' and
                current_scale != 'UNKNOWN' and
                str(current_scale).strip() != ''):
            continue

        # Try to map using market_capital
        if pd.notna(current_mktcap) and isinstance(current_mktcap, (int, float)) and current_mktcap > 0:
            mapped_category = None

            try:
                for (lower, upper), category in category_mapping.items():
                    if lower <= current_mktcap < upper:
                        mapped_category = category
                        break

                if mapped_category:
                    result_df.at[idx, 'scalemarketcap'] = mapped_category
                    filled_count += 1
                else:
                    result_df.at[idx, 'scalemarketcap'] = "UNKNOWN"
            except (TypeError, ValueError):
                result_df.at[idx, 'scalemarketcap'] = "UNKNOWN"
        else:
            result_df.at[idx, 'scalemarketcap'] = "UNKNOWN"

    # Final cleanup
    result_df['scalemarketcap'] = result_df['scalemarketcap'].fillna("UNKNOWN")
    result_df['scalemarketcap'] = result_df['scalemarketcap'].replace('', "UNKNOWN")
    result_df['scalemarketcap'] = result_df['scalemarketcap'].replace('None', "UNKNOWN")
    return result_df
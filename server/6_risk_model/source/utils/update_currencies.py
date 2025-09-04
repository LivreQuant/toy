import pandas as pd
import numpy as np


def update_currencies(df):
    """
    Update currency information with fallback logic.
    """
    result_df = df.copy()

    if 'currency' not in result_df.columns:
        result_df['currency'] = None

    region_to_currency = {
        'North America': 'USD',
        'Europe': 'EUR',
        'Japan': 'JPY',
        'Asia ex-Japan': 'USD',
        'Australia & NZ': 'AUD',
        'Latin America': 'USD',
        'Middle East & Africa': 'USD',
        'Emerging Europe': 'EUR',
        'Offshore': 'USD',
    }

    filled_count = 0
    debug_count = 0

    for idx, row in result_df.iterrows():
        current_currency = row.get('currency')

        # Skip if we already have a valid currency
        if (pd.notna(current_currency) and
                current_currency != '' and
                current_currency != 'UNKNOWN' and
                str(current_currency).strip() != ''):
            continue

        # Debug the first few problematic records
        if debug_count < 5:
            print(f"DEBUG: Symbol {row.get('symbol')}, Region: '{row.get('region')}', Currency: '{current_currency}'")
            debug_count += 1

        # Try to map using region
        if 'region' in result_df.columns:
            current_region = row.get('region')
            if (pd.notna(current_region) and
                    current_region != 'UNKNOWN' and
                    str(current_region).strip() in region_to_currency):

                mapped_currency = region_to_currency[str(current_region).strip()]
                result_df.at[idx, 'currency'] = mapped_currency
                filled_count += 1

                if debug_count <= 5:
                    print(f"DEBUG: Mapped {current_region} -> {mapped_currency}")
                continue

        # Default to UNKNOWN
        result_df.at[idx, 'currency'] = "UNKNOWN"

    # Final cleanup
    result_df['currency'] = result_df['currency'].fillna("UNKNOWN")
    result_df['currency'] = result_df['currency'].replace('', "UNKNOWN")
    result_df['currency'] = result_df['currency'].replace('None', "UNKNOWN")

    return result_df
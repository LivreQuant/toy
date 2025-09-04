import pandas as pd
import numpy as np
from collections import defaultdict


def update_sectors(df):
    """
    Update sector information with comprehensive fallback logic using unique identifiers.
    """
    # Create a copy to avoid modifying the original DataFrame
    result_df = df.copy()

    # Initialize sector column if it doesn't exist
    if 'sector' not in result_df.columns:
        result_df['sector'] = None

    # FIRST: Clean up sector naming inconsistencies
    sector_mapping = {
        'Healthcare': 'Health Care',  # Standardize to 'Health Care'
        'Technology': 'Information Technology',  # Standardize to 'Information Technology'
        'Financial Services': 'Financials',  # Standardize to 'Financials'
        'Consumer Cyclical': 'Consumer Discretionary',  # Standardize
        'Consumer Defensive': 'Consumer Staples',  # Standardize
        'Basic Materials': 'Materials',  # Standardize
    }

    # Apply sector standardization
    for idx, row in result_df.iterrows():
        current_sector = row.get('sector')
        if pd.notna(current_sector) and str(current_sector).strip() in sector_mapping:
            result_df.at[idx, 'sector'] = sector_mapping[str(current_sector).strip()]

    # Define identifier columns to use for mapping (in priority order)
    identifier_columns = ['composite_figi', 'share_class_figi', 'cik', 'isin',
                          'sic_code', 'sic_description', 'sic_sector', 'sic_industry',
                          'fama_industry','industry']
    available_identifiers = [col for col in identifier_columns if col in result_df.columns]

    if not available_identifiers:
        # If no identifier columns exist, just fill missing sectors with "UNKNOWN"
        result_df['sector'] = result_df['sector'].fillna("UNKNOWN")
        result_df['sector'] = result_df['sector'].replace('', "UNKNOWN")
        return result_df

    # Create mappings from identifiers to sectors for records that already have sectors
    identifier_to_sector_maps = {}

    for identifier_col in available_identifiers:
        identifier_to_sector_maps[identifier_col] = {}

        # Get records that have both the identifier and a valid sector
        valid_records = result_df[
            (result_df[identifier_col].notna()) &
            (result_df[identifier_col] != '') &
            (result_df['sector'].notna()) &
            (result_df['sector'] != '') &
            (result_df['sector'] != 'UNKNOWN')
            ]

        if len(valid_records) > 0:
            # Group by identifier and collect unique sectors
            identifier_sectors = defaultdict(set)
            for _, row in valid_records.iterrows():
                identifier_key = str(row[identifier_col]).strip()
                sector_value = str(row['sector']).strip()
                identifier_sectors[identifier_key].add(sector_value)

            # Only keep mappings where identifier maps to exactly one unique sector
            for identifier_key, sectors in identifier_sectors.items():
                if len(sectors) == 1:
                    identifier_to_sector_maps[identifier_col][identifier_key] = list(sectors)[0]

    # Apply fallback logic to fill missing sectors
    filled_count = 0

    for idx, row in result_df.iterrows():
        current_sector = row.get('sector')

        # Skip if we already have a valid sector
        if (pd.notna(current_sector) and
                current_sector != '' and
                current_sector != 'UNKNOWN' and
                str(current_sector).strip() != ''):
            continue

        # Try to find a sector using available identifiers (in priority order)
        found_sector = None

        for identifier_col in available_identifiers:
            if identifier_col in result_df.columns:
                identifier_value = row.get(identifier_col)

                if (pd.notna(identifier_value) and
                        identifier_value != '' and
                        str(identifier_value).strip() != ''):

                    identifier_key = str(identifier_value).strip()

                    if (identifier_col in identifier_to_sector_maps and
                            identifier_key in identifier_to_sector_maps[identifier_col]):
                        found_sector = identifier_to_sector_maps[identifier_col][identifier_key]
                        break

        # Update the sector
        if found_sector:
            result_df.at[idx, 'sector'] = found_sector
            filled_count += 1
        else:
            result_df.at[idx, 'sector'] = "UNKNOWN"

    # Final cleanup: ensure any remaining null/empty values are set to "UNKNOWN"
    result_df['sector'] = result_df['sector'].fillna("UNKNOWN")
    result_df['sector'] = result_df['sector'].replace('', "UNKNOWN")
    result_df['sector'] = result_df['sector'].replace('None', "UNKNOWN")
    return result_df
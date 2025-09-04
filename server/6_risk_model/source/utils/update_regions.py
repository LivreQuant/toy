import pandas as pd
import numpy as np
from collections import defaultdict


def update_regions(df):
    """
    Update region information by mapping countries to regions based on legal/regulatory frameworks.

    Args:
        df (pd.DataFrame): DataFrame containing country column

    Returns:
        pd.DataFrame: DataFrame with cleaned 'region' column
    """
    # Create a copy to avoid modifying the original DataFrame
    result_df = df.copy()

    # Country to region mapping based on legal/regulatory frameworks
    # Country to region mapping based on legal/regulatory frameworks
    country_to_region_mapping = {
        # North America (SEC jurisdiction)
        'USA': 'North America',
        'United States': 'North America',
        'US': 'North America',
        'Canada': 'North America',
        'Mexico': 'North America',
        'Panama': 'North America',  # ADD
        'Costa Rica': 'North America',  # ADD

        # Europe (EU regulatory framework)
        'Germany': 'Europe',
        'France': 'Europe',
        'Belgium': 'Europe',
        'Netherlands': 'Europe',
        'Italy': 'Europe',
        'Spain': 'Europe',
        'United Kingdom': 'Europe',
        'UK': 'Europe',
        'Switzerland': 'Europe',
        'Austria': 'Europe',
        'Ireland': 'Europe',
        'Denmark': 'Europe',
        'Sweden': 'Europe',
        'Norway': 'Europe',
        'Finland': 'Europe',
        'Poland': 'Europe',
        'Czech Republic': 'Europe',
        'Hungary': 'Europe',
        'Portugal': 'Europe',
        'Greece': 'Europe',
        'Luxembourg': 'Europe',
        'Cyprus': 'Europe',  # ADD
        'Monaco': 'Europe',  # ADD

        # Offshore Financial Centers
        'Bermuda': 'Offshore',  # ADD
        'Cayman Islands': 'Offshore',  # ADD
        'British Virgin Islands': 'Offshore',  # ADD
        'Jersey': 'Offshore',  # ADD
        'Guernsey': 'Offshore',  # ADD
        'Gibraltar': 'Offshore',  # ADD

        # Japan (unique regulatory framework)
        'Japan': 'Japan',

        # Asia excluding Japan
        'China': 'Asia ex-Japan',
        'South Korea': 'Asia ex-Japan',
        'Taiwan': 'Asia ex-Japan',
        'Hong Kong': 'Asia ex-Japan',
        'Singapore': 'Asia ex-Japan',
        'India': 'Asia ex-Japan',
        'Thailand': 'Asia ex-Japan',
        'Malaysia': 'Asia ex-Japan',
        'Indonesia': 'Asia ex-Japan',
        'Philippines': 'Asia ex-Japan',
        'Vietnam': 'Asia ex-Japan',
        'Macau': 'Asia ex-Japan',  # ADD
        'Cambodia': 'Asia ex-Japan',  # ADD

        # Australia & New Zealand
        'Australia': 'Australia & NZ',
        'New Zealand': 'Australia & NZ',

        # Latin America
        'Brazil': 'Latin America',
        'Argentina': 'Latin America',
        'Chile': 'Latin America',
        'Colombia': 'Latin America',
        'Peru': 'Latin America',
        'Uruguay': 'Latin America',  # ADD

        # Middle East & Africa
        'Saudi Arabia': 'Middle East & Africa',
        'UAE': 'Middle East & Africa',
        'United Arab Emirates': 'Middle East & Africa',  # ADD
        'Israel': 'Middle East & Africa',
        'South Africa': 'Middle East & Africa',
        'Egypt': 'Middle East & Africa',
        'Qatar': 'Middle East & Africa',
        'Kuwait': 'Middle East & Africa',

        # Emerging Europe
        'Russia': 'Emerging Europe',
        'Turkey': 'Emerging Europe',
        'Ukraine': 'Emerging Europe',
        'Kazakhstan': 'Emerging Europe',  # ADD
    }

    # Initialize region column if it doesn't exist
    if 'region' not in result_df.columns:
        result_df['region'] = None

    # Check if country column exists
    if 'country' not in result_df.columns:
        result_df['region'] = result_df['region'].fillna("UNKNOWN")
        return result_df

    # Check for unmapped countries FIRST
    # Check for unmapped countries FIRST
    unique_countries = result_df['country'].dropna().unique()
    unmapped_countries = []

    for country in unique_countries:
        country_str = str(country).strip()
        # Skip empty strings - they'll be mapped to UNKNOWN
        if country_str != '' and country_str not in country_to_region_mapping:
            unmapped_countries.append(country_str)

    if unmapped_countries:
        raise ValueError(
            f"Unmapped countries found: {unmapped_countries}. Add these to country_to_region_mapping in update_regions.py")

    # Map countries to regions
    mapped_count = 0

    for idx, row in result_df.iterrows():
        current_region = row.get('region')
        current_country = row.get('country')

        # Skip if we already have a valid region
        if (pd.notna(current_region) and
                current_region != '' and
                current_region != 'UNKNOWN' and
                str(current_region).strip() != ''):
            continue

        # Map country to region
        if pd.notna(current_country) and str(current_country).strip() != '':
            country_key = str(current_country).strip()

            result_df.at[idx, 'region'] = country_to_region_mapping[country_key]
            mapped_count += 1
        else:
            # Empty or null countries map to UNKNOWN
            result_df.at[idx, 'region'] = "UNKNOWN"

    # Final cleanup
    result_df['region'] = result_df['region'].fillna("UNKNOWN")
    result_df['region'] = result_df['region'].replace('', "UNKNOWN")
    result_df['region'] = result_df['region'].replace('None', "UNKNOWN")
    return result_df
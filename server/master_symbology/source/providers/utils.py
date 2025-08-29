import re
import pandas as pd
import json
import os
from functools import reduce
from datetime import datetime
from pathlib import Path


def process_location(location_data):
    """
    Convert location dictionary or string into a readable address format.

    Args:
        location_data: Can be dict, string, or None

    Returns:
        Formatted address string or None
    """
    if pd.isna(location_data) or location_data is None:
        return None

    # If it's already a string, return as-is
    if isinstance(location_data, str):
        # Check if it looks like a JSON string
        if location_data.startswith('{') and location_data.endswith('}'):
            try:
                location_dict = json.loads(location_data.replace("'", '"'))
                return format_address_dict(location_dict)
            except (json.JSONDecodeError, ValueError):
                return location_data
        return location_data

    # If it's a dictionary
    if isinstance(location_data, dict):
        return format_address_dict(location_data)

    return str(location_data)


def format_address_dict(addr_dict):
    """
    Format address dictionary into readable string.

    Args:
        addr_dict: Dictionary containing address components

    Returns:
        Formatted address string
    """
    parts = []

    # Add address lines
    if addr_dict.get('address1'):
        parts.append(addr_dict['address1'])
    if addr_dict.get('address2'):
        parts.append(addr_dict['address2'])

    # Add city, state, postal code
    city_state_zip = []
    if addr_dict.get('city'):
        city_state_zip.append(addr_dict['city'])
    if addr_dict.get('state'):
        city_state_zip.append(addr_dict['state'])
    if addr_dict.get('postal_code'):
        city_state_zip.append(addr_dict['postal_code'])

    if city_state_zip:
        parts.append(', '.join(city_state_zip))

    # Add country if present and not USA
    if addr_dict.get('country') and addr_dict['country'].upper() not in ['USA', 'US', 'UNITED STATES']:
        parts.append(addr_dict['country'])

    return ', '.join(parts) if parts else None


def clean_branding_url(branding_url):
    """
    Extract the path component after the base Polygon branding URL for storage efficiency.

    Args:
        branding_url: Full URL to branding asset

    Returns:
        Path component after base URL or None

    Examples:
        Input:  "https://api.polygon.io/v1/reference/company-branding/abc123/images/2025-04-04_logo.png"
        Output: "/abc123/images/2025-04-04_logo.png"

        Input:  "https://api.polygon.io/v1/reference/company-branding/enltZXdvcmtzLmNvbQ/images/2025-04-04_logo.png"
        Output: "/enltZXdvcmtzLmNvbQ/images/2025-04-04_logo.png"
    """
    if pd.isna(branding_url) or not branding_url:
        return None

    if isinstance(branding_url, str):
        base_url = "https://api.polygon.io/v1/reference/company-branding"

        # Check if the URL starts with the expected base URL
        if branding_url.startswith(base_url):
            # Extract everything after the base URL
            path_component = branding_url[len(base_url):]

            # Only return if there's actually content after the base URL
            if path_component and len(path_component) > 1:  # More than just "/"
                return path_component

    return None

def standardize(symbol):
    """Standardize symbol by removing non-alphabetic characters."""
    if not isinstance(symbol, str):
        return None
    return re.sub(r'[^A-Z]', '', symbol.upper())


def average_or_keep(row):
    """Calculate average of two market cap values or keep the available one."""
    val1 = row.get('market_capital_1')
    val2 = row.get('market_capital_2')

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

    # Define the base variables to be consolidated
    base_variables = {re.sub(r'^[a-z]{2}_', '', col) for col in merged_df.columns if re.match(r'^[a-z]{2}_', col)}

    # Define the mapping from table names to column prefixes
    prefix_map = {
        't1': 'na',
        't2': 'ny',
        't3': 'fd',
        't4': 'it',
        't5': 'ed',
        't6': 'pl',
        't7': 'sh',
        't8': 'fp',
        't9': 'av',
        't10': 'al',
    }

    # Create the priority map for consolidation
    priority_map = [(table, prefix_map.get(table)) for table in priorities if table in prefix_map]

    # Collect all consolidated columns efficiently
    consolidated_columns = {}
    for base_variable in base_variables:
        consolidated_columns[base_variable] = consolidate_column(merged_df, base_variable, priority_map)

    # KEEP ALL PROVIDER COLUMNS - Don't drop the original al_symbol, av_symbol, etc.
    # Get all provider columns (columns that start with provider prefixes)
    provider_columns = {}
    for col in merged_df.columns:
        if re.match(r'^[a-z]{2}_', col):  # This matches al_symbol, av_symbol, etc.
            provider_columns[col] = merged_df[col]

    # Create final dataframe efficiently using pd.concat
    final_df_parts = [
        merged_df[merge_keys + indicator_cols + ['confidence_score']],
        pd.DataFrame(consolidated_columns, index=merged_df.index),
        pd.DataFrame(provider_columns, index=merged_df.index)  # ADD THIS LINE!
    ]
    final_df = pd.concat(final_df_parts, axis=1)

    return final_df, base_variables


def create_debug_directory():
    """Create timestamped debug directory for this run"""
    debug_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "debug"))
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    run_debug_dir = os.path.join(debug_dir, f"run_{timestamp}")
    os.makedirs(run_debug_dir, exist_ok=True)
    return run_debug_dir


def validate_and_debug_dataframe(df, provider_name, debug_dir):
    """Comprehensive validation and debugging for each provider's data"""
    provider_debug = {}

    # Basic stats
    provider_debug['shape'] = df.shape
    provider_debug['memory_usage'] = df.memory_usage(deep=True).sum()

    # Check for required columns
    required_cols = ['standardized_symbol', 'exchange']
    missing_required = [col for col in required_cols if col not in df.columns]
    provider_debug['missing_required_columns'] = missing_required

    # Data quality checks
    provider_debug['null_counts'] = df.isnull().sum().to_dict()
    provider_debug['duplicate_symbols'] = df.duplicated(subset=['standardized_symbol', 'exchange']).sum()
    provider_debug['empty_symbols'] = (df['standardized_symbol'].isnull() | (df['standardized_symbol'] == '')).sum()

    # Exchange distribution
    provider_debug['exchange_distribution'] = df['exchange'].value_counts().to_dict()

    # Symbol pattern analysis
    if 'standardized_symbol' in df.columns:
        symbols = df['standardized_symbol'].dropna()
        provider_debug['symbol_stats'] = {
            'unique_count': symbols.nunique(),
            'avg_length': symbols.str.len().mean(),
            'min_length': symbols.str.len().min(),
            'max_length': symbols.str.len().max(),
            'contains_numbers': symbols.str.contains(r'\d').sum(),
            'single_letter': symbols.str.len().eq(1).sum()
        }

        # Sample unusual symbols (very long or very short)
        unusual_symbols = symbols[symbols.str.len() > 5].head(10).tolist()
        provider_debug['sample_unusual_symbols'] = unusual_symbols

    # Save detailed debug info
    debug_file = os.path.join(debug_dir, f"{provider_name}_debug.json")
    with open(debug_file, 'w') as f:
        json.dump(provider_debug, f, indent=2, default=str)

    # Save sample data
    sample_file = os.path.join(debug_dir, f"{provider_name}_sample.csv")
    df.head(20).to_csv(sample_file, index=False)

    return provider_debug


def generate_cross_provider_analysis(dataframes, debug_dir):
    """Analyze overlaps and differences between providers"""
    analysis = {}

    # Symbol overlap analysis
    all_symbols = {}
    for name, df in dataframes.items():
        if 'standardized_symbol' in df.columns and 'exchange' in df.columns:
            # Fix the FutureWarning by using proper column access
            symbols_set = set(df['standardized_symbol'].astype(str) + ':' + df['exchange'].astype(str))
            all_symbols[name] = symbols_set

    # Calculate overlaps
    overlap_matrix = {}
    for name1, symbols1 in all_symbols.items():
        overlap_matrix[name1] = {}
        for name2, symbols2 in all_symbols.items():
            if name1 != name2:
                overlap = len(symbols1.intersection(symbols2))
                overlap_matrix[name1][name2] = {
                    'overlap_count': overlap,
                    'overlap_percentage': (overlap / len(symbols1) * 100) if symbols1 else 0
                }

    analysis['symbol_overlaps'] = overlap_matrix

    # Find symbols only in specific providers
    unique_to_provider = {}
    for name, symbols in all_symbols.items():
        other_symbols = set()
        for other_name, other_set in all_symbols.items():
            if other_name != name:
                other_symbols.update(other_set)
        unique_symbols = symbols - other_symbols
        unique_to_provider[name] = {
            'count': len(unique_symbols),
            'sample': list(unique_symbols)[:10]
        }

    analysis['unique_to_provider'] = unique_to_provider

    # Save analysis
    analysis_file = os.path.join(debug_dir, "cross_provider_analysis.json")
    with open(analysis_file, 'w') as f:
        json.dump(analysis, f, indent=2, default=str)

    return analysis


def validate_merge_results(df_final, df_not_in, debug_dir):
    """Validate the final merged results"""
    merge_validation = {}

    # Basic merge stats
    merge_validation['final_shape'] = df_final.shape
    merge_validation['excluded_shape'] = df_not_in.shape
    merge_validation['total_processed'] = df_final.shape[0] + df_not_in.shape[0]

    # Confidence score analysis
    if 'confidence_score' in df_final.columns:
        confidence_dist = df_final['confidence_score'].value_counts().sort_index().to_dict()
        merge_validation['confidence_distribution'] = confidence_dist

        # Low confidence symbols for review
        low_confidence = df_final[df_final['confidence_score'] <= 2]
        merge_validation['low_confidence_count'] = len(low_confidence)

        # Save low confidence symbols for manual review
        if not low_confidence.empty:
            low_conf_file = os.path.join(debug_dir, "low_confidence_symbols.csv")
            low_confidence.to_csv(low_conf_file, index=False)

    # Data quality issues in final dataset
    quality_issues = {}

    # Check for critical missing data
    critical_columns = ['symbol', 'exchange', 'type', 'name']
    for col in critical_columns:
        if col in df_final.columns:
            missing_count = df_final[col].isnull().sum()
            quality_issues[f'missing_{col}'] = missing_count

    # Check for data inconsistencies
    if 'type' in df_final.columns:
        quality_issues['type_distribution'] = df_final['type'].value_counts().to_dict()

    if 'currency' in df_final.columns:
        quality_issues['currency_distribution'] = df_final['currency'].value_counts().to_dict()
        non_usd = df_final[df_final['currency'] != 'USD'].shape[0]
        quality_issues['non_usd_securities'] = non_usd

    merge_validation['quality_issues'] = quality_issues

    # Save validation results
    validation_file = os.path.join(debug_dir, "merge_validation.json")
    with open(validation_file, 'w') as f:
        json.dump(merge_validation, f, indent=2, default=str)

    # Save excluded symbols for review
    if not df_not_in.empty:
        excluded_file = os.path.join(debug_dir, "excluded_symbols.csv")
        df_not_in.to_csv(excluded_file, index=False)

    return merge_validation


def generate_comparison_with_previous(df_current, debug_dir):
    """Compare current run with previous day's output"""
    comparison = {}

    # Look for previous day's master file - fix the path issue
    script_dir = os.path.dirname(debug_dir)  # This gets us to the main project dir
    data_dir = os.path.join(script_dir, "data")

    if not os.path.exists(data_dir):
        comparison['error'] = f"Data directory not found: {data_dir}"
        comparison_file = os.path.join(debug_dir, "daily_comparison.json")
        with open(comparison_file, 'w') as f:
            json.dump(comparison, f, indent=2, default=str)
        return comparison

    try:
        previous_files = sorted([f for f in os.listdir(data_dir) if f.endswith('_MASTER.csv')])
    except Exception as e:
        comparison['error'] = f"Could not list files in data directory: {str(e)}"
        comparison_file = os.path.join(debug_dir, "daily_comparison.json")
        with open(comparison_file, 'w') as f:
            json.dump(comparison, f, indent=2, default=str)
        return comparison

    if len(previous_files) >= 2:
        # Load previous file (second to last, since last is current)
        previous_file = previous_files[-2]
        previous_path = os.path.join(data_dir, previous_file)

        try:
            df_previous = pd.read_csv(previous_path, sep='|')

            # Compare counts
            comparison['current_count'] = len(df_current)
            comparison['previous_count'] = len(df_previous)
            comparison['count_change'] = len(df_current) - len(df_previous)
            comparison['count_change_percentage'] = (comparison['count_change'] / len(df_previous) * 100) if len(
                df_previous) > 0 else 0

            # Find new and removed symbols
            current_symbols = set(df_current['symbol'].astype(str) + ':' + df_current['exchange'].astype(str))
            previous_symbols = set(df_previous['symbol'].astype(str) + ':' + df_previous['exchange'].astype(str))

            new_symbols = current_symbols - previous_symbols
            removed_symbols = previous_symbols - current_symbols

            comparison['new_symbols'] = {
                'count': len(new_symbols),
                'sample': list(new_symbols)[:20]
            }
            comparison['removed_symbols'] = {
                'count': len(removed_symbols),
                'sample': list(removed_symbols)[:20]
            }

            # Save detailed lists if there are significant changes
            if new_symbols:
                new_symbols_file = os.path.join(debug_dir, "new_symbols.txt")
                with open(new_symbols_file, 'w') as f:
                    f.write('\n'.join(sorted(new_symbols)))

            if removed_symbols:
                removed_symbols_file = os.path.join(debug_dir, "removed_symbols.txt")
                with open(removed_symbols_file, 'w') as f:
                    f.write('\n'.join(sorted(removed_symbols)))

        except Exception as e:
            comparison['error'] = f"Could not compare with previous file: {str(e)}"
    else:
        comparison['note'] = "No previous file found for comparison"

    # Save comparison
    comparison_file = os.path.join(debug_dir, "daily_comparison.json")
    with open(comparison_file, 'w') as f:
        json.dump(comparison, f, indent=2, default=str)

    return comparison


def generate_debug_summary(debug_dir, provider_debugs, cross_analysis, merge_validation, daily_comparison):
    """Generate a human-readable summary report"""
    summary = []
    summary.append(f"Master Symbology Debug Report - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    summary.append("=" * 80)
    summary.append("")

    # Provider summary
    summary.append("PROVIDER DATA SUMMARY:")
    summary.append("-" * 40)
    for provider, debug_info in provider_debugs.items():
        summary.append(f"{provider.upper()}:")
        summary.append(f"  - Records: {debug_info['shape'][0]:,}")
        summary.append(f"  - Duplicates: {debug_info['duplicate_symbols']}")
        summary.append(f"  - Empty symbols: {debug_info['empty_symbols']}")
        summary.append(f"  - Exchanges: {list(debug_info['exchange_distribution'].keys())}")
        if debug_info['missing_required_columns']:
            summary.append(f"  - ⚠️  Missing required columns: {debug_info['missing_required_columns']}")
        summary.append("")

    # Cross-provider analysis
    summary.append("CROSS-PROVIDER ANALYSIS:")
    summary.append("-" * 40)
    if 'unique_to_provider' in cross_analysis:
        for provider, unique_info in cross_analysis['unique_to_provider'].items():
            summary.append(f"{provider.upper()}: {unique_info['count']} unique symbols")
    summary.append("")

    # Merge results
    summary.append("MERGE RESULTS:")
    summary.append("-" * 40)
    summary.append(f"Final dataset: {merge_validation['final_shape'][0]:,} records")
    summary.append(f"Excluded records: {merge_validation['excluded_shape'][0]:,}")
    if 'confidence_distribution' in merge_validation:
        summary.append("Confidence distribution:")
        for score, count in merge_validation['confidence_distribution'].items():
            summary.append(f"  - Score {score}: {count:,} records")
    summary.append("")

    # Daily changes
    summary.append("DAILY CHANGES:")
    summary.append("-" * 40)
    if 'count_change' in daily_comparison:
        change = daily_comparison['count_change']
        pct_change = daily_comparison['count_change_percentage']
        summary.append(f"Count change: {change:+,} ({pct_change:+.2f}%)")
        summary.append(f"New symbols: {daily_comparison['new_symbols']['count']}")
        summary.append(f"Removed symbols: {daily_comparison['removed_symbols']['count']}")
    else:
        summary.append("No previous data for comparison")
    summary.append("")

    # Quality issues
    summary.append("DATA QUALITY ALERTS:")
    summary.append("-" * 40)
    quality_issues = merge_validation.get('quality_issues', {})
    alerts = []

    for issue, count in quality_issues.items():
        if isinstance(count, int) and count > 0 and 'missing_' in issue:
            alerts.append(f"⚠️  {count:,} records missing {issue.replace('missing_', '')}")

    if not alerts:
        summary.append("✅ No critical data quality issues detected")
    else:
        summary.extend(alerts)

    summary.append("")
    summary.append(f"Debug files saved to: {debug_dir}")

    # Save summary
    summary_file = os.path.join(debug_dir, "debug_summary.txt")
    with open(summary_file, 'w') as f:
        f.write('\n'.join(summary))

    # Also print to console
    print('\n'.join(summary))

    return summary
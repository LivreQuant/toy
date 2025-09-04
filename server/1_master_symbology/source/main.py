import os
import numpy as np
from datetime import datetime
from source.config import config

from source.providers.alpaca import load_alpaca_data
from source.providers.alphavantage import load_alphavantage_data
from source.providers.eodhd import load_eodhd_data
from source.providers.finance_db import load_fd_data
from source.providers.fmp import load_fmp_data
from source.providers.intrinio import load_intrinio_data
from source.providers.nasdaq import load_nasdaq_data
from source.providers.nyse import load_nyse_data
from source.providers.poly import load_poly_data
from source.providers.sharadar import load_sharadar_data

from source.providers.utils import (
    merge_and_prioritize, average_or_keep, process_location, clean_branding_url,
    create_debug_directory, validate_and_debug_dataframe, generate_cross_provider_analysis, generate_debug_summary
)


def main_with_debugging():
    """Enhanced main function with comprehensive debugging"""

    # Create debug directory
    debug_dir = create_debug_directory()
    print(f"Debug files will be saved to: {debug_dir}")

    provider_debugs = {}

    try:
        # Load data with debugging
        print("\nLoading Nasdaq data...")
        nasdaq_df = load_nasdaq_data()
        provider_debugs['nasdaq'] = validate_and_debug_dataframe(nasdaq_df, 'nasdaq', debug_dir)
        print(f"Loaded Nasdaq data with shape: {nasdaq_df.shape}")

        print("\nLoading NYSE data...")
        nyse_df = load_nyse_data()
        provider_debugs['nyse'] = validate_and_debug_dataframe(nyse_df, 'nyse', debug_dir)
        print(f"Loaded NYSE data with shape: {nyse_df.shape}")

        print("Loading FMP data...")
        fmp_df = load_fmp_data()
        provider_debugs['fmp'] = validate_and_debug_dataframe(fmp_df, 'fmp', debug_dir)
        print(f"Loaded FMP data with shape: {fmp_df.shape}")

        print("\nLoading Intrinio data...")
        intrinio_df = load_intrinio_data()
        provider_debugs['intrinio'] = validate_and_debug_dataframe(intrinio_df, 'intrinio', debug_dir)
        print(f"Loaded Intrinio data with shape: {intrinio_df.shape}")

        print("\nLoading Poly data...")
        poly_df = load_poly_data()
        provider_debugs['poly'] = validate_and_debug_dataframe(poly_df, 'poly', debug_dir)
        print(f"Loaded Poly data with shape: {poly_df.shape}")

        print("\nLoading Alpha Vantage data...")
        av_df = load_alphavantage_data()
        provider_debugs['alphavantage'] = validate_and_debug_dataframe(av_df, 'alphavantage', debug_dir)
        print(f"Loaded Alpha Vantage data with shape: {av_df.shape}")

        print("\nLoading EODHD data...")
        eodhd_df = load_eodhd_data()
        provider_debugs['eodhd'] = validate_and_debug_dataframe(eodhd_df, 'eodhd', debug_dir)
        print(f"Loaded EODHD data with shape: {eodhd_df.shape}")

        print("\nLoading Alpaca data...")
        alpaca_df = load_alpaca_data()
        provider_debugs['alpaca'] = validate_and_debug_dataframe(alpaca_df, 'alpaca', debug_dir)
        print(f"Loaded Alpaca data with shape: {alpaca_df.shape}")

        print("\nLoading Sharadar data...")
        sharadar_df = load_sharadar_data()
        provider_debugs['sharadar'] = validate_and_debug_dataframe(sharadar_df, 'sharadar', debug_dir)
        print(f"Loaded Sharadar data with shape: {sharadar_df.shape}")

        print("\nLoading FinanceDatabase data...")
        fd_df = load_fd_data()
        provider_debugs['fd'] = validate_and_debug_dataframe(fd_df, 'financedatabase', debug_dir)
        print(f"Loaded FinanceDatabase data with shape: {fd_df.shape}")

        dataframes = {
            't1': nasdaq_df,
            't2': nyse_df,
            't3': fd_df,
            't4': intrinio_df,
            't5': eodhd_df,
            't6': poly_df,
            't7': sharadar_df,
            't8': fmp_df,
            't9': av_df,
            't10': alpaca_df,
        }

        # Cross-provider analysis
        print("\nPerforming cross-provider analysis...")
        cross_analysis = generate_cross_provider_analysis(dataframes, debug_dir)

        # Merge with debugging
        print("\nMerging data...")
        priorities = ['t1', 't2', 't3', 't4', 't5', 't6', 't7', 't8', 't9', 't10']
        df, variables = merge_and_prioritize(dataframes, priorities,
                                             required_tables=['t1', 't2'],
                                             merge_keys=['standardized_symbol', 'exchange'])

        # Continue with existing processing - fix SettingWithCopyWarning
        variables_ = [x for x in variables if x != 'etf']
        if 'etf' in df.columns:
            df_in = df.drop(columns=['etf'])

        # Create a proper copy and select columns
        column_list = ['exchange', 'confidence_score'] + [x for x in variables_ if x in df.columns]

        # Mapping to different providers
        if 'al_symbol' in df.columns and 'al_symbol' not in column_list:
            column_list.insert(2, 'al_symbol')
        if 'av_symbol' in df.columns and 'av_symbol' not in column_list:
            column_list.insert(3, 'av_symbol')
        if 'ed_symbol' in df.columns and 'ed_symbol' not in column_list:
            column_list.insert(4, 'ed_symbol')
        if 'fd_symbol' in df.columns and 'fd_symbol' not in column_list:
            column_list.insert(5, 'fd_symbol')
        if 'fp_symbol' in df.columns and 'fp_symbol' not in column_list:
            column_list.insert(6, 'fp_symbol')
        if 'it_symbol' in df.columns and 'it_symbol' not in column_list:
            column_list.insert(7, 'it_symbol')
        if 'pl_symbol' in df.columns and 'pl_symbol' not in column_list:
            column_list.insert(8, 'pl_symbol')
        if 'sh_symbol' in df.columns and 'sh_symbol' not in column_list:
            column_list.insert(9, 'sh_symbol')

        df = df[column_list].copy()

        # Now safely modify the copy
        if 'short_sale_restricted' in df.columns:
            df['short_sale_restricted'] = df['short_sale_restricted'].replace(' ', None)

        if 'halt_reason' in df.columns:
            df['halt_reason'] = df['halt_reason'].replace(' ', None)

        # Calculate market capital if the source columns exist
        if 'market_capital_1' in df.columns or 'market_capital_2' in df.columns:
            df['market_capital'] = df.apply(average_or_keep, axis=1)
            # Remove source columns
            columns_to_drop = [col for col in ['market_capital_1', 'market_capital_2'] if col in df.columns]
            if columns_to_drop:
                df = df.drop(columns=columns_to_drop)

        # Process location and branding
        print("\nProcessing location and branding data...")
        if 'location' in df.columns:
            df['location'] = df['location'].apply(process_location)

        if 'branding' in df.columns:
            df['branding'] = df['branding'].apply(clean_branding_url)

        df = df.replace(np.nan, None)
        df['null_count'] = df.isnull().sum(axis=1)
        df = df.sort_values(by='null_count', ascending=True)

        # df_not_in = df.loc[df['confidence_score'] == 0].copy()
        # df_in = df.loc[df['confidence_score'] >= 0].copy()

        # print(f"After merge - Total records: {len(df):,}")
        # print(f"Records meeting confidence requirements: {len(df_in):,}")
        # print(f"Records excluded (confidence_score = 0): {len(df_not_in):,}")

        # Validate merge results
        # merge_validation = validate_merge_results(df_in, df_not_in, debug_dir)

        # Remove duplicates if symbol and exchange columns exist
        if 'symbol' in df.columns and 'exchange' in df.columns:
            df = df.drop_duplicates(subset=['symbol', 'exchange'], keep='first')

        print(f"After processing - Total records: {len(df):,}")

        # DEBUG: Check what columns we actually have
        print(f"\nDEBUG: Available columns in df_in_:")
        print(f"Columns: {list(df.columns)}")

        # Check if al_symbol column exists and what it contains
        if 'al_symbol' in df.columns:
            print(f"\nDEBUG: al_symbol column stats:")
            print(f"  Non-null values: {df['al_symbol'].notna().sum()}")
            print(f"  Null values: {df['al_symbol'].isna().sum()}")
            print(f"  Empty strings: {(df['al_symbol'] == '').sum()}")
            print(f"  Sample non-null values: {df['al_symbol'].dropna().head(5).tolist()}")
        else:
            print(f"\nDEBUG: 'al_symbol' column NOT FOUND!")
            raise ValueError(f"\nDEBUG: 'al_symbol' column NOT FOUND!")

        # Check type column too
        if 'type' in df.columns:
            print(f"\nDEBUG: type column stats:")
            print(f"  Non-null values: {df['type'].notna().sum()}")
            print(f"  Null values: {df['type'].isna().sum()}")
            print(f"  Empty strings: {(df['type'] == '').sum()}")
            print(f"  Sample types: {df['type'].value_counts().head(5).to_dict()}")
        else:
            print(f"\nDEBUG: 'type' column NOT FOUND!")
            raise ValueError(f"\nDEBUG: 'type' column NOT FOUND!")

        # Your original filtering logic (keeping it exactly as you had it)
        # df_in_no_type = df_in_.loc[df_in_['type'].isnull()]
        # df_in_ = df_in_.loc[~df_in_['type'].isnull()]

        # Enhanced filtering to handle both null and empty strings for al_symbol
        # if 'al_symbol' in df.columns:
        #     has_al_symbol = (~df['al_symbol'].isnull()) & (df['al_symbol'] != '')
        #     df_in_price = df.loc[has_al_symbol]
        #     df_in_no_price = df.loc[~has_al_symbol]
        # else:
        #     print("ERROR: al_symbol column not found! Cannot filter by Alpaca symbols.")
        #     df_in_price = df.iloc[0:0].copy()  # Empty dataframe
        #     df_in_no_price = df.copy()

        print(f"\nFiltering results:")
        print(f"  Started with: {len(nasdaq_df) + len(nyse_df)} = {len(df)} records after processing")
        print(f"  Records without type: {(df['type'].isnull() | (df['type'] == '')).sum():,}")
        print(f"  Records without al_symbol: {(df['al_symbol'].isnull() | (df['al_symbol'] == '')).sum():,}")
        print(f"  Records without al_symbol and type: {(df['type'].isnull() | (df['type'] == '') | df['al_symbol'].isnull() | (df['al_symbol'] == '')).sum()}")

        assert len(nasdaq_df) + len(nyse_df) == len(df), f"Master length mismatch! Expected {len(nasdaq_df) + len(nyse_df):,} but got {len(df):,}"

        # Define desired column order and filter to available columns
        variables_orders = ['symbol',
                            # MAP TO CA, FUND, EVENTS
                            'al_symbol', 'av_symbol', 'fd_symbol', 'ed_symbol', 'fp_symbol', 'it_symbol', 'pl_symbol',
                            'sh_symbol',
                            'composite_symbol', 'exchange', 'status', 'type', 'currency',
                            'location',
                            'name', 'primary_listing', 'country', 'description', 'lot',
                            'cik', 'cusips', 'isin', 'figi', 'composite_figi', 'share_class_figi',
                            'market_capital', 'scalemarketcap', 'scalerevenue',
                            'shares_outstanding', 'share_class_shares_outstanding', 'weighted_shares_outstanding',
                            'sic_code', 'sic_description', 'sic_sector', 'sic_industry',
                            'fama_sector', 'fama_industry', 'sector', 'industry',
                            'earnings_announcement',
                            'easy_to_borrow', 'halt_reason', 'shortable', 'marginable', 'tradable',
                            'short_sale_restricted',
                            'margin_requirement_short', 'margin_requirement_long', 'maintenance_margin_requirement',
                            'homepage_url', 'branding']

        # Filter to only columns that exist in the dataframe
        available_columns = [col for col in variables_orders if col in df.columns]
        df = df[available_columns]

        # Save debugging datasets
        debug_data_dir = os.path.join(debug_dir, "filtered_data")
        os.makedirs(debug_data_dir, exist_ok=True)

        """
        if not df_in_no_type.empty:
            no_type_file = os.path.join(debug_data_dir, "records_without_type.csv")
            df_in_no_type.to_csv(no_type_file, sep="|", index=False)
            print(f"Records without type saved to: {no_type_file}")
        
        if not df_in_no_price.empty:
            no_alpaca_file = os.path.join(debug_data_dir, "records_without_alpaca.csv")
            df_in_no_price.to_csv(no_alpaca_file, sep="|", index=False)
            print(f"Records without Alpaca symbol saved to: {no_alpaca_file}")
        """

        # Show type distribution in final dataset
        if 'type' in df.columns and not df.empty:
            print("\nType distribution in final dataset:")
            type_counts = df['type'].value_counts()
            for type_name, count in type_counts.items():
                print(f"  {type_name}: {count:,}")

        # Generate summary report
        print("\nGenerating debug summary...")
        generate_debug_summary(debug_dir, provider_debugs, cross_analysis)

        # Save final output
        os.makedirs(config.data_dir, exist_ok=True)
        file_path = os.path.join(config.data_dir, f"{datetime.now().strftime('%Y%m%d')}_MASTER.csv")

        if not df.empty:
            df.to_csv(file_path, sep="|", index=False)
            print(f"\n✅ Processing completed successfully!")
            print(f"Master file saved to: {file_path}")
            print(f"Final records: {len(df):,}")
        else:
            print(f"\n⚠️ No records with both type and Alpaca symbol found!")
            print("Check the debug output above to see what's wrong with the al_symbol column.")

        print(f"Debug files available in: {debug_dir}")

    except Exception as e:
        # Save error information
        error_file = os.path.join(debug_dir, "error_log.txt")
        with open(error_file, 'w') as f:
            f.write(f"Error occurred at: {datetime.now()}\n")
            f.write(f"Error: {str(e)}\n")
            f.write(f"Error type: {type(e).__name__}\n")
            import traceback
            f.write(f"Traceback:\n{traceback.format_exc()}")

        print(f"❌ Error occurred: {e}")
        print(f"Error details saved to: {error_file}")
        raise


if __name__ == "__main__":
    main_with_debugging()

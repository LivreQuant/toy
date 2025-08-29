import os
import numpy as np
from datetime import datetime

from source.providers.fmp import load_fmp_data
from source.providers.intrinio import load_intrinio_data
from source.providers.poly import load_poly_data
from source.providers.nasdaq import load_nasdaq_data
from source.providers.nyse import load_nyse_data
from source.providers.alphavantage import load_alphavantage_data
from source.providers.eodhd import load_eodhd_data
from source.providers.alpaca import load_alpaca_data
from source.providers.sharadar import load_sharadar_data

from source.providers.utils import merge_and_prioritize, average_or_keep


"""
OFFICAL SOURCE
"""
print("\nLoading Nasdaq data...")
nasdaq_df = load_nasdaq_data()
print(f"Loaded Nasdaq data with shape: {nasdaq_df.shape}")

print("\nLoading NYSE data...")
nyse_df = load_nyse_data()
print(f"Loaded NYSE data with shape: {nyse_df.shape}")

"""
UNOFFICAL SOURCE
"""

print("Loading FMP data...")
fmp_df = load_fmp_data()
print(f"Loaded FMP data with shape: {fmp_df.shape}")

print("\nLoading Intrinio data...")
intrinio_df = load_intrinio_data()
print(f"Loaded Intrinio data with shape: {intrinio_df.shape}")

print("\nLoading Poly data...")
poly_df = load_poly_data()
print(f"Loaded Poly data with shape: {poly_df.shape}")

print("\nLoading Alpha Vantage data...")
av_df = load_alphavantage_data()
print(f"Loaded Alpha Vantage data with shape: {av_df.shape}")

print("\nLoading EODHD data...")
eodhd_df = load_eodhd_data()
print(f"Loaded EODHD data with shape: {eodhd_df.shape}")

print("\nLoading Alpaca data...")
alpaca_df = load_alpaca_data()
print(f"Loaded Alpaca data with shape: {alpaca_df.shape}")

print("\nLoading Sharadar data...")
sharadar_df = load_sharadar_data()
print(f"Loaded Sharadar data with shape: {sharadar_df.shape}")

dataframes = {
    't1': nasdaq_df,
    't2': nyse_df,
    't3': intrinio_df,
    't4': eodhd_df,
    't5': poly_df,
    't6': sharadar_df,
    't7': fmp_df,
    't8': av_df,
    't9': alpaca_df,
}

priorities = ['t1', 't2', 't3', 't4', 't5', 't6', 't7', 't8', 't9']

df, variables = merge_and_prioritize(dataframes, priorities,
                                     required_tables=['t1', 't2'],
                                     merge_keys=['standardized_symbol', 'exchange'])

df_not_in = df.loc[df['confidence_score'] == 0]
df_in = df.loc[df['confidence_score'] > 0]

df_in['confidence_score'].value_counts()
df_test = df_in.loc[df_in['confidence_score'] <= 2]

df_in['etf'].value_counts()
df_in['currency'].value_counts()
df_in['status'].value_counts()
df_in['locale'].value_counts()
df_in['type'].value_counts()

# RAISE VALUE ERROR?
x = df_in.loc[(df_in['etf'] == 'N') & ((df_in['type'] == 'ETF') | (df_in['type'] == 'ETC'))]
y = df_in.loc[(df_in['etf'] == 'Y') & (df_in['type'] != 'ETF') & (df_in['type'] != 'ETC')]

variables_ = [x for x in variables if x != 'etf']
df_in = df_in.drop(columns=['etf'])

df_in_ = df_in[['exchange', 'confidence_score', 'al_symbol'] + [x for x in variables_]]
df_in_['short_sale_restricted'] = df_in_['short_sale_restricted'].replace(' ', None)
df_in_['halt_reason'] = df_in_['halt_reason'].replace(' ', None)
df_in_['market_capital'] = df_in_.apply(average_or_keep, axis=1)
df_in_ = df_in_.drop(columns=['market_capital_1', 'market_capital_2'])
df_in_ = df_in_.replace(np.nan, None)
df_in_['null_count'] = df_in_.isnull().sum(axis=1)
df_in_ = df_in_.sort_values(by='null_count', ascending=True)
df_in_ = df_in_.drop_duplicates(subset=['symbol', 'exchange'], keep='first')

variables_orders = ['symbol',

                    # MAP TO CA, FUND, EVENTS
                    'al_symbol', 'av_symbol', 'ed_symbol', 'fp_symbol', 'it_symbol', 'pl_symbol', 'sh_symbol',

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
                    'margin_requirement_short',  'margin_requirement_long', 'maintenance_margin_requirement',
                    'homepage_url', 'branding']

set(df_in_.columns) - set(variables_orders)

df_in_ = df_in_[variables_orders]

df_in_no_type = df_in_.loc[df_in_['type'].isnull()]
df_in_ = df_in_.loc[~df_in_['type'].isnull()]

df_in_price = df_in_.loc[~df_in_['al_symbol'].isnull()]
df_in_no_price = df_in_.loc[df_in_['al_symbol'].isnull()]

data_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "data"))
os.makedirs(data_dir, exist_ok=True)
file_path = os.path.join(data_dir, f"{datetime.now().strftime('%Y%m%d')}_MASTER.csv")

df_in_price.to_csv(file_path, sep="|", index=False)

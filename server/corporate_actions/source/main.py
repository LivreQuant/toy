from source.providers import fmp, poly, sharadar, alpaca

"""Main function to load data from all sources."""
print("Loading data from FMP...")
fmp_dividends, fmp_splits = fmp.load_data()
print(f"Loaded {len(fmp_dividends)} dividend records and {len(fmp_splits)} split records from FMP.")

print("\nLoading data from Polygon...")
poly_dividends, poly_splits = poly.load_data()
print(f"Loaded {len(poly_dividends)} dividend records and {len(poly_splits)} split records from Polygon.")

print("\nLoading data from Sharadar...")
sharadar_data = sharadar.load_data()
print(f"Loaded {len(sharadar_data)} records from Sharadar.")

print("\nLoading data from Alpaca...")
alpaca_tables = alpaca.load_data()
print(f"Loaded data for {list(alpaca_tables.keys())} action types from Alpaca.")

for action_type, df in alpaca_tables.items():
    print(f"  - {action_type}: {len(df)} records")

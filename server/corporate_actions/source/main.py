from source.providers import fmp, poly, sharadar, alpaca

"""Main function to load data from all sources."""
print("Loading data from FMP...")
fmp_data = fmp.load_data()
print("FMP data loaded:")
for action_type, df in fmp_data.items():
    print(f"  - {action_type}: {len(df)} records")

print("\nLoading data from Polygon...")
poly_data = poly.load_data()
print("Polygon data loaded:")
for action_type, df in poly_data.items():
    print(f"  - {action_type}: {len(df)} records")

print("\nLoading data from Sharadar...")
sharadar_data = sharadar.load_data()
print(f"Loaded {len(sharadar_data)} records from Sharadar.")

print("\nLoading data from Alpaca...")
alpaca_data = alpaca.load_data()
print("Alpaca data loaded:")
for action_type, df in alpaca_data.items():
    print(f"  - {action_type}: {len(df)} records")

from source.config import config
from source.providers import fmp, poly, sharadar, alpaca

from source.actions import cash_dividends

def main():
    """Main function to load data from all sources."""
    # Ensure directories exist
    config.ensure_directories()
    
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

    print("\nAnalyzing Cash Dividends...")
    cash_dividends.run(alpaca_data, fmp_data, poly_data, sharadar_data)


if __name__ == "__main__":
    main()

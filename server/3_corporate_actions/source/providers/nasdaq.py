import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime
import os
from source.config import config


def get_nasdaq_security_status():
    """
    Fetch NASDAQ security status updates for today and return filtered IPO/DELIST data as DataFrames

    Returns:
        dict: Dictionary with 'ipos' and 'delistings' DataFrames
    """

    # Get today's date in MM/DD/YYYY format
    today = datetime.now().strftime("%m/%d/%Y")

    # Construct the URL with today's date
    url = f"https://www.nasdaqtrader.com/Trader.aspx?id=nasdaq-security-status-updates&from={today}&to={today}"

    print(f"Fetching NASDAQ data for {today}")
    print(f"URL: {url}")

    # Define the mapping for Issue Events we want to track
    event_mapping = {
        'Security Additions': 'ipos',
        'Anticipated Security Additions': 'ipos',
        'Issue Suspensions': 'delistings',
        'Issue Deletions': 'delistings'
    }

    # Initialize empty results
    results = {
        'ipos': pd.DataFrame(),
        'delistings': pd.DataFrame()
    }

    try:
        # Set headers to mimic a browser request
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }

        # Make the request
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()

        print(f"Successfully fetched page (Status: {response.status_code})")

        # Parse the HTML
        soup = BeautifulSoup(response.content, 'html.parser')

        # Find the table with class "genTable"
        table = soup.find('div', class_='genTable')

        if not table:
            print("Warning: Could not find table with class 'genTable' - returning empty DataFrames")
            return results

        # Find the actual table element within the div
        table_element = table.find('table')
        if not table_element:
            print("Warning: No table element found within genTable div - returning empty DataFrames")
            return results

        print("Found table, extracting data...")

        # Get header row
        header_row = table_element.find('tr')
        if not header_row:
            print("Warning: No header row found - returning empty DataFrames")
            return results

        headers = [th.get_text(strip=True) for th in header_row.find_all(['th', 'td'])]
        print(f"Table headers: {headers}")

        # Find the required column indices
        symbol_index = None
        company_name_index = None
        issue_event_index = None

        for i, header in enumerate(headers):
            header_lower = header.lower()
            if 'symbol' in header_lower:
                symbol_index = i
            elif 'company' in header_lower and 'name' in header_lower:
                company_name_index = i
            elif 'issue event' in header_lower or 'event' in header_lower:
                issue_event_index = i

        if symbol_index is None:
            print("Warning: Could not find 'Symbol' column - returning empty DataFrames")
            return results

        if company_name_index is None:
            print("Warning: Could not find 'Company Name' column - returning empty DataFrames")
            return results

        if issue_event_index is None:
            print("Warning: Could not find 'Issue Event' column - returning empty DataFrames")
            return results

        print(
            f"Found columns - Symbol: {symbol_index}, Company Name: {company_name_index}, Issue Event: {issue_event_index}")

        # Get data rows (skip the first row since it's the header)
        data_rows = table_element.find_all('tr')[1:]

        # Separate IPO and delisting data
        ipo_data = []
        delisting_data = []

        for row in data_rows:
            cells = row.find_all(['td', 'th'])
            row_data = [cell.get_text(strip=True) for cell in cells]

            if len(row_data) > max(symbol_index, company_name_index, issue_event_index):
                symbol = row_data[symbol_index] if symbol_index < len(row_data) else ''
                company_name = row_data[company_name_index] if company_name_index < len(row_data) else ''
                issue_event = row_data[issue_event_index] if issue_event_index < len(row_data) else ''

                # Check if this issue event matches our criteria
                event_type = None
                for key, value in event_mapping.items():
                    if key.lower() in issue_event.lower():
                        event_type = value
                        break

                # Add to appropriate list based on event type
                if event_type == 'ipos':
                    ipo_data.append({
                        'symbol': symbol,
                        'company_name': company_name,
                        'issue_event': issue_event,
                        'listing_date': today,  # Use today as listing date
                        'source': 'nasdaq'
                    })
                    print(f"Found IPO: {symbol} - {company_name}")
                elif event_type == 'delistings':
                    delisting_data.append({
                        'symbol': symbol,
                        'company_name': company_name,
                        'issue_event': issue_event,
                        'delisting_date': today,  # Use today as delisting date
                        'delisting_reason': issue_event,
                        'source': 'nasdaq'
                    })
                    print(f"Found Delisting: {symbol} - {company_name}")

        # Create DataFrames
        if ipo_data:
            results['ipos'] = pd.DataFrame(ipo_data)
            print(f"Created IPO DataFrame with {len(ipo_data)} records")
        else:
            print("No IPO events found for today")

        if delisting_data:
            results['delistings'] = pd.DataFrame(delisting_data)
            print(f"Created Delisting DataFrame with {len(delisting_data)} records")
        else:
            print("No delisting events found for today")

        # Optional: Save raw data to CSV for debugging
        save_debug_csv(ipo_data, delisting_data, today)

        return results

    except requests.exceptions.RequestException as e:
        print(f"Error fetching NASDAQ data: {e}")
        return results
    except Exception as e:
        print(f"Error processing NASDAQ data: {e}")
        return results


def save_debug_csv(ipo_data, delisting_data, date_str):
    """
    Save debug CSV files for IPO and delisting data
    """
    try:
        # Ensure debug directory exists
        debug_dir = os.path.join(config.debug_dir, 'nasdaq')
        os.makedirs(debug_dir, exist_ok=True)

        # Create filename with today's date
        date_formatted = date_str.replace('/', '_')

        # Save IPO data
        if ipo_data:
            ipo_filename = os.path.join(debug_dir, f"nasdaq_ipos_{date_formatted}.csv")
            pd.DataFrame(ipo_data).to_csv(ipo_filename, index=False)
            print(f"Debug IPO data saved to: {ipo_filename}")

        # Save delisting data
        if delisting_data:
            delisting_filename = os.path.join(debug_dir, f"nasdaq_delistings_{date_formatted}.csv")
            pd.DataFrame(delisting_data).to_csv(delisting_filename, index=False)
            print(f"Debug delisting data saved to: {delisting_filename}")

    except Exception as e:
        print(f"Warning: Could not save debug CSV files: {e}")


def load_data():
    """
    Loads all corporate action data from the NASDAQ dataset by scraping live data.

    Returns:
        A dictionary of pandas DataFrames where keys are action types:
        - ipos: DataFrame with IPO information.
        - delistings: DataFrame with delisting information.
    """

    print("Loading NASDAQ data...")

    try:
        # Get live data from NASDAQ website
        results = get_nasdaq_security_status()

        # Print summary
        ipo_count = len(results['ipos']) if not results['ipos'].empty else 0
        delisting_count = len(results['delistings']) if not results['delistings'].empty else 0

        print(f"NASDAQ data loaded successfully:")
        print(f"  - IPOs: {ipo_count} records")
        print(f"  - Delistings: {delisting_count} records")

        return results

    except Exception as e:
        print(f"Error in NASDAQ load_data: {e}")
        print("Returning empty DataFrames")
        raise ValueError("Missing NASDAQ Data")

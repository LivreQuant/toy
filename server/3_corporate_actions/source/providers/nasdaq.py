import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime
import csv
import sys

"""
ISSUE EVENTS:
The category of the change to the affected
security. List of all Allowed Values:
    Security Additions : IPO
    Anticipated Security Additions : IPO
    Issue Suspensions : DELIST
    Issue Deletions : DELIST
    Name/Symbol Changes
    Market Class Changes
    Market Participant Additions
    Market Participant Changes
    Market Participant Deletions
    Financial Status Changes
"""


def get_nasdaq_security_status():
    """
    Fetch NASDAQ security status updates for today and save filtered IPO/DELIST data as CSV
    """

    # Get today's date in MM/DD/YYYY format
    today = datetime.now().strftime("%m/%d/%Y")

    # Construct the URL with today's date
    url = f"https://www.nasdaqtrader.com/Trader.aspx?id=nasdaq-security-status-updates&from={today}&to={today}"

    print(f"Fetching data for {today}")
    print(f"URL: {url}")

    # Define the mapping for Issue Events we want to track
    event_mapping = {
        'Security Additions': 'IPO',
        'Anticipated Security Additions': 'IPO',
        'Issue Suspensions': 'DELIST',
        'Issue Deletions': 'DELIST'
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
            print("Error: Could not find table with class 'genTable'")
            print("Available div classes:")
            for div in soup.find_all('div', class_=True):
                print(f"  - {div.get('class')}")
            return False

        # Find the actual table element within the div
        table_element = table.find('table')
        if not table_element:
            print("Error: No table element found within genTable div")
            return False

        print("Found table, extracting data...")

        # Extract table data
        rows = []

        # Get header row
        header_row = table_element.find('tr')
        if not header_row:
            print("Error: No header row found")
            return False

        headers = [th.get_text(strip=True) for th in header_row.find_all(['th', 'td'])]
        print(f"Original headers: {headers}")

        # Find the Issue Event column index
        issue_event_index = None
        for i, header in enumerate(headers):
            if 'issue event' in header.lower() or 'event' in header.lower():
                issue_event_index = i
                break

        if issue_event_index is None:
            print("Error: Could not find 'Issue Event' column")
            print("Available columns:", headers)
            return False

        print(f"Found Issue Event column at index: {issue_event_index}")

        # Add our custom column for IPO/DELIST classification
        filtered_headers = headers + ['Event_Type']

        # Get data rows (skip the first row since it's the header)
        data_rows = table_element.find_all('tr')[1:]
        filtered_rows = []

        for row in data_rows:
            cells = row.find_all(['td', 'th'])
            row_data = [cell.get_text(strip=True) for cell in cells]

            if len(row_data) > issue_event_index:
                issue_event = row_data[issue_event_index]

                # Check if this issue event matches our criteria
                event_type = None
                for key, value in event_mapping.items():
                    if key.lower() in issue_event.lower():
                        event_type = value
                        break

                # Only include rows that match our IPO/DELIST criteria
                if event_type:
                    row_with_type = row_data + [event_type]
                    filtered_rows.append(row_with_type)
                    print(f"Found {event_type}: {issue_event}")

        if not filtered_rows:
            print("No IPO or DELIST events found for today")
            # Still create an empty CSV with headers
            final_rows = [filtered_headers]
        else:
            print(f"Found {len(filtered_rows)} IPO/DELIST events")
            final_rows = [filtered_headers] + filtered_rows

            # Print summary
            ipo_count = sum(1 for row in filtered_rows if row[-1] == 'IPO')
            delist_count = sum(1 for row in filtered_rows if row[-1] == 'DELIST')
            print(f"  - IPO events: {ipo_count}")
            print(f"  - DELIST events: {delist_count}")

        # Create filename with today's date
        filename = f"nasdaq_ipo_delist_{today.replace('/', '_')}.csv"

        # Write to CSV
        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerows(final_rows)

        print(f"Filtered data successfully saved to: {filename}")

        # Create DataFrame for preview if we have data
        if len(final_rows) > 1:
            df = pd.DataFrame(final_rows[1:], columns=final_rows[0])
            print(f"\nFiltered DataFrame preview:")
            print(df.to_string(index=False))
            print(f"\nShape: {df.shape}")
        else:
            print("\nNo data to preview - empty results")

        return True

    except requests.exceptions.RequestException as e:
        print(f"Error fetching data: {e}")
        return False
    except Exception as e:
        print(f"Error processing data: {e}")
        return False


def run():
    """
    Main function to run the script
    """
    print("NASDAQ IPO/DELIST Event Tracker")
    print("=" * 40)
    print("Tracking events:")
    print("  • Security Additions → IPO")
    print("  • Anticipated Security Additions → IPO")
    print("  • Issue Suspensions → DELIST")
    print("  • Issue Deletions → DELIST")
    print("=" * 40)

    success = get_nasdaq_security_status()

    if success:
        print("\n✓ Script completed successfully!")
    else:
        print("\n✗ Script failed to complete")
        sys.exit(1)

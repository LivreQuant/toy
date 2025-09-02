import ftplib
import os
import datetime
import pandas as pd
import shutil
from source.providers.utils import standardize
from source.config import config

OLD_COLUMNS = ['Symbol', 'PrimaryListingMarketParticipantID', 'FinancialStatusIndicator', 
               'ShortSaleRestrictionIndicator', 'HaltReason']

NEW_COLUMNS = ['ny_symbol', 'exchange', 'ny_status', 'ny_short_sale_restricted', 'ny_halt_reason']


def get_nyse_symbol_list_robust():
    """
    Connects to the NYSE FTP server, finds the latest CTA symbol file
    by checking recent dates, and downloads it.
    """
    ftp_server = "ftp.nyse.com"
    remote_dir = "cta_symbol_files"

    local_path = None

    try:
        with ftplib.FTP(ftp_server, 'anonymous', 'anonymous@') as ftp:
            ftp.cwd(remote_dir)
            print(f"Connecting to {ftp_server} and navigating to {remote_dir}...")

            # Start from today and go back a few days to find the latest file
            for i in range(10):  # Check the last 10 days to be safe
                date_to_check = datetime.date.today() - datetime.timedelta(days=i)
                file_name = f"CTA.Symbol.File.{date_to_check.strftime('%Y%m%d')}.csv"

                try:
                    ftp.size(file_name)  # Check if the file exists on the server
                    print(f"Found latest file: {file_name}")

                    local_path = os.path.join(os.getcwd(), file_name)
                    with open(local_path, "wb") as f:
                        ftp.retrbinary(f"RETR {file_name}", f.write)

                    print(f"Successfully downloaded {file_name} to {local_path}")
                    return local_path

                except ftplib.error_perm as e:
                    # 550 error means the file doesn't exist, so we keep looking
                    print(f"File {file_name} not found. Trying previous day.")
                    continue

            print("Could not find a recent symbol file within the last 10 days.")
            return None

    except ftplib.all_errors as e:
        print(f"FTP Error: {e}")
        return None
    except Exception as e:
        print(f"An error occurred: {e}")
        return None


def load_nyse_data():
    """
    Loads the NYSE symbol data from the downloaded file into a pandas DataFrame.
    Caches the data to a local file.
    """
    # Ensure data directory exists
    os.makedirs(config.nyse_data_path, exist_ok=True)
    file_path = os.path.join(config.nyse_data_path, f"{datetime.datetime.now().strftime('%Y%m%d')}_NYSE.csv")

    # Check if the cached file exists
    if os.path.exists(file_path):
        print(f"Loading data from cached file: {file_path}")
        df = pd.read_csv(file_path)

        # Columns to keep
        df = df[OLD_COLUMNS]
        df.columns = NEW_COLUMNS

        # Standardize symbol
        df['standardized_symbol'] = df['ny_symbol'].apply(standardize)

        # Standardize exchange
        df['exchange'] = df['exchange'].replace({
            'T': 'XNAS',
            'N': 'XNYS'
        })

        df = df.loc[df['exchange'].isin(['XNYS', 'XNAS'])]

        # Status
        df['ny_status'] = df['ny_status'].astype(str).replace({
            '0': 'Normal',
            '1': "Bankrupt",
            '2': 'Deficient',
            "3": "Bankrupt",
            '4': "Delinquent",
            "5": "Bankrupt",
            "6": "Delinquent",
            "7": "Bankrupt",
            "8": "Suspended",
            "9": "Suspended",
            "A": "Liquidation"
        })

        return df

    downloaded_file_path = get_nyse_symbol_list_robust()
    if downloaded_file_path:
        try:
            # Move the downloaded file to the data directory
            shutil.move(downloaded_file_path, file_path)
            print(f"Moved downloaded file to: {file_path}")

            df = pd.read_csv(file_path)

            # Columns to keep
            df = df[OLD_COLUMNS]
            df.columns = NEW_COLUMNS

            # Standardize symbol
            df['standardized_symbol'] = df['ny_symbol'].apply(standardize)

            # Standardize exchange
            df['exchange'] = df['exchange'].replace({
                'T': 'XNAS',
                'N': 'XNYS'
            })

            df = df.loc[df['exchange'].isin(['XNYS', 'XNAS'])]

            # Status
            df['ny_status'] = df['ny_status'].astype(str).replace({
                '0': 'Normal',
                '1': "Bankrupt",
                '2': 'Deficient',
                "3": "Bankrupt",
                '4': "Delinquent",
                "5": "Bankrupt",
                "6": "Delinquent",
                "7": "Bankrupt",
                "8": "Suspended",
                "9": "Suspended",
                "A": "Liquidation"
            })

            return df
        except Exception as e:
            print(f"Error reading or parsing the NYSE symbol file: {e}")
            raise ValueError("Missing NYSE Data")
    else:
        raise ValueError("Missing NYSE Data")
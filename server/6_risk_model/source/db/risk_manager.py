# db/risk_manager.py
from db.base_manager import BaseManager
import logging
import pandas as pd
import pyodbc
from config import config

class RiskManager(BaseManager):
    """
    Manages database operations for the risk factor data.
    """
    def __init__(self):
        """
        Initializes the risk manager.
        """
        super().__init__()
        self.table = config.db.table
        
    def load(self, data):
        """
        Loads the provided risk factor data into the database,
        overwriting existing data for the given date, model, and symbol.

        Args:
            data (list of dict): A list of dictionaries, where each dict
                                 represents a row of data to be inserted.
        """
        if not data:
            logging.warning("No data provided to load.")
            return

        df = pd.DataFrame(data)
        
        try:
            # Connect to the database
            with pyodbc.connect(self._get_connection_string(), autocommit=False) as conn:
                with conn.cursor() as cursor:
                    logging.info(f"Connected to database '{self.database}'.")

                    # Use a unique temporary table to avoid conflicts
                    temp_table = "#temp_risk_factor_data"
                    
                    # Create the temporary table with the new schema
                    create_temp_sql = f"""
                    CREATE TABLE {temp_table} (
                        date DATE NOT NULL,
                        model VARCHAR(20) NOT NULL,
                        factor1 VARCHAR(20) NOT NULL,
                        factor2 VARCHAR(20) NOT NULL,
                        factor3 VARCHAR(20) NOT NULL,
                        symbol VARCHAR(20) NOT NULL,
                        type VARCHAR(100),
                        name VARCHAR(100),
                        value DECIMAL(12,6)
                    );
                    """
                    cursor.execute(create_temp_sql)

                    # Insert data from the pandas DataFrame into the temp table
                    logging.info("Inserting new data into temporary table...")
                    
                    # Prepare the data for insertion
                    params = df[['date', 'model', 'factor1', 'factor2', 'factor3', 'symbol', 'type', 'name', 'value']].to_records(index=False).tolist()
                    insert_temp_sql = f"INSERT INTO {temp_table} (date, model, factor1, factor2, factor3, symbol, type, name, value) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);"
                    cursor.executemany(insert_temp_sql, params)

                    # Delete existing data from the main table for the specific date, model, and symbols
                    symbols_tuple = tuple(df['symbol'].unique())
                    delete_sql = f"""
                    DELETE FROM {self.table}
                    WHERE date = ? AND model = ? AND symbol IN ({','.join(['?'] * len(symbols_tuple))});
                    """
                    
                    logging.info("Deleting existing data from main table...")
                    cursor.execute(delete_sql, df['date'].iloc[0], df['model'].iloc[0], *symbols_tuple)

                    # Insert data from the temporary table into the main table
                    insert_sql = f"""
                    INSERT INTO {self.table} (date, model, factor1, factor2, factor3, symbol, type, name, value)
                    SELECT date, model, factor1, factor2, factor3, symbol, type, name, value FROM {temp_table};
                    """
                    logging.info("Inserting new data from temporary table into main table...")
                    cursor.execute(insert_sql)

                    # Commit the transaction
                    conn.commit()
                    logging.info("Data loaded successfully.")

        except pyodbc.Error as ex:
            sqlstate = ex.args[0]
            logging.error(f"Database error: {sqlstate}")
            raise
        except Exception as e:
            logging.error(f"An unexpected error occurred during database loading: {e}")
            raise
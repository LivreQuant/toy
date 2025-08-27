
# db/base_manager.py
import pyodbc
import logging

class BaseManager:
    """
    Abstract base class for all database managers.
    Contains common database connection logic.
    """
    def __init__(self):
        """
        Initializes the base database manager with connection details.
        NOTE: Update these details with your specific SQL Server credentials.
        """
        self.driver = '{ODBC Driver 17 for SQL Server}'
        self.server = 'your_server_name'
        self.database = 'your_database_name'
        self.username = 'your_username'
        self.password = 'your_password'
        
    def _get_connection_string(self):
        """
        Constructs the connection string.
        """
        return f'DRIVER={self.driver};SERVER={self.server};DATABASE={self.database};UID={self.username};PWD={self.password}'

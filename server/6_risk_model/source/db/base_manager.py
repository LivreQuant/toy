# db/base_manager.py
from source.config import config


class BaseManager:
    """
    Abstract base class for all database managers.
    Contains common database connection logic.
    """

    def __init__(self):
        """
        Initializes the base database manager with connection details from config.
        """
        self.driver = config.db.driver
        self.server = config.db.server
        self.database = config.db.database
        self.username = config.db.username
        self.password = config.db.password

    def _get_connection_string(self):
        """
        Constructs the connection string using config.
        """
        return config.db.connection_string

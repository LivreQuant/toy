# source/db/__init__.py
from source.db.base_manager import BaseDatabaseManager
from source.db.handlers.user import UserDatabaseManager
from source.db.handlers.auth import AuthDatabaseManager
from source.db.handlers.profile import ProfileDatabaseManager
from source.db.handlers.verification import VerificationDatabaseManager
from source.db.handlers.password_reset import PasswordResetDatabaseManager
from source.db.handlers.feedback import FeedbackDatabaseManager


class DatabaseManager(BaseDatabaseManager,
                      UserDatabaseManager,
                      AuthDatabaseManager,
                      ProfileDatabaseManager,
                      VerificationDatabaseManager,
                      PasswordResetDatabaseManager,
                      FeedbackDatabaseManager):
    """
    Unified database manager that combines all database operations.

    This class inherits from BaseDatabaseManager to provide core connection
    functionality and from all specialized database handlers to provide
    domain-specific database operations.

    By using multiple inheritance, the DatabaseManager exposes all methods
    from the specialized handlers while maintaining a single connection pool
    that is initialized in the BaseDatabaseManager.
    """

    def __init__(self):
        """
        Initialize the database manager.

        Calls the __init__ method of BaseDatabaseManager to set up configuration
        and prepare for connection establishment.
        """
        BaseDatabaseManager.__init__(self)
        # We don't need to call __init__ on other parent classes
        # as they inherit from BaseDatabaseManager and don't override __init__

    async def initialize(self):
        """
        Fully initialize the database manager by establishing a connection.

        This method should be called before using any database operations.
        """
        await self.connect()
        return self

    async def cleanup(self):
        """
        Clean up all database resources.

        This should be called when shutting down the application.
        """
        await self.close()


# Export DatabaseManager as the main class
__all__ = ['DatabaseManager']

# source/db/__init__.py
from source.db.base_manager import BaseDatabaseManager
from source.db.handlers.user_db import UserDatabaseManager
from source.db.auth_db import AuthDatabaseManager
from source.db.handlers.profile_db import ProfileDatabaseManager
from source.db.handlers.verification_db import VerificationDatabaseManager
from source.db.handlers.password_reset_db import PasswordResetDatabaseManager
from source.db.handlers.feedback_db import FeedbackDatabaseManager

class DatabaseManager(UserDatabaseManager, AuthDatabaseManager, ProfileDatabaseManager, 
                     VerificationDatabaseManager, PasswordResetDatabaseManager, 
                     FeedbackDatabaseManager):
    """
    Unified database manager that combines all database operations.
    Inherits from all specialized database managers.
    """
    pass

# Export DatabaseManager as the main class
__all__ = ['DatabaseManager']
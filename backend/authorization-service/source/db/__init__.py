# source/db/__init__.py
from source.db.base_manager import BaseDatabaseManager
from source.db.user_db import UserDatabaseManager
from source.db.auth_db import AuthDatabaseManager
from source.db.profile_db import ProfileDatabaseManager
from source.db.verification_db import VerificationDatabaseManager
from source.db.password_reset_db import PasswordResetDatabaseManager
from source.db.feedback_db import FeedbackDatabaseManager

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
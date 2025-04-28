# source/core/base_manager.py
import logging
from opentelemetry import trace


class BaseManager:
    """
    Base manager class that provides common functionality for all managers.

    This serves as the foundation for specialized managers like AuthManager,
    ProfileManager, etc. It ensures consistent initialization patterns and
    common utilities.
    """

    def __init__(self, db_manager=None):
        """
        Initialize the base manager.

        Args:
            db_manager: The database manager instance for database operations
        """
        self.db = db_manager
        self.logger = logging.getLogger(self.__class__.__name__)
        self.tracer = trace.get_tracer(self.__class__.__name__)
        self._dependencies = {}

    def register_dependency(self, name, dependency):
        """
        Register a dependency with this manager.

        Args:
            name: The name to use for this dependency
            dependency: The dependency object
        """
        self._dependencies[name] = dependency
        setattr(self, name, dependency)
        return self

    async def initialize(self):
        """
        Initialize the manager and its dependencies.
        This should be overridden by subclasses if needed.
        """
        self.logger.info(f"Initializing {self.__class__.__name__}")
        return self

    async def cleanup(self):
        """
        Clean up any resources used by this manager.
        This should be overridden by subclasses if needed.
        """
        self.logger.info(f"Cleaning up {self.__class__.__name__}")
        return self
    
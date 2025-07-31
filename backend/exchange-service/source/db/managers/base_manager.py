# source/db/managers/base_manager.py
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from source.db.db_manager import DatabaseManager


class BaseTableManager:
    """Base class for all table-specific managers"""

    def __init__(self, db_manager: 'DatabaseManager'):
        self.db_manager = db_manager
        self.logger = logging.getLogger(self.__class__.__name__)

    @property
    def pool(self):
        """Get the database pool from the main manager"""
        return self.db_manager.pool

    async def ensure_connection(self):
        """Ensure database connection is available"""
        if not self.pool:
            await self.db_manager.initialize()
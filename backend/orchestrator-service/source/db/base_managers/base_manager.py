# source/db/base_managers/base_manager.py
import logging
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)


class BaseManager:
    """Simple base database manager - just CRUD operations"""

    def __init__(self, db_manager):
        self.db_manager = db_manager
        self.pool = db_manager.pool

    async def fetch_one(self, query: str, *args) -> Optional[Dict[str, Any]]:
        """Fetch single row as dict"""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(query, *args)
            return dict(row) if row else None

    async def fetch_all(self, query: str, *args) -> List[Dict[str, Any]]:
        """Fetch all rows as list of dicts"""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, *args)
            return [dict(row) for row in rows]

    async def execute(self, query: str, *args) -> str:
        """Execute query and return status"""
        async with self.pool.acquire() as conn:
            return await conn.execute(query, *args)

    async def execute_returning(self, query: str, *args) -> Optional[Dict[str, Any]]:
        """Execute query and return single row"""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(query, *args)
            return dict(row) if row else None
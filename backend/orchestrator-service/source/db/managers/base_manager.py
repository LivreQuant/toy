# db/managers/base_manager.py
import logging
from typing import Dict, List, Any, Optional, Union
from datetime import date, datetime
import asyncpg
from decimal import Decimal
import uuid

logger = logging.getLogger(__name__)

class BaseManager:
    """Base database manager with common patterns"""
    
    def __init__(self, db_manager):
        self.db_manager = db_manager
        self.pool = db_manager.pool
    
    async def fetch_one(self, query: str, *args) -> Optional[Dict[str, Any]]:
        """Fetch single row as dict"""
        try:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow(query, *args)
                return dict(row) if row else None
        except Exception as e:
            logger.error(f"Database query failed: {query[:100]}... Error: {e}")
            raise
    
    async def fetch_all(self, query: str, *args) -> List[Dict[str, Any]]:
        """Fetch all rows as list of dicts"""
        try:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch(query, *args)
                return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Database query failed: {query[:100]}... Error: {e}")
            raise
    
    async def execute(self, query: str, *args) -> str:
        """Execute query and return status"""
        try:
            async with self.pool.acquire() as conn:
                result = await conn.execute(query, *args)
                return result
        except Exception as e:
            logger.error(f"Database execution failed: {query[:100]}... Error: {e}")
            raise
    
    async def execute_returning(self, query: str, *args) -> Optional[Dict[str, Any]]:
        """Execute query with RETURNING clause"""
        try:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow(query, *args)
                return dict(row) if row else None
        except Exception as e:
            logger.error(f"Database execution failed: {query[:100]}... Error: {e}")
            raise
    
    async def execute_transaction(self, queries: List[tuple]) -> bool:
        """Execute multiple queries in a transaction"""
        try:
            async with self.pool.acquire() as conn:
                async with conn.transaction():
                    for query, args in queries:
                        await conn.execute(query, *args)
                return True
        except Exception as e:
            logger.error(f"Transaction failed: {e}")
            raise
    
    async def bulk_insert(self, table: str, columns: List[str], 
                         data: List[tuple]) -> int:
        """Bulk insert data"""
        if not data:
            return 0
        
        placeholders = ','.join([f'${i}' for i in range(1, len(columns) + 1)])
        query = f"""
            INSERT INTO {table} ({','.join(columns)})
            VALUES ({placeholders})
        """
        
        try:
            async with self.pool.acquire() as conn:
                await conn.executemany(query, data)
                return len(data)
        except Exception as e:
            logger.error(f"Bulk insert failed for table {table}: {e}")
            raise
    
    def convert_decimal_fields(self, row: Dict[str, Any], decimal_fields: List[str]) -> Dict[str, Any]:
        """Convert specified fields to Decimal"""
        if not row:
            return row
        
        converted = row.copy()
        for field in decimal_fields:
            if field in converted and converted[field] is not None:
                converted[field] = Decimal(str(converted[field]))
        
        return converted
    
    def build_where_clause(self, filters: Dict[str, Any]) -> tuple[str, List[Any]]:
        """Build WHERE clause from filters dict"""
        if not filters:
            return "1=1", []
        
        conditions = []
        params = []
        
        for key, value in filters.items():
            if value is not None:
                conditions.append(f"{key} = ${len(params) + 1}")
                params.append(value)
        
        where_clause = " AND ".join(conditions) if conditions else "1=1"
        return where_clause, params
    
    async def create_schema_if_not_exists(self, schema_name: str):
        """Create schema if it doesn't exist"""
        query = f"CREATE SCHEMA IF NOT EXISTS {schema_name}"
        await self.execute(query)
        
    async def table_exists(self, table_name: str, schema_name: str = 'public') -> bool:
        """Check if table exists"""
        query = """
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = $1 AND table_name = $2
            )
        """
        result = await self.fetch_one(query, schema_name, table_name)
        return result['exists'] if result else False
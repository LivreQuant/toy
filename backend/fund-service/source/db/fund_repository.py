# source/db/fund_repository.py
import logging
import time
import decimal
import uuid
import json
from typing import Dict, Any, Optional

from source.db.connection_pool import DatabasePool
from source.utils.metrics import track_db_operation

logger = logging.getLogger('fund_repository')

def serialize_json_safe(obj):
    """Convert non-JSON serializable objects to serializable types"""
    if isinstance(obj, decimal.Decimal):
        return float(obj)
    elif isinstance(obj, uuid.UUID):
        return str(obj)
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

def ensure_json_serializable(data):
    """Recursively convert all values in a data structure to JSON serializable types"""
    if isinstance(data, dict):
        return {k: ensure_json_serializable(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [ensure_json_serializable(item) for item in data]
    elif isinstance(data, (decimal.Decimal, uuid.UUID)):
        return serialize_json_safe(data)
    return data
    
class FundRepository:
    """Data access layer for funds"""

    def __init__(self):
        """Initialize the fund repository"""
        self.db_pool = DatabasePool()

    async def create_fund(self, fund_data: Dict[str, Any]) -> Optional[str]:
        """
        Create a new fund for a user
        
        Args:
            fund_data: Dictionary with fund properties
            
        Returns:
            Fund ID if successful, None otherwise
        """
        pool = await self.db_pool.get_pool()
        
        query = """
        INSERT INTO fund.funds (
            id, name, status, user_id, created_at, updated_at
        ) VALUES (
            $1, $2, $3, $4, to_timestamp($5), to_timestamp($6)
        ) RETURNING id
        """
        
        start_time = time.time()
        try:
            async with pool.acquire() as conn:
                async with conn.transaction():
                    fund_id = await conn.fetchval(
                        query,
                        fund_data['fund_id'],
                        fund_data['name'],
                        fund_data.get('status', 'active'),
                        fund_data['user_id'],
                        fund_data['created_at'],
                        fund_data['updated_at']
                    )
                    
                    # If there are fund properties to save
                    if fund_data.get('properties'):
                        await self._save_fund_properties(conn, fund_id, fund_data['properties'])
                
                duration = time.time() - start_time
                track_db_operation("create_fund", True, duration)
                
                # Convert UUID to string before returning
                if isinstance(fund_id, uuid.UUID):
                    return str(fund_id)
                
                return fund_id
        except Exception as e:
            duration = time.time() - start_time
            track_db_operation("create_fund", False, duration)
            logger.error(f"Error creating fund: {e}")
            return None

    async def _save_fund_properties(self, conn, fund_id: str, properties: Dict[str, Dict[str, Dict[str, Any]]]) -> bool:
        """
        Save fund properties using the EAV model
        
        Args:
            conn: Database connection
            fund_id: Fund ID
            properties: Properties structure {category: {subcategory: {key: value}}}
            
        Returns:
            Success flag
        """
        query = """
        INSERT INTO fund.properties (
            fund_id, category, subcategory, key, value, created_at, updated_at
        ) VALUES (
            $1, $2, $3, $4, $5, to_timestamp($6), to_timestamp($7)
        ) ON CONFLICT (fund_id, category, subcategory, key) 
        DO UPDATE SET value = $5, updated_at = to_timestamp($7)
        """
        
        now = time.time()
        
        try:
            for category, subcategories in properties.items():
                for subcategory, items in subcategories.items():
                    for key, value in items.items():
                        # Convert non-string values to JSON strings
                        if not isinstance(value, str):
                            value = json.dumps(value)
                            
                        await conn.execute(
                            query,
                            fund_id,
                            category,
                            subcategory,
                            key,
                            value,
                            now,
                            now
                        )
            return True
        except Exception as e:
            logger.error(f"Error saving fund properties for {fund_id}: {e}")
            raise
    
    async def get_fund_by_user(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a fund by user ID (one-to-one relationship)
        
        Args:
            user_id: User ID
            
        Returns:
            Fund data with properties if found, None otherwise
        """
        pool = await self.db_pool.get_pool()
        
        fund_query = """
        SELECT 
            id as fund_id, 
            user_id, 
            name,
            status,
            extract(epoch from created_at) as created_at,
            extract(epoch from updated_at) as updated_at
        FROM fund.funds 
        WHERE user_id = $1
        """
        
        properties_query = """
        SELECT 
            category,
            subcategory,
            key,
            value
        FROM fund.properties
        WHERE fund_id = $1
        """
        
        start_time = time.time()
        try:
            async with pool.acquire() as conn:
                # Get fund basic data
                fund_row = await conn.fetchrow(fund_query, user_id)
                
                if not fund_row:
                    duration = time.time() - start_time
                    track_db_operation("get_fund_by_user", False, duration)
                    return None
                
                # Convert to dictionary
                fund_data = ensure_json_serializable(dict(fund_row))
                
                # Get fund properties
                property_rows = await conn.fetch(properties_query, fund_data['fund_id'])
                
                # Organize properties into nested structure
                properties = {}
                for row in property_rows:
                    category = row['category']
                    subcategory = row['subcategory']
                    key = row['key']
                    value = row['value']
                    
                    # Try to parse JSON values
                    try:
                        if value.startswith('{') or value.startswith('['):
                            value = json.loads(value)
                    except (json.JSONDecodeError, AttributeError):
                        pass
                    
                    # Create nested structure
                    if category not in properties:
                        properties[category] = {}
                    if subcategory not in properties[category]:
                        properties[category][subcategory] = {}
                    
                    properties[category][subcategory][key] = value
                
                # Add properties to fund data
                fund_data['properties'] = properties
                
                duration = time.time() - start_time
                track_db_operation("get_fund_by_user", True, duration)
                
                return fund_data
        except Exception as e:
            duration = time.time() - start_time
            track_db_operation("get_fund_by_user", False, duration)
            logger.error(f"Error retrieving fund for user {user_id}: {e}")
            return None
    
    async def update_fund(self, fund_id: str, user_id: str, update_data: Dict[str, Any]) -> bool:
        """
        Update a fund
        
        Args:
            fund_id: Fund ID to update
            user_id: User ID to validate ownership
            update_data: Dictionary with fields to update
            
        Returns:
            True if successful, False otherwise
        """
        pool = await self.db_pool.get_pool()
        
        # We'll handle properties separately
        properties = update_data.pop('properties', None)
        
        # Only proceed with basic update if there are fields to update
        fund_updated = True
        if update_data:
            # Build dynamic query based on provided fields
            set_clauses = [f"{key} = ${i+3}" for i, key in enumerate(update_data.keys())]
            set_clauses.append("updated_at = to_timestamp($" + str(len(update_data) + 3) + ")")
            set_clause = ", ".join(set_clauses)
            
            query = f"""
            UPDATE funds 
            SET {set_clause}
            WHERE id = $1 AND user_id = $2
            """
            
            start_time = time.time()
            try:
                async with pool.acquire() as conn:
                    params = [fund_id, user_id] + list(update_data.values()) + [time.time()]
                    result = await conn.execute(query, *params)
                    
                    duration = time.time() - start_time
                    fund_updated = result == "UPDATE 1"
                    track_db_operation("update_fund", fund_updated, duration)
                    
            except Exception as e:
                duration = time.time() - start_time
                track_db_operation("update_fund", False, duration)
                logger.error(f"Error updating fund {fund_id}: {e}")
                return False
        
        # Update properties if provided
        if properties:
            try:
                async with pool.acquire() as conn:
                    await self._save_fund_properties(conn, fund_id, properties)
            except Exception as e:
                logger.error(f"Error updating fund properties for {fund_id}: {e}")
                return False
        
        return fund_updated
    
    async def check_fund_exists(self, user_id: str) -> bool:
        """
        Check if a fund exists for a user
        
        Args:
            user_id: User ID
            
        Returns:
            True if fund exists, False otherwise
        """
        pool = await self.db_pool.get_pool()
        
        query = """
        SELECT 1 FROM fund.funds WHERE user_id = $1 LIMIT 1
        """
        
        try:
            async with pool.acquire() as conn:
                result = await conn.fetchval(query, user_id)
                return result is not None
        except Exception as e:
            logger.error(f"Error checking fund existence for user {user_id}: {e}")
            return False
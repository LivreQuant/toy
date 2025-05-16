# source/db/fund_repository.py
import logging
import time
import decimal
import uuid
import json
import asyncpg
from typing import Dict, Any, Optional, List

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
            fund_id, name, status, user_id, created_at, updated_at
        ) VALUES (
            $1, $2, $3, $4, to_timestamp($5), to_timestamp($6)
        ) RETURNING fund_id
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

    async def create_fund_with_details(self, fund_data: Dict[str, Any],
                                       properties: Dict[str, Any], 
                                       team_members: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Create a fund with its properties and team members
        
        Args:
            fund_data: Fund basic data
            properties: Nested properties dict
            team_members: List of team member data
            
        Returns:
            Dictionary with fund_id if successful
        """
        pool = await self.db_pool.get_pool()
        
        try:
            logger.info(f"Creating fund: {fund_data['name']}")
            logger.info(f"Properties structure: {type(properties)}, Counts: {len(properties) if isinstance(properties, dict) else 'N/A'}")
            logger.info(f"Team members structure: {type(team_members)}, Counts: {len(team_members) if isinstance(team_members, list) else 'N/A'}")
            
            async with pool.acquire() as conn:
                # Start a transaction
                async with conn.transaction():
                    # 1. Create the fund
                    fund_query = """
                    INSERT INTO fund.funds (
                        fund_id, name, status, user_id, created_at, updated_at
                    ) VALUES (
                        $1, $2, $3, $4, to_timestamp($5), to_timestamp($6)
                    ) RETURNING fund_id
                    """
                    
                    fund_id = await conn.fetchval(
                        fund_query,
                        fund_data['fund_id'],
                        fund_data['name'],
                        fund_data.get('status', 'active'),
                        fund_data['user_id'],
                        fund_data['created_at'],
                        fund_data['updated_at']
                    )
                    
                    # Convert UUID to string
                    if isinstance(fund_id, uuid.UUID):
                        fund_id = str(fund_id)
                    
                    logger.info(f"Fund created with ID: {fund_id}")
                    
                    # 2. Save fund properties
                    if properties:
                        logger.info(f"Saving fund properties")
                        await self._save_fund_properties(conn, fund_id, properties)
                    
                    # 3. Create team members
                    for i, team_member_data in enumerate(team_members):
                        logger.info(f"Processing team member #{i}: {team_member_data}")
                        
                        # Create team member
                        team_query = """
                        INSERT INTO fund.team_members (
                            fund_id, status, created_at, updated_at
                        ) VALUES (
                            $1, $2, NOW(), NOW()
                        ) RETURNING team_member_id
                        """
                        
                        team_member_id = await conn.fetchval(
                            team_query,
                            fund_id,
                            'active'
                        )
                        
                        # Convert UUID to string
                        if isinstance(team_member_id, uuid.UUID):
                            team_member_id = str(team_member_id)
                        
                        logger.info(f"Created team member with ID: {team_member_id}")
                        
                        # Save team member properties
                        logger.info(f"Saving team member properties")
                        await self._save_team_member_properties(conn, team_member_id, team_member_data)
                    
                    return {"fund_id": fund_id, "success": True}
                    
        except Exception as e:
            logger.error(f"Error creating fund with details: {e}")
            return {"success": False, "error": str(e)}


    async def _save_fund_properties(self, conn, fund_id: str, properties: Dict[str, Dict[str, Any]]) -> bool:
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
            $1, $2, $3, $4, $5, NOW(), NOW()
        ) ON CONFLICT (fund_id, category, subcategory, key) 
        DO UPDATE SET value = $5, updated_at = NOW()
        """
        
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
                            value
                        )
            return True
        except Exception as e:
            logger.error(f"Error saving fund properties for {fund_id}: {e}")
            raise

    async def _save_team_member_properties(self, conn, team_member_id: str, properties: Dict[str, Dict[str, Any]]) -> None:
        """
        Save team member properties
        
        Args:
            conn: Database connection
            team_member_id: Team member ID
            properties: Properties structure {category: {key: value}}
        """
        query = """
        INSERT INTO fund.team_member_properties (
            member_id, category, subcategory, key, value, created_at, updated_at
        ) VALUES (
            $1, $2, $3, $4, $5, NOW(), NOW()
        ) ON CONFLICT (member_id, category, subcategory, key) 
        DO UPDATE SET value = $5, updated_at = NOW()
        """
        
        try:
            logger.info(f"Save team member properties: processing properties for {team_member_id}: {properties}")
            
            for category, subcategories in properties.items():
                logger.info(f"Save team member properties: processing category: {category}, Type: {type(subcategories)}")
                
                if not isinstance(subcategories, dict):
                    logger.error(f"Save team member properties: expected dict for subcategories, got {type(subcategories)}: {subcategories}")
                    continue
                
                for key, value in subcategories.items():
                    # Here, key is the subcategory (firstName, lastName, etc.)
                    # And value is the actual value (Sergio, Amaral, etc.)
                    logger.info(f"Save team member properties: processing key: {key}, Value: {value}, Type: {type(value)}")
                    
                    if isinstance(value, dict):
                        # If value is a dict, it's a nested structure like education: {institution: "MIT, PSU"}
                        for sub_key, sub_value in value.items():
                            logger.info(f"Save team member properties: processing nested value - key: {sub_key}, value: {sub_value}")
                            
                            # Convert non-string values to JSON strings
                            if not isinstance(sub_value, str):
                                sub_value = json.dumps(sub_value)
                            
                            logger.info(f"Save team member properties: executing query with values: {team_member_id}, {category}, {key}, {sub_key}, {sub_value}")
                            
                            await conn.execute(
                                query,
                                team_member_id,
                                category,
                                key,  # Use the original key as subcategory
                                sub_key,  # Use the sub_key as the key
                                sub_value
                            )
                    else:
                        # For the subcategory, use the key and set subcategory to "info"
                        subcategory = "info"
                        
                        # Convert non-string values to JSON strings
                        if not isinstance(value, str):
                            value = json.dumps(value)
                        
                        logger.info(f"Save team member properties: executing query with values: {team_member_id}, {category}, {subcategory}, {key}, {value}")
                        
                        await conn.execute(
                            query,
                            team_member_id,
                            category,
                            subcategory,
                            key,
                            value
                        )
                
        except Exception as e:
            logger.error(f"Save team member properties: error saving team member properties for {team_member_id}: {e}")
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
            fund_id, 
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
        
        team_members_query = """
        SELECT 
            team_member_id
        FROM fund.team_members
        WHERE fund_id = $1
        """
        
        team_member_properties_query = """
        SELECT 
            category,
            subcategory,
            key,
            value
        FROM fund.team_member_properties
        WHERE member_id = $1
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
                        if value and (value.startswith('{') or value.startswith('[')):
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
                
                # Get team members
                team_member_rows = await conn.fetch(team_members_query, fund_data['fund_id'])
                team_members = []
                
                for team_row in team_member_rows:
                    team_member_id = team_row['team_member_id']
                    
                    # Get team member properties
                    member_property_rows = await conn.fetch(
                        team_member_properties_query, 
                        team_member_id
                    )
                    
                    # Organize team member properties
                    member_properties = {}
                    for row in member_property_rows:
                        category = row['category']
                        subcategory = row['subcategory']
                        key = row['key']
                        value = row['value']
                        
                        # Try to parse JSON values
                        try:
                            if value and (value.startswith('{') or value.startswith('[')):
                                value = json.loads(value)
                        except (json.JSONDecodeError, AttributeError):
                            pass
                        
                        # Create nested structure
                        if category not in member_properties:
                            member_properties[category] = {}
                        if subcategory not in member_properties[category]:
                            member_properties[category][subcategory] = {}
                        
                        member_properties[category][subcategory][key] = value
                    
                    # Add team member with properties
                    team_members.append({
                        "team_member_id": str(team_member_id),
                        "properties": member_properties
                    })
                
                # Add team members to fund data
                fund_data['team_members'] = team_members
                
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
        logger.info(f"Repository: updating fund {fund_id} for user {user_id}")
        logger.info(f"Repository: update data received: {update_data}")
        
        pool = await self.db_pool.get_pool()
        
        # We'll handle properties separately
        properties = update_data.pop('properties', None)
        team_members = update_data.pop('team_members', None)
        
        logger.info(f"Repository: properties to update: {properties}")
        logger.info(f"Repository: team members to update: {team_members}")
        
        fund_updated = True
        
        try:
            async with pool.acquire() as conn:
                async with conn.transaction():
                    # Only proceed with basic update if there are fields to update
                    if update_data:
                        # Build dynamic query based on provided fields
                        set_clauses = [f"{key} = ${i+3}" for i, key in enumerate(update_data.keys())]
                        set_clauses.append("updated_at = NOW()")
                        set_clause = ", ".join(set_clauses)
                        
                        query = f"""
                        UPDATE fund.funds 
                        SET {set_clause}
                        WHERE fund_id = $1 AND user_id = $2
                        """
                        
                        logger.info(f"Repository: executing fund update query: {query}")
                        logger.info(f"Repository: with parameters: {fund_id}, {user_id}, {list(update_data.values())}")
                        
                        result = await conn.execute(query, fund_id, user_id, *update_data.values())
                        fund_updated = result == "UPDATE 1"
                        logger.info(f"Repository: basic fund update result: {result}, success: {fund_updated}")
                    
                    # Update properties if provided
                    if properties:
                        logger.info(f"Repository: updating fund properties")
                        await self._save_fund_properties(conn, fund_id, properties)
                    
                    # Update team members if provided
                    if team_members:
                        logger.info(f"Repository: processing {len(team_members)} team members")
                        
                        for i, team_member in enumerate(team_members):
                            logger.info(f"Repository: processing team member {i+1}/{len(team_members)}: {team_member}")
                            
                            # Extract team member ID
                            member_id = team_member.get('id')
                            if not member_id:
                                logger.warning(f"Repository: team member has no ID, skipping")
                                continue  # Skip if no ID provided
                            
                            logger.info(f"Repository: checking if team member {member_id} belongs to fund {fund_id}")
                            
                            # Verify the team member belongs to this fund
                            member_check_query = """
                            SELECT 1 FROM fund.team_members
                            WHERE team_member_id = $1 AND fund_id = $2
                            """
                            member_exists = await conn.fetchval(member_check_query, member_id, fund_id)
                            
                            if not member_exists:
                                logger.warning(f"Repository: team member {member_id} does not belong to fund {fund_id}, skipping")
                                continue  # Skip if team member doesn't belong to this fund
                            
                            logger.info(f"Repository: team member {member_id} belongs to fund {fund_id}, proceeding with update")
                            
                            # Update team member's properties
                            # Process personal info
                            if 'personal' in team_member:
                                logger.info(f"Repository: updating personal info for team member {member_id}")
                                await self._save_team_member_properties(conn, member_id, {'personal': team_member['personal']})
                            
                            # Process professional info
                            if 'professional' in team_member:
                                logger.info(f"Repository: updating professional info for team member {member_id}")
                                await self._save_team_member_properties(conn, member_id, {'professional': team_member['professional']})
                            
                            # Process education info - handle it directly if present
                            if 'education' in team_member:
                                logger.info(f"Repository: updating education info for team member {member_id}: {team_member['education']}")
                                education_data = {'education': {'info': team_member['education']}}
                                await self._save_team_member_properties(conn, member_id, education_data)
                        
                logger.info(f"Repository: fund update completed with result: {fund_updated}")
                return fund_updated
        except Exception as e:
            logger.error(f"Repository: error updating fund {fund_id}: {e}")
            return False
    
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
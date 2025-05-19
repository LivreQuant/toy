# source/db/fund_repository.py
import logging
import time
import decimal
import uuid
import json
import datetime
from typing import Dict, Any, Optional, List

from source.db.connection_pool import DatabasePool
from source.utils.metrics import track_db_operation
from source.utils.property_mappings import (
    get_team_member_db_mapping, get_original_team_member_field,
    get_fund_db_mapping, get_original_fund_field
)

logger = logging.getLogger('fund_repository')

def serialize_json_safe(obj):
    """Convert non-JSON serializable objects to serializable types"""
    if isinstance(obj, decimal.Decimal):
        return float(obj)
    elif isinstance(obj, uuid.UUID):
        return str(obj)
    elif isinstance(obj, datetime.datetime):
        return obj.timestamp()
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

def ensure_json_serializable(data):
    """Recursively convert all values in a data structure to JSON serializable types"""
    if isinstance(data, dict):
        return {k: ensure_json_serializable(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [ensure_json_serializable(item) for item in data]
    elif isinstance(data, (decimal.Decimal, uuid.UUID, datetime.datetime)):
        return serialize_json_safe(data)
    return data
    
class FundRepository:
    """Data access layer for funds using temporal data pattern"""

    def __init__(self):
        """Initialize the fund repository"""
        self.db_pool = DatabasePool()
        # Far future date used for active records
        self.future_date = datetime.datetime(2999, 1, 1, tzinfo=datetime.timezone.utc)

    async def create_fund(self, fund_data: Dict[str, Any]) -> Optional[str]:
        """
        Create a new fund for a user
        
        Args:
            fund_data: Dictionary with fund properties
            
        Returns:
            Fund ID if successful, None otherwise
        """
        pool = await self.db_pool.get_pool()
        
        logger.info(f"Starting create_fund with data: {fund_data}")
        
        query = """
        INSERT INTO fund.funds (
            fund_id, name, status, user_id, active_at, expire_at
        ) VALUES (
            $1, $2, $3, $4, NOW(), $5
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
                        self.future_date
                    )
                    
                    logger.info(f"Fund created in database with ID: {fund_id}")
                    
                    # If there are fund properties to save
                    if fund_data.get('properties'):
                        logger.info(f"Properties detected in fund_data: {fund_data['properties']}")
                        await self._save_fund_properties(conn, fund_id, fund_data['properties'])
                    else:
                        logger.warning("No properties found in fund_data")
                
                duration = time.time() - start_time
                track_db_operation("create_fund", True, duration)
                
                # Convert UUID to string before returning
                if isinstance(fund_id, uuid.UUID):
                    return str(fund_id)
                
                return fund_id
        except Exception as e:
            duration = time.time() - start_time
            track_db_operation("create_fund", False, duration)
            logger.error(f"Error creating fund: {e}", exc_info=True)
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
        now = datetime.datetime.now(datetime.timezone.utc)
        
        try:
            logger.info(f"Creating fund: {fund_data['name']}")
            logger.info(f"Properties structure: {type(properties)}, Counts: {len(properties) if isinstance(properties, dict) else 'N/A'}")
            logger.info(f"Detailed properties: {properties}")
            logger.info(f"Team members structure: {type(team_members)}, Counts: {len(team_members) if isinstance(team_members, list) else 'N/A'}")
            
            async with pool.acquire() as conn:
                # Start a transaction
                async with conn.transaction():
                    # 1. Create the fund
                    fund_query = """
                    INSERT INTO fund.funds (
                        fund_id, name, status, user_id, active_at, expire_at
                    ) VALUES (
                        $1, $2, $3, $4, $5, $6
                    ) RETURNING fund_id
                    """
                    
                    fund_id = await conn.fetchval(
                        fund_query,
                        fund_data['fund_id'],
                        fund_data['name'],
                        fund_data.get('status', 'active'),
                        fund_data['user_id'],
                        now,
                        self.future_date
                    )
                    
                    # Convert UUID to string
                    if isinstance(fund_id, uuid.UUID):
                        fund_id = str(fund_id)
                    
                    logger.info(f"Fund created with ID: {fund_id}")
                    
                    # 2. Save fund properties
                    if properties:
                        logger.info(f"Saving fund properties: {properties}")
                        
                        # Direct property insertion
                        for prop_name, prop_value in properties.items():
                            logger.info(f"Processing property {prop_name}: {prop_value}")
                            
                            # Skip empty values
                            if prop_value is None or (isinstance(prop_value, str) and not prop_value.strip()):
                                logger.info(f"Skipping empty property {prop_name}")
                                continue
                                
                            # Convert non-string values to strings
                            if not isinstance(prop_value, str):
                                prop_value = json.dumps(prop_value)
                                logger.info(f"Converted to JSON: {prop_value}")
                            
                            # Insert using mapping if available
                            db_mapping = get_fund_db_mapping(prop_name)
                            
                            if db_mapping:
                                category, subcategory, _ = db_mapping
                                logger.info(f"Using mapping for {prop_name}: category={category}, subcategory={subcategory}")
                            else:
                                # Default category/subcategory for unmapped properties
                                category = 'fund'
                                subcategory = prop_name
                                logger.info(f"No mapping found, using defaults: category={category}, subcategory={subcategory}")
                            
                            # Execute insertion
                            logger.info(f"Inserting property: fund_id={fund_id}, category={category}, subcategory={subcategory}, key={prop_name}, value={prop_value}")
                            
                            try:
                                await conn.execute(
                                    """
                                    INSERT INTO fund.properties (
                                        fund_id, category, subcategory, key, value, active_at, expire_at
                                    ) VALUES (
                                        $1, $2, $3, $4, $5, $6, $7
                                    )
                                    """,
                                    fund_id,
                                    category,
                                    subcategory,
                                    prop_name,
                                    prop_value,
                                    now,
                                    self.future_date
                                )
                                logger.info(f"Successfully inserted property {prop_name}")
                            except Exception as prop_err:
                                logger.error(f"Error inserting property {prop_name}: {prop_err}", exc_info=True)
                    else:
                        logger.warning("No properties provided to save")
                    
                    # 3. Create team members
                    for i, team_member_data in enumerate(team_members):
                        logger.info(f"Processing team member #{i}: {team_member_data}")
                        
                        # Create team member
                        team_query = """
                        INSERT INTO fund.team_members (
                            fund_id, status, active_at, expire_at
                        ) VALUES (
                            $1, $2, $3, $4
                        ) RETURNING team_member_id
                        """
                        
                        team_member_id = await conn.fetchval(
                            team_query,
                            fund_id,
                            'active',
                            now,
                            self.future_date
                        )
                        
                        # Convert UUID to string
                        if isinstance(team_member_id, uuid.UUID):
                            team_member_id = str(team_member_id)
                        
                        logger.info(f"Created team member with ID: {team_member_id}")
                        
                        # Save team member properties with index
                        logger.info(f"Saving team member properties")
                        await self._save_team_member_properties(conn, team_member_id, team_member_data, i)
                    
                    return {"fund_id": fund_id, "success": True}
                    
        except Exception as e:
            logger.error(f"Error creating fund with details: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    async def _save_fund_properties(self, conn, fund_id: str, properties: Dict[str, Any]) -> bool:
        """
        Save fund properties using a mapping system
        
        Args:
            conn: Database connection
            fund_id: Fund ID
            properties: Properties structure
            
        Returns:
            Success flag
        """
        now = datetime.datetime.now(datetime.timezone.utc)
        query = """
        INSERT INTO fund.properties (
            fund_id, category, subcategory, key, value, active_at, expire_at
        ) VALUES (
            $1, $2, $3, $4, $5, $6, $7
        )
        """
        
        logger.info(f"START _save_fund_properties for fund_id {fund_id}")
        logger.info(f"Properties to save: {properties}")
        
        try:
            if not properties:
                logger.warning("No properties provided to save")
                return True
                
            insertion_count = 0
            # Process properties using mapping system
            for input_field, value in properties.items():
                logger.info(f"Processing property {input_field}: {value}")
                
                # Skip if value is None or empty
                if value is None or (isinstance(value, str) and not value.strip()):
                    logger.info(f"Skipping empty property {input_field}")
                    continue
                    
                # Look up the mapping
                db_mapping = get_fund_db_mapping(input_field)
                logger.info(f"Mapping for {input_field}: {db_mapping}")
                
                if db_mapping:
                    # Use the mapping format
                    category, subcategory, _ = db_mapping
                    
                    # Use the input_field as the key for better identification
                    key = input_field
                    
                    # Convert non-string values to JSON strings
                    if not isinstance(value, str):
                        value = json.dumps(value)
                        logger.info(f"Converted non-string value to JSON: {value}")
                    
                    logger.info(f"Executing query with: fund_id={fund_id}, category={category}, subcategory={subcategory}, key={key}, value={value}")
                    
                    try:
                        await conn.execute(
                            query,
                            fund_id,
                            category,
                            subcategory,
                            key,
                            value,
                            now,
                            self.future_date
                        )
                        insertion_count += 1
                        logger.info(f"Successfully inserted property {input_field}")
                    except Exception as e:
                        logger.error(f"Error executing insert for property {input_field}: {e}", exc_info=True)
                else:
                    # Handle unmapped properties - use as-is
                    category = 'fund'
                    subcategory = input_field
                    key = input_field  # Use the input_field directly as the key
                    
                    # Convert non-string values to JSON strings
                    if not isinstance(value, str):
                        value = json.dumps(value)
                        logger.info(f"Converted non-string value to JSON: {value}")
                    
                    logger.info(f"Executing query for unmapped property with: fund_id={fund_id}, category={category}, subcategory={subcategory}, key={key}, value={value}")
                    
                    try:
                        await conn.execute(
                            query,
                            fund_id,
                            category,
                            subcategory,
                            key,
                            value,
                            now,
                            self.future_date
                        )
                        insertion_count += 1
                        logger.info(f"Successfully inserted unmapped property {input_field}")
                    except Exception as e:
                        logger.error(f"Error executing insert for unmapped property {input_field}: {e}", exc_info=True)
            
            logger.info(f"END _save_fund_properties: Inserted {insertion_count} properties")
            return True
        except Exception as e:
            logger.error(f"Error saving fund properties for {fund_id}: {e}", exc_info=True)
            raise

    async def _save_team_member_properties(self, conn, team_member_id: str, properties: Dict[str, Any], member_index: int = 0) -> None:
        """
        Save team member properties without using index in category
        
        Args:
            conn: Database connection
            team_member_id: Team member ID
            properties: Properties dictionary
            member_index: Not used for categories anymore, kept for compatibility
        """
        # Import the mappings at the top of the function to ensure they're available
        from source.utils.property_mappings import TEAM_MEMBER_MAPPING
        
        now = datetime.datetime.now(datetime.timezone.utc)
        query = """
        INSERT INTO fund.team_member_properties (
            member_id, category, subcategory, key, value, active_at, expire_at
        ) VALUES (
            $1, $2, $3, $4, $5, $6, $7
        )
        """
        
        logger.info(f"START _save_team_member_properties for member {team_member_id}")
        logger.info(f"Properties to save: {properties}")
        
        try:
            # Process each property category
            insertion_count = 0
            for input_category, category_props in properties.items():
                logger.info(f"Processing category {input_category}: {category_props}")
                
                if isinstance(category_props, dict):
                    # Process each field in this category
                    for input_field, value in category_props.items():
                        logger.info(f"Processing field {input_field}: {value}")
                        
                        # Skip if value is None or empty
                        if value is None or (isinstance(value, str) and not value.strip()):
                            logger.info(f"Skipping empty field {input_field}")
                            continue
                        
                        # Look up the mapping but don't use member index
                        db_mapping = None
                        try:
                            if input_category in TEAM_MEMBER_MAPPING and input_field in TEAM_MEMBER_MAPPING[input_category]:
                                db_mapping = TEAM_MEMBER_MAPPING[input_category][input_field]
                        except Exception as mapping_error:
                            logger.error(f"Error looking up mapping: {mapping_error}")
                            db_mapping = None
                            
                        logger.info(f"Mapping for {input_category}.{input_field}: {db_mapping}")
                        
                        if db_mapping:
                            category, subcategory, _ = db_mapping
                            
                            # Use descriptive key instead of random UUID
                            key = f"{input_category}.{input_field}"
                            
                            # Convert non-string values to JSON strings
                            if not isinstance(value, str):
                                value = json.dumps(value)
                                logger.info(f"Converted non-string value to JSON: {value}")
                            
                            # Save to database with mapped values
                            logger.info(f"Executing query with: member_id={team_member_id}, category={category}, subcategory={subcategory}, key={key}, value={value}")
                            
                            try:
                                await conn.execute(
                                    query,
                                    team_member_id,
                                    category,
                                    subcategory,
                                    key,
                                    value,
                                    now,
                                    self.future_date
                                )
                                insertion_count += 1
                                logger.info(f"Successfully inserted property {input_category}.{input_field}")
                            except Exception as e:
                                logger.error(f"Error executing insert for property {input_category}.{input_field}: {e}", exc_info=True)
                        else:
                            # Handle unmapped properties - use direct category without index
                            category = input_category
                            subcategory = input_field
                            key = f"{input_category}.{input_field}"  # Descriptive key
                            
                            # Convert non-string values to JSON strings
                            if not isinstance(value, str):
                                value = json.dumps(value)
                                logger.info(f"Converted non-string value to JSON: {value}")
                            
                            logger.info(f"Executing query for unmapped property with: member_id={team_member_id}, category={category}, subcategory={subcategory}, key={key}, value={value}")
                            
                            try:
                                await conn.execute(
                                    query,
                                    team_member_id,
                                    category,
                                    subcategory,
                                    key,
                                    value,
                                    now,
                                    self.future_date
                                )
                                insertion_count += 1
                                logger.info(f"Successfully inserted unmapped property {input_category}.{input_field}")
                            except Exception as e:
                                logger.error(f"Error executing insert for unmapped property {input_category}.{input_field}: {e}", exc_info=True)
                elif isinstance(category_props, (str, int, float, bool)):
                    # Handle case where the category value is a primitive rather than a dict
                    # For example: properties['education'] = 'MIT, Harvard'
                    logger.info(f"Processing primitive value for {input_category}: {category_props}")
                    
                    # Use a simple, direct mapping without index
                    category = input_category
                    subcategory = "value"  # Generic subcategory for primitive values
                    key = input_category  # Descriptive key
                    
                    value = str(category_props)
                    
                    logger.info(f"Executing query for primitive with: member_id={team_member_id}, category={category}, subcategory={subcategory}, key={key}, value={value}")
                    
                    try:
                        await conn.execute(
                            query,
                            team_member_id,
                            category, 
                            subcategory,
                            key,
                            value,
                            now,
                            self.future_date
                        )
                        insertion_count += 1
                        logger.info(f"Successfully inserted primitive property {input_category}")
                    except Exception as e:
                        logger.error(f"Error executing insert for primitive property {input_category}: {e}", exc_info=True)
            
            logger.info(f"END _save_team_member_properties: Inserted {insertion_count} properties")
        
        except Exception as e:
            logger.error(f"Error saving team member properties: {e}", exc_info=True)
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
        
        logger.info(f"Getting fund by user: {user_id}")
        
        fund_query = """
        SELECT DISTINCT ON (fund_id)
            fund_id, 
            user_id, 
            name,
            status,
            extract(epoch from active_at) as active_at
        FROM fund.funds 
        WHERE user_id = $1 AND expire_at > NOW()
        ORDER BY fund_id, active_at DESC
        """
        
        properties_query = """
        SELECT 
            category,
            subcategory,
            key,
            value
        FROM fund.properties
        WHERE fund_id = $1 AND expire_at > NOW()
        """
        
        team_members_query = """
        SELECT DISTINCT ON (team_member_id)
            team_member_id
        FROM fund.team_members
        WHERE fund_id = $1 AND expire_at > NOW()
        ORDER BY team_member_id, active_at DESC
        """
        
        team_member_properties_query = """
        SELECT 
            category,
            subcategory,
            key,
            value
        FROM fund.team_member_properties
        WHERE member_id = $1 AND expire_at > NOW()
        """
        
        start_time = time.time()
        try:
            async with pool.acquire() as conn:
                # Get fund basic data
                fund_row = await conn.fetchrow(fund_query, user_id)
                
                if not fund_row:
                    duration = time.time() - start_time
                    track_db_operation("get_fund_by_user", False, duration)
                    logger.info(f"No fund found for user {user_id}")
                    return None
                
                # Convert to dictionary and ensure all values are JSON serializable
                fund_data = ensure_json_serializable(dict(fund_row))
                logger.info(f"Found fund: {fund_data['fund_id']} for user {user_id}")
                
                # Get fund properties
                property_rows = await conn.fetch(properties_query, fund_data['fund_id'])
                logger.info(f"Found {len(property_rows)} properties for fund {fund_data['fund_id']}")
                
                # Process properties using reverse mapping
                transformed_properties = {}
                
                for row in property_rows:
                    category = row['category']
                    subcategory = row['subcategory']
                    key = row['key']
                    value = row['value']
                    
                    logger.info(f"Processing property: category={category}, subcategory={subcategory}, key={key}, value={value}")
                    
                    # Try to parse JSON values
                    try:
                        if isinstance(value, str) and (value.startswith('{') or value.startswith('[')):
                            value = json.loads(value)
                            logger.info(f"Parsed JSON value: {value}")
                    except (json.JSONDecodeError, AttributeError):
                        logger.info("Value is not valid JSON, keeping as string")
                        pass
                    
                    # Try to map back to original field
                    original_field = get_original_fund_field(category, subcategory, key)
                    logger.info(f"Original field for ({category}, {subcategory}, {key}): {original_field}")
                    
                    if original_field:
                        transformed_properties[original_field] = value
                        logger.info(f"Mapped to original field: {original_field}")
                    else:
                        # For unmapped fields, use a descriptive key
                        if subcategory:
                            field_name = f"{category}_{subcategory}"
                        else:
                            field_name = category
                        transformed_properties[field_name] = value
                        logger.info(f"Using generated field name: {field_name}")
                
                # Add transformed properties to fund data
                logger.info(f"Adding transformed properties to fund data: {transformed_properties}")
                fund_data.update(transformed_properties)
                
                # Get team members
                team_member_rows = await conn.fetch(team_members_query, fund_data['fund_id'])
                logger.info(f"Found {len(team_member_rows)} team members for fund {fund_data['fund_id']}")
                team_members_data = {}  # Will store team members by index
                
                # Process each team member
                for team_row in team_member_rows:
                    team_member_id = ensure_json_serializable(team_row['team_member_id'])
                    logger.info(f"Processing team member: {team_member_id}")
                    
                    # Get team member properties
                    member_property_rows = await conn.fetch(
                        team_member_properties_query, 
                        team_row['team_member_id']
                    )
                    logger.info(f"Found {len(member_property_rows)} properties for team member {team_member_id}")
                    
                    # Process team member properties
                    member_data = {'id': team_member_id, 'team_member_id': team_member_id}
                    member_index = None
                    
                    # First pass: Look for properties that tell us the member index
                    for row in member_property_rows:
                        category = row['category']
                        if '_' in category:
                            parts = category.split('_')
                            if len(parts) >= 2 and parts[-1].isdigit():
                                current_index = int(parts[-1]) - 1
                                logger.info(f"Extracted member index from category: {current_index}")
                                if member_index is None:
                                    member_index = current_index
                    
                    # Second pass: Process all properties into the right structure
                    for row in member_property_rows:
                        category = row['category']
                        subcategory = row['subcategory']
                        key = row['key']
                        value = row['value']
                        
                        logger.info(f"Processing member property: category={category}, subcategory={subcategory}, key={key}, value={value}")
                        
                        # Try to parse JSON values
                        try:
                            if isinstance(value, str) and (value.startswith('{') or value.startswith('[')):
                                value = json.loads(value)
                                logger.info(f"Parsed JSON value: {value}")
                        except (json.JSONDecodeError, AttributeError):
                            logger.info("Value is not valid JSON, keeping as string")
                            pass
                        
                        # Try extracting from key if it's in format "category.field"
                        if key and '.' in key:
                            # This is our descriptive key format from the save method 
                            key_parts = key.split('.')
                            if len(key_parts) == 2:
                                input_category, input_field = key_parts[0], key_parts[1]
                                logger.info(f"Extracted from key: {input_category}.{input_field}")
                                
                                # Initialize the category dict if needed
                                if input_category not in member_data:
                                    member_data[input_category] = {}
                                
                                # Set the value
                                member_data[input_category][input_field] = value
                                logger.info(f"Set value using key parts: {input_category}.{input_field}")
                                continue
                        
                        # Try to map back to original fields
                        original = get_original_team_member_field(category, subcategory, key)
                        logger.info(f"Original info for ({category}, {subcategory}, {key}): {original}")
                        
                        if original[0] is not None:
                            input_category, input_field, _ = original
                            logger.info(f"Mapped to original fields: {input_category}.{input_field}")
                            
                            # Initialize the category dict if needed
                            if input_category not in member_data:
                                member_data[input_category] = {}
                            
                            # Set the value
                            member_data[input_category][input_field] = value
                        else:
                            # For unmapped properties
                            logger.info(f"No mapping found, using direct fields")
                            
                            # Always create a flattened property name to avoid nesting issues
                            if subcategory:
                                field_name = f"{category}_{subcategory}"
                            else:
                                field_name = category
                                
                            member_data[field_name] = value
                            logger.info(f"Added flattened field: {field_name}")
                    
                    # Store member with index
                    if member_index is not None:
                        logger.info(f"Storing team member with index {member_index}")
                        team_members_data[member_index] = member_data
                    else:
                        # Fallback if no index found
                        fallback_index = len(team_members_data)
                        logger.info(f"No index found, using fallback index {fallback_index}")
                        team_members_data[fallback_index] = member_data
                
                # Sort team members by index and replace the original list
                sorted_indices = sorted(team_members_data.keys())
                logger.info(f"Sorted member indices: {sorted_indices}")
                sorted_members = [team_members_data[idx] for idx in sorted_indices]
                fund_data['team_members'] = sorted_members
                
                logger.info(f"Final team members count: {len(sorted_members)}")
                
                duration = time.time() - start_time
                track_db_operation("get_fund_by_user", True, duration)
                
                # Final check to ensure all is JSON serializable
                result = ensure_json_serializable(fund_data)
                logger.info(f"Returning fund data with keys: {list(result.keys())}")
                return result
                
        except Exception as e:
            duration = time.time() - start_time
            track_db_operation("get_fund_by_user", False, duration)
            logger.error(f"Error getting fund by user: {e}", exc_info=True)
            return None        

    async def update_fund(self, fund_id: str, user_id: str, update_data: Dict[str, Any]) -> bool:
        """
        Update a fund using temporal data pattern
        
        Args:
            fund_id: Fund ID to update
            user_id: User ID to validate ownership
            update_data: Dictionary with fields to update
            
        Returns:
            True if successful, False otherwise
        """
        logger.info(f"Updating fund {fund_id} for user {user_id}")
        logger.info(f"Update data received: {update_data}")
        
        pool = await self.db_pool.get_pool()
        now = datetime.datetime.now(datetime.timezone.utc)
        
        # We'll handle properties separately
        properties = update_data.pop('properties', None)
        team_members = update_data.pop('team_members', None)
        
        logger.info(f"Properties to update: {properties}")
        logger.info(f"Team members to update: {team_members}")
        
        try:
            async with pool.acquire() as conn:
                async with conn.transaction():
                    # Update fund entity if basic fields changed
                    if update_data:
                        # Fetch current fund data
                        current_fund = await conn.fetchrow(
                            """
                            SELECT * FROM fund.funds
                            WHERE fund_id = $1 AND user_id = $2 AND expire_at > NOW()
                            ORDER BY active_at DESC LIMIT 1
                            """,
                            fund_id, user_id
                        )
                        
                        if not current_fund:
                            logger.error(f"Fund {fund_id} not found or does not belong to user {user_id}")
                            return False
                        
                        # Expire current fund record
                        expire_result = await conn.execute(
                            """
                            UPDATE fund.funds
                            SET expire_at = $1
                            WHERE fund_id = $2 AND user_id = $3 AND expire_at > NOW()
                            """,
                            now, fund_id, user_id
                        )
                        
                        logger.info(f"Expired fund record, result: {expire_result}")
                        
                        # Create new record with updated values
                        new_record = dict(current_fund)
                        
                        # Apply updates
                        for field, value in update_data.items():
                            if field not in ['fund_id', 'user_id', 'active_at', 'expire_at']:
                                new_record[field] = value
                        
                        # Set new timestamps
                        new_record['active_at'] = now
                        new_record['expire_at'] = self.future_date
                        
                        # Dynamically build insert query
                        columns = list(new_record.keys())
                        placeholders = [f'${i+1}' for i in range(len(columns))]
                        values = [new_record[col] for col in columns]
                        
                        insert_query = f"""
                        INSERT INTO fund.funds ({', '.join(columns)})
                        VALUES ({', '.join(placeholders)})
                        """
                        
                        logger.info(f"Inserting new fund record with fields: {columns}")
                        insert_result = await conn.execute(insert_query, *values)
                        logger.info(f"Inserted new fund record, result: {insert_result}")
                    
                    # Update properties if provided
                    if properties:
                        logger.info(f"Updating fund properties: {properties}")
                        
                        # Expire all current properties
                        expire_result = await conn.execute(
                            """
                            UPDATE fund.properties
                            SET expire_at = $1
                            WHERE fund_id = $2 AND expire_at > NOW()
                            """,
                            now, fund_id
                        )
                        
                        logger.info(f"Expired existing properties, result: {expire_result}")
                        
                        # Save new properties
                        property_count = await self._save_fund_properties(conn, fund_id, properties)
                        logger.info(f"Saved {property_count} new properties")
                    
                    # Update team members if provided
                    if team_members:
                        logger.info(f"Processing {len(team_members)} team members")
                        
                        # Process each team member with its index
                        for i, team_member in enumerate(team_members):
                            logger.info(f"Processing team member #{i}: {team_member}")
                            
                            # Get team member ID
                            member_id = team_member.get('id')
                            if not member_id:
                                logger.warning(f"Team member has no ID, skipping")
                                continue
                            
                            # Verify the team member belongs to this fund
                            member_exists = await conn.fetchval(
                                """
                                SELECT 1 FROM fund.team_members
                                WHERE team_member_id = $1 AND fund_id = $2 AND expire_at > NOW()
                                """,
                                member_id, fund_id
                            )
                            
                            if not member_exists:
                                logger.warning(f"Team member {member_id} does not belong to fund {fund_id}, skipping")
                                continue
                            
                            # Update this team member with its index
                            await self._update_team_member(conn, member_id, team_member, i)
                
                logger.info(f"Fund update completed with result: True")
                return True
        except Exception as e:
            logger.error(f"Error updating fund {fund_id}: {e}", exc_info=True)
            return False

    async def _update_team_member(self, conn, member_id: str, team_member: Dict[str, Any], member_index: int) -> None:
        """
        Update a team member's properties with correct ordering
        
        Args:
            conn: Database connection
            member_id: Team member ID
            team_member: Team member data
            member_index: The index of this team member (0-based)
        """
        now = datetime.datetime.now(datetime.timezone.utc)
        
        logger.info(f"Updating team member {member_id} with index {member_index}")
        logger.info(f"Team member data: {team_member}")
        
        # Expire all current properties for this member
        current_props = await conn.fetch(
            """
            SELECT property_id
            FROM fund.team_member_properties
            WHERE member_id = $1 AND expire_at > NOW()
            """,
            member_id
        )
        
        if current_props:
            prop_ids = [p['property_id'] for p in current_props]
            logger.info(f"Expiring {len(prop_ids)} existing properties for team member {member_id}")
            
            await conn.execute(
                """
                UPDATE fund.team_member_properties
                SET expire_at = $1
                WHERE property_id = ANY($2)
                """,
                now, prop_ids
            )
            logger.info(f"Expired {len(prop_ids)} properties for team member {member_id}")
        else:
            logger.info(f"No existing properties found for team member {member_id}")
        
        # Save new properties with correct index
        logger.info(f"Saving new properties for team member {member_id}")
        await self._save_team_member_properties(conn, member_id, team_member, member_index)
    
    async def check_fund_exists(self, user_id: str) -> bool:
        """
        Check if a fund exists for a user
        
        Args:
            user_id: User ID
            
        Returns:
            True if fund exists, False otherwise
        """
        pool = await self.db_pool.get_pool()
        
        logger.info(f"Checking if fund exists for user {user_id}")
        
        query = """
        SELECT 1 FROM fund.funds 
        WHERE user_id = $1 AND expire_at > NOW()
        LIMIT 1
        """
        
        try:
            async with pool.acquire() as conn:
                result = await conn.fetchval(query, user_id)
                exists = result is not None
                logger.info(f"Fund exists for user {user_id}: {exists}")
                return exists
        except Exception as e:
            logger.error(f"Error checking fund existence for user {user_id}: {e}", exc_info=True)
            return False
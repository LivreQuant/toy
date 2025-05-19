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
        now = datetime.datetime.now(datetime.timezone.utc)
        
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
                        logger.info(f"Saving fund properties")
                        await self._save_fund_properties(conn, fund_id, properties)
                    
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
                        
                        # Save team member properties
                        logger.info(f"Saving team member properties")
                        await self._save_team_member_properties(conn, team_member_id, team_member_data)
                    
                    return {"fund_id": fund_id, "success": True}
                    
        except Exception as e:
            logger.error(f"Error creating fund with details: {e}")
            return {"success": False, "error": str(e)}


    async def _save_fund_properties(self, conn, fund_id: str, properties: Dict[str, Dict[str, Any]]) -> bool:
        """
        Save fund properties using the temporal EAV model
        
        Args:
            conn: Database connection
            fund_id: Fund ID
            properties: Properties structure {category: {subcategory: {key: value}}}
            
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
        
        try:
            for category, subcategories in properties.items():
                for subcategory, items in subcategories.items():
                    for _, value in items.items():
                        # Generate a random UUID for the key field
                        random_key = str(uuid.uuid4())
                        
                        # Convert non-string values to JSON strings
                        if not isinstance(value, str):
                            value = json.dumps(value)
                            
                        await conn.execute(
                            query,
                            fund_id,
                            category,
                            subcategory,
                            random_key,  # Use the generated UUID as the key
                            value,
                            now,
                            self.future_date
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
        now = datetime.datetime.now(datetime.timezone.utc)
        query = """
        INSERT INTO fund.team_member_properties (
            member_id, category, subcategory, key, value, active_at, expire_at
        ) VALUES (
            $1, $2, $3, $4, $5, $6, $7
        )
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
                            
                            # Generate random UUID for key
                            random_key = str(uuid.uuid4())
                            
                            # Convert non-string values to JSON strings
                            if not isinstance(sub_value, str):
                                sub_value = json.dumps(sub_value)
                            
                            logger.info(f"Save team member properties: executing query with values: {team_member_id}, {category}, {key}, {random_key}, {sub_value}")
                            
                            await conn.execute(
                                query,
                                team_member_id,
                                category,
                                key,  # Use the original key as subcategory
                                random_key,  # Use random UUID as key
                                sub_value,
                                now,
                                self.future_date
                            )
                    else:
                        # For the subcategory, use the key and set subcategory to "info"
                        subcategory = "info"
                        
                        # Generate random UUID for key
                        random_key = str(uuid.uuid4())
                        
                        # Convert non-string values to JSON strings
                        if not isinstance(value, str):
                            value = json.dumps(value)
                        
                        logger.info(f"Save team member properties: executing query with values: {team_member_id}, {category}, {subcategory}, {random_key}, {value}")
                        
                        await conn.execute(
                            query,
                            team_member_id,
                            category,
                            subcategory,
                            random_key,  # Use random UUID as key
                            value,
                            now,
                            self.future_date
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
        
        logger.info(f"[DEBUG] Getting fund by user: {user_id}")
        
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
            logger.info("[DEBUG] Starting database operations")
            async with pool.acquire() as conn:
                # Get fund basic data
                logger.info("[DEBUG] Executing fund query")
                fund_row = await conn.fetchrow(fund_query, user_id)
                
                if not fund_row:
                    duration = time.time() - start_time
                    track_db_operation("get_fund_by_user", False, duration)
                    logger.info(f"[DEBUG] No fund found for user {user_id}")
                    return None
                
                # Convert to dictionary
                fund_data = ensure_json_serializable(dict(fund_row))
                logger.info(f"[DEBUG] Found fund: {fund_data['fund_id']} for user {user_id}")
                
                # Get fund properties
                logger.info("[DEBUG] Executing properties query")
                property_rows = await conn.fetch(properties_query, fund_data['fund_id'])
                logger.info(f"[DEBUG] Retrieved {len(property_rows)} property rows for fund {fund_data['fund_id']}")
                
                # EXTREME DEBUGGING: Log every single property in full detail
                for i, row in enumerate(property_rows):
                    category = row['category']
                    subcategory = row['subcategory']
                    key = row['key']
                    value = row['value']
                    logger.info(f"[DEBUG] PROPERTY {i}: category='{category}', subcategory='{subcategory}', key='{key}', value='{value}', type={type(value).__name__}")
                    
                    # Try to parse as JSON for debugging
                    if isinstance(value, str):
                        try:
                            if value.startswith('{') or value.startswith('['):
                                parsed = json.loads(value)
                                logger.info(f"[DEBUG]   PARSED JSON: type={type(parsed).__name__}, value={parsed}")
                        except Exception as e:
                            logger.info(f"[DEBUG]   NOT JSON: {e}")
                
                # Define property mappings
                logger.info("[DEBUG] Defining property mappings")
                property_mappings = {
                    'profile': {
                        'legalStructure': 'legalStructure',
                        'location': 'location',
                        'yearEstablished': 'yearEstablished',
                        'aumRange': 'aumRange',
                        'purpose': 'profilePurpose',
                        'otherDetails': 'otherPurposeDetails'
                    },
                    'strategy': {
                        'thesis': 'investmentStrategy'
                    }
                }
                
                # Build property mapping table - with extreme caution and logging
                logger.info(f"[DEBUG] Building property mapping table for fund {fund_data['fund_id']}")
                
                # Initialize an empty mapping table
                property_mapping_table = {}
                
                # Process each property row one by one with detailed logging
                for i, row in enumerate(property_rows):
                    category = row['category']
                    subcategory = row['subcategory']
                    raw_value = row['value']
                    
                    # Keep the original value as a string for dictionary keys
                    value_str = str(raw_value)
                    
                    logger.info(f"[DEBUG] MAPPING ROW {i}: category='{category}', subcategory='{subcategory}', raw_value='{raw_value}', type={type(raw_value).__name__}")
                    
                    # Try to parse JSON - with thorough error handling
                    value = raw_value  # Default to raw value
                    try:
                        if isinstance(raw_value, str) and (raw_value.startswith('{') or raw_value.startswith('[')):
                            logger.info(f"[DEBUG]   Attempting to parse as JSON: '{raw_value}'")
                            parsed_value = json.loads(raw_value)
                            logger.info(f"[DEBUG]   Successfully parsed as JSON: {type(parsed_value).__name__} = {parsed_value}")
                            value = parsed_value
                    except Exception as e:
                        logger.info(f"[DEBUG]   Failed to parse as JSON: {str(e)}")
                    
                    # Super safe mapping logic with individual try/except for each check
                    try:
                        # Default mapping key
                        mapped_key = None
                        
                        logger.info(f"[DEBUG]   MAPPING LOGIC for category='{category}', subcategory='{subcategory}'")
                        
                        if category == 'general':
                            if subcategory == 'profile':
                                # Use explicit pre-check for string operations
                                logger.info(f"[DEBUG]     Checking profile mapping for value type: {type(value).__name__}")
                                
                                # Check 1: Legal structure values (only for string values)
                                try:
                                    if isinstance(value, str) and value in ["Personal Account", "LLC", "Limited Partnership", "Corporation"]:
                                        mapped_key = 'legalStructure'
                                        logger.info(f"[DEBUG]     MATCHED: Legal structure '{value}'")
                                    else:
                                        logger.info(f"[DEBUG]     NOT MATCHED: Not a legal structure value")
                                except Exception as e:
                                    logger.info(f"[DEBUG]     ERROR in legal structure check: {str(e)}")
                                
                                # Check 2: AUM range check (only for string values with startswith)
                                if not mapped_key:
                                    try:
                                        if isinstance(value, str) and (value.startswith("Under $") or value.startswith("$") or value.startswith("Over $")):
                                            mapped_key = 'aumRange'
                                            logger.info(f"[DEBUG]     MATCHED: AUM range '{value}'")
                                        else:
                                            logger.info(f"[DEBUG]     NOT MATCHED: Not an AUM range value")
                                    except Exception as e:
                                        logger.info(f"[DEBUG]     ERROR in AUM range check: {str(e)}")
                                
                                # Check 3: Year established (only for string values with isdigit)
                                if not mapped_key:
                                    try:
                                        if isinstance(value, str) and (value.isdigit() or (len(value) == 4 and value.isdigit())):
                                            mapped_key = 'yearEstablished'
                                            logger.info(f"[DEBUG]     MATCHED: Year established '{value}'")
                                        else:
                                            logger.info(f"[DEBUG]     NOT MATCHED: Not a year established value")
                                    except Exception as e:
                                        logger.info(f"[DEBUG]     ERROR in year established check: {str(e)}")
                                
                                # Check 4: Profile purpose (for specific values and lists)
                                if not mapped_key:
                                    try:
                                        if value in ["raise_capital", "manage_investments", "other"] or isinstance(value, list):
                                            mapped_key = 'profilePurpose'
                                            logger.info(f"[DEBUG]     MATCHED: Profile purpose value or list")
                                        else:
                                            logger.info(f"[DEBUG]     NOT MATCHED: Not a profile purpose value")
                                    except Exception as e:
                                        logger.info(f"[DEBUG]     ERROR in profile purpose check: {str(e)}")
                                
                                # Check 5: Other purpose details (strings with specific patterns)
                                if not mapped_key:
                                    try:
                                        if isinstance(value, str) and (value.startswith("To be ") or len(value.split()) > 3):
                                            mapped_key = 'otherPurposeDetails'
                                            logger.info(f"[DEBUG]     MATCHED: Other purpose details '{value}'")
                                        else:
                                            logger.info(f"[DEBUG]     NOT MATCHED: Not other purpose details")
                                    except Exception as e:
                                        logger.info(f"[DEBUG]     ERROR in other purpose details check: {str(e)}")
                                
                                # Default fallback for profile: location
                                if not mapped_key:
                                    mapped_key = 'location'
                                    logger.info(f"[DEBUG]     DEFAULT MAPPING: Using location as fallback")
                                
                            elif subcategory == 'strategy':
                                # Strategy mapping is simpler
                                mapped_key = 'investmentStrategy'
                                logger.info(f"[DEBUG]     MAPPED strategy to investmentStrategy")
                        
                        # Store the mapping using the string representation as the key
                        if mapped_key:
                            property_mapping_table[(category, subcategory, value_str)] = mapped_key
                            logger.info(f"[DEBUG]   FINAL MAPPING: ({category}, {subcategory}, {value_str}) -> {mapped_key}")
                        else:
                            # Fallback
                            random_key = str(uuid.uuid4())[0:8]
                            property_mapping_table[(category, subcategory, value_str)] = random_key
                            logger.info(f"[DEBUG]   NO MAPPING FOUND: Using random key {random_key}")
                    
                    except Exception as e:
                        logger.info(f"[DEBUG]   CRITICAL ERROR in mapping logic: {str(e)}")
                        import traceback
                        logger.info(f"[DEBUG]   TRACEBACK: {traceback.format_exc()}")
                        # Use a safe fallback
                        property_mapping_table[(category, subcategory, value_str)] = f"error_{str(uuid.uuid4())[0:8]}"
                
                logger.info(f"[DEBUG] Property mapping table created with {len(property_mapping_table)} entries")
                
                # Use the mapping table to build the response
                logger.info("[DEBUG] Building properties structure for response")
                properties = {}
                
                for i, row in enumerate(property_rows):
                    category = row['category']
                    subcategory = row['subcategory']
                    raw_value = row['value']
                    
                    logger.info(f"[DEBUG] RESPONSE ROW {i}: category='{category}', subcategory='{subcategory}', raw_value='{raw_value}'")
                    
                    # Try to parse JSON for the response
                    value = raw_value  # Default to raw value
                    try:
                        if isinstance(raw_value, str) and (raw_value.startswith('{') or raw_value.startswith('[')):
                            parsed_value = json.loads(raw_value)
                            logger.info(f"[DEBUG]   Parsed for response: {type(parsed_value).__name__} = {parsed_value}")
                            value = parsed_value
                    except Exception as e:
                        logger.info(f"[DEBUG]   Failed to parse for response: {str(e)}")
                    
                    # Create nested structure
                    if category not in properties:
                        properties[category] = {}
                        logger.info(f"[DEBUG]   Created category: {category}")
                    
                    if subcategory not in properties[category]:
                        properties[category][subcategory] = {}
                        logger.info(f"[DEBUG]   Created subcategory: {subcategory} in {category}")
                    
                    # Look up the mapping using string representation
                    value_str = str(raw_value)  # Always use string for lookup
                    key_tuple = (category, subcategory, value_str)
                    
                    logger.info(f"[DEBUG]   Looking up mapping for key: {key_tuple}")
                    
                    if key_tuple in property_mapping_table:
                        meaningful_key = property_mapping_table[key_tuple]
                        logger.info(f"[DEBUG]   Found mapping: {meaningful_key}")
                    else:
                        # Fallback to a random key if mapping not found
                        meaningful_key = str(uuid.uuid4())[0:8]
                        logger.info(f"[DEBUG]   No mapping found, using random key: {meaningful_key}")
                    
                    # Store the value with its key
                    properties[category][subcategory][meaningful_key] = value
                    logger.info(f"[DEBUG]   Stored value at {category}.{subcategory}.{meaningful_key}")
                
                # Add properties to fund data
                fund_data['properties'] = properties
                
                # Get team members
                logger.info("[DEBUG] Getting team members")
                team_member_rows = await conn.fetch(team_members_query, fund_data['fund_id'])
                team_members = []
                
                # Process each team member
                for tm_idx, team_row in enumerate(team_member_rows):
                    team_member_id = team_row['team_member_id']
                    logger.info(f"[DEBUG] Processing team member {tm_idx}: {team_member_id}")
                    
                    # Get team member properties
                    member_property_rows = await conn.fetch(
                        team_member_properties_query, 
                        team_member_id
                    )
                    logger.info(f"[DEBUG]   Found {len(member_property_rows)} properties for team member")
                    
                    # Process team member properties
                    member_properties = {}
                    for prop_idx, row in enumerate(member_property_rows):
                        category = row['category']
                        subcategory = row['subcategory']
                        raw_value = row['value']
                        
                        logger.info(f"[DEBUG]   TM PROPERTY {prop_idx}: category='{category}', subcategory='{subcategory}', value='{raw_value}'")
                        
                        # Try to parse JSON
                        value = raw_value
                        try:
                            if isinstance(raw_value, str) and (raw_value.startswith('{') or raw_value.startswith('[')):
                                value = json.loads(raw_value)
                                logger.info(f"[DEBUG]     Parsed TM property as JSON: {type(value).__name__}")
                        except Exception as e:
                            logger.info(f"[DEBUG]     Failed to parse TM property as JSON: {str(e)}")
                        
                        # Create nested structure
                        if category not in member_properties:
                            member_properties[category] = {}
                        if subcategory not in member_properties[category]:
                            member_properties[category][subcategory] = {}
                        
                        # Determine meaningful key with extreme caution
                        try:
                            meaningful_key = None
                            
                            # Safe key determination
                            if category == 'personal' and subcategory == 'info':
                                # Be extremely careful with type checking for string operations
                                if isinstance(value, str):
                                    if '-' in value and len(value) == 10:
                                        meaningful_key = 'birthDate'
                                    elif len(value.split()) <= 2:
                                        meaningful_key = 'firstName' if 'lastName' not in member_properties.get(category, {}).get(subcategory, {}) else 'lastName'
                            elif category == 'professional' and subcategory == 'info':
                                if isinstance(value, str):
                                    if value in ['Portfolio Manager', 'Analyst', 'Trader']:
                                        meaningful_key = 'role'
                                    elif value.isdigit() or value in ['1', '2', '3', '4', '5']:
                                        meaningful_key = 'yearsExperience'
                                    elif value.startswith('http'):
                                        meaningful_key = 'linkedin'
                                    else:
                                        meaningful_key = 'investmentExpertise'
                            elif category == 'education':
                                meaningful_key = 'institution'
                            
                            # Fallback to random key if not determined
                            if not meaningful_key:
                                meaningful_key = str(uuid.uuid4())[0:8]
                                
                            # Store the value
                            member_properties[category][subcategory][meaningful_key] = value
                            logger.info(f"[DEBUG]     Stored TM property with key: {meaningful_key}")
                            
                        except Exception as e:
                            logger.info(f"[DEBUG]     ERROR processing TM property: {str(e)}")
                            # Fallback - use a random key
                            random_key = str(uuid.uuid4())[0:8]
                            member_properties[category][subcategory][random_key] = value
                    
                    # Add team member to results
                    team_members.append({
                        "id": team_member_id,
                        "team_member_id": str(team_member_id),
                        "properties": member_properties
                    })
                    logger.info(f"[DEBUG]   Added team member to results")
                
                # Add team members to fund data
                fund_data['team_members'] = team_members
                logger.info(f"[DEBUG] Added {len(team_members)} team members to fund data")
                
                duration = time.time() - start_time
                track_db_operation("get_fund_by_user", True, duration)
                
                logger.info("[DEBUG] Returning complete fund data")
                return fund_data
                
        except Exception as e:
            duration = time.time() - start_time
            track_db_operation("get_fund_by_user", False, duration)
            logger.error(f"[DEBUG] CRITICAL ERROR: {str(e)}")
            import traceback
            logger.error(f"[DEBUG] TRACEBACK: {traceback.format_exc()}")
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
        logger.info(f"Repository: updating fund {fund_id} for user {user_id}")
        logger.info(f"Repository: update data received: {update_data}")
        
        pool = await self.db_pool.get_pool()
        now = datetime.datetime.now(datetime.timezone.utc)
        
        # We'll handle properties separately
        properties = update_data.pop('properties', None)
        team_members = update_data.pop('team_members', None)
        
        logger.info(f"Repository: properties to update: {properties}")
        logger.info(f"Repository: team members to update: {team_members}")
        
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
                        
                        logger.info(f"Repository: expired fund record, result: {expire_result}")
                        
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
                        
                        insert_result = await conn.execute(insert_query, *values)
                        logger.info(f"Repository: inserted new fund record, result: {insert_result}")
                    
                    # Update properties if provided
                    if properties:
                        logger.info(f"Repository: updating fund properties")
                        
                        # Fetch current properties
                        current_props = await conn.fetch(
                            """
                            SELECT property_id, category, subcategory, value
                            FROM fund.properties
                            WHERE fund_id = $1 AND expire_at > NOW()
                            """,
                            fund_id
                        )
                        
                        # Build map of current properties
                        current_prop_map = {}
                        for prop in current_props:
                            key = (prop['category'], prop['subcategory'])
                            if key not in current_prop_map:
                                current_prop_map[key] = []
                            current_prop_map[key].append({
                                'property_id': prop['property_id'],
                                'value': prop['value']
                            })
                        
                        # Track properties to expire
                        props_to_expire = []
                        
                        # Identify properties to expire and values that have changed
                        for category, subcategories in properties.items():
                            for subcategory, items in subcategories.items():
                                key = (category, subcategory)
                                
                                # If this category/subcategory exists, expire all values
                                # as we'll create new ones
                                if key in current_prop_map:
                                    for prop_info in current_prop_map[key]:
                                        props_to_expire.append(prop_info['property_id'])
                        
                        # Expire outdated properties
                        if props_to_expire:
                            logger.info(f"Repository: expiring {len(props_to_expire)} properties")
                            expire_result = await conn.execute(
                                """
                                UPDATE fund.properties
                                SET expire_at = $1
                                WHERE property_id = ANY($2)
                                """,
                                now, props_to_expire
                            )
                            logger.info(f"Repository: expire properties result: {expire_result}")
                        
                        # Create new property records
                        for category, subcategories in properties.items():
                            for subcategory, items in subcategories.items():
                                for _, value in items.items():
                                    # Generate random UUID for key
                                    random_key = str(uuid.uuid4())
                                    
                                    # Convert non-string values to JSON
                                    if not isinstance(value, str):
                                        value = json.dumps(value)
                                    
                                    await conn.execute(
                                        """
                                        INSERT INTO fund.properties (
                                            fund_id, category, subcategory, key, value, active_at, expire_at
                                        ) VALUES (
                                            $1, $2, $3, $4, $5, $6, $7
                                        )
                                        """,
                                        fund_id, category, subcategory, random_key, value, now, self.future_date
                                    )
                    
                    # Update team members if provided
                    if team_members:
                        logger.info(f"Repository: processing {len(team_members)} team members")
                        
                        for team_member in team_members:
                            # Get team member ID
                            member_id = team_member.get('id')
                            if not member_id:
                                logger.warning(f"Repository: team member has no ID, skipping")
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
                                logger.warning(f"Repository: team member {member_id} does not belong to fund {fund_id}, skipping")
                                continue
                            
                            # Process updates for this team member
                            for category in ['personal', 'professional', 'education']:
                                if category in team_member:
                                    category_data = team_member[category]
                                    logger.info(f"Repository: updating {category} info for team member {member_id}")
                                    
                                    # Fetch current properties for this category
                                    current_props = await conn.fetch(
                                        """
                                        SELECT property_id, subcategory, value
                                        FROM fund.team_member_properties
                                        WHERE member_id = $1 AND category = $2 AND expire_at > NOW()
                                        """,
                                        member_id, category
                                    )
                                    
                                    # Expire all current properties for this category
                                    if current_props:
                                        prop_ids = [p['property_id'] for p in current_props]
                                        await conn.execute(
                                            """
                                            UPDATE fund.team_member_properties
                                            SET expire_at = $1
                                            WHERE property_id = ANY($2)
                                            """,
                                            now, prop_ids
                                        )
                                    
                                    # Insert new properties
                                    if isinstance(category_data, dict):
                                        for key, value in category_data.items():
                                            # Generate random UUID for key
                                            random_key = str(uuid.uuid4())
                                            
                                            # Convert non-string values to JSON
                                            if not isinstance(value, str):
                                                value = json.dumps(value)
                                            
                                            await conn.execute(
                                                """
                                                INSERT INTO fund.team_member_properties (
                                                    member_id, category, subcategory, key, value, active_at, expire_at
                                                ) VALUES (
                                                    $1, $2, $3, $4, $5, $6, $7
                                                )
                                                """,
                                                member_id, category, 'info', random_key, value, now, self.future_date
                                            )
                
                logger.info(f"Repository: fund update completed with result: True")
                return True
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
        SELECT 1 FROM fund.funds 
        WHERE user_id = $1 AND expire_at > NOW()
        LIMIT 1
        """
        
        try:
            async with pool.acquire() as conn:
                result = await conn.fetchval(query, user_id)
                return result is not None
        except Exception as e:
            logger.error(f"Error checking fund existence for user {user_id}: {e}")
            return False
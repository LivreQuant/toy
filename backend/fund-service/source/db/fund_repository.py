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
        
        # Update this query to also retrieve the key column
        properties_query = """
        SELECT 
            category,
            subcategory,
            key,  # Added key to the query
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
        
        # Update this query to also retrieve the key column
        team_member_properties_query = """
        SELECT 
            category,
            subcategory,
            key,  # Added key to the query
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
                    return None
                
                # Convert to dictionary
                fund_data = ensure_json_serializable(dict(fund_row))
                
                # Get fund properties
                property_rows = await conn.fetch(properties_query, fund_data['fund_id'])
                
                # Define property mappings (subcategory names to keys)
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
                
                # Build a special mapping table to know what key to use for each property
                # This will help us identify specific properties
                property_mapping_table = {}
                for row in property_rows:
                    category = row['category']
                    subcategory = row['subcategory']
                    value = row['value']
                    
                    # Try to determine a meaningful key based on the value's content
                    # This is a simple heuristic approach - adjust as needed
                    if category == 'general':
                        if subcategory == 'profile':
                            if value in ["Personal Account", "LLC", "Limited Partnership", "Corporation"]:
                                property_mapping_table[(category, subcategory, value)] = 'legalStructure'
                            elif value.startswith(("Under $", "$", "Over $")):
                                property_mapping_table[(category, subcategory, value)] = 'aumRange'
                            elif value.isdigit() or (len(value) == 4 and value.isdigit()):
                                property_mapping_table[(category, subcategory, value)] = 'yearEstablished'
                            elif value in ["raise_capital", "manage_investments", "other"] or isinstance(value, list):
                                property_mapping_table[(category, subcategory, value)] = 'profilePurpose'
                            elif value.startswith("To be ") or len(value.split()) > 3:
                                property_mapping_table[(category, subcategory, value)] = 'otherPurposeDetails'
                            else:
                                property_mapping_table[(category, subcategory, value)] = 'location'
                        elif subcategory == 'strategy':
                            property_mapping_table[(category, subcategory, value)] = 'investmentStrategy'
                
                # Use the mapping table to build a more meaningful response
                properties = {}
                for row in property_rows:
                    category = row['category']
                    subcategory = row['subcategory']
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
                    
                    # Look up a meaningful key from our mapping table
                    key_tuple = (category, subcategory, value)
                    meaningful_key = property_mapping_table.get(key_tuple)
                    if not meaningful_key:
                        # If no mapping, use a short uuid
                        meaningful_key = str(uuid.uuid4())[0:8]
                    
                    # Use the meaningful key
                    properties[category][subcategory][meaningful_key] = value
                
                # Add properties to fund data
                fund_data['properties'] = properties
                
                # Get team members
                team_member_rows = await conn.fetch(team_members_query, fund_data['fund_id'])
                team_members = []
                
                # Define team member property mappings
                tm_property_mappings = {
                    'personal': {'firstName': 'firstName', 'lastName': 'lastName', 'birthDate': 'birthDate'},
                    'professional': {
                        'role': 'role', 
                        'yearsExperience': 'yearsExperience',
                        'currentEmployment': 'currentEmployment',
                        'investmentExpertise': 'investmentExpertise',
                        'linkedin': 'linkedin'
                    },
                    'education': {'institution': 'education'}
                }
                
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
                        
                        # Try to determine a meaningful property name
                        meaningful_key = None
                        
                        # For standard categories
                        if category in tm_property_mappings and subcategory in tm_property_mappings[category]:
                            meaningful_key = tm_property_mappings[category][subcategory]
                        elif category in tm_property_mappings and subcategory == 'info':
                            # Try to match based on content
                            if 'birth' in value or '-' in value and len(value) == 10:
                                meaningful_key = 'birthDate'
                            elif value in ['Portfolio Manager', 'Analyst', 'Trader']:
                                meaningful_key = 'role'
                            elif value.isdigit() or value in ['1', '2', '3', '4', '5']:
                                meaningful_key = 'yearsExperience'
                            elif value.startswith('http'):
                                meaningful_key = 'linkedin'
                            elif len(value.split()) <= 2 and value[0].isupper():
                                # If value is 1-2 words and starts with capital, assume it's a name
                                if category == 'personal':
                                    meaningful_key = 'firstName' if 'lastName' in member_properties.get(category, {}).get(subcategory, {}) else 'lastName'
                                elif category == 'education':
                                    meaningful_key = 'institution'
                                else:
                                    meaningful_key = 'currentEmployment'
                            elif category == 'professional':
                                meaningful_key = 'investmentExpertise'
                        
                        # If no mapping found, use a short UUID
                        if not meaningful_key:
                            meaningful_key = str(uuid.uuid4())[0:8]
                        
                        member_properties[category][subcategory][meaningful_key] = value
                    
                    # Add team member with properties
                    team_members.append({
                        "id": team_member_id,  # Change team_member_id to id to match frontend expectations
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
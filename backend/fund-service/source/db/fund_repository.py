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

    async def create_fund_with_details(self, fund_data: Dict[str, Any],
                                       properties: Dict[str, Any], 
                                       team_members: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Create a fund with its properties and team members
        
        Args:
            fund_data: Fund basic data
            properties: Properties dict
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
                        user_id, fund_id, name, active_at
                    ) VALUES (
                        $1, $2, $3, $4
                    ) RETURNING fund_id
                    """
                    
                    fund_id = await conn.fetchval(
                        fund_query,
                        fund_data['user_id'],
                        fund_data['fund_id'],
                        fund_data['name'],
                        now
                    )
                    
                    # Convert UUID to string
                    if isinstance(fund_id, uuid.UUID):
                        fund_id = str(fund_id)
                    
                    logger.info(f"Fund created with ID: {fund_id}")
                    
                    # 2. Save fund properties
                    if properties:
                        await self._save_fund_properties(conn, fund_id, properties, now)
                    
                    # 3. Create team members
                    for i, team_member in enumerate(team_members):
                        # Create team member
                        team_query = """
                        INSERT INTO fund.team_members (
                            fund_id, active_at, expire_at
                        ) VALUES (
                            $1, $2, $3
                        ) RETURNING team_member_id
                        """
                        
                        team_member_id = await conn.fetchval(
                            team_query,
                            fund_id,
                            now,
                            self.future_date
                        )
                        
                        # Convert UUID to string
                        if isinstance(team_member_id, uuid.UUID):
                            team_member_id = str(team_member_id)
                        
                        # Save team member properties
                        await self._save_team_member_properties(conn, team_member_id, team_member, i, now)
                    
                    return {"fund_id": fund_id, "success": True}
                    
        except Exception as e:
            logger.error(f"Error creating fund with details: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    async def _save_fund_properties(self, conn, fund_id: str, properties: Dict[str, Any], timestamp: datetime.datetime) -> None:
        """
        Save fund properties with direct category/subcategory mapping
        
        Args:
            conn: Database connection
            fund_id: Fund ID
            properties: Properties dictionary
            timestamp: Current timestamp for active_at
        """
        # Property mapping - maps frontend field to DB category/subcategory
        property_mapping = {
            'legalStructure': ('property', 'legalStructure'),
            'location': ('property', 'state_country'),
            'yearEstablished': ('property', 'yearEstablished'),
            'aumRange': ('metadata', 'aumRange'),
            'profilePurpose': ('metadata', 'purpose'),
            'otherPurposeDetails': ('metadata', 'otherDetails'),
            'investmentStrategy': ('metadata', 'thesis')
        }
        
        query = """
        INSERT INTO fund.fund_properties (
            fund_id, category, subcategory, value, active_at, expire_at
        ) VALUES (
            $1, $2, $3, $4, $5, $6
        )
        """
        
        for field, value in properties.items():
            if value is None or (isinstance(value, str) and not value.strip()):
                continue
                
            # Get category/subcategory from mapping
            if field in property_mapping:
                category, subcategory = property_mapping[field]
            
            # Convert non-string values to JSON strings
            if not isinstance(value, str):
                value = json.dumps(value)
            
            # Insert property
            await conn.execute(
                query,
                fund_id,
                category,
                subcategory,
                value,
                timestamp,
                self.future_date
            )

    async def _save_team_member_properties(self, conn, team_member_id: str, 
                                          team_member: Dict[str, Any], 
                                          member_index: int,
                                          timestamp: datetime.datetime) -> None:
        """
        Save team member properties with direct field mapping
        
        Args:
            conn: Database connection
            team_member_id: Team member ID
            team_member: Team member properties dict
            member_index: Index for ordering
            timestamp: Current timestamp for active_at
        """
        # Property mapping - maps frontend fields to DB category/subcategory
        property_mapping = {
            'order': ('personal', 'order'),
            'firstName': ('personal', 'firstName'),
            'lastName': ('personal', 'lastName'),
            'birthDate': ('personal', 'birthDate'),
            'role': ('professional', 'role'),
            'yearsExperience': ('professional', 'yearsExperience'),
            'currentEmployment': ('professional', 'currentEmployment'),
            'investmentExpertise': ('professional', 'investmentExpertise'),
            'linkedin': ('social', 'linkedin'),
            'education': ('education', 'education')
        }
        
        query = """
        INSERT INTO fund.team_member_properties (
            member_id, category, subcategory, value, active_at, expire_at
        ) VALUES (
            $1, $2, $3, $4, $5, $6
        )
        """
                
        # Save each property
        for field, value in team_member.items():
            logger.info(f"Processing field '{field}' with value '{value}'")

            if value is None or (isinstance(value, str) and not value.strip()):
                continue
                
            # Get category/subcategory from mapping
            if field in property_mapping:
                category, subcategory = property_mapping[field]
            
            # Convert non-string values to JSON strings
            if not isinstance(value, str):
                value = json.dumps(value)
            
            # Insert property
            await conn.execute(
                query,
                team_member_id,
                category,
                subcategory,
                value,
                timestamp,
                self.future_date
            )

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
            extract(epoch from active_at) as active_at
        FROM fund.funds 
        WHERE user_id = $1
        ORDER BY fund_id, active_at DESC
        """
        
        properties_query = """
        SELECT 
            category,
            subcategory,
            value
        FROM fund.fund_properties
        WHERE fund_id = $1 AND expire_at > NOW()
        """
        
        team_members_query = """
        SELECT DISTINCT ON (team_member_id)
            team_member_id
        FROM fund.team_members
        WHERE fund_id = $1 AND expire_at > NOW()
        """
        
        team_member_properties_query = """
        SELECT 
            category,
            subcategory,
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
                
                # Get fund properties
                property_rows = await conn.fetch(properties_query, fund_data['fund_id'])
                
                # Property mapping from DB to frontend fields
                reverse_property_mapping = {
                    ('property', 'legalStructure'): 'legalStructure',
                    ('property', 'state_country'): 'location',
                    ('property', 'yearEstablished'): 'yearEstablished',
                    ('metadata', 'aumRange'): 'aumRange',
                    ('metadata', 'purpose'): 'profilePurpose',
                    ('metadata', 'otherDetails'): 'otherPurposeDetails',
                    ('metadata', 'thesis'): 'investmentStrategy'
                }
                
                # Process properties
                for row in property_rows:
                    category = row['category']
                    subcategory = row['subcategory']
                    value = row['value']
                    
                    # Try to parse JSON values
                    try:
                        if isinstance(value, str) and (value.startswith('{') or value.startswith('[')):
                            value = json.loads(value)
                    except (json.JSONDecodeError, AttributeError):
                        pass
                    
                    # Map back to frontend field names
                    db_key = (category, subcategory)
                    if db_key in reverse_property_mapping:
                        field_name = reverse_property_mapping[db_key]
                        fund_data[field_name] = value
                    else:
                        # For unmapped properties, use a descriptive key
                        field_name = f"{category}_{subcategory.replace('.', '_')}"
                        fund_data[field_name] = value
                
                # Get team members
                logger.info(f"Getting team members for fund {fund_data['fund_id']}")
                team_member_rows = await conn.fetch(team_members_query, fund_data['fund_id'])
                logger.info(f"Found {len(team_member_rows)} team members")
                
                team_members = []
                
                # Team member property mapping from DB to frontend fields
                reverse_team_mapping = {
                    ('personal', 'order'): 'order',
                    ('personal', 'firstName'): 'firstName',
                    ('personal', 'lastName'): 'lastName',
                    ('personal', 'birthDate'): 'birthDate',
                    ('professional', 'role'): 'role',
                    ('professional', 'yearsExperience'): 'yearsExperience',
                    ('professional', 'currentEmployment'): 'currentEmployment',
                    ('professional', 'investmentExpertise'): 'investmentExpertise',
                    ('social', 'linkedin'): 'linkedin',
                    ('education', 'education'): 'education'
                }
                
                # Process each team member
                for team_row in team_member_rows:
                    team_member_id = ensure_json_serializable(team_row['team_member_id'])
                    
                    # Get team member properties
                    member_property_rows = await conn.fetch(
                        team_member_properties_query, 
                        team_row['team_member_id']
                    )
                    
                    # Process team member properties
                    member_data = {
                        'team_member_id': team_member_id
                    }
                    
                    for row in member_property_rows:
                        category = row['category']
                        subcategory = row['subcategory']
                        value = row['value']
                        
                        # Try to parse JSON values
                        try:
                            if isinstance(value, str) and (value.startswith('{') or value.startswith('[')):
                                value = json.loads(value)
                        except (json.JSONDecodeError, AttributeError):
                            pass
                                                
                        # Map back to frontend field names
                        db_key = (category, subcategory)
                        if db_key in reverse_team_mapping:
                            field_name = reverse_team_mapping[db_key]
                            member_data[field_name] = value
                        else:
                            # For unmapped properties, use a descriptive key
                            field_name = f"{category}_{subcategory.replace('.', '_')}"
                            member_data[field_name] = value
                    
                    # Add member to the list
                    team_members.append(member_data)
                
                # Sort team members by order if available
                team_members.sort(key=lambda m: int(m.get('order', '0')) if m.get('order', '0').isdigit() else 0)
                
                # Add team members to fund data
                fund_data['team_members'] = team_members
                
                duration = time.time() - start_time
                track_db_operation("get_fund_by_user", True, duration)
                
                # Final check to ensure all is JSON serializable
                result = ensure_json_serializable(fund_data)
                return result
                
        except Exception as e:
            duration = time.time() - start_time
            track_db_operation("get_fund_by_user", False, duration)
            logger.error(f"Error getting fund by user: {e}", exc_info=True)
            return None

    async def update_fund(self, fund_id: str, user_id: str, update_data: Dict[str, Any]) -> bool:
        """
        Update a fund's properties and team members using temporal data pattern
        
        Args:
            fund_id: Fund ID to update
            user_id: User ID to validate ownership
            update_data: Dictionary with fields to update
            
        Returns:
            True if successful, False otherwise
        """
        logger.info(f"Updating fund {fund_id} for user {user_id}")
        
        pool = await self.db_pool.get_pool()
        now = datetime.datetime.now(datetime.timezone.utc)
        
        # Extract properties and team members
        properties = update_data.get('properties', {})
        team_members = update_data.get('team_members', [])
        name = update_data.get('name')
        
        try:
            async with pool.acquire() as conn:
                async with conn.transaction():
                    # Verify ownership
                    fund_check = await conn.fetchrow(
                        """
                        SELECT 1 FROM fund.funds
                        WHERE fund_id = $1 AND user_id = $2
                        """,
                        fund_id, user_id
                    )
                    
                    if not fund_check:
                        logger.error(f"Fund {fund_id} not found or does not belong to user {user_id}")
                        return False
                    
                    # Update fund name if provided
                    if name:
                        # Insert new record
                        await conn.execute(
                            """
                            UPDATE fund.funds
                            SET name = $1
                            WHERE fund_id = $2
                            """,
                            name, fund_id
                        )
                    
                    # Update properties if provided
                    if properties:
                        # Expire all current properties
                        await conn.execute(
                            """
                            UPDATE fund.fund_properties
                            SET expire_at = $1
                            WHERE fund_id = $2 AND expire_at > NOW()
                            """,
                            now, fund_id
                        )
                        
                        # Save new properties
                        await self._save_fund_properties(conn, fund_id, properties, now)
                    
                    # Update team members if provided
                    if team_members:
                        # Get existing team members
                        existing_members = await conn.fetch(
                            """
                            SELECT team_member_id FROM fund.team_members
                            WHERE fund_id = $1 AND expire_at > NOW()
                            """,
                            fund_id
                        )
                        
                        # Expire all existing team members and their properties
                        for row in existing_members:
                            member_id = row['team_member_id']
                            
                            # Expire member properties
                            await conn.execute(
                                """
                                UPDATE fund.team_member_properties
                                SET expire_at = $1
                                WHERE member_id = $2 AND expire_at > NOW()
                                """,
                                now, member_id
                            )
                            
                            # Expire team member
                            await conn.execute(
                                """
                                UPDATE fund.team_members
                                SET expire_at = $1
                                WHERE team_member_id = $2 AND expire_at > NOW()
                                """,
                                now, member_id
                            )
                        
                        # Create new team members
                        for i, team_member in enumerate(team_members):
                            # Create new team member
                            new_member_id = await conn.fetchval(
                                """
                                INSERT INTO fund.team_members (
                                    fund_id, active_at, expire_at
                                ) VALUES (
                                    $1, $2, $3
                                ) RETURNING team_member_id
                                """,
                                fund_id, now, self.future_date
                            )
                            
                            # Convert UUID to string
                            if isinstance(new_member_id, uuid.UUID):
                                new_member_id = str(new_member_id)
                            
                            # Save team member properties
                            await self._save_team_member_properties(conn, new_member_id, team_member, i, now)
                    
                    return True
                    
        except Exception as e:
            logger.error(f"Error updating fund {fund_id}: {e}", exc_info=True)
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
        WHERE user_id = $1
        LIMIT 1
        """
        
        try:
            async with pool.acquire() as conn:
                result = await conn.fetchval(query, user_id)
                exists = result is not None
                return exists
        except Exception as e:
            logger.error(f"Error checking fund existence for user {user_id}: {e}", exc_info=True)
            return False
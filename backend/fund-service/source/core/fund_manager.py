# source/core/fund_manager.py
import logging
import uuid
from typing import Dict, Any, List, Optional

from source.models.fund import Fund
from source.db.fund_repository import FundRepository
from source.utils.metrics import track_fund_created

logger = logging.getLogger('fund_manager')


class FundManager:
    """Manager for fund operations"""

    def __init__(
            self,
            fund_repository: FundRepository,
    ):
        """Initialize the fund manager with dependencies"""
        self.fund_repository = fund_repository

    async def create_fund(self, fund_data: Dict[str, Any], user_id: str) -> Dict[str, Any]:
        """
        Create a new fund for a user
        
        Args:
            fund_data: Fund data dictionary
            user_id: User ID
            
        Returns:
            Result dictionary with success flag and fund_id
        """
        logger.info(f"Creating fund for user {user_id}")
        
        # Check if the user already has a fund (one-to-one relationship)
        existing_fund = await self.fund_repository.check_fund_exists(user_id)
        if existing_fund:
            return {
                "success": False,
                "error": "User already has a fund profile"
            }
        
        # Basic validation for required fields
        if 'name' not in fund_data:
            return {
                "success": False,
                "error": "Missing required field: name"
            }
        
        # Create fund model
        try:
            fund = Fund(
                user_id=user_id,
                name=fund_data['name'],
                status=fund_data.get('status', 'active'),
                fund_id=str(uuid.uuid4())
            )
            
            # Extract properties from fund data
            properties = {}
            
            # Map general properties to the properties object
            if 'legalStructure' in fund_data:
                properties['legalStructure'] = fund_data['legalStructure']
            if 'location' in fund_data:
                properties['location'] = fund_data['location']
            if 'yearEstablished' in fund_data:
                properties['yearEstablished'] = fund_data['yearEstablished']
            if 'aumRange' in fund_data:
                properties['aumRange'] = fund_data['aumRange']
            if 'profilePurpose' in fund_data:
                properties['profilePurpose'] = fund_data['profilePurpose']
            if 'otherPurposeDetails' in fund_data:
                properties['otherPurposeDetails'] = fund_data['otherPurposeDetails']
            if 'investmentStrategy' in fund_data:
                properties['investmentStrategy'] = fund_data['investmentStrategy']
            
            # Process team members
            team_members = []
            if 'team_members' in fund_data and isinstance(fund_data['team_members'], list):
                for member in fund_data['team_members']:
                    team_member = {
                        'id': member.get('id', ''),
                        'personal': {
                            'firstName': member.get('firstName', ''),
                            'lastName': member.get('lastName', ''),
                            'birthDate': member.get('birthDate', '')
                        },
                        'professional': {
                            'role': member.get('role', ''),
                            'yearsExperience': member.get('yearsExperience', ''),
                            'currentEmployment': member.get('currentEmployment', ''),
                            'investmentExpertise': member.get('investmentExpertise', ''),
                            'linkedin': member.get('linkedin', '')
                        }
                    }
                    
                    # Handle education as either a string or object
                    if 'education' in member:
                        if isinstance(member['education'], dict):
                            team_member['education'] = member['education']
                        else:
                            team_member['education'] = {'institution': member['education']}
                    
                    team_members.append(team_member)
            
            # Save fund to database with properties and team members
            result = await self.fund_repository.create_fund_with_details(
                fund.to_dict(),
                properties,
                team_members
            )
            
            if result and result.get("success"):
                # Track metrics
                track_fund_created(user_id)
                
                return {
                    "success": True,
                    "fund_id": result['fund_id']
                }
            else:
                return {
                    "success": False,
                    "error": result.get("error", "Failed to save fund")
                }
        except Exception as e:
            logger.error(f"Error creating fund: {e}")
            return {
                "success": False,
                "error": f"Error creating fund: {str(e)}"
            }
    
    async def get_fund(self, user_id: str) -> Dict[str, Any]:
        """
        Get a fund for a user
        
        Args:
            user_id: User ID
            
        Returns:
            Result dictionary with success flag and fund data
        """
        logger.info(f"Getting fund for user {user_id}")
        
        try:
            fund = await self.fund_repository.get_fund_by_user(user_id)
            
            if not fund:
                return {
                    "success": False,
                    "error": "Fund not found",
                    "fund": None
                }
            
            return {
                "success": True,
                "fund": fund
            }
        except Exception as e:
            logger.error(f"Error getting fund for user {user_id}: {e}")
            return {
                "success": False,
                "error": f"Error getting fund: {str(e)}",
                "fund": None
            }
    
    async def update_fund(self, fund_data: Dict[str, Any], user_id: str) -> Dict[str, Any]:
        """
        Update a fund for a user
        
        Args:
            fund_data: Fund data dictionary with updates
            user_id: User ID
            
        Returns:
            Result dictionary with success flag
        """
        logger.info(f"Updating fund for user {user_id}")
        logger.info(f"Update data received in fund_manager: {fund_data}")
        
        try:
            # First, get the fund to verify existence and get fund_id
            current_fund = await self.fund_repository.get_fund_by_user(user_id)
            
            if not current_fund:
                return {
                    "success": False,
                    "error": "Fund not found"
                }
            
            fund_id = current_fund['fund_id']
            logger.info(f"Found fund with ID: {fund_id}")
            
            # Process updates
            update_object = {}
            
            # Handle basic fund fields
            if 'name' in fund_data:
                update_object['name'] = fund_data['name']
            
            if 'status' in fund_data:
                if fund_data['status'] in ['active', 'archived', 'pending']:
                    update_object['status'] = fund_data['status']
                else:
                    return {
                        "success": False,
                        "error": "Invalid status value. Must be one of: active, archived, pending"
                    }
            
            # Handle properties
            properties = {}
            
            # Check if any property fields are being updated
            property_fields = [
                'legalStructure', 'location', 'yearEstablished', 'aumRange',
                'profilePurpose', 'otherPurposeDetails', 'investmentStrategy'
            ]
            
            for field in property_fields:
                if field in fund_data:
                    properties[field] = fund_data[field]
            
            if properties:
                update_object['properties'] = properties
            
            # Handle team members
            if 'team_members' in fund_data and isinstance(fund_data['team_members'], list):
                team_members = []
                
                for member in fund_data['team_members']:
                    # Skip team members without ID - can't update what we can't identify
                    if 'id' not in member:
                        logger.warning(f"Skipping team member without ID: {member}")
                        continue
                    
                    team_member = {
                        'id': member['id'],
                        'personal': {
                            'firstName': member.get('firstName', ''),
                            'lastName': member.get('lastName', ''),
                            'birthDate': member.get('birthDate', '')
                        },
                        'professional': {
                            'role': member.get('role', ''),
                            'yearsExperience': member.get('yearsExperience', ''),
                            'currentEmployment': member.get('currentEmployment', ''),
                            'investmentExpertise': member.get('investmentExpertise', ''),
                            'linkedin': member.get('linkedin', '')
                        }
                    }
                    
                    # Handle education as either a string or object
                    if 'education' in member:
                        if isinstance(member['education'], dict):
                            team_member['education'] = member['education']
                        else:
                            team_member['education'] = {'institution': member['education']}
                    
                    team_members.append(team_member)
                
                if team_members:
                    update_object['team_members'] = team_members
            
            # Apply the updates
            if update_object:
                success = await self.fund_repository.update_fund(fund_id, user_id, update_object)
                
                if success:
                    logger.info(f"Successfully updated fund {fund_id}")
                    return {
                        "success": True
                    }
                else:
                    logger.error(f"Failed to update fund {fund_id}")
                    return {
                        "success": False,
                        "error": "Failed to update fund"
                    }
            else:
                logger.info("No valid updates provided")
                return {
                    "success": True,
                    "message": "No valid updates provided"
                }
        except Exception as e:
            logger.error(f"Error updating fund for user {user_id}: {e}")
            return {
                "success": False,
                "error": f"Error updating fund: {str(e)}"
            }
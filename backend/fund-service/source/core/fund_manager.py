# backend/fund-service/source/core/fund_manager.py
import logging
import uuid
from typing import Dict, Any, List, Optional

from source.models.fund import Fund

from source.db.fund_repository import FundRepository
from source.core.crypto_manager import CryptoManager

from source.utils.metrics import track_fund_created

logger = logging.getLogger('fund_manager')

class FundManager:
    """Manager for fund operations"""

    def __init__(
            self,
            fund_repository: FundRepository,
            crypto_manager: CryptoManager,
    ):
        """Initialize the fund manager with dependencies"""
        self.fund_repository = fund_repository
        self.crypto_manager = crypto_manager

    async def create_fund(self, fund_data: Dict[str, Any], user_id: str) -> Dict[str, Any]:
        """
        Create a new fund for a user with blockchain wallet integration
        
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
        
        # Create fund model
        try:
            fund = Fund(
                user_id=user_id,
                fund_id=str(uuid.uuid4())
            )
            
            # Extract properties from fund data
            properties = {}
            
            # Map general properties to the properties object
            property_fields = [
                'fundName', 'legalStructure', 'location', 'yearEstablished', 'aumRange',
                'profilePurpose', 'otherPurposeDetails', 'investmentStrategy'
            ]
            
            for field in property_fields:
                if field in fund_data:
                    properties[field] = fund_data[field]

            # Process team members
            team_members = []
            if 'team_members' in fund_data and isinstance(fund_data['team_members'], list):
                for idx, member in enumerate(fund_data['team_members']):
                    team_member = {
                        'order': idx,
                        'firstName': member.get('firstName', ''),
                        'lastName': member.get('lastName', ''),
                        'birthDate': member.get('birthDate', ''),
                        'role': member.get('role', ''),
                        'yearsExperience': member.get('yearsExperience', ''),
                        'currentEmployment': member.get('currentEmployment', ''),
                        'investmentExpertise': member.get('investmentExpertise', ''),
                        'linkedin': member.get('linkedin', ''),
                        'education': member.get('education', '')
                    }
                    team_members.append(team_member)
            
            # Save fund to database with properties and team members
            result = await self.fund_repository.create_fund_with_details(
                fund.to_dict(),
                properties,
                team_members
            )

            if result and result.get("success"):
                fund_id = result['fund_id']
                
                # STEP 1: Create blockchain wallet for the fund
                logger.info(f"Creating blockchain wallet for fund {fund_id}")
                wallet_result = await self.crypto_manager.create_wallet(user_id, fund_id)
                
                if not wallet_result.get("success"):
                    logger.error(f"Failed to create wallet for fund {fund_id}: {wallet_result.get('error')}")
                    # Note: We could rollback the fund creation here if desired
                    return {
                        "success": False,
                        "error": f"Fund created but wallet creation failed: {wallet_result.get('error')}"
                    }
                
                logger.info(f"Blockchain wallet created successfully for fund {fund_id}")
                
                # Track metrics
                track_fund_created(user_id)
                
                return {
                    "success": True,
                    "fund_id": fund_id,
                    "wallet_address": wallet_result.get("address")
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
        Get a fund for a user with blockchain wallet information
        
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
            
            fund_id = fund['fund_id']
            
            # Get blockchain wallet information
            wallet_data = await self.crypto_manager.get_wallet(user_id, fund_id)
            
            if wallet_data:
                # Add wallet information to fund data
                fund['wallet'] = {
                    'address': wallet_data.get('address'),
                    'active_at': wallet_data.get('active_at')
                }
                logger.info(f"Retrieved fund with wallet for user {user_id}")
            else:
                logger.warning(f"Fund found but no wallet data for user {user_id}")
                fund['wallet'] = None
            
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
        Update a fund for a user (blockchain wallet remains unchanged)
        
        Args:
            fund_data: Fund data dictionary with updates
            user_id: User ID
            
        Returns:
            Result dictionary with success flag
        """
        logger.info(f"Updating fund for user {user_id}")
        
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
            
            # Prepare update data
            update_object = {}
                        
            # Handle properties
            properties = {}
            
            # Check if any property fields are being updated
            property_fields = [
                'fundName', 'legalStructure', 'location', 'yearEstablished', 'aumRange',
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
                
                for idx, member in enumerate(fund_data['team_members']):
                    team_member = {
                        'order': idx,
                        'firstName': member.get('firstName', ''),
                        'lastName': member.get('lastName', ''),
                        'birthDate': member.get('birthDate', ''),
                        'role': member.get('role', ''),
                        'yearsExperience': member.get('yearsExperience', ''),
                        'currentEmployment': member.get('currentEmployment', ''),
                        'investmentExpertise': member.get('investmentExpertise', ''),
                        'linkedin': member.get('linkedin', ''),
                        'education': member.get('education', '')
                    }
                    team_members.append(team_member)
                
                if team_members:
                    update_object['team_members'] = team_members
            
            # Apply the updates
            if update_object:
                success = await self.fund_repository.update_fund(fund_id, user_id, update_object)
                
                # Note: Wallet operations are not needed for fund updates
                # The blockchain wallet remains the same throughout the fund's lifecycle
                
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

    async def get_fund_wallet_info(self, user_id: str) -> Dict[str, Any]:
        """
        Get wallet information for a user's fund
        
        Args:
            user_id: User ID
            
        Returns:
            Result dictionary with wallet information
        """
        try:
            # First get the fund to get the fund_id
            fund = await self.fund_repository.get_fund_by_user(user_id)
            
            if not fund:
                return {
                    "success": False,
                    "error": "Fund not found"
                }
            
            fund_id = fund['fund_id']
            
            # Get wallet information
            wallet_data = await self.crypto_manager.get_wallet(user_id, fund_id)
            
            if wallet_data:
                return {
                    "success": True,
                    "wallet": wallet_data
                }
            else:
                return {
                    "success": False,
                    "error": "Wallet not found"
                }
                
        except Exception as e:
            logger.error(f"Error getting wallet info for user {user_id}: {e}")
            return {
                "success": False,
                "error": f"Error getting wallet info: {str(e)}"
            }
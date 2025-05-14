# source/core/fund_manager.py
import logging
import time
import uuid
from typing import Dict, Any

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
                fund_id=str(uuid.uuid4()),
                created_at=time.time(),
                updated_at=time.time()
            )
            
            # Prepare data for repository with properties
            fund_dict = fund.to_dict()
            if 'properties' in fund_data:
                fund_dict['properties'] = fund_data['properties']
            
            # Save to database
            fund_id = await self.fund_repository.create_fund(fund_dict)
            
            if fund_id:
                # Track metrics
                track_fund_created(user_id)
                
                return {
                    "success": True,
                    "fund_id": fund_id
                }
            else:
                return {
                    "success": False,
                    "error": "Failed to save fund"
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
                    "error": "Fund not found"
                }
            
            return {
                "success": True,
                "fund": fund
            }
        except Exception as e:
            logger.error(f"Error getting fund for user {user_id}: {e}")
            return {
                "success": False,
                "error": f"Error getting fund: {str(e)}"
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
        
        try:
            # First, get the fund to verify existence and get fund_id
            fund = await self.fund_repository.get_fund_by_user(user_id)
            
            if not fund:
                return {
                    "success": False,
                    "error": "Fund not found"
                }
            
            fund_id = fund['fund_id']
            
            # Process updates
            valid_updates = {}
            
            # Only process valid fields
            if 'name' in fund_data:
                valid_updates['name'] = fund_data['name']
            
            if 'status' in fund_data:
                if fund_data['status'] in ['active', 'archived', 'pending']:
                    valid_updates['status'] = fund_data['status']
                else:
                    return {
                        "success": False,
                        "error": "Invalid status value. Must be one of: active, archived, pending"
                    }
            
            # Handle properties
            if 'properties' in fund_data:
                valid_updates['properties'] = fund_data['properties']
            
            # Apply updates
            if valid_updates:
                success = await self.fund_repository.update_fund(fund_id, user_id, valid_updates)
                
                if success:
                    return {
                        "success": True
                    }
                else:
                    return {
                        "success": False,
                        "error": "Failed to update fund"
                    }
            else:
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
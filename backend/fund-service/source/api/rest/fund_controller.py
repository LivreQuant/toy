# source/api/rest/fund_controller.py
import logging
from aiohttp import web

from source.api.rest.base_controller import BaseController

from source.core.state_manager import StateManager
from source.core.session_manager import SessionManager
from source.core.fund_manager import FundManager

logger = logging.getLogger('fund_controllers')

class FundController(BaseController):
    """Controller for fund-related REST endpoints"""

    def __init__(self,
                 state_manager: StateManager,
                 session_manager: SessionManager,
                 fund_manager: FundManager):
        """Initialize controller with dependencies"""
        super().__init__(session_manager)
        self.state_manager = state_manager
        self.fund_manager = fund_manager

    async def create_fund(self, request: web.Request) -> web.Response:
        """
        Handle fund creation endpoint
        """
        # Try to acquire the lock first
        acquired = await self.state_manager.acquire()
        if not acquired:
            return self.create_error_response("Service is currently busy. Please try again later.", 503)

        try:
            return await self._create_fund(request)
        except Exception as e:
            logger.error(f"Error handling fund creation: {e}")
            return self.create_error_response("Server error processing fund creation")
        finally:
            # Always release the lock, even if there's an error
            await self.state_manager.release()

    async def get_fund(self, request: web.Request) -> web.Response:
        """
        Handle fund retrieval endpoint
        """
        # Try to acquire the lock first
        acquired = await self.state_manager.acquire()
        if not acquired:
            return self.create_error_response("Service is currently busy. Please try again later.", 503)

        try:
            return await self._get_fund(request)
        except Exception as e:
            logger.error(f"Error handling fund retrieval: {e}")
            return self.create_error_response("Server error processing fund request")
        finally:
            # Always release the lock, even if there's an error
            await self.state_manager.release()

    async def update_fund(self, request: web.Request) -> web.Response:
        """
        Handle fund update endpoint
        """
        # Try to acquire the lock first
        acquired = await self.state_manager.acquire()
        if not acquired:
            return self.create_error_response("Service is currently busy. Please try again later.", 503)

        try:
            return await self._update_fund(request)
        except Exception as e:
            logger.error(f"Error handling fund update: {e}")
            return self.create_error_response("Server error processing fund update")
        finally:
            # Always release the lock, even if there's an error
            await self.state_manager.release()

    async def _create_fund(self, request: web.Request) -> web.Response:
        """Handle fund creation endpoint"""
        # Authenticate request
        auth_success, auth_result = await self.authenticate(request)
        if not auth_success:
            return self.create_error_response(auth_result["error"], auth_result["status"])

        user_id = auth_result["user_id"]

        # Parse request body
        parse_success, data = await self.parse_json_body(request)
        if not parse_success:
            return self.create_error_response(data["error"], data["status"])
        
        logger.info(f"Received fund creation request data: {data}")
        
        # Prepare fund data
        fund_data = {
            'user_id': user_id,
        }
                
        # Extract properties
        property_fields = [
            'fundName','legalStructure', 'location', 'yearEstablished', 'aumRange',
            'profilePurpose', 'otherPurposeDetails', 'investmentStrategy'
        ]
        
        for field in property_fields:
            if field in data:
                fund_data[field] = data[field]
        
        # Extract team members
        if 'teamMembers' in data and isinstance(data['teamMembers'], list):
            fund_data['team_members'] = data['teamMembers']
            logger.info(f"Extracted {len(data['teamMembers'])} team members")
        
        # Create fund
        result = await self.fund_manager.create_fund(fund_data, user_id)

        if not result["success"]:
            error = result.get("error", "Failed to create fund")
            status = 400 if "already has a fund" in error else 500
            return self.create_error_response(error, status)

        return self.create_success_response({"fundId": result["fund_id"]})

    async def _get_fund(self, request: web.Request) -> web.Response:
        """Handle fund retrieval endpoint"""
        # Authenticate request
        auth_success, auth_result = await self.authenticate(request)
        if not auth_success:
            return self.create_error_response(auth_result["error"], auth_result["status"])

        user_id = auth_result["user_id"]

        # Get active fund for this user
        result = await self.fund_manager.get_fund(user_id)

        if not result["success"]:
            if "not found" in result.get("error", ""):
                # Fund not found - return success with null fund
                return self.create_success_response({"fund": None})
            else:
                # Other error - return error response
                return self.create_error_response(result.get("error", "Failed to retrieve fund"), 500)

        return self.create_success_response({"fund": result["fund"]})

    async def _update_fund(self, request: web.Request) -> web.Response:
        """Handle fund update endpoint using temporal data pattern"""
        # Authenticate request
        auth_success, auth_result = await self.authenticate(request)
        if not auth_success:
            return self.create_error_response(auth_result["error"], auth_result["status"])

        user_id = auth_result["user_id"]

        # Parse request body
        parse_success, data = await self.parse_json_body(request)
        if not parse_success:
            return self.create_error_response(data["error"], data["status"])

        # Extract fund name
        update_data = {}

        # Extract properties
        property_fields = [
            'fundName', 'legalStructure', 'location', 'yearEstablished', 'aumRange',
            'profilePurpose', 'otherPurposeDetails', 'investmentStrategy'
        ]
        
        for field in property_fields:
            if field in data:
                update_data[field] = data[field]
        
        # Extract team members
        if 'teamMembers' in data and isinstance(data['teamMembers'], list):
            update_data['team_members'] = data['teamMembers']
        
        # Update fund
        result = await self.fund_manager.update_fund(update_data, user_id)

        if not result["success"]:
            error = result.get("error", "Failed to update fund")
            status = 404 if "not found" in error else 500
            return self.create_error_response(error, status)

        return self.create_success_response({
            "message": result.get("message", "Fund updated successfully")
        })
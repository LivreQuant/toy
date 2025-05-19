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
        
        # Log the entire request data for debugging
        logger.info(f"Received fund creation request data: {data}")
        
        # Map frontend field names to expected field names
        fund_data = {
            'name': data.get('fundName', data.get('name', '')),
            'user_id': user_id,
        }
        
        # Validate required fields
        if not fund_data['name']:
            return self.create_error_response("Missing required field: name", 400)
        
        # Explicitly extract and add each property field
        if 'legalStructure' in data:
            fund_data['legalStructure'] = data['legalStructure']
            logger.info(f"Extracted legalStructure: {data['legalStructure']}")
        
        if 'location' in data:
            fund_data['location'] = data['location']
            logger.info(f"Extracted location: {data['location']}")
            
        if 'yearEstablished' in data:
            fund_data['yearEstablished'] = data['yearEstablished']
            logger.info(f"Extracted yearEstablished: {data['yearEstablished']}")
            
        if 'aumRange' in data:
            fund_data['aumRange'] = data['aumRange']
            logger.info(f"Extracted aumRange: {data['aumRange']}")
            
        if 'profilePurpose' in data:
            fund_data['profilePurpose'] = data['profilePurpose']
            logger.info(f"Extracted profilePurpose: {data['profilePurpose']}")
            
        if 'otherPurposeDetails' in data:
            fund_data['otherPurposeDetails'] = data['otherPurposeDetails']
            logger.info(f"Extracted otherPurposeDetails: {data['otherPurposeDetails']}")
            
        if 'investmentStrategy' in data:
            fund_data['investmentStrategy'] = data['investmentStrategy']
            logger.info(f"Extracted investmentStrategy: {data['investmentStrategy']}")
        
        # Process team members
        if 'teamMembers' in data and isinstance(data['teamMembers'], list):
            fund_data['team_members'] = data['teamMembers']
            logger.info(f"Extracted {len(data['teamMembers'])} team members")
        
        # Log what we're sending to the fund manager
        logger.info(f"Sending fund_data to manager: {fund_data}")
        
        # Create fund using the temporal data pattern
        result = await self.fund_manager.create_fund(fund_data, user_id)

        if not result["success"]:
            error = result.get("error", "Failed to create fund")
            status = 400 if "already has a fund" in error else 500
            return self.create_error_response(error, status)

        return self.create_success_response({"fundId": result["fund_id"]})


    # In fund_controller.py, modify the _get_fund method:
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

        # Transform the properties structure to be more client-friendly
        fund = result["fund"]
        if fund and 'properties' in fund:
            # Map properties to a more useful structure
            transformed_properties = {}
            
            # Handle general properties
            if 'general' in fund['properties']:
                general = fund['properties']['general']
                
                if 'profile' in general:
                    profile = general['profile']
                    for key, value in profile.items():
                        # Try to identify the property type - WITH STRICT TYPE CHECKING
                        if value in ["Personal Account", "LLC", "Limited Partnership", "Corporation"]:
                            transformed_properties['legalStructure'] = value
                        elif isinstance(value, str) and value.startswith(("Under $", "$", "Over $")):  # FIXED: Type check before startswith
                            transformed_properties['aumRange'] = value
                        elif str(value).isdigit() or (len(str(value)) == 4 and str(value).isdigit()):
                            transformed_properties['yearEstablished'] = value
                        elif isinstance(value, list) or value in ["raise_capital", "manage_investments", "other"]:
                            transformed_properties['profilePurpose'] = value
                        elif isinstance(value, str) and (value.startswith("To be ") or len(str(value).split()) > 3):  # FIXED: Type check before startswith
                            transformed_properties['otherPurposeDetails'] = value
                        else:
                            transformed_properties['location'] = value
                            
                if 'strategy' in general:
                    strategy = general['strategy']
                    for key, value in strategy.items():
                        transformed_properties['investmentStrategy'] = value
            
            # Merge the transformed properties with the fund data
            fund.update(transformed_properties)
            
            # Transform team members
            if 'team_members' in fund:
                for member in fund['team_members']:
                    member_data = {}
                    member_data['id'] = member['team_member_id']
                    
                    if 'properties' in member:
                        props = member['properties']
                        
                        # Extract personal info
                        if 'personal' in props and 'info' in props['personal']:
                            for key, value in props['personal']['info'].items():
                                if isinstance(value, str) and '-' in value and len(value) == 10:  # Looks like a date
                                    member_data['birthDate'] = value
                                elif isinstance(value, str) and len(value.split()) <= 2:  # Looks like a name
                                    if 'firstName' not in member_data:
                                        member_data['firstName'] = value
                                    else:
                                        member_data['lastName'] = value
                        
                        # Extract professional info
                        if 'professional' in props and 'info' in props['professional']:
                            for key, value in props['professional']['info'].items():
                                if value in ['Portfolio Manager', 'Analyst', 'Trader']:
                                    member_data['role'] = value
                                elif isinstance(value, str) and (value.isdigit() or value in ['1', '2', '3', '4', '5']):
                                    member_data['yearsExperience'] = value
                                elif isinstance(value, str) and value.startswith('http'):
                                    member_data['linkedin'] = value
                                elif isinstance(value, str) and len(value.split()) >= 2 and not value.startswith('http'):
                                    member_data['investmentExpertise'] = value
                                else:
                                    member_data['currentEmployment'] = value
                        
                        # Extract education info
                        if 'education' in props:
                            for key, value in props.get('education', {}).get('info', {}).items():
                                member_data['education'] = value
                    
                    # Replace the original member data with our transformed version
                    for key in list(member.keys()):
                        if key != 'team_member_id':
                            del member[key]
                    member.update(member_data)
            
            # Remove the original properties
            if 'properties' in fund:
                del fund['properties']
        
        return self.create_success_response({"fund": fund})


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

        # Map frontend field names to expected field names similar to create_fund
        update_data = {
            'properties': {}
        }

        # Add name field if present
        if 'fundName' in data:
            update_data['name'] = data['fundName']
        elif 'name' in data:
            update_data['name'] = data['name']
        
        # Map general properties
        general_properties = {
            'profile': {},
            'strategy': {}
        }
        
        # Add profile properties
        if 'legalStructure' in data:
            general_properties['profile']['legalStructure'] = data['legalStructure']
        if 'location' in data:
            general_properties['profile']['location'] = data['location']
        if 'yearEstablished' in data:
            general_properties['profile']['yearEstablished'] = data['yearEstablished']
        if 'aumRange' in data:
            general_properties['profile']['aumRange'] = data['aumRange']
        if 'profilePurpose' in data:
            general_properties['profile']['purpose'] = data['profilePurpose']
        if 'otherPurposeDetails' in data:
            general_properties['profile']['otherDetails'] = data['otherPurposeDetails']
        
        # Add strategy properties
        if 'investmentStrategy' in data:
            general_properties['strategy']['thesis'] = data['investmentStrategy']
        
        # Add properties if they exist
        if general_properties['profile'] or general_properties['strategy']:
            update_data['properties']['general'] = general_properties
            
        # Process team members if present
        if 'teamMembers' in data and isinstance(data['teamMembers'], list):
            team_members = []
            for member in data['teamMembers']:
                logger.info(f"Processing team member in controller: {member}")
                
                # Make sure we have the ID
                if 'id' not in member:
                    logger.warning(f"Team member without ID, skipping: {member}")
                    continue
                    
                team_member = {
                    'id': member.get('id'),  # Important! Include the team member ID for updates
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
                    },
                    'education': {
                        'institution': member.get('education', '')
                    }
                }
                team_members.append(team_member)
                logger.info(f"Transformed team member: {team_member}")
            
            if team_members:
                update_data['team_members'] = team_members
                logger.info(f"Added {len(team_members)} team members to update data")
        
        # Log the transformed update data
        logger.info(f"Transformed update data: {update_data}")

        # Update fund using temporal data pattern
        result = await self.fund_manager.update_fund(update_data, user_id)

        if not result["success"]:
            error = result.get("error", "Failed to update fund")
            status = 404 if "not found" in error else 500
            return self.create_error_response(error, status)

        return self.create_success_response({
            "message": result.get("message", "Fund updated successfully")
        })
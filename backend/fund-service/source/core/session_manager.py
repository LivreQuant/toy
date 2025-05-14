# source/core/session_manager.py
import logging
from typing import Tuple, Optional, Dict, Any

from aiohttp import web

from source.clients.auth_client import AuthClient
from source.db.session_repository import SessionRepository

logger = logging.getLogger('validation_manager')


class SessionManager:
    """Manager for validating authentication, sessions, and orders"""

    def __init__(
            self,
            session_repository: SessionRepository,
            auth_client: AuthClient
    ):
        self.session_repository = session_repository
        self.auth_client = auth_client

    async def validate_user_auth(self, token: str, csrf_token: str = None) -> Dict[str, Any]:
        """
        Validate authentication token
        
        Args:
            token: Authentication token
            csrf_token: Optional CSRF token
                
        Returns:
            Validation result with valid flag and user_id if successful
        """
        # Validate the auth token
        auth_result = await self.auth_client.validate_token(token, csrf_token)

        if not auth_result.get('valid', False):
            logger.warning(f"Invalid authentication token")
            return {
                "valid": False,
                "error": auth_result.get('error', 'Invalid authentication token')
            }

        user_id = auth_result.get('user_id')

        # Ensure user ID was returned
        if not user_id:
            logger.warning("Auth token valid but no user ID returned")
            return {
                "valid": False,
                "error": "Authentication error: missing user ID"
            }

        return {
            "valid": True,
            "user_id": user_id
        }

    async def validate_session(self, device_id: str, user_id: str) -> Dict[str, Any]:
        """
        Validate session and device ID directly from database
        
        Args:
            device_id: Device ID to validate
            user_id: User ID to find the simulator
            
        Returns:
            Validation result with simulator info if available
        """
        # Directly validate from database
        device_valid = await self.session_repository.validate_device_id(device_id)

        if not device_valid:
            logger.warning(f"Device {device_id} not valid for session")
            return {
                "valid": False,
                "error": "Invalid device ID for this session"
            }

        # Get simulator information if exists
        simulator = await self.session_repository.get_session_simulator(user_id)

        return {
            "valid": True,
            "simulator_id": simulator.get('simulator_id') if simulator else None,
            "simulator_endpoint": simulator.get('endpoint') if simulator else None
        }

    async def validate_device_id(self, device_id: str) -> bool:
        """
        Validate the device ID
        
        Args:
            device_id: Device ID to validate
            
        Returns:
            True if valid, False otherwise
        """
        if not device_id:
            logger.warning("No device ID provided")
            return False
            
        # Check if device ID exists in the database
        try:
            return await self.session_repository.validate_device_id(device_id)
        except Exception as e:
            logger.error(f"Error validating device ID: {e}")
            return False

    async def get_token(self,
                        request: web.Request
                        ) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """
        Extract authentication token and device ID from request

        Args:
            request: Web request object

        Returns:
            Tuple of (token, device_id, csrf_token)
        """
        auth_header = request.headers.get('Authorization')
        csrf_token = request.headers.get('X-CSRF-Token')

        if auth_header and auth_header.startswith('Bearer '):
            return auth_header[7:], request.query.get('deviceId'), csrf_token

        # Try query parameter
        return request.query.get('token'), request.query.get('deviceId'), csrf_token


    async def get_user_id_from_token(self,
                                     token: str,
                                     csrf_token: str = None
                                     ) -> Optional[str]:
        """
        Extract user ID from authentication token

        Args:
            session_manager: Session Manager
            token: Authentication token
            csrf_token: CSRF token

        Returns:
            User ID if token is valid, None otherwise
        """
        try:
            validation_result = await self.validate_token(token, csrf_token)

            if not validation_result.get('valid', False):
                logger.warning(f"Invalid authentication token")
                return None

            # Check for both naming conventions (snake_case and camelCase)
            user_id = validation_result.get('user_id') or validation_result.get('userId')
            if not user_id:
                logger.warning("Auth token valid but no user ID returned")
                return None

            return user_id
        except Exception as e:
            logger.error(f"Error extracting user ID from token: {e}")
            return None


    async def authenticate_request(self,
                                   request: web.Request,
                                   ) -> Tuple[bool, Dict[str, Any]]:
        """
        Authenticate and validate a request

        Args:
            request: Web request
            session_manager: Session Manager
            session_manager: Session manager

        Returns:
            Tuple of (success, result_dict)
            If success is False, result_dict contains error information with 'status' code
            If success is True, result_dict contains 'user_id'
        """
        # Extract token and device ID
        token, device_id, csrf_token = self.get_token(request)

        if not token:
            return False, {
                "success": False,
                "error": "Authentication token is required",
                "status": 401
            }

        # Get user_id from token
        user_id = await self.get_user_id_from_token(token, csrf_token)
        if not user_id:
            return False, {
                "success": False,
                "error": "Invalid authentication token",
                "status": 401
            }

        # Validate device ID
        device_valid = await self.validate_device_id(device_id)
        if not device_valid:
            return False, {
                "success": False,
                "error": "Invalid device ID for this session",
                "status": 400
            }

        return True, {"user_id": user_id}
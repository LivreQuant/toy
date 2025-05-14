import logging
import json
import time
from aiohttp import web

from source.db.fund_repository import FundRepository
from source.core.fund_manager import FundManager
from source.api.rest.controllers import get_token

logger = logging.getLogger('fund_controllers')

class FundController:
    """Controller for fund-related REST endpoints"""

    def __init__(self, fund_manager, auth_client, validation_manager):
        """Initialize controller with repositories and services"""
        self.fund_manager = fund_manager
        self.auth_client = auth_client
        self.validation_manager = validation_manager

    async def _get_user_id_from_token(self, token: str, csrf_token: str = None) -> str:
        """Extract user ID from authentication token"""
        try:
            # Use auth_client directly
            validation_result = await self.auth_client.validate_token(token, csrf_token)

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
        
    async def create_fund(self, request: web.Request) -> web.Response:
        """Handle fund creation endpoint"""
        try:
            # Extract token and device ID
            token, device_id, csrf_token = get_token(request)

            if not token:
                return web.json_response({
                    "success": False,
                    "error": "Authentication token is required"
                }, status=401)

            # Get user_id from token
            user_id = await self._get_user_id_from_token(token, csrf_token)
            if not user_id:
                return web.json_response({
                    "success": False,
                    "error": "Invalid authentication token"
                }, status=401)

            # Validate device ID
            device_valid = await self.validation_manager.validate_device_id(device_id)
            if not device_valid:
                return web.json_response({
                    "success": False,
                    "error": "Invalid device ID for this session"
                }, status=400)

            # Parse request body
            try:
                data = await request.json()
            except json.JSONDecodeError:
                return web.json_response({
                    "success": False,
                    "error": "Invalid JSON in request body"
                }, status=400)

            # Validate required fields
            required_fields = ['name']
            missing_fields = [field for field in required_fields if field not in data]
            if missing_fields:
                return web.json_response({
                    "success": False,
                    "error": f"Missing required fields: {', '.join(missing_fields)}"
                }, status=400)

            # Create fund
            result = await self.fund_manager.create_fund(data, user_id)
            
            if not result["success"]:
                return web.json_response({
                    "success": False,
                    "error": result.get("error", "Failed to create fund")
                }, status=400 if "already has a fund" in result.get("error", "") else 500)

            return web.json_response({
                "success": True,
                "fundId": result["fund_id"]
            })

        except Exception as e:
            logger.error(f"Error handling fund creation: {e}")
            return web.json_response({
                "success": False,
                "error": "Server error processing fund creation"
            }, status=500)

    async def get_fund(self, request: web.Request) -> web.Response:
        """Handle fund retrieval endpoint"""
        try:
            # Extract token and device ID
            token, device_id, csrf_token = get_token(request)

            if not token:
                return web.json_response({
                    "success": False,
                    "error": "Authentication token is required"
                }, status=401)

            # Get user_id from token
            user_id = await self._get_user_id_from_token(token, csrf_token)
            if not user_id:
                return web.json_response({
                    "success": False,
                    "error": "Invalid authentication token"
                }, status=401)

            # Validate device ID
            device_valid = await self.validation_manager.validate_device_id(device_id)
            if not device_valid:
                return web.json_response({
                    "success": False,
                    "error": "Invalid device ID for this session"
                }, status=400)

            # Get fund for this user
            result = await self.fund_manager.get_fund(user_id)
            
            if not result["success"]:
                return web.json_response({
                    "success": False,
                    "error": result.get("error", "Failed to retrieve fund")
                }, status=404 if "not found" in result.get("error", "") else 500)

            return web.json_response({
                "success": True,
                "fund": result["fund"]
            })

        except Exception as e:
            logger.error(f"Error handling fund retrieval: {e}")
            return web.json_response({
                "success": False,
                "error": "Server error processing fund request"
            }, status=500)

    async def update_fund(self, request: web.Request) -> web.Response:
        """Handle fund update endpoint"""
        try:
            # Extract token and device ID
            token, device_id, csrf_token = get_token(request)

            if not token:
                return web.json_response({
                    "success": False,
                    "error": "Authentication token is required"
                }, status=401)

            # Get user_id from token
            user_id = await self._get_user_id_from_token(token, csrf_token)
            if not user_id:
                return web.json_response({
                    "success": False,
                    "error": "Invalid authentication token"
                }, status=401)

            # Validate device ID
            device_valid = await self.validation_manager.validate_device_id(device_id)
            if not device_valid:
                return web.json_response({
                    "success": False,
                    "error": "Invalid device ID for this session"
                }, status=400)

            # Parse request body
            try:
                data = await request.json()
            except json.JSONDecodeError:
                return web.json_response({
                    "success": False,
                    "error": "Invalid JSON in request body"
                }, status=400)

            # Update fund
            result = await self.fund_manager.update_fund(data, user_id)
            
            if not result["success"]:
                return web.json_response({
                    "success": False,
                    "error": result.get("error", "Failed to update fund")
                }, status=404 if "not found" in result.get("error", "") else 500)

            return web.json_response({
                "success": True,
                "message": result.get("message", "Fund updated successfully")
            })

        except Exception as e:
            logger.error(f"Error handling fund update: {e}")
            return web.json_response({
                "success": False,
                "error": "Server error processing fund update"
            }, status=500)
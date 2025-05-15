# source/api/rest/base_controller.py
import logging
import json
from typing import Tuple, Dict, Any, Optional

from aiohttp import web

logger = logging.getLogger('base_controller')

class BaseController:
    """Base controller class with common functionality"""
    
    def __init__(self, session_manager):
        """Initialize with common dependencies"""
        self.session_manager = session_manager
    
    async def authenticate(self, request: web.Request) -> Tuple[bool, Dict[str, Any]]:
        """Authenticate and validate a request"""
        return await self.session_manager.authenticate_request(request)
    
    async def parse_json_body(self, request: web.Request) -> Tuple[bool, Any]:
        """
        Parse request body as JSON
        
        Returns:
            Tuple of (success, result)
            If success is True, result is the parsed JSON
            If success is False, result is an error response dict
        """
        try:
            data = await request.json()
            return True, data
        except json.JSONDecodeError:
            return False, {
                "success": False,
                "error": "Invalid JSON in request body",
                "status": 400
            }
    
    def validate_required_fields(self, data: Dict[str, Any], required_fields: list) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """
        Validate that required fields are present
        
        Returns:
            Tuple of (valid, error_response)
            If valid is True, error_response is None
            If valid is False, error_response is an error response dict
        """
        missing_fields = [field for field in required_fields if field not in data]
        if missing_fields:
            return False, {
                "success": False,
                "error": f"Missing required fields: {', '.join(missing_fields)}",
                "status": 400
            }
        return True, None
    
    def create_error_response(self, error: str, status: int = 500) -> web.Response:
        """Create a standardized error response"""
        return web.json_response({
            "success": False,
            "error": error
        }, status=status)
    
    def create_success_response(self, data: Dict[str, Any] = None) -> web.Response:
        """Create a standardized success response"""
        response = {"success": True}
        if data:
            response.update(data)
        return web.json_response(response)
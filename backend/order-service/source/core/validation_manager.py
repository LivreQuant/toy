import logging
from typing import Dict, Any

from source.clients.auth_client import AuthClient
from source.db.order_repository import OrderRepository

logger = logging.getLogger('validation_manager')


class ValidationManager:
    """Manager for validating authentication, sessions, and orders"""

    def __init__(
            self,
            order_repository: OrderRepository,
            auth_client: AuthClient
    ):
        self.order_repository = order_repository
        self.auth_client = auth_client

    async def validate_user_auth(self, token: str) -> Dict[str, Any]:
        """
        Validate authentication token
        
        Args:
            token: Authentication token
            
        Returns:
            Validation result with valid flag and user_id if successful
        """
        # Validate the auth token
        auth_result = await self.auth_client.validate_token(token)

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
        device_valid = await self.order_repository.validate_device_id(device_id)

        if not device_valid:
            logger.warning(f"Device {device_id} not valid for session")
            return {
                "valid": False,
                "error": "Invalid device ID for this session"
            }

        # Get simulator information if exists
        simulator = await self.order_repository.get_session_simulator(user_id)

        return {
            "valid": True,
            "simulator_id": simulator.get('simulator_id') if simulator else None,
            "simulator_endpoint": simulator.get('endpoint') if simulator else None
        }

    async def validate_order_parameters(self, order_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate order parameters
        
        Args:
            order_data: Order data to validate
            
        Returns:
            Validation result with extracted parameters if valid
        """
        try:
            symbol = order_data.get('symbol')
            side = order_data.get('side')
            quantity = float(order_data.get('quantity', 0))
            order_type = order_data.get('type')
            price = float(order_data.get('price', 0)) if 'price' in order_data else None

            # Basic validation
            if not symbol or not side or not order_type or quantity <= 0:
                logger.warning(f"Order validation failed: {order_data}")
                return {
                    "valid": False,
                    "error": "Invalid order parameters"
                }

            # For limit orders, price is required
            if order_type == 'LIMIT' and (price is None or price <= 0):
                return {
                    "valid": False,
                    "error": "Limit orders require a valid price greater than zero"
                }

            # Return validated parameters
            return {
                "valid": True,
                "symbol": symbol,
                "side": side,
                "quantity": quantity,
                "order_type": order_type,
                "price": price
            }

        except ValueError:
            return {
                "valid": False,
                "error": "Invalid order parameters: quantity and price must be numeric"
            }

from source.db.order_repository import OrderRepository
from source.clients.auth_client import AuthClient
from source.clients.exchange_client import ExchangeClient
from source.core.validation_manager import ValidationManager
from source.core.record_manager import RecordManager
from source.core.exchange_manager import ExchangeManager
from source.core.operation_manager import OperationManager

from source.core.state_manager import StateManager


class OrderManager:
    def __init__(
        self, 
        order_repository: OrderRepository, 
        auth_client: AuthClient,
        exchange_client: ExchangeClient,
        state_manager: StateManager  # New parameter
    ):
        """Initialize managers"""
        self.order_repository = order_repository
        self.state_manager = state_manager
        
        # Create specialized managers
        self.validation_manager = ValidationManager(order_repository, auth_client)
        self.record_manager = RecordManager(order_repository)
        self.exchange_manager = ExchangeManager(exchange_client)
        
        # Create main operation manager
        self.operation_manager = OperationManager(
            self.validation_manager,
            self.record_manager,
            self.exchange_manager
        )

    async def submit_order(self, order_data, device_id, token):
        """Submit an order by delegating to operation manager"""
        async def _submit_order():
            return await self.operation_manager.submit_order(order_data, device_id, token)

        return await self.state_manager.with_lock(
            user_id=self._extract_user_id(token),
            operation=_submit_order
        )

    async def cancel_order(self, order_id, device_id, token):
        """Cancel an order by delegating to operation manager"""
        async def _cancel_order():
            return await self.operation_manager.cancel_order(order_id, device_id, token)

        return await self.state_manager.with_lock(
            user_id=self._extract_user_id(token),
            operation=_cancel_order
        )

    async def _extract_user_id(self, token: str) -> str:
        """
        Extract user ID from authentication token
        
        Args:
            token: JWT authentication token
        
        Returns:
            User ID as a string
        
        Raises:
            ValueError if token is invalid or user ID cannot be extracted
        """
        try:
            # Use the auth client to validate the token
            validation_result = await self.auth_client.validate_token(token)
            
            # Check if validation was successful
            if not validation_result.get('valid', False):
                raise ValueError("Invalid authentication token")
            
            # Extract user ID from the validation result
            user_id = validation_result.get('user_id')
            
            if not user_id:
                raise ValueError("No user ID found in token")
            
            return user_id
        
        except Exception as e:
            logger.error(f"Error extracting user ID: {e}")
            raise ValueError("Failed to extract user ID from token")
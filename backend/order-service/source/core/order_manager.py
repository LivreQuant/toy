from source.db.order_repository import OrderRepository
from source.api.clients.auth_client import AuthClient
from source.api.clients.exchange_client import ExchangeClient
from source.core.validation_manager import ValidationManager
from source.core.record_manager import RecordManager
from source.core.exchange_manager import ExchangeManager
from source.core.operation_manager import OperationManager

class OrderManager:
    """Main order manager that coordinates specialized managers"""

    def __init__(
        self, 
        order_repository: OrderRepository, 
        auth_client: AuthClient,
        exchange_client: ExchangeClient
    ):
        """Initialize managers"""
        self.order_repository = order_repository
        
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

    async def submit_order(self, order_data, token):
        """Submit an order by delegating to operation manager"""
        return await self.operation_manager.submit_order(order_data, token)

    async def cancel_order(self, order_id, session_id, device_id, token):
        """Cancel an order by delegating to operation manager"""
        return await self.operation_manager.cancel_order(order_id, session_id, device_id, token)
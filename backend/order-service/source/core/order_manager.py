import logging
from source.core.validation_manager import ValidationManager
from source.core.exchange_manager import ExchangeManager
from source.core.operation_manager import OperationManager

logger = logging.getLogger('order_manager')


class OrderManager:
    """Main manager for order operations"""
    
    def __init__(
            self,
            order_repository,
            auth_client,
            exchange_client
    ):
        """Initialize the order manager with dependencies"""
        self.order_repository = order_repository
        self.auth_client = auth_client
        
        # Create specialized managers
        self.validation_manager = ValidationManager(order_repository, auth_client)
        self.exchange_manager = ExchangeManager(exchange_client)
        self.operation_manager = OperationManager(
            self.validation_manager,
            self.order_repository,
            self.exchange_manager
        )

    async def submit_orders(self, orders_data, user_id):
        """Submit orders in batch"""
        return await self.operation_manager.submit_orders(orders_data, user_id)
        
    async def cancel_orders(self, order_ids, user_id):
        """Cancel orders in batch"""
        return await self.operation_manager.cancel_orders(order_ids, user_id)
    
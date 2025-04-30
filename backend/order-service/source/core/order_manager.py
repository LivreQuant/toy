import logging
from source.db.order_repository import OrderRepository
from source.clients.auth_client import AuthClient
from source.clients.exchange_client import ExchangeClient
from source.core.validation_manager import ValidationManager
from source.core.record_manager import RecordManager
from source.core.exchange_manager import ExchangeManager
from source.core.operation_manager import OperationManager

logger = logging.getLogger('order_manager')


class OrderManager:
    def __init__(
            self,
            order_repository: OrderRepository,
            auth_client: AuthClient,
            exchange_client: ExchangeClient,
    ):
        """Initialize managers"""
        self.order_repository = order_repository
        self.auth_client = auth_client  # Store auth_client directly

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

    async def submit_order(self, order_data, user_id):
        """Submit an order directly to operation manager"""
        # No need to use the state manager lock here anymore
        # since it's already handled at the controller level
        return await self.operation_manager.submit_order(order_data, user_id)

    async def cancel_order(self, order_id, user_id):
        """Cancel an order directly to operation manager"""
        # No need to use the state manager lock here anymore
        # since it's already handled at the controller level
        return await self.operation_manager.cancel_order(order_id, user_id)

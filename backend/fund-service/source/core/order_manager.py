# source/core/order_manager.py
import logging

from source.clients.exchange_client import ExchangeClient
from source.db.order_repository import OrderRepository
from source.core.session_manager import SessionManager

from source.core.order_manager_exchange import ExchangeManager
from source.core.order_manager_record import RecordManager
from source.core.order_manager_operation import OperationManager


logger = logging.getLogger('order_manager')


class OrderManager:
    """Main manager for order operations"""
    
    def __init__(
            self,
            order_repository: OrderRepository,
            session_manager: SessionManager,
            exchange_client: ExchangeClient,
    ):
        """Initialize the order manager with dependencies"""
        # Create specialized managers
        self.order_repository = order_repository
        self.session_manager = session_manager

        self.record_manager = RecordManager(order_repository)
        self.exchange_manager = ExchangeManager(exchange_client)

        self.operation_manager = OperationManager(
            self.order_repository,
            self.session_manager,
            self.record_manager,
            self.exchange_manager
        )

    async def submit_orders(self, orders_data, user_id):
        """Submit orders in batch"""
        return await self.operation_manager.submit_orders(orders_data, user_id)
        
    async def cancel_orders(self, order_ids, user_id):
        """Cancel orders in batch"""
        return await self.operation_manager.cancel_orders(order_ids, user_id)
    
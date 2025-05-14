# source/api/rest/order_controller.py
import logging
from aiohttp import web

from source.api.rest.base_controller import BaseController

from source.core.state_manager import StateManager
from source.core.session_manager import SessionManager
from source.core.order_manager import OrderManager


logger = logging.getLogger('rest_controllers')

class OrderController(BaseController):
    """Controller for order-related REST endpoints"""

    def __init__(self,
                 state_manager: StateManager,
                 session_manager: SessionManager,
                 order_manager: OrderManager):
        """Initialize controller with dependencies"""
        super().__init__(session_manager)
        self.state_manager = state_manager
        self.order_manager = order_manager
        
    async def submit_orders(self, request: web.Request) -> web.Response:
        """
        Handle order submission endpoint - Only batch submission is supported
        """
        # Try to acquire the lock first
        acquired = await self.state_manager.acquire()
        if not acquired:
            return self.create_error_response("Service is currently busy. Please try again later.", 503)

        try:
            return await self._submit_orders(request)

        except Exception as e:
            logger.error(f"Error handling order submission: {e}")
            return self.create_error_response("Server error processing order")
        finally:
            # Always release the lock, even if there's an error
            await self.state_manager.release()

    async def cancel_orders(self, request: web.Request) -> web.Response:
        """
        Handle order cancellation endpoint - Only batch cancellation is supported
        """
        # Try to acquire the lock first
        acquired = await self.state_manager.acquire()
        if not acquired:
            return self.create_error_response("Service is currently busy. Please try again later.", 503)

        try:
            return await self._cancel_orders(request)

        except Exception as e:
            logger.error(f"Error handling order cancellation: {e}")
            return self.create_error_response("Server error processing cancellation")
        finally:
            # Always release the lock, even if there's an error
            await self.state_manager.release()


    async def _submit_orders(self, request: web.Request) -> web.Response:
        """
        Handle order submission endpoint - Only batch submission is supported
        """

        # Authenticate request
        auth_success, auth_result = await self.authenticate(request)
        if not auth_success:
            return self.create_error_response(auth_result["error"], auth_result["status"])

        user_id = auth_result["user_id"]
        logger.info(f"FOUND USER {user_id}")

        # Parse request body
        parse_success, data = await self.parse_json_body(request)
        if not parse_success:
            return self.create_error_response(data["error"], data["status"])

        # Extract orders array
        if not isinstance(data, dict) or 'orders' not in data or not isinstance(data['orders'], list):
            return self.create_error_response("Request must contain an 'orders' array", 400)

        orders = data['orders']
        if len(orders) == 0:
            return self.create_error_response("No orders provided", 400)

        # Process orders
        result = await self.order_manager.submit_orders(orders, user_id)
        return web.json_response(result)


    async def _cancel_orders(self, request: web.Request) -> web.Response:
        """
        Handle order cancellation endpoint - Only batch cancellation is supported
        """

        # Authenticate request
        auth_success, auth_result = await self.authenticate(request)
        if not auth_success:
            return self.create_error_response(auth_result["error"], auth_result["status"])

        user_id = auth_result["user_id"]

        # Parse request body
        parse_success, data = await self.parse_json_body(request)
        if not parse_success:
            return self.create_error_response(data["error"], data["status"])

        # Extract order_ids array
        if not isinstance(data, dict) or 'orderIds' not in data or not isinstance(data['orderIds'], list):
            return self.create_error_response("Request must contain an 'orderIds' array", 400)

        order_ids = data['orderIds']
        if len(order_ids) == 0:
            return self.create_error_response("No order IDs provided", 400)

        if len(order_ids) > 100:  # Set a reasonable limit
            return self.create_error_response("Too many orders. Maximum of 100 cancellations allowed per batch.",
                                              400)

        # Process cancellations
        result = await self.order_manager.cancel_orders(order_ids, user_id)
        return web.json_response(result)

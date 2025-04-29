import logging
import time
from typing import Dict, Any

from source.models.enums import OrderStatus
from source.core.validation_manager import ValidationManager
from source.core.record_manager import RecordManager
from source.core.exchange_manager import ExchangeManager
from source.utils.metrics import track_order_submission_latency

logger = logging.getLogger('operation_manager')

class OperationManager:
    """Manager for order operations that coordinates other managers"""

    def __init__(
        self, 
        validation_manager: ValidationManager,
        record_manager: RecordManager,
        exchange_manager: ExchangeManager
    ):
        self.validation_manager = validation_manager
        self.record_manager = record_manager
        self.exchange_manager = exchange_manager

    async def submit_order(self, order_data: Dict[str, Any], token: str) -> Dict[str, Any]:
        """
        Submit a new order - main entry point that coordinates the process
        
        Args:
            order_data: Order data
            token: Authentication token
            
        Returns:
            Submission result
        """
        start_time = time.time()

        # Extract key fields
        session_id = order_data.get('sessionId')
        device_id = order_data.get('deviceId')
        request_id = order_data.get('requestId')

        # 1. Validate authentication
        auth_validation = await self.validation_manager.validate_user_auth(token)
        if not auth_validation.get('valid'):
            error_msg = auth_validation.get('error', 'Invalid authentication')
            
            # Record submission failure
            duration = time.time() - start_time
            track_order_submission_latency(order_data.get('type', 'UNKNOWN'), False, duration)

            return {
                "success": False,
                "error": error_msg
            }

        user_id = auth_validation.get('user_id')

        # 2. Check for duplicate request
        if request_id:
            cached_response = await self.record_manager.check_duplicate_request(user_id, request_id)
            if cached_response:
                return cached_response

        # 3. Validate session and device ID
        session_validation = await self.validation_manager.validate_session(session_id, device_id)
        if not session_validation.get('valid'):
            error_msg = session_validation.get('error', 'Invalid session')
            
            response = {
                "success": False,
                "error": error_msg
            }
            await self.record_manager.cache_request_response(user_id, request_id, response)
            
            # Record submission failure
            duration = time.time() - start_time
            track_order_submission_latency(order_data.get('type', 'UNKNOWN'), False, duration)
            
            return response

        simulator_id = session_validation.get('simulator_id')
        simulator_endpoint = session_validation.get('simulator_endpoint')

        # 4. Validate order parameters
        order_validation = await self.validation_manager.validate_order_parameters(order_data)
        if not order_validation.get('valid'):
            error_msg = order_validation.get('error', 'Invalid order parameters')
            
            response = {
                "success": False,
                "error": error_msg
            }
            await self.record_manager.cache_request_response(user_id, request_id, response)
            
            # Record submission failure
            duration = time.time() - start_time
            track_order_submission_latency(order_data.get('type', 'UNKNOWN'), False, duration)
            
            return response

        # 5. Create and save order
        try:
            order = await self.record_manager.create_order(
                order_validation, user_id, session_id, device_id, request_id, simulator_id
            )
        except Exception as e:
            logger.error(f"Error creating order record: {e}")
            
            response = {
                "success": False,
                "error": f"Database error: {str(e)}",
                "orderId": None
            }
            await self.record_manager.cache_request_response(user_id, request_id, response)
            
            # Record submission failure
            duration = time.time() - start_time
            track_order_submission_latency(order_data.get('type', 'UNKNOWN'), False, duration)
            
            return response

        # 6. Check if we need to submit to exchange
        if not simulator_id or not simulator_endpoint:
            logger.info(f"Order {order.order_id} recorded but no active simulator for session {session_id}")
            
            response = {
                "success": True,
                "orderId": order.order_id,
                "notice": "Order recorded but not sent to simulator as no active simulator exists"
            }
            await self.record_manager.cache_request_response(user_id, request_id, response)

            # Record submission success (but not submitted to exchange)
            duration = time.time() - start_time
            track_order_submission_latency(order.order_type, True, duration)

            return response

        # 7. Submit to exchange
        exchange_result = await self.exchange_manager.submit_order_to_exchange(order, simulator_endpoint)
        
        if not exchange_result.get('success'):
            # Update order status to REJECTED
            order.status = OrderStatus.REJECTED
            order.error_message = exchange_result.get('error')
            await self.record_manager.update_order(order)

            response = {
                "success": False,
                "error": exchange_result.get('error'),
                "orderId": order.order_id
            }
            await self.record_manager.cache_request_response(user_id, request_id, response)

            # Record submission failure
            duration = time.time() - start_time
            track_order_submission_latency(order.order_type, False, duration)

            return response
            
        # 8. Update order if exchange assigned a different ID
        if exchange_result.get('original_order_id'):
            old_id = order.order_id
            order.order_id = exchange_result.get('order_id')
            await self.record_manager.update_order(order)
            logger.info(f"Updated order ID from {old_id} to {order.order_id}")

        # Record submission success
        duration = time.time() - start_time
        track_order_submission_latency(order.order_type, True, duration)

        # 9. Return success response
        response = {
            "success": True,
            "orderId": order.order_id
        }
        await self.record_manager.cache_request_response(user_id, request_id, response)

        return response

    async def cancel_order(self, order_id: str, session_id: str, device_id: str, token: str) -> Dict[str, Any]:
        """
        Cancel an existing order
        
        Args:
            order_id: Order ID to cancel
            session_id: Session ID
            device_id: Device ID
            token: Authentication token
            
        Returns:
            Cancellation result
        """
        # 1. Validate authentication
        auth_validation = await self.validation_manager.validate_user_auth(token)
        if not auth_validation.get('valid'):
            error_msg = auth_validation.get('error', 'Invalid authentication')
            return {
                "success": False,
                "error": error_msg
            }

        user_id = auth_validation.get('user_id')

        # 2. Validate session and device ID
        session_validation = await self.validation_manager.validate_session(session_id, device_id)
        if not session_validation.get('valid'):
            error_msg = session_validation.get('error', 'Invalid session')
            return {
                "success": False,
                "error": error_msg
            }

        simulator_endpoint = session_validation.get('simulator_endpoint')

        # 3. Get order from database
        try:
            order = await self.validation_manager.order_repository.get_order(order_id)

            if not order:
                logger.warning(f"Order {order_id} not found")
                return {
                    "success": False,
                    "error": "Order not found"
                }

            # Verify order belongs to user
            if order.user_id != user_id:
                logger.warning(f"Order {order_id} does not belong to user {user_id}")
                return {
                    "success": False,
                    "error": "Order does not belong to this user"
                }

            # Check if order can be canceled
            if order.status not in [OrderStatus.NEW, OrderStatus.PARTIALLY_FILLED]:
                logger.warning(f"Cannot cancel order {order_id} in state {order.status}")
                return {
                    "success": False,
                    "error": f"Cannot cancel order in state {order.status}"
                }

        except Exception as db_error:
            logger.error(f"Database error retrieving order: {db_error}")
            return {
                "success": False,
                "error": f"Database error: {str(db_error)}"
            }

        # 4. Check if we have an active simulator - if not, just update the order status
        if not simulator_endpoint:
            # Update order status directly
            order.status = OrderStatus.CANCELED
            success = await self.record_manager.update_order(order)

            if not success:
                return {
                    "success": False,
                    "error": "Failed to update order status"
                }

            return {
                "success": True,
                "notice": "Order canceled in database, but not in simulator (no active simulator)"
            }

        # 5. If we have a simulator, cancel order in exchange
        exchange_result = await self.exchange_manager.cancel_order_on_exchange(order, simulator_endpoint)

        if not exchange_result.get('success'):
            return {
                "success": False,
                "error": exchange_result.get('error', 'Failed to cancel order')
            }

        # 6. Update order status in database
        order.status = OrderStatus.CANCELED
        await self.record_manager.update_order(order)

        return {
            "success": True
        }
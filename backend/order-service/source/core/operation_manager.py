import logging
import time
import uuid
from typing import Dict, Any, List

from source.models.order import Order
from source.models.enums import OrderStatus, OrderSide, OrderType
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

    async def submit_orders(self, orders_data: List[Dict[str, Any]], user_id: str) -> Dict[str, Any]:
        """
        Submit orders in batch - first cancel existing open orders for the same symbols
        
        Args:
            orders_data: List of order data dictionaries
            user_id: User ID
            
        Returns:
            Batch submission result
        """
        start_time = time.time()
        
        # Extract all symbols from the new orders
        symbols = list(set(order.get('symbol') for order in orders_data if order.get('symbol')))
        
        # 1. Get simulator information for the user
        simulator = await self.validation_manager.order_repository.get_session_simulator(user_id)
        simulator_id = simulator.get('simulator_id') if simulator else None
        simulator_endpoint = simulator.get('endpoint') if simulator else None
        
        # 2. Find all open orders for these symbols
        open_orders = await self.record_manager.get_open_orders_by_symbol(user_id, symbols)
        open_order_ids = [order['order_id'] for order in open_orders]
        
        # 3. Cancel existing open orders first
        """
        if open_order_ids:
            logger.info(f"Cancelling {len(open_order_ids)} existing open orders for symbols {symbols}")
            
            # Create Order objects for cancellation
            orders_to_cancel = []
            for order_info in open_orders:
                dummy_order = Order(
                    order_id=order_info['order_id'],
                    user_id=user_id,
                    symbol=order_info['symbol'],
                    side=OrderSide.BUY,  # Placeholder
                    quantity=0,          # Placeholder
                    order_type=OrderType.MARKET  # Placeholder
                )
                orders_to_cancel.append(dummy_order)
                
            # Cancel on exchange if we have a simulator
            if simulator_endpoint:
                cancel_result = await self.exchange_manager.cancel_orders_on_exchange(
                    orders_to_cancel, simulator_endpoint
                )
                
                # Log the result but continue regardless
                if not cancel_result.get('success'):
                    logger.warning(f"Failed to cancel some existing orders: {cancel_result.get('errorMessage')}")
                    
            # Record cancellations in database
            for order_id in open_order_ids:
                await self.record_manager.save_order_status(
                    order_id, user_id, OrderStatus.CANCELED.value, "Cancelled due to new order submission"
                )
        """
        
        # 4. Extract request IDs for duplicate checking
        request_ids = [order.get('requestId') for order in orders_data if order.get('requestId')]
        
        # 5. Check all request IDs simultaneously
        duplicate_responses = {}
        if request_ids:
            duplicate_responses = await self.validation_manager.order_repository.check_duplicate_requests(
                user_id, request_ids
            )
        
        # 6. Process each order - validation and object creation (in memory)
        valid_orders = []
        results = []
        
        for i, order_data in enumerate(orders_data):
            # Check for duplicate request
            request_id = order_data.get('requestId')
            if request_id and request_id in duplicate_responses:
                cached_response = duplicate_responses[request_id]
                results.append({
                    **cached_response,
                    "index": i
                })
                continue
                
            # Validate order parameters
            order_validation = await self.validation_manager.validate_order_parameters(order_data)
            if not order_validation.get('valid'):
                error_msg = order_validation.get('error', 'Invalid order parameters')
                
                result = {
                    "success": False,
                    "errorMessage": error_msg,
                    "index": i
                }
                
                results.append(result)
                continue
                
            # Create order object (but don't save yet)
            try:
                order = Order(
                    symbol=order_validation.get('symbol'),
                    side=OrderSide(order_validation.get('side')),
                    quantity=order_validation.get('quantity'),
                    order_type=OrderType(order_validation.get('order_type')),
                    price=order_validation.get('price'),
                    user_id=user_id,
                    simulator_id=simulator_id,
                    request_id=request_id,
                    order_id=str(uuid.uuid4()),
                    status=OrderStatus.NEW.value,
                    created_at=time.time(),
                    updated_at=time.time()
                )
                
                valid_orders.append((order, i))
            except Exception as e:
                logger.error(f"Error creating order object: {e}")
                
                result = {
                    "success": False,
                    "errorMessage": f"Order parsing error: {str(e)}",
                    "index": i
                }
                
                results.append(result)
        
        # 7. Save all valid orders in a single batch operation
        if valid_orders:
            orders_to_save = [order for order, _ in valid_orders]
            save_result = await self.record_manager.save_orders(orders_to_save)
            
            # Add results for saved orders
            for order, idx in valid_orders:
                if order.order_id in save_result["successful"]:
                    results.append({
                        "success": True,
                        "orderId": order.order_id,
                        "index": idx
                    })
                else:
                    results.append({
                        "success": False,
                        "errorMessage": "Failed to save order to database",
                        "index": idx
                    })
        
        # 8. Submit to exchange if we have a simulator
        if simulator_endpoint and valid_orders:
            successful_order_ids = save_result.get("successful", [])
            orders_to_submit = [order for order, _ in valid_orders if order.order_id in successful_order_ids]
            
            if orders_to_submit:
                exchange_result = await self.exchange_manager.submit_orders_to_exchange(
                    orders_to_submit, simulator_endpoint
                )
                
                if not exchange_result.get('success'):
                    # All orders rejected by exchange - record new status
                    error_msg = exchange_result.get('errorMessage', 'Batch rejected by exchange')
                    
                    for order in orders_to_submit:
                        # Create new row with REJECTED status
                        await self.record_manager.save_order_status(
                            order.order_id, user_id, OrderStatus.REJECTED.value, error_msg
                        )
                        
                        # Update results
                        for j, res in enumerate(results):
                            if res.get('orderId') == order.order_id:
                                results[j] = {
                                    "success": False,
                                    "errorMessage": error_msg,
                                    "orderId": order.order_id,
                                    "index": res.get('index')
                                }
                else:
                    # You mentioned we can assume the exchange cannot reject orders,
                    # but I'm keeping minimal handling just in case
                    pass
        
        # 9. Record metrics
        duration = time.time() - start_time
        success_count = sum(1 for r in results if r.get('success', False))
        track_order_submission_latency("batch", success_count > 0, duration)
        
        # 10. Return final results sorted by original index
        sorted_results = sorted(results, key=lambda x: x.get('index', 0))
        return {
            "success": True,  # Overall request processed
            "results": [
                {
                    "success": r.get('success', False),
                    "orderId": r.get('orderId'),
                    "errorMessage": r.get('errorMessage')
                }
                for r in sorted_results
            ]
        }

    async def cancel_orders(self, order_ids: List[str], user_id: str) -> Dict[str, Any]:
        """
        Cancel orders in batch
        
        Args:
            order_ids: List of order IDs to cancel
            user_id: User ID
            
        Returns:
            Batch cancellation result
        """
        start_time = time.time()
        
        # 1. Get simulator information for the user
        simulator = await self.validation_manager.order_repository.get_session_simulator(user_id)
        simulator_endpoint = simulator.get('endpoint') if simulator else None
        
        # 2. Get all order information in a single query
        order_info_list = await self.record_manager.get_orders_info(order_ids)
        
        # Create mapping of order_id to info
        order_info_map = {info['order_id']: info for info in order_info_list}
        
        # 3. Validate orders and categorize them
        results = []
        valid_orders = []
        
        for i, order_id in enumerate(order_ids):
            # Check if order exists and belongs to user
            if order_id not in order_info_map:
                results.append({
                    "orderId": order_id,
                    "success": False,
                    "errorMessage": "Order not found",
                    "index": i
                })
                continue
                
            info = order_info_map[order_id]
            
            if info['user_id'] != user_id:
                results.append({
                    "orderId": order_id,
                    "success": False,
                    "errorMessage": "Order does not belong to this user",
                    "index": i
                })
                continue
                
            # Order is valid for cancellation regardless of status
            # Create minimal Order object for the exchange client
            order = Order(
                order_id=order_id,
                user_id=user_id,
                symbol="",  # Placeholder, not needed for cancellation
                side=OrderSide.BUY,  # Placeholder, not needed for cancellation
                quantity=0,  # Placeholder, not needed for cancellation
                order_type=OrderType.MARKET  # Placeholder, not needed for cancellation
            )
            
            valid_orders.append((order, i))
        
        # 4. Cancel orders on exchange if we have a simulator
        if simulator_endpoint and valid_orders:
            orders = [order for order, _ in valid_orders]
            
            exchange_result = await self.exchange_manager.cancel_orders_on_exchange(orders, simulator_endpoint)
            
            # Process individual results
            if exchange_result.get('success'):
                exchange_results = exchange_result.get('results', [])
                
                for i, ex_result in enumerate(exchange_results):
                    if i < len(valid_orders):
                        order, idx = valid_orders[i]
                        
                        if ex_result.get('success'):
                            # Create new row with CANCELED status
                            success = await self.record_manager.save_order_status(
                                order.order_id, user_id, OrderStatus.CANCELED.value
                            )
                            
                            results.append({
                                "orderId": order.order_id,
                                "success": success,
                                "index": idx
                            })
                        else:
                            error_msg = ex_result.get('errorMessage', 'Failed to cancel on exchange')
                            
                            results.append({
                                "orderId": order.order_id,
                                "success": False,
                                "errorMessage": error_msg,
                                "index": idx
                            })
            else:
                # Batch cancellation failed on exchange
                error_msg = exchange_result.get('errorMessage', 'Batch cancellation failed')
                
                for order, idx in valid_orders:
                    results.append({
                        "orderId": order.order_id,
                        "success": False,
                        "errorMessage": error_msg,
                        "index": idx
                    })
        elif valid_orders:
            # No simulator - just mark orders as canceled in database
            for order, idx in valid_orders:
                # Create new row with CANCELED status
                success = await self.record_manager.save_order_status(
                    order.order_id, user_id, OrderStatus.CANCELED.value
                )
                
                results.append({
                    "orderId": order.order_id,
                    "success": success,
                    "index": idx
                })
        
        # 5. Record metrics
        duration = time.time() - start_time
        success_count = sum(1 for r in results if r.get('success', False))
        track_order_submission_latency("batch_cancel", success_count > 0, duration)
        
        # 6. Return final results sorted by original index
        sorted_results = sorted(results, key=lambda x: x.get('index', 0))
        return {
            "success": True,  # Overall request processed
            "results": [
                {
                    "success": r.get('success', False),
                    "orderId": r.get('orderId'),
                    "errorMessage": r.get('errorMessage')
                }
                for r in sorted_results
            ]
        }

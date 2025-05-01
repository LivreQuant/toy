import logging
import time
from typing import Dict, Any, List

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

        
    async def submit_orders(self, orders_data: List[Dict[str, Any]], user_id: str) -> Dict[str, Any]:
        """
        Submit orders in batch - this is the only order submission method
        
        Args:
            orders_data: List of order data dictionaries
            user_id: User ID
            
        Returns:
            Batch submission result
        """
        start_time = time.time()
        
        # 1. Get simulator information for the user
        simulator = await self.validation_manager.order_repository.get_session_simulator(user_id)
        simulator_id = simulator.get('simulator_id') if simulator else None
        simulator_endpoint = simulator.get('endpoint') if simulator else None
        
        # 2. Validate and create all orders
        parsed_orders = []
        results = []
        
        for i, order_data in enumerate(orders_data):
            # Extract request_id for idempotency
            request_id = order_data.get('requestId')
            
            # Check for duplicate request using PostgreSQL
            if request_id:
                cached_response = await self.record_manager.check_duplicate_request(user_id, request_id)
                if cached_response:
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
                
                # Store the response in PostgreSQL for idempotency if request_id provided
                if request_id:
                    await self.record_manager.cache_request_response(user_id, request_id, result)
                    
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
                    created_at=time.time(),
                    updated_at=time.time()
                )
                
                parsed_orders.append((order, i))  # Store order with original index
            except Exception as e:
                logger.error(f"Error creating order object: {e}")
                
                result = {
                    "success": False,
                    "errorMessage": f"Order parsing error: {str(e)}",
                    "index": i
                }
                
                # Store the response in PostgreSQL for idempotency
                if request_id:
                    await self.record_manager.cache_request_response(user_id, request_id, result)
                    
                results.append(result)
                
        # 3. Save all orders in a batch
        if parsed_orders:
            orders_to_save = [order for order, _ in parsed_orders]
            save_result = await self.order_repository.save_orders(orders_to_save)
            
            # Create placeholder results for saved orders
            for order, idx in parsed_orders:
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
        
        # 4. Submit to exchange if we have a simulator
        if simulator_endpoint and parsed_orders:
            valid_orders = [order for order, _ in parsed_orders if order.order_id in save_result["successful"]]
            
            if valid_orders:
                exchange_result = await self.exchange_manager.submit_orders_to_exchange(valid_orders, simulator_endpoint)
                
                # Update orders in database based on exchange response
                if exchange_result.get('success'):
                    exchange_results = exchange_result.get('results', [])
                    
                    # Update each order with its result
                    for i, ex_result in enumerate(exchange_results):
                        if i < len(valid_orders):
                            order = valid_orders[i]
                            
                            if not ex_result.get('success'):
                                # Update order status to REJECTED
                                order.status = OrderStatus.REJECTED
                                order.error_message = ex_result.get('errorMessage')
                                await self.order_repository.save_order(order)
                                
                                # Update the corresponding result
                                for j, res in enumerate(results):
                                    if res.get('orderId') == order.order_id:
                                        results[j] = {
                                            "success": False,
                                            "errorMessage": ex_result.get('errorMessage', 'Rejected by exchange'),
                                            "orderId": order.order_id,
                                            "index": res.get('index')
                                        }
                else:
                    # All orders were rejected by the exchange
                    error_msg = exchange_result.get('errorMessage', 'Batch rejected by exchange')
                    
                    # Update all orders to REJECTED
                    for order in valid_orders:
                        order.status = OrderStatus.REJECTED
                        order.error_message = error_msg
                        await self.order_repository.save_order(order)
                        
                        # Update the corresponding result
                        for j, res in enumerate(results):
                            if res.get('orderId') == order.order_id:
                                results[j] = {
                                    "success": False,
                                    "errorMessage": error_msg,
                                    "orderId": order.order_id,
                                    "index": res.get('index')
                                }
        
        # 5. Record metrics
        duration = time.time() - start_time
        success_count = sum(1 for r in results if r.get('success', False))
        track_order_submission_latency("batch", success_count > 0, duration)
        
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
    
        
    async def cancel_orders(self, order_ids: List[str], user_id: str) -> Dict[str, Any]:
        """
        Cancel orders in batch - this is the only cancellation method
        
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
        
        # 2. Validate all orders
        results = []
        valid_orders = []
        
        for i, order_id in enumerate(order_ids):
            # Check if order exists and belongs to user
            try:
                order = await self.order_repository.get_order(order_id)
                
                if not order:
                    results.append({
                        "orderId": order_id,
                        "success": False,
                        "errorMessage": "Order not found",
                        "index": i
                    })
                    continue
                    
                if order.user_id != user_id:
                    results.append({
                        "orderId": order_id,
                        "success": False,
                        "errorMessage": "Order does not belong to this user",
                        "index": i
                    })
                    continue
                    
                # Check if order can be canceled
                if order.status not in [OrderStatus.NEW, OrderStatus.PARTIALLY_FILLED]:
                    results.append({
                        "orderId": order_id,
                        "success": False,
                        "errorMessage": f"Cannot cancel order in state {order.status}",
                        "index": i
                    })
                    continue
                    
                # Order is valid for cancellation
                valid_orders.append((order, i))
                
            except Exception as e:
                logger.error(f"Error validating order {order_id}: {e}")
                results.append({
                    "orderId": order_id,
                    "success": False,
                    "errorMessage": f"Database error: {str(e)}",
                    "index": i
                })
        
        # 3. Cancel orders on exchange if we have a simulator
        if simulator_endpoint and valid_orders:
            orders = [order for order, _ in valid_orders]
            exchange_result = await self.exchange_manager.cancel_orders_on_exchange(orders, simulator_endpoint)
            
            if exchange_result.get('success'):
                exchange_results = exchange_result.get('results', [])
                
                # Process individual results
                for i, ex_result in enumerate(exchange_results):
                    if i < len(valid_orders):
                        order, idx = valid_orders[i]
                        
                        if ex_result.get('success'):
                            # Update order status
                            order.status = OrderStatus.CANCELED
                            await self.order_repository.save_order(order)
                            
                            results.append({
                                "orderId": order.order_id,
                                "success": True,
                                "index": idx
                            })
                        else:
                            results.append({
                                "orderId": order.order_id,
                                "success": False,
                                "errorMessage": ex_result.get('errorMessage', 'Failed to cancel on exchange'),
                                "index": idx
                            })
            else:
                # Batch cancellation failed
                error_msg = exchange_result.get('errorMessage', 'Batch cancellation failed')
                
                for order, idx in valid_orders:
                    results.append({
                        "orderId": order.order_id,
                        "success": False,
                        "errorMessage": error_msg,
                        "index": idx
                    })
        else if valid_orders:
            # No simulator - just mark orders as canceled in database
            for order, idx in valid_orders:
                order.status = OrderStatus.CANCELED
                await self.order_repository.save_order(order)
                
                results.append({
                    "orderId": order.order_id,
                    "success": True,
                    "index": idx
                })
        
        # 4. Record metrics
        duration = time.time() - start_time
        success_count = sum(1 for r in results if r.get('success', False))
        track_order_cancellation_latency("batch", success_count > 0, duration)
        
        # 5. Return final results sorted by original index
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
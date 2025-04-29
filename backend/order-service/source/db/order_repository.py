import logging
import time
from typing import List, Optional, Dict, Any

from source.db.connection_pool import DatabasePool
from source.models.order import Order
from source.models.enums import OrderStatus
from source.utils.metrics import track_db_operation

logger = logging.getLogger('order_repository')


class OrderRepository:
    """Data access layer for orders"""

    def __init__(self):
        """Initialize the order repository"""
        self.db_pool = DatabasePool()

    async def save_order(self, order: Order) -> bool:
        """Save a new order or update existing order"""
        pool = await self.db_pool.get_pool()

        query = """
        INSERT INTO trading.orders (
            order_id, user_id, session_id, symbol, side, quantity, price, 
            order_type, status, filled_quantity, avg_price, simulator_id,
            created_at, updated_at, request_id, error_message, device_id
        ) VALUES (
            $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, 
            to_timestamp($13), to_timestamp($14), $15, $16, $17
        )
        ON CONFLICT (order_id) DO UPDATE SET
            status = EXCLUDED.status,
            filled_quantity = EXCLUDED.filled_quantity,
            avg_price = EXCLUDED.avg_price,
            updated_at = EXCLUDED.updated_at,
            error_message = EXCLUDED.error_message
        """

        try:
            start_time = time.time()

            async with pool.acquire() as conn:
                await conn.execute(
                    query,
                    order.order_id,
                    order.user_id,
                    order.session_id,
                    order.symbol,
                    order.side.value,
                    order.quantity,
                    order.price,
                    order.order_type.value,
                    order.status.value,
                    order.filled_quantity,
                    order.avg_price,
                    order.simulator_id,
                    order.created_at,
                    order.updated_at,
                    order.request_id,
                    order.error_message,
                    order.device_id
                )
                duration = time.time() - start_time
                track_db_operation("save_order", True, duration)
                return True
        except Exception as e:
            duration = time.time() - start_time
            track_db_operation("save_order", False, duration)
            logger.error(f"Error saving order: {e}")
            return False

    async def get_order(self, order_id: str) -> Optional[Order]:
        """Get an order by ID"""
        pool = await self.db_pool.get_pool()

        query = """
        SELECT 
            order_id, user_id, session_id, symbol, side, quantity, price, 
            order_type, status, filled_quantity, avg_price, simulator_id,
            EXTRACT(EPOCH FROM created_at) as created_at, 
            EXTRACT(EPOCH FROM updated_at) as updated_at, 
            request_id, error_message, device_id
        FROM trading.orders
        WHERE order_id = $1
        """

        try:
            start_time = time.time()

            async with pool.acquire() as conn:
                row = await conn.fetchrow(query, order_id)

                duration = time.time() - start_time
                success = row is not None
                track_db_operation("get_order", success, duration)

                if not row:
                    return None

                # Convert row to dict
                order_dict = dict(row)

                # Create order object
                return Order.from_dict(order_dict)
        except Exception as e:
            duration = time.time() - start_time
            track_db_operation("get_order", False, duration)
            logger.error(f"Error retrieving order: {e}")
            return None

    async def get_user_orders(self, user_id: str, limit: int = 50, offset: int = 0) -> List[Order]:
        """Get orders for a specific user"""
        pool = await self.db_pool.get_pool()

        query = """
        SELECT 
            order_id, user_id, session_id, symbol, side, quantity, price, 
            order_type, status, filled_quantity, avg_price, simulator_id,
            EXTRACT(EPOCH FROM created_at) as created_at, 
            EXTRACT(EPOCH FROM updated_at) as updated_at, 
            request_id, error_message, device_id
        FROM trading.orders
        WHERE user_id = $1
        ORDER BY created_at DESC
        LIMIT $2 OFFSET $3
        """

        try:
            start_time = time.time()

            async with pool.acquire() as conn:
                rows = await conn.fetch(query, user_id, limit, offset)

                orders = []
                for row in rows:
                    # Convert row to dict
                    order_dict = dict(row)

                    # Create order object
                    orders.append(Order.from_dict(order_dict))

                duration = time.time() - start_time
                track_db_operation("get_user_orders", True, duration)
                return orders
        except Exception as e:
            duration = time.time() - start_time
            track_db_operation("get_user_orders", False, duration)
            logger.error(f"Error retrieving user orders: {e}")
            return []

    async def validate_device_id(self, session_id: str, device_id: str) -> bool:
        """Validate if the device ID is associated with the session directly from database"""
        pool = await self.db_pool.get_pool()

        query = """
        SELECT 1 FROM session.session_details
        WHERE session_id = $1 AND device_id = $2
        """

        try:
            start_time = time.time()

            async with pool.acquire() as conn:
                row = await conn.fetchrow(query, session_id, device_id)

                duration = time.time() - start_time
                valid = row is not None
                track_db_operation("validate_device_id", valid, duration)

                return valid
        except Exception as e:
            duration = time.time() - start_time
            track_db_operation("validate_device_id", False, duration)
            logger.error(f"Error validating device ID: {e}")
            return False

    async def get_session_simulator(self, session_id: str) -> Dict[str, Any]:
        """Get simulator information for a session directly from database"""
        pool = await self.db_pool.get_pool()

        query = """
        SELECT simulator_id, endpoint, status
        FROM simulator.instances
        WHERE session_id = $1 AND status IN ('RUNNING', 'STARTING')
        ORDER BY created_at DESC
        LIMIT 1
        """

        try:
            start_time = time.time()

            async with pool.acquire() as conn:
                row = await conn.fetchrow(query, session_id)

                duration = time.time() - start_time
                track_db_operation("get_session_simulator", row is not None, duration)

                if not row:
                    return None

                return dict(row)
        except Exception as e:
            duration = time.time() - start_time
            track_db_operation("get_session_simulator", False, duration)
            logger.error(f"Error getting session simulator: {e}")
            return None

    async def update_order_status(self, order_id: str, status: OrderStatus,
                                  filled_quantity: Optional[float] = None,
                                  avg_price: Optional[float] = None,
                                  error_message: Optional[str] = None) -> bool:
        """Update an order's status"""
        pool = await self.db_pool.get_pool()

        # Build dynamic update query
        query_parts = ["UPDATE trading.orders SET status = $1"]
        params = [status.value]

        param_idx = 2
        if filled_quantity is not None:
            query_parts.append(f"filled_quantity = ${param_idx}")
            params.append(filled_quantity)
            param_idx += 1

        if avg_price is not None:
            query_parts.append(f"avg_price = ${param_idx}")
            params.append(avg_price)
            param_idx += 1

        if error_message is not None:
            query_parts.append(f"error_message = ${param_idx}")
            params.append(error_message)
            param_idx += 1

        query_parts.append(f"updated_at = NOW()")
        query_parts.append(f"WHERE order_id = ${param_idx}")
        params.append(order_id)

        query = " ".join(query_parts)

        try:
            start_time = time.time()

            async with pool.acquire() as conn:
                result = await conn.execute(query, *params)
                success = "UPDATE 1" in result

                duration = time.time() - start_time
                track_db_operation("update_order_status", success, duration)
                return success
        except Exception as e:
            duration = time.time() - start_time
            track_db_operation("update_order_status", False, duration)
            logger.error(f"Error updating order status: {e}")
            return False

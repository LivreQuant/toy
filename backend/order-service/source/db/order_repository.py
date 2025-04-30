import logging
import time
from typing import Dict, Any

from source.db.connection_pool import DatabasePool
from source.models.order import Order
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
            order_id, user_id, symbol, side, quantity, price, 
            order_type, status, filled_quantity, avg_price, simulator_id,
            created_at, updated_at, request_id, error_message
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

        start_time = time.time()
        try:

            async with pool.acquire() as conn:
                await conn.execute(
                    query,
                    order.order_id,
                    order.user_id,
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
                )
                duration = time.time() - start_time
                track_db_operation("save_order", True, duration)
                return True
        except Exception as e:
            duration = time.time() - start_time
            track_db_operation("save_order", False, duration)
            logger.error(f"Error saving order: {e}")
            return False

    async def validate_device_id(self, device_id: str) -> bool:
        """Validate if the device ID is associated with the session directly from database"""
        pool = await self.db_pool.get_pool()

        query = """
        SELECT 1 FROM session.session_details
        WHERE device_id = $2
        """

        start_time = time.time()
        try:

            async with pool.acquire() as conn:
                row = await conn.fetchrow(query, device_id)

                duration = time.time() - start_time
                valid = row is not None
                track_db_operation("validate_device_id", valid, duration)

                return valid
        except Exception as e:
            duration = time.time() - start_time
            track_db_operation("validate_device_id", False, duration)
            logger.error(f"Error validating device ID: {e}")
            return False

    async def get_session_simulator(self, user_id: str) -> Dict[str, Any]:
        """Get simulator information for a user directly from database"""
        pool = await self.db_pool.get_pool()

        query = """
        SELECT simulator_id, endpoint, status
        FROM simulator.instances
        WHERE user_id = $1 
        AND status IN ('RUNNING')
        ORDER BY created_at DESC
        LIMIT 1
        """

        try:
            async with pool.acquire() as conn:
                row = await conn.fetchrow(query, user_id)
                if not row:
                    return None
                return dict(row)
        except Exception as e:
            logger.error(f"Error getting user simulator: {e}")
            return None

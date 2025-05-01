import logging
import time
import json
from typing import Dict, Any, List, Optional

from source.db.connection_pool import DatabasePool
from source.models.order import Order
from source.utils.metrics import track_db_operation


logger = logging.getLogger('order_repository')


class OrderRepository:
    """Data access layer for orders"""

    def __init__(self):
        """Initialize the order repository"""
        self.db_pool = DatabasePool()
        
    async def save_orders(self, orders: List[Order]) -> Dict[str, List[str]]:
        """
        Save multiple orders in a batch
        
        Returns:
            Dict with successful and failed order IDs
        """
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
        
        successful_order_ids = []
        failed_order_ids = []
        
        start_time = time.time()
        try:
            async with pool.acquire() as conn:
                # Start a transaction
                async with conn.transaction():
                    for order in orders:
                        try:
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
                            successful_order_ids.append(order.order_id)
                        except Exception as order_error:
                            logger.error(f"Error saving order {order.order_id}: {order_error}")
                            failed_order_ids.append(order.order_id)
                    
                    duration = time.time() - start_time
                    track_db_operation("save_orders_batch", True, duration)
                    
                    return {
                        "successful": successful_order_ids,
                        "failed": failed_order_ids
                    }
        except Exception as e:
            duration = time.time() - start_time
            track_db_operation("save_orders_batch", False, duration)
            logger.error(f"Error batch saving orders: {e}")
            
            return {
                "successful": successful_order_ids,
                "failed": failed_order_ids if failed_order_ids else [o.order_id for o in orders]
            }

    async def validate_device_id(self, device_id: str) -> bool:
        """Validate if the device ID is associated with the session directly from database"""
        if not device_id:
            return False
            
        pool = await self.db_pool.get_pool()

        query = """
        SELECT 1 FROM session.session_details
        WHERE device_id = $1
        """

        start_time = time.time()
        try:
            async with pool.acquire() as conn:
                # Cast the parameter to text explicitly
                row = await conn.fetchrow(query, str(device_id))

                duration = time.time() - start_time
                valid = row is not None
                track_db_operation("validate_device_id", valid, duration)

                return valid
        except Exception as e:
            duration = time.time() - start_time
            track_db_operation("validate_device_id", False, duration)
            logger.error(f"Error validating device ID: {e}")
            
            # For development purposes, temporarily skip device ID validation
            # REMOVE THIS IN PRODUCTION!
            logger.warning("⚠️ Skipping device ID validation due to database error")
            return True  # Temporarily return True to bypass the check

    async def check_duplicate_request(self, user_id: str, request_id: str) -> Optional[Dict[str, Any]]:
        """
        Check if this is a duplicate request and return cached response if it is
        
        Args:
            user_id: User ID
            request_id: Request ID
            
        Returns:
            Cached response if duplicate, None otherwise
        """
        if not request_id:
            return None

        try:
            pool = await self.db_pool.get_pool()
            async with pool.acquire() as conn:
                query = """
                SELECT response FROM trading.orders
                WHERE request_id = $1 AND user_id = $2
                """
                row = await conn.fetchrow(query, request_id, user_id)
                
                if row:
                    logger.info(f"Returning cached response for duplicate request {request_id}")
                    return json.loads(row['response'])
                return None
        except Exception as e:
            logger.error(f"Error checking duplicate request: {e}")
            return None

    async def cache_request_response(self, user_id: str, request_id: str, response: Dict[str, Any]) -> None:
        """
        Cache a response for a request ID in PostgreSQL
        
        Args:
            user_id: User ID
            request_id: Request ID
            response: Response to cache
        """
        if not request_id:
            return

        try:
            pool = await self.db_pool.get_pool()
            async with pool.acquire() as conn:
                query = """
                INSERT INTO trading.request_idempotency (request_id, user_id, response)
                VALUES ($1, $2, $3)
                ON CONFLICT (request_id, user_id) DO UPDATE
                SET response = $3
                """
                await conn.execute(query, request_id, user_id, json.dumps(response))
        except Exception as e:
            logger.error(f"Error caching request response: {e}")
        
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

import logging
import time
import uuid
import json
from typing import Dict, Any, Optional

from source.models.order import Order
from source.db.order_repository import OrderRepository
from source.utils.metrics import track_order_created, track_user_order

logger = logging.getLogger('record_manager')


class RecordManager:
    """Manager for recording orders and tracking request duplicates"""

    def __init__(
            self,
            order_repository: OrderRepository
    ):
        self.order_repository = order_repository

    async def check_duplicate_request(self, user_id: str, request_id: str) -> Optional[Dict[str, Any]]:
        """
        Check if this is a duplicate request and return cached response from PostgreSQL if it is
        
        Args:
            user_id: User ID
            request_id: Request ID
            
        Returns:
            Cached response if duplicate, None otherwise
        """
        if not request_id:
            return None

        try:
            pool = await self.order_repository.db_pool.get_pool()
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
            pool = await self.order_repository.db_pool.get_pool()
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

    async def cleanup_old_requests(self) -> None:
        """
        Clean up old request records 
        This method should be called periodically, e.g., via a scheduled task
        """
        try:
            pool = await self.order_repository.db_pool.get_pool()
            async with pool.acquire() as conn:
                query = """
                DELETE FROM trading.request_idempotency
                WHERE created_at < NOW() - INTERVAL '1 day'
                """
                result = await conn.execute(query)
                logger.info(f"Cleaned up old request records: {result}")
        except Exception as e:
            logger.error(f"Error cleaning up old requests: {e}")

    async def save_order(self, order_params: Dict[str, Any], user_id: str,
                           request_id: str = None,
                           simulator_id: str = None) -> Order:
        """
        Create a new order object and save it to database
        
        Args:
            order_params: Validated order parameters
            user_id: User ID
            request_id: Optional request ID for idempotency
            simulator_id: Optional simulator ID
            
        Returns:
            New Order object
        """
        # Create order object with a new UUID
        order = Order(
            symbol=order_params.get('symbol'),
            side=order_params.get('side'),
            quantity=order_params.get('quantity'),
            order_type=order_params.get('order_type'),
            price=order_params.get('price'),
            user_id=user_id,
            request_id=request_id,
            order_id=str(uuid.uuid4()),  # Generate new order ID
            created_at=time.time(),
            updated_at=time.time(),
            simulator_id=simulator_id
        )

        # Track order creation metrics
        track_order_created(order.order_type, order.symbol, order.side)
        track_user_order(user_id)

        # Save to database
        success = await self.order_repository.save_order(order)
        if not success:
            logger.error(f"Failed to save order {order.order_id} to database")
            raise Exception("Database error: Failed to save order")

        logger.info(f"Successfully created and saved order {order.order_id}")
        return order

    
import logging
import time
import uuid
from typing import Dict, Any, Optional
import asyncio

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

        # Track request IDs to detect duplicates
        self.recently_processed = {}
        self._cache_lock = asyncio.Lock()  # For thread-safe cache operations

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

        # Check cache in a thread-safe way
        async with self._cache_lock:
            # Check cache
            request_key = f"{user_id}:{request_id}"
            cached = self.recently_processed.get(request_key)

            if cached:
                # Return cached response for duplicate
                logger.info(f"Returning cached response for duplicate request {request_id}")
                return cached['response']

        # Clean up old cache entries
        await self._cleanup_old_request_ids()
        return None

    async def _cleanup_old_request_ids(self):
        """Clean up old request IDs from cache"""
        async with self._cache_lock:
            current_time = time.time()
            expiry = 300  # 5 minutes

            # Remove entries older than expiry time
            keys_to_remove = []
            for key, entry in self.recently_processed.items():
                if current_time - entry['timestamp'] > expiry:
                    keys_to_remove.append(key)

            for key in keys_to_remove:
                del self.recently_processed[key]

    async def cache_request_response(self, user_id: str, request_id: str, response: Dict[str, Any]):
        """Cache a response for a request ID"""
        if not request_id:
            return

        async with self._cache_lock:
            request_key = f"{user_id}:{request_id}"
            self.recently_processed[request_key] = {
                'timestamp': time.time(),
                'response': response
            }

    async def create_order(self, order_params: Dict[str, Any], user_id: str,
                           session_id: str, device_id: str, request_id: str = None,
                           simulator_id: str = None) -> Order:
        """
        Create a new order object and save it to database
        
        Args:
            order_params: Validated order parameters
            user_id: User ID
            session_id: Session ID
            device_id: Device ID
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
            session_id=session_id,
            device_id=device_id,
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

    async def update_order(self, order: Order) -> bool:
        """
        Update an existing order in the database
        
        Args:
            order: Order to update
            
        Returns:
            True if successful
        """
        order.updated_at = time.time()
        return await self.order_repository.save_order(order)

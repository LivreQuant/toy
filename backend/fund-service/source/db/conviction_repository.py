# source/db/order_repository.py
import logging
import time
import uuid
from typing import Dict, Any, List, Optional

from source.db.connection_pool import DatabasePool
from source.models.conviction import ConvictionData

from source.utils.metrics import track_db_operation, track_order_created, track_user_order


logger = logging.getLogger('order_repository')


class OrderRepository:
    """Data access layer for orders"""

    def __init__(self):
        """Initialize the order repository"""
        self.db_pool = DatabasePool()
        
    async def save_orders(self, orders: List[ConvictionData]) -> Dict[str, List[str]]:
        """
        Save multiple orders in a batch
        
        Returns:
            Dict with successful and failed order IDs
        """
        pool = await self.db_pool.get_pool()
        
        # Query exactly matching the schema
        query = """
        INSERT INTO trading.orders (
            order_id, user_id, symbol, side, quantity, price, 
            order_type, status, filled_quantity, avg_price,
            created_at, updated_at, request_id, error_message
        ) VALUES (
            $1, $2, $3, $4, $5, $6, $7, $8, $9, $10,
            to_timestamp($11), to_timestamp($12), $13, $14
        )
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
                                order.created_at,
                                order.updated_at,
                                order.request_id,
                                order.error_message
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

    async def check_duplicate_requests(self, user_id: str, request_ids: List[str]) -> Dict[str, Dict[str, Any]]:
        """
        Check multiple request IDs for duplicates in a single query
        
        Args:
            user_id: User ID
            request_ids: List of request IDs to check
            
        Returns:
            Dictionary mapping request_id to cached response
        """
        if not request_ids:
            return {}

        try:
            pool = await self.db_pool.get_pool()
            async with pool.acquire() as conn:
                # Check for duplicate request_ids
                query = """
                SELECT DISTINCT ON (request_id) 
                    request_id, order_id, status, created_at
                FROM trading.orders
                WHERE user_id = $1 AND request_id = ANY($2::text[]) AND request_id IS NOT NULL
                ORDER BY request_id, created_at DESC
                """
                rows = await conn.fetch(query, user_id, request_ids)
                
                # Create mapping of request_id to basic response structure
                results = {}
                for row in rows:
                    results[row['request_id']] = {
                        "success": True,
                        "orderId": row['order_id'],
                        "message": f"Order previously submitted with status: {row['status']}"
                    }
                    
                return results
        except Exception as e:
            logger.error(f"Error checking duplicate requests: {e}")
            return {}

    async def check_duplicate_request(self, user_id: str, request_id: str) -> Optional[Dict[str, Any]]:
        """
        Check if this is a duplicate request
        
        Args:
            user_id: User ID
            request_id: Request ID
            
        Returns:
            Response information if duplicate, None otherwise
        """
        if not request_id:
            return None

        try:
            pool = await self.db_pool.get_pool()
            async with pool.acquire() as conn:
                query = """
                SELECT order_id, status FROM trading.orders
                WHERE request_id = $1 AND user_id = $2
                ORDER BY created_at DESC
                LIMIT 1
                """
                row = await conn.fetchrow(query, request_id, user_id)
                
                if row:
                    logger.info(f"Found duplicate request {request_id}")
                    return {
                        "success": True,
                        "orderId": row['order_id'],
                        "message": f"Order previously submitted with status: {row['status']}"
                    }
                return None
        except Exception as e:
            logger.error(f"Error checking duplicate request: {e}")
            return None
      
    async def save_order(self, order: ConvictionData) -> bool:
        """Save a single order to the database"""
        pool = await self.db_pool.get_pool()
        
        query = """
        INSERT INTO trading.orders (
            order_id, user_id, symbol, side, quantity, price, 
            order_type, status, filled_quantity, avg_price,
            created_at, updated_at, request_id, error_message
        ) VALUES (
            $1, $2, $3, $4, $5, $6, $7, $8, $9, $10,
            to_timestamp($11), to_timestamp($12), $13, $14
        )
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
                    order.created_at,
                    order.updated_at,
                    order.request_id,
                    order.error_message
                )
                
                duration = time.time() - start_time
                track_db_operation("save_order", True, duration)
                
                # Track order creation metrics
                track_order_created(order.order_type, order.symbol, order.side)
                track_user_order(order.user_id)
                
                return True
        except Exception as e:
            duration = time.time() - start_time
            track_db_operation("save_order", False, duration)
            logger.error(f"Error saving order {order.order_id}: {e}")
            return False
            
    async def save_order_status(self, order_id: str, user_id: str, status: str, error_message: str = None) -> bool:
        """
        Create a new row with updated status for an order
        
        Args:
            order_id: Order ID
            user_id: User ID
            status: New status
            error_message: Optional error message
            
        Returns:
            Success flag
        """
        try:
            pool = await self.db_pool.get_pool()
            async with pool.acquire() as conn:
                # First get the current order data
                query_select = """
                WITH latest_order AS (
                    SELECT * FROM trading.orders 
                    WHERE order_id = $1 
                    ORDER BY created_at DESC 
                    LIMIT 1
                )
                SELECT * FROM latest_order
                """
                
                order_data = await conn.fetchrow(query_select, order_id)
                
                if not order_data:
                    logger.error(f"Order not found: {order_id}")
                    return False
                    
                # Insert new row with updated status
                query_insert = """
                INSERT INTO trading.orders (
                    order_id, status, user_id, symbol, side, quantity, price, 
                    order_type, filled_quantity, avg_price, created_at, updated_at, 
                    request_id, error_message
                ) VALUES (
                    $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, 
                    to_timestamp($11), to_timestamp($12), $13, $14
                )
                """
                
                now = time.time()
                
                await conn.execute(
                    query_insert,
                    order_id,
                    status,
                    order_data['user_id'],
                    order_data['symbol'],
                    order_data['side'],
                    order_data['quantity'],
                    order_data['price'],
                    order_data['order_type'],
                    order_data['filled_quantity'],
                    order_data['avg_price'],
                    now,
                    now,
                    order_data['request_id'],
                    error_message or order_data['error_message']
                )
                
                return True
                
        except Exception as e:
            logger.error(f"Error saving order status: {e}")
            return False
    
    async def batch_save_order_status(self, order_ids: List[str], status: str, error_message: str = None) -> Dict[str, List[str]]:
        """
        Create new rows with updated status for multiple orders
        
        Args:
            order_ids: List of order IDs
            status: New status
            error_message: Optional error message
            
        Returns:
            Dictionary with successful and failed order IDs
        """
        if not order_ids:
            return {"successful": [], "failed": []}
            
        successful = []
        failed = []
        
        try:
            pool = await self.db_pool.get_pool()
            async with pool.acquire() as conn:
                # Use a transaction for all updates
                async with conn.transaction():
                    for order_id in order_ids:
                        try:
                            # First get the current order data
                            query_select = """
                            WITH latest_order AS (
                                SELECT * FROM trading.orders 
                                WHERE order_id = $1 
                                ORDER BY created_at DESC 
                                LIMIT 1
                            )
                            SELECT * FROM latest_order
                            """
                            
                            order_data = await conn.fetchrow(query_select, order_id)
                            
                            if not order_data:
                                logger.error(f"Order not found: {order_id}")
                                failed.append(order_id)
                                continue
                                
                            # Insert new row with updated status
                            query_insert = """
                            INSERT INTO trading.orders (
                                order_id, status, user_id, symbol, side, quantity, price, 
                                order_type, filled_quantity, avg_price, created_at, updated_at, 
                                request_id, error_message
                            ) VALUES (
                                $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, 
                                to_timestamp($11), to_timestamp($12), $13, $14
                            )
                            """
                            
                            now = time.time()
                            
                            await conn.execute(
                                query_insert,
                                order_id,
                                status,
                                order_data['user_id'],
                                order_data['symbol'],
                                order_data['side'],
                                order_data['quantity'],
                                order_data['price'],
                                order_data['order_type'],
                                order_data['filled_quantity'],
                                order_data['avg_price'],
                                now,
                                now,
                                order_data['request_id'],
                                error_message or order_data['error_message']
                            )
                            
                            successful.append(order_id)
                        except Exception as e:
                            logger.error(f"Error updating order {order_id}: {e}")
                            failed.append(order_id)
                            
            return {"successful": successful, "failed": failed}
        except Exception as e:
            logger.error(f"Error in batch status update: {e}")
            return {"successful": successful, "failed": failed}
    
    async def get_orders_info(self, order_ids: List[str]) -> List[Dict[str, Any]]:
        """
        Get information about multiple orders in a single query
        
        Args:
            order_ids: List of order IDs to check
            
        Returns:
            List of order information dictionaries
        """
        if not order_ids:
            return []

        try:
            pool = await self.db_pool.get_pool()
            async with pool.acquire() as conn:
                # Use WITH to get the latest status of each order
                query = """
                WITH latest_orders AS (
                    SELECT DISTINCT ON (order_id) *
                    FROM trading.orders
                    WHERE order_id = ANY($1::uuid[])
                    ORDER BY order_id, created_at DESC
                )
                SELECT order_id, user_id, symbol, side, status
                FROM latest_orders
                """
                rows = await conn.fetch(query, order_ids)
                return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Error getting order information: {e}")
            return []
            
    async def get_open_orders_by_symbol(self, user_id: str, symbols: List[str]) -> List[Dict[str, Any]]:
        """
        Get all open orders for a user by symbols
        
        Args:
            user_id: User ID
            symbols: List of symbols to find orders for
            
        Returns:
            List of order information dictionaries
        """
        if not symbols:
            return []
            
        try:
            pool = await self.db_pool.get_pool()
            async with pool.acquire() as conn:
                # Find the most recent status for each order_id that matches our criteria
                query = """
                WITH latest_orders AS (
                    SELECT DISTINCT ON (order_id) *
                    FROM trading.orders
                    WHERE user_id = $1 AND symbol = ANY($2::text[])
                    ORDER BY order_id, created_at DESC
                )
                SELECT order_id, symbol, status
                FROM latest_orders
                WHERE status IN ('NEW', 'PARTIALLY_FILLED')
                """
                
                rows = await conn.fetch(query, user_id, symbols)
                return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Error getting open orders: {e}")
            return []
    
    async def get_order(self, order_id: str) -> Optional[ConvictionData]:
        """Get a single order by ID (latest status)"""
        pool = await self.db_pool.get_pool()
        
        query = """
        WITH latest_order AS (
            SELECT * FROM trading.orders 
            WHERE order_id = $1 
            ORDER BY created_at DESC 
            LIMIT 1
        )
        SELECT * FROM latest_order
        """
        
        try:
            async with pool.acquire() as conn:
                row = await conn.fetchrow(query, order_id)
                if not row:
                    return None
                    
                # Create Order object from row
                order_data = dict(row)
                
                # Convert timestamp to float for created_at and updated_at
                if 'created_at' in order_data:
                    order_data['created_at'] = order_data['created_at'].timestamp()
                if 'updated_at' in order_data:
                    order_data['updated_at'] = order_data['updated_at'].timestamp()
                
                return Order.from_dict(order_data)
        except Exception as e:
            logger.error(f"Error getting order {order_id}: {e}")
            return None
    
    async def store_submit_conviction_data(self, tx_id: str, book_id: str, orders_data: list) -> bool:
        """
        Store submission data in conv.submit table
        
        Args:
            tx_id: Transaction ID from crypto.txs
            book_id: Book ID
            orders_data: List of order data dictionaries
            
        Returns:
            Success flag
        """
        pool = await self.db_pool.get_pool()
        
        submit_query = """
        INSERT INTO conv.submit (
            book_id, tx_id, ix, instrument_id, participation_rate, tag, order_id,
            side, score, quantity, zscore, target_percentage, target_notional, horizon_zscore
        ) VALUES (
            $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14
        )
        """
        
        start_time = time.time()
        try:
            async with pool.acquire() as conn:
                async with conn.transaction():
                    for ix, order in enumerate(orders_data):
                        # Map ConvictionData fields to database columns
                        instrument_id = order.get('instrumentId', '')
                        participation_rate = str(order.get('participationRate', ''))
                        tag = order.get('tag', '')
                        order_id = order.get('orderId', str(uuid.uuid4()))  # Generate if not provided
                        
                        # Optional fields
                        side = order.get('side')
                        score = order.get('score')
                        quantity = order.get('quantity')
                        zscore = order.get('zscore')
                        target_percentage = order.get('targetPercent')
                        target_notional = order.get('targetNotional')
                        
                        # Handle dynamic horizon z-scores (multi-horizon support)
                        horizon_zscore = None
                        horizon_fields = {k: v for k, v in order.items() 
                                        if k not in ['instrumentId', 'participationRate', 'tag', 'orderId', 
                                                'side', 'score', 'quantity', 'zscore', 'targetPercent', 'targetNotional']}
                        if horizon_fields:
                            horizon_zscore = json.dumps(horizon_fields)
                        
                        await conn.execute(
                            submit_query,
                            book_id, tx_id, ix, instrument_id, participation_rate, tag, order_id,
                            side, score, quantity, zscore, target_percentage, target_notional, horizon_zscore
                        )
                    
                    duration = time.time() - start_time
                    track_db_operation("store_submit_conviction", True, duration)
                    logger.info(f"Stored {len(orders_data)} conviction submit records for transaction {tx_id}")
                    return True
                    
        except Exception as e:
            duration = time.time() - start_time
            track_db_operation("store_submit_conviction", False, duration)
            logger.error(f"Error storing conviction submit data: {e}")
            return False

    async def store_cancel_conviction_data(self, tx_id: str, book_id: str, order_ids: list) -> bool:
        """
        Store cancellation data in conv.cancel table
        
        Args:
            tx_id: Transaction ID from crypto.txs
            book_id: Book ID
            order_ids: List of order IDs to cancel
            
        Returns:
            Success flag
        """
        pool = await self.db_pool.get_pool()
        
        cancel_query = """
        INSERT INTO conv.cancel (
            book_id, tx_id, ix, order_id
        ) VALUES (
            $1, $2, $3, $4
        )
        """
        
        start_time = time.time()
        try:
            async with pool.acquire() as conn:
                async with conn.transaction():
                    for ix, order_id in enumerate(order_ids):
                        await conn.execute(
                            cancel_query,
                            book_id, tx_id, ix, order_id
                        )
                    
                    duration = time.time() - start_time
                    track_db_operation("store_cancel_conviction", True, duration)
                    logger.info(f"Stored {len(order_ids)} conviction cancel records for transaction {tx_id}")
                    return True
                    
        except Exception as e:
            duration = time.time() - start_time
            track_db_operation("store_cancel_conviction", False, duration)
            logger.error(f"Error storing conviction cancel data: {e}")
            return False
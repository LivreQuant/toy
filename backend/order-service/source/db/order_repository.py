import logging
import asyncio
import asyncpg
import time
from typing import List, Optional, Dict, Any

from source.models.order import Order
from source.models.enums import OrderStatus
from source.config import config
from source.utils.metrics import track_db_operation, set_db_connection_count
from opentelemetry import trace

from source.utils.tracing import optional_trace_span

logger = logging.getLogger('order_repository')


class OrderRepository:
    """Data access layer for orders"""

    def __init__(self):
        """Initialize the order repository"""
        self.pool = None
        self._conn_lock = asyncio.Lock()
        self.tracer = trace.get_tracer("order_repository")

    async def connect(self):
        """Create the database connection pool with retry logic"""
        with optional_trace_span(self.tracer, "connect") as span:
            async with self._conn_lock:
                if self.pool:
                    return

                max_retries = 5
                retry_count = 0
                retry_delay = 1.0

                while retry_count < max_retries:
                    try:
                        span.set_attribute("retry_count", retry_count)
                        span.set_attribute("db.name", config.db_name)
                        span.set_attribute("db.user", config.db_user)
                        span.set_attribute("db.host", config.db_host)

                        self.pool = await asyncpg.create_pool(
                            min_size=config.db_min_connections,
                            max_size=config.db_max_connections,
                            command_timeout=10,
                            host=config.db_host,
                            port=config.db_port,
                            user=config.db_user,
                            password=config.db_password,
                            database=config.db_name
                        )

                        # Report connection count in metrics
                        set_db_connection_count(config.db_min_connections)

                        logger.info("Database connection established")
                        span.set_attribute("success", True)
                        return
                    except Exception as e:
                        retry_count += 1
                        logger.error(f"Database connection error (attempt {retry_count}/{max_retries}): {e}")
                        span.set_attribute("error", str(e))

                        if retry_count < max_retries:
                            await asyncio.sleep(retry_delay)
                            retry_delay *= 2  # Exponential backoff
                        else:
                            span.set_attribute("success", False)
                            logger.error("Maximum database connection retries reached")
                            raise

    async def close(self):
        """Close database connections"""
        with optional_trace_span(self.tracer, "close") as span:
            if self.pool:
                await self.pool.close()
                self.pool = None
                logger.info("Closed database connections")
                span.set_attribute("success", True)

                # Update connection count in metrics
                set_db_connection_count(0)

    async def save_order(self, order: Order) -> bool:
        """Save a new order or update existing order"""
        with optional_trace_span(self.tracer, "save_order") as span:
            span.set_attribute("order_id", order.order_id)
            span.set_attribute("symbol", order.symbol)
            span.set_attribute("operation", "insert" if not order.updated_at else "update")

            if not self.pool:
                await self.connect()

            query = """
            INSERT INTO trading.orders (
                order_id, user_id, session_id, symbol, side, quantity, price, 
                order_type, status, filled_quantity, avg_price, simulator_id,
                created_at, updated_at, request_id, error_message
            ) VALUES (
                $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, 
                to_timestamp($13), to_timestamp($14), $15, $16
            )
            ON CONFLICT (order_id) DO UPDATE SET
                status = EXCLUDED.status,
                filled_quantity = EXCLUDED.filled_quantity,
                avg_price = EXCLUDED.avg_price,
                updated_at = EXCLUDED.updated_at,
                error_message = EXCLUDED.error_message
            """

            span.set_attribute("db.statement", query)

            try:
                start_time = time.time()

                async with self.pool.acquire() as conn:
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
                        order.error_message
                    )
                    duration = time.time() - start_time
                    track_db_operation("save_order", True, duration)
                    span.set_attribute("success", True)
                    return True
            except Exception as e:
                duration = time.time() - start_time
                track_db_operation("save_order", False, duration)
                span.record_exception(e)
                span.set_attribute("success", False)
                span.set_attribute("error", str(e))
                logger.error(f"Error saving order: {e}")
                return False

    async def get_order(self, order_id: str) -> Optional[Order]:
        """Get an order by ID"""
        with optional_trace_span(self.tracer, "get_order") as span:
            span.set_attribute("order_id", order_id)

            if not self.pool:
                await self.connect()

            query = """
            SELECT 
                order_id, user_id, session_id, symbol, side, quantity, price, 
                order_type, status, filled_quantity, avg_price, simulator_id,
                EXTRACT(EPOCH FROM created_at) as created_at, 
                EXTRACT(EPOCH FROM updated_at) as updated_at, 
                request_id, error_message
            FROM trading.orders
            WHERE order_id = $1
            """

            span.set_attribute("db.statement", query)

            try:
                start_time = time.time()

                async with self.pool.acquire() as conn:
                    row = await conn.fetchrow(query, order_id)

                    duration = time.time() - start_time
                    success = row is not None
                    track_db_operation("get_order", success, duration)

                    span.set_attribute("success", success)

                    if not row:
                        span.set_attribute("order_found", False)
                        return None

                    # Convert row to dict
                    order_dict = dict(row)
                    span.set_attribute("order_found", True)
                    span.set_attribute("order.status", order_dict.get('status'))

                    # Create order object
                    return Order.from_dict(order_dict)
            except Exception as e:
                duration = time.time() - start_time
                track_db_operation("get_order", False, duration)
                span.record_exception(e)
                span.set_attribute("success", False)
                span.set_attribute("error", str(e))
                logger.error(f"Error retrieving order: {e}")
                return None

    async def get_user_orders(self, user_id: str, limit: int = 50, offset: int = 0) -> List[Order]:
        """Get orders for a specific user"""
        with optional_trace_span(self.tracer, "get_user_orders") as span:
            span.set_attribute("user_id", user_id)
            span.set_attribute("limit", limit)
            span.set_attribute("offset", offset)

            if not self.pool:
                await self.connect()

            query = """
            SELECT 
                order_id, user_id, session_id, symbol, side, quantity, price, 
                order_type, status, filled_quantity, avg_price, simulator_id,
                EXTRACT(EPOCH FROM created_at) as created_at, 
                EXTRACT(EPOCH FROM updated_at) as updated_at, 
                request_id, error_message
            FROM trading.orders
            WHERE user_id = $1
            ORDER BY created_at DESC
            LIMIT $2 OFFSET $3
            """

            span.set_attribute("db.statement", query)

            try:
                start_time = time.time()

                async with self.pool.acquire() as conn:
                    rows = await conn.fetch(query, user_id, limit, offset)

                    orders = []
                    for row in rows:
                        # Convert row to dict
                        order_dict = dict(row)

                        # Create order object
                        orders.append(Order.from_dict(order_dict))

                    duration = time.time() - start_time
                    track_db_operation("get_user_orders", True, duration)

                    span.set_attribute("success", True)
                    span.set_attribute("order_count", len(orders))
                    return orders
            except Exception as e:
                duration = time.time() - start_time
                track_db_operation("get_user_orders", False, duration)
                span.record_exception(e)
                span.set_attribute("success", False)
                span.set_attribute("error", str(e))
                logger.error(f"Error retrieving user orders: {e}")
                return []

    async def get_session_orders(self, session_id: str, limit: int = 50, offset: int = 0) -> List[Order]:
        """Get orders for a specific session"""
        with optional_trace_span(self.tracer, "get_session_orders") as span:
            span.set_attribute("session_id", session_id)
            span.set_attribute("limit", limit)
            span.set_attribute("offset", offset)

            if not self.pool:
                await self.connect()

            query = """
            SELECT 
                order_id, user_id, session_id, symbol, side, quantity, price, 
                order_type, status, filled_quantity, avg_price, simulator_id,
                EXTRACT(EPOCH FROM created_at) as created_at, 
                EXTRACT(EPOCH FROM updated_at) as updated_at, 
                request_id, error_message
            FROM trading.orders
            WHERE session_id = $1
            ORDER BY created_at DESC
            LIMIT $2 OFFSET $3
            """

            span.set_attribute("db.statement", query)

            try:
                start_time = time.time()

                async with self.pool.acquire() as conn:
                    rows = await conn.fetch(query, session_id, limit, offset)

                    orders = []
                    for row in rows:
                        # Convert row to dict
                        order_dict = dict(row)

                        # Create order object
                        orders.append(Order.from_dict(order_dict))

                    duration = time.time() - start_time
                    track_db_operation("get_session_orders", True, duration)

                    span.set_attribute("success", True)
                    span.set_attribute("order_count", len(orders))
                    return orders
            except Exception as e:
                duration = time.time() - start_time
                track_db_operation("get_session_orders", False, duration)
                span.record_exception(e)
                span.set_attribute("success", False)
                span.set_attribute("error", str(e))
                logger.error(f"Error retrieving session orders: {e}")
                return []

    async def update_order_status(self, order_id: str, status: OrderStatus,
                                  filled_quantity: Optional[float] = None,
                                  avg_price: Optional[float] = None,
                                  error_message: Optional[str] = None) -> bool:
        """Update an order's status"""
        with optional_trace_span(self.tracer, "update_order_status") as span:
            span.set_attribute("order_id", order_id)
            span.set_attribute("new_status", status.value)
            if filled_quantity is not None:
                span.set_attribute("filled_quantity", filled_quantity)
            if avg_price is not None:
                span.set_attribute("avg_price", avg_price)

            if not self.pool:
                await self.connect()

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
            span.set_attribute("db.statement", query)

            try:
                start_time = time.time()

                async with self.pool.acquire() as conn:
                    result = await conn.execute(query, *params)
                    success = "UPDATE 1" in result

                    duration = time.time() - start_time
                    track_db_operation("update_order_status", success, duration)

                    span.set_attribute("success", success)
                    span.set_attribute("affected_rows", 1 if success else 0)
                    return success
            except Exception as e:
                duration = time.time() - start_time
                track_db_operation("update_order_status", False, duration)
                span.record_exception(e)
                span.set_attribute("success", False)
                span.set_attribute("error", str(e))
                logger.error(f"Error updating order status: {e}")
                return False


    async def check_connection(self) -> bool:
        """Check if database connection is working"""
        with optional_trace_span(self.tracer, "check_connection") as span:
            if not self.pool:
                try:
                    await self.connect()
                    span.set_attribute("success", True)
                    return True
                except Exception as e:
                    span.record_exception(e)
                    span.set_attribute("success", False)
                    return False

            try:
                async with self.pool.acquire() as conn:
                    await conn.execute("SELECT 1")
                    span.set_attribute("success", True)
                    return True
            except Exception as e:
                span.record_exception(e)
                span.set_attribute("success", False)
                span.set_attribute("error", str(e))
                logger.error(f"Database connection check failed: {e}")
                return False

# source/db/order_store.py
import logging
import asyncpg
import os
import time
from typing import List, Optional, Dict, Any

from source.models.order import Order, OrderStatus

logger = logging.getLogger('order_store')

class OrderStore:
    def __init__(self):
        self.pool = None
        self.db_config = {
            'host': os.getenv('DB_HOST', 'postgres'),
            'port': int(os.getenv('DB_PORT', '5432')),
            'database': os.getenv('DB_NAME', 'opentp'),
            'user': os.getenv('DB_USER', 'opentp'),
            'password': os.getenv('DB_PASSWORD', 'samaral')
        }
        self.min_connections = int(os.getenv('DB_MIN_CONNECTIONS', '1'))
        self.max_connections = int(os.getenv('DB_MAX_CONNECTIONS', '10'))
    
    async def connect(self):
        """Create the database connection pool"""
        if self.pool:
            return
        
        try:
            self.pool = await asyncpg.create_pool(
                min_size=self.min_connections,
                max_size=self.max_connections,
                **self.db_config
            )
            logger.info("Database connection established")
            
            # Ensure required schema exists
            await self.ensure_schema()
        except Exception as e:
            logger.error(f"Database connection failed: {e}")
            raise
    
    async def close(self):
        """Close all database connections"""
        if self.pool:
            await self.pool.close()
            self.pool = None
            logger.info("Database connections closed")
    
    async def ensure_schema(self):
        """Ensure the orders schema and tables exist"""
        schema_query = """
        -- Create schema if not exists
        CREATE SCHEMA IF NOT EXISTS trading;
        
        -- Create orders table if not exists
        CREATE TABLE IF NOT EXISTS trading.orders (
            order_id UUID PRIMARY KEY,
            user_id VARCHAR(100) NOT NULL,
            session_id VARCHAR(100) NOT NULL,
            symbol VARCHAR(20) NOT NULL,
            side VARCHAR(10) NOT NULL,
            quantity NUMERIC(18,8) NOT NULL,
            price NUMERIC(18,8),
            order_type VARCHAR(20) NOT NULL,
            status VARCHAR(20) NOT NULL,
            filled_quantity NUMERIC(18,8) NOT NULL DEFAULT 0,
            avg_price NUMERIC(18,8) NOT NULL DEFAULT 0,
            simulator_id VARCHAR(100),
            created_at TIMESTAMP WITH TIME ZONE NOT NULL,
            updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
            request_id VARCHAR(100),
            error_message TEXT
        );
        
        -- Create indexes
        CREATE INDEX IF NOT EXISTS idx_orders_user_id ON trading.orders(user_id);
        CREATE INDEX IF NOT EXISTS idx_orders_session_id ON trading.orders(session_id);
        CREATE INDEX IF NOT EXISTS idx_orders_status ON trading.orders(status);
        CREATE INDEX IF NOT EXISTS idx_orders_created_at ON trading.orders(created_at);
        """
        
        async with self.pool.acquire() as conn:
            await conn.execute(schema_query)
        
        logger.info("Orders schema verification complete")
    
    async def save_order(self, order: Order) -> bool:
        """Save a new order to the database"""
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
        
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    query,
                    order.order_id,
                    order.user_id,
                    order.session_id,
                    order.symbol,
                    order.side.value if isinstance(order.side, OrderStatus) else order.side,
                    order.quantity,
                    order.price,
                    order.order_type.value if isinstance(order.order_type, OrderStatus) else order.order_type,
                    order.status.value if isinstance(order.status, OrderStatus) else order.status,
                    order.filled_quantity,
                    order.avg_price,
                    order.simulator_id,
                    order.created_at,
                    order.updated_at,
                    order.request_id,
                    order.error_message
                )
                return True
        except Exception as e:
            logger.error(f"Error saving order: {e}")
            return False
    
    async def get_order(self, order_id: str) -> Optional[Order]:
        """Get an order by ID"""
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
        
        try:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow(query, order_id)
                if not row:
                    return None
                
                # Convert to Order object
                return Order(
                    order_id=row['order_id'],
                    user_id=row['user_id'],
                    session_id=row['session_id'],
                    symbol=row['symbol'],
                    side=row['side'],
                    quantity=float(row['quantity']),
                    price=float(row['price']) if row['price'] is not None else None,
                    order_type=row['order_type'],
                    status=row['status'],
                    filled_quantity=float(row['filled_quantity']),
                    avg_price=float(row['avg_price']),
                    simulator_id=row['simulator_id'],
                    created_at=float(row['created_at']),
                    updated_at=float(row['updated_at']),
                    request_id=row['request_id'],
                    error_message=row['error_message']
                )
        except Exception as e:
            logger.error(f"Error retrieving order: {e}")
            return None
    
    async def update_order_status(self, order_id: str, status: OrderStatus, 
                                  filled_quantity: float = None, avg_price: float = None, 
                                  error_message: str = None) -> bool:
        """Update an order's status"""
        if not self.pool:
            await self.connect()
        
        # Build update query based on provided fields
        query_parts = ["UPDATE trading.orders SET status = $1"]
        params = [status.value if isinstance(status, OrderStatus) else status]
        
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
        
        query_parts.append(f"updated_at = to_timestamp(${param_idx})")
        params.append(time.time())
        
        query_parts.append(f"WHERE order_id = ${param_idx + 1}")
        params.append(order_id)
        
        query = " ".join(query_parts)
        
        try:
            async with self.pool.acquire() as conn:
                result = await conn.execute(query, *params)
                return result.endswith("UPDATE 1")
        except Exception as e:
            logger.error(f"Error updating order status: {e}")
            return False
    
    async def get_user_orders(self, user_id: str, limit: int = 50, offset: int = 0) -> List[Order]:
        """Get orders for a specific user"""
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
        
        try:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch(query, user_id, limit, offset)
                
                orders = []
                for row in rows:
                    orders.append(Order(
                        order_id=row['order_id'],
                        user_id=row['user_id'],
                        session_id=row['session_id'],
                        symbol=row['symbol'],
                        side=row['side'],
                        quantity=float(row['quantity']),
                        price=float(row['price']) if row['price'] is not None else None,
                        order_type=row['order_type'],
                        status=row['status'],
                        filled_quantity=float(row['filled_quantity']),
                        avg_price=float(row['avg_price']),
                        simulator_id=row['simulator_id'],
                        created_at=float(row['created_at']),
                        updated_at=float(row['updated_at']),
                        request_id=row['request_id'],
                        error_message=row['error_message']
                    ))
                
                return orders
        except Exception as e:
            logger.error(f"Error retrieving user orders: {e}")
            return []
    
    async def get_session_orders(self, session_id: str, limit: int = 50, offset: int = 0) -> List[Order]:
        """Get orders for a specific session"""
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
        
        try:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch(query, session_id, limit, offset)
                
                orders = []
                for row in rows:
                    orders.append(Order(
                        order_id=row['order_id'],
                        user_id=row['user_id'],
                        session_id=row['session_id'],
                        symbol=row['symbol'],
                        side=row['side'],
                        quantity=float(row['quantity']),
                        price=float(row['price']) if row['price'] is not None else None,
                        order_type=row['order_type'],
                        status=row['status'],
                        filled_quantity=float(row['filled_quantity']),
                        avg_price=float(row['avg_price']),
                        simulator_id=row['simulator_id'],
                        created_at=float(row['created_at']),
                        updated_at=float(row['updated_at']),
                        request_id=row['request_id'],
                        error_message=row['error_message']
                    ))
                
                return orders
        except Exception as e:
            logger.error(f"Error retrieving session orders: {e}")
            return []
    
    async def cleanup_old_orders(self, days_old: int = 30) -> int:
        """Clean up orders older than the specified number of days"""
        if not self.pool:
            await self.connect()
        
        query = """
        DELETE FROM trading.orders
        WHERE created_at < NOW() - INTERVAL '$1 days'
        """
        
        try:
            async with self.pool.acquire() as conn:
                result = await conn.execute(query, days_old)
                deleted_count = int(result.split(" ")[1])
                logger.info(f"Cleaned up {deleted_count} old orders")
                return deleted_count
        except Exception as e:
            logger.error(f"Error cleaning up old orders: {e}")
            return 0
    
    async def check_connection(self) -> bool:
        """Check if database connection is working"""
        if not self.pool:
            try:
                await self.connect()
                return True
            except:
                return False
        
        try:
            async with self.pool.acquire() as conn:
                await conn.execute("SELECT 1")
                return True
        except Exception as e:
            logger.error(f"Database connection check failed: {e}")
            return False
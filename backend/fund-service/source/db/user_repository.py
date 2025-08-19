# source/db/user_repository.py
import logging
import time
import uuid
import datetime
from typing import Dict, Any, Optional

from source.db.connection_pool import DatabasePool
from source.utils.metrics import track_db_operation

logger = logging.getLogger('user_repository')

class UserRepository:
    """Repository for managing exchange user data"""

    def __init__(self, db_pool=None):
        """Initialize the user repository"""
        self.db_pool = db_pool or DatabasePool()

    async def get_connection(self):
        """Get database connection for user operations"""
        pool = await self.db_pool.get_pool()
        return pool.acquire()

    async def create_exchange_user(self, user_id: str, exch_id: str, initial_capital: float = 1000000.0) -> bool:
        """
        Create a complete exchange user setup with all required tables
        
        Args:
            user_id: User ID
            exch_id: Exchange ID
            initial_capital: Starting capital amount (default 1M)
            
        Returns:
            True if successful, False otherwise
        """
        pool = await self.db_pool.get_pool()
        
        logger.info(f"Creating exchange user setup for user {user_id} on exchange {exch_id}")
        
        start_time = time.time()
        try:
            async with pool.acquire() as conn:
                async with conn.transaction():
                    # 1. Create user in exch_us_equity.users
                    await self._create_exchange_user_record(conn, user_id, exch_id, initial_capital)
                    
                    # 2. Create user operational parameters
                    await self._create_user_operational_parameters(conn, user_id)
                    
                    # 3. Create initial account data
                    await self._create_initial_account_data(conn, user_id, initial_capital)
                    
                    duration = time.time() - start_time
                    track_db_operation("create_exchange_user", True, duration)
                    
                    logger.info(f"Successfully created exchange user setup for {user_id}")
                    return True
                    
        except Exception as e:
            duration = time.time() - start_time
            track_db_operation("create_exchange_user", False, duration)
            logger.error(f"Error creating exchange user setup for {user_id}: {e}")
            return False

    async def _create_exchange_user_record(self, conn, user_id: str, exch_id: str, initial_capital: float):
        """Create the main user record in exch_us_equity.users"""
        query = """
        INSERT INTO exch_us_equity.users (
            user_id,
            exch_id,
            timezone,
            base_currency,
            initial_nav,
            operation_id,
            engine_id,
            transaction_cost_model,
            market_impact_model
        ) VALUES (
            $1, $2, $3, $4, $5, $6, $7, $8, $9
        )
        ON CONFLICT (user_id, exch_id) DO NOTHING
        """
        
        await conn.execute(
            query,
            user_id,                    # user_id
            exch_id,                    # exch_id
            'America/New_York',         # timezone
            'USD',                      # base_currency
            int(initial_capital * 100), # initial_nav (in cents)
            0,                          # operation_id
            1,                          # engine_id
            0,                          # transaction_cost_model
            0                           # market_impact_model
        )
        
        logger.info(f"Created user record for {user_id} on exchange {exch_id}")

    async def _create_user_operational_parameters(self, conn, user_id: str):
        """Create user operational parameters"""
        query = """
        INSERT INTO exch_us_equity.user_operational_parameters (
            user_id,
            max_position_size_pct,
            min_position_size_pct,
            max_days_to_liquidate
        ) VALUES (
            $1, $2, $3, $4
        )
        ON CONFLICT (user_id) DO NOTHING
        """
        
        await conn.execute(
            query,
            user_id,    # user_id
            1.0,        # max_position_size_pct (100%)
            0.0,        # min_position_size_pct (0%)
            365         # max_days_to_liquidate
        )
        
        logger.info(f"Created operational parameters for user {user_id}")

    async def _create_initial_account_data(self, conn, user_id: str, initial_capital: float):
        """Create initial account data records"""
        now = datetime.datetime.now(datetime.timezone.utc)
        
        query = """
        INSERT INTO exch_us_equity.account_data (
            user_id,
            timestamp,
            type,
            currency,
            amount,
            previous_amount,
            change
        ) VALUES (
            $1, $2, $3, $4, $5, $6, $7
        )
        """
        
        # Create all account types
        account_types = [
            ('CREDIT', initial_capital, initial_capital, 0.0),
            ('SHORT_CREDIT', 0.0, 0.0, 0.0),
            ('DEBIT', 0.0, 0.0, 0.0),
            ('INVESTOR', 0.0, 0.0, 0.0)
        ]
        
        for account_type, amount, previous_amount, change in account_types:
            await conn.execute(
                query,
                user_id,            # user_id
                now,                # timestamp
                account_type,       # type
                'USD',              # currency
                amount,             # amount
                previous_amount,    # previous_amount
                change              # change
            )
            
            logger.debug(f"Created {account_type} account for user {user_id} with amount {amount}")
        
        logger.info(f"Created initial account data for user {user_id}")

    async def get_exchange_user(self, user_id: str, exch_id: str = None) -> Optional[Dict[str, Any]]:
        """
        Get exchange user information
        
        Args:
            user_id: User ID
            exch_id: Optional exchange ID filter
            
        Returns:
            User data if found, None otherwise
        """
        pool = await self.db_pool.get_pool()
        
        if exch_id:
            query = """
            SELECT user_id, exch_id, timezone, base_currency, initial_nav,
                   operation_id, engine_id, transaction_cost_model, market_impact_model
            FROM exch_us_equity.users
            WHERE user_id = $1 AND exch_id = $2
            """
            params = [user_id, exch_id]
        else:
            query = """
            SELECT user_id, exch_id, timezone, base_currency, initial_nav,
                   operation_id, engine_id, transaction_cost_model, market_impact_model
            FROM exch_us_equity.users
            WHERE user_id = $1
            """
            params = [user_id]
        
        start_time = time.time()
        try:
            async with pool.acquire() as conn:
                row = await conn.fetchrow(query, *params)
                
                duration = time.time() - start_time
                track_db_operation("get_exchange_user", True, duration)
                
                if row:
                    return dict(row)
                return None
                
        except Exception as e:
            duration = time.time() - start_time
            track_db_operation("get_exchange_user", False, duration)
            logger.error(f"Error getting exchange user {user_id}: {e}")
            return None

    async def update_user_capital(self, user_id: str, new_capital: float) -> bool:
        """
        Update user's initial capital and account data
        
        Args:
            user_id: User ID
            new_capital: New capital amount
            
        Returns:
            True if successful, False otherwise
        """
        pool = await self.db_pool.get_pool()
        now = datetime.datetime.now(datetime.timezone.utc)
        
        logger.info(f"Updating capital for user {user_id} to {new_capital}")
        
        start_time = time.time()
        try:
            async with pool.acquire() as conn:
                async with conn.transaction():
                    # Update initial_nav in users table
                    await conn.execute(
                        """
                        UPDATE exch_us_equity.users
                        SET initial_nav = $1
                        WHERE user_id = $2
                        """,
                        int(new_capital * 100),  # Convert to cents
                        user_id
                    )
                    
                    # Get current CREDIT amount
                    current_credit = await conn.fetchval(
                        """
                        SELECT amount FROM exch_us_equity.account_data
                        WHERE user_id = $1 AND type = 'CREDIT'
                        ORDER BY timestamp DESC
                        LIMIT 1
                        """,
                        user_id
                    )
                    
                    if current_credit is None:
                        current_credit = 0.0
                    
                    change = new_capital - current_credit
                    
                    # Insert new account data record
                    await conn.execute(
                        """
                        INSERT INTO exch_us_equity.account_data (
                            user_id, timestamp, type, currency, amount, previous_amount, change
                        ) VALUES (
                            $1, $2, $3, $4, $5, $6, $7
                        )
                        """,
                        user_id,            # user_id
                        now,                # timestamp
                        'CREDIT',           # type
                        'USD',              # currency
                        new_capital,        # amount
                        current_credit,     # previous_amount
                        change              # change
                    )
                    
                    duration = time.time() - start_time
                    track_db_operation("update_user_capital", True, duration)
                    
                    logger.info(f"Updated capital for user {user_id} from {current_credit} to {new_capital}")
                    return True
                    
        except Exception as e:
            duration = time.time() - start_time
            track_db_operation("update_user_capital", False, duration)
            logger.error(f"Error updating user capital for {user_id}: {e}")
            return False

    async def get_user_account_data(self, user_id: str, account_type: str = None) -> List[Dict[str, Any]]:
        """
        Get user account data
        
        Args:
            user_id: User ID
            account_type: Optional account type filter
            
        Returns:
            List of account records
        """
        pool = await self.db_pool.get_pool()
        
        if account_type:
            query = """
            SELECT user_id, timestamp, type, currency, amount, previous_amount, change
            FROM exch_us_equity.account_data
            WHERE user_id = $1 AND type = $2
            ORDER BY timestamp DESC
            """
            params = [user_id, account_type]
        else:
            query = """
            SELECT user_id, timestamp, type, currency, amount, previous_amount, change
            FROM exch_us_equity.account_data
            WHERE user_id = $1
            ORDER BY timestamp DESC, type
            """
            params = [user_id]
        
        start_time = time.time()
        try:
            async with pool.acquire() as conn:
                rows = await conn.fetch(query, *params)
                
                duration = time.time() - start_time
                track_db_operation("get_user_account_data", True, duration)
                
                return [dict(row) for row in rows]
                
        except Exception as e:
            duration = time.time() - start_time
            track_db_operation("get_user_account_data", False, duration)
            logger.error(f"Error getting user account data for {user_id}: {e}")
            return []

    async def get_user_operational_parameters(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get user operational parameters
        
        Args:
            user_id: User ID
            
        Returns:
            Parameters dict if found, None otherwise
        """
        pool = await self.db_pool.get_pool()
        
        query = """
        SELECT user_id, max_position_size_pct, min_position_size_pct, max_days_to_liquidate
        FROM exch_us_equity.user_operational_parameters
        WHERE user_id = $1
        """
        
        start_time = time.time()
        try:
            async with pool.acquire() as conn:
                row = await conn.fetchrow(query, user_id)
                
                duration = time.time() - start_time
                track_db_operation("get_user_operational_parameters", True, duration)
                
                if row:
                    return dict(row)
                return None
                
        except Exception as e:
            duration = time.time() - start_time
            track_db_operation("get_user_operational_parameters", False, duration)
            logger.error(f"Error getting user operational parameters for {user_id}: {e}")
            return None

    async def update_user_operational_parameters(self, user_id: str, parameters: Dict[str, Any]) -> bool:
        """
        Update user operational parameters
        
        Args:
            user_id: User ID
            parameters: Dict with parameter updates
            
        Returns:
            True if successful, False otherwise
        """
        pool = await self.db_pool.get_pool()
        
        # Build dynamic update query
        set_clauses = []
        values = [user_id]
        param_count = 1
        
        allowed_params = ['max_position_size_pct', 'min_position_size_pct', 'max_days_to_liquidate']
        
        for param, value in parameters.items():
            if param in allowed_params:
                param_count += 1
                set_clauses.append(f"{param} = ${param_count}")
                values.append(value)
        
        if not set_clauses:
            logger.warning(f"No valid parameters to update for user {user_id}")
            return True
        
        query = f"""
        UPDATE exch_us_equity.user_operational_parameters
        SET {', '.join(set_clauses)}
        WHERE user_id = $1
        """
        
        start_time = time.time()
        try:
            async with pool.acquire() as conn:
                result = await conn.execute(query, *values)
                
                duration = time.time() - start_time
                track_db_operation("update_user_operational_parameters", True, duration)
                
                logger.info(f"Updated operational parameters for user {user_id}")
                return True
                
        except Exception as e:
            duration = time.time() - start_time
            track_db_operation("update_user_operational_parameters", False, duration)
            logger.error(f"Error updating user operational parameters for {user_id}: {e}")
            return False

    async def delete_exchange_user(self, user_id: str, exch_id: str = None) -> bool:
        """
        Delete exchange user data (hard delete)
        
        Args:
            user_id: User ID
            exch_id: Optional exchange ID filter
            
        Returns:
            True if successful, False otherwise
        """
        pool = await self.db_pool.get_pool()
        
        logger.info(f"Deleting exchange user data for {user_id}")
        
        start_time = time.time()
        try:
            async with pool.acquire() as conn:
                async with conn.transaction():
                    # Delete account data
                    await conn.execute(
                        "DELETE FROM exch_us_equity.account_data WHERE user_id = $1",
                        user_id
                    )
                    
                    # Delete operational parameters
                    await conn.execute(
                        "DELETE FROM exch_us_equity.user_operational_parameters WHERE user_id = $1",
                        user_id
                    )
                    
                    # Delete user record
                    if exch_id:
                        await conn.execute(
                            "DELETE FROM exch_us_equity.users WHERE user_id = $1 AND exch_id = $2",
                            user_id, exch_id
                        )
                    else:
                        await conn.execute(
                            "DELETE FROM exch_us_equity.users WHERE user_id = $1",
                            user_id
                        )
                    
                    duration = time.time() - start_time
                    track_db_operation("delete_exchange_user", True, duration)
                    
                    logger.info(f"Deleted exchange user data for {user_id}")
                    return True
                    
        except Exception as e:
            duration = time.time() - start_time
            track_db_operation("delete_exchange_user", False, duration)
            logger.error(f"Error deleting exchange user data for {user_id}: {e}")
            return False

    async def user_exists_on_exchange(self, user_id: str, exch_id: str) -> bool:
        """
        Check if user exists on a specific exchange
        
        Args:
            user_id: User ID
            exch_id: Exchange ID
            
        Returns:
            True if user exists, False otherwise
        """
        pool = await self.db_pool.get_pool()
        
        query = """
        SELECT 1 FROM exch_us_equity.users
        WHERE user_id = $1 AND exch_id = $2
        LIMIT 1
        """
        
        start_time = time.time()
        try:
            async with pool.acquire() as conn:
                result = await conn.fetchval(query, user_id, exch_id)
                
                duration = time.time() - start_time
                track_db_operation("user_exists_on_exchange", True, duration)
                
                return result is not None
                
        except Exception as e:
            duration = time.time() - start_time
            track_db_operation("user_exists_on_exchange", False, duration)
            logger.error(f"Error checking if user exists on exchange: {e}")
            return False
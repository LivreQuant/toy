# source/db/exchange_repository.py
import logging
import time
import uuid
import datetime
from typing import Dict, Any, Optional

from source.db.connection_pool import DatabasePool
from source.utils.metrics import track_db_operation

logger = logging.getLogger('exchange_repository')

class ExchangeRepository:
    """Repository for managing exchange metadata and user setup"""

    def __init__(self, db_pool=None):
        """Initialize the exchange repository"""
        self.db_pool = db_pool or DatabasePool()

    async def setup_exchange_for_book(self, user_id: str, book_id: str, initial_nav: float) -> bool:
        """
        Setup complete exchange configuration when a book is created
        
        Args:
            user_id: User ID
            book_id: Book ID (used to generate unique exchange ID)
            initial_nav: Initial NAV/capital from book form
            
        Returns:
            True if successful, False otherwise
        """
        logger.info(f"Setting up exchange for book {book_id}, user {user_id}, initial_nav {initial_nav}")
        
        # Generate unique exchange ID based on book ID
        exch_id = str(uuid.uuid4())
        
        pool = await self.db_pool.get_pool()
        start_time = time.time()
        
        try:
            async with pool.acquire() as conn:
                async with conn.transaction():
                    # 1. Create exchange metadata
                    await self._create_exchange_metadata(conn, exch_id)
                    
                    # 2. Create user in exchange
                    await self._create_exchange_user(conn, user_id, exch_id, initial_nav)
                    
                    # 3. Create user operational parameters
                    await self._create_user_operational_parameters(conn, user_id)
                    
                    # 4. Create initial account data
                    await self._create_initial_account_data(conn, user_id, initial_nav)
                    
                    duration = time.time() - start_time
                    track_db_operation("setup_exchange_for_book", True, duration)
                    
                    logger.info(f"Successfully set up exchange {exch_id} for book {book_id}")
                    return True
                    
        except Exception as e:
            duration = time.time() - start_time
            track_db_operation("setup_exchange_for_book", False, duration)
            logger.error(f"Error setting up exchange for book {book_id}: {e}")
            return False

    async def _create_exchange_metadata(self, conn, exch_id: str):
        """Create exchange metadata entry"""
        now = datetime.datetime.now(datetime.timezone.utc)
        
        query = """
        INSERT INTO exch_us_equity.metadata (
            exch_id,
            exchange_type,
            endpoint,
            pod_name,
            namespace,
            timezone,
            exchanges,
            last_snap,
            pre_market_open,
            market_open,
            market_close,
            post_market_close
        ) VALUES (
            $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12
        )
        """
        
        await conn.execute(
            query,
            exch_id,                                # exch_id
            'US_EQUITIES',                          # exchange_type
            'placeholder_endpoint',                 # endpoint (placeholder)
            'placeholder_pod_name',                 # pod_name (placeholder)
            'placeholder_namespace',                # namespace (placeholder)
            'America/New_York',                     # timezone
            ['NYSE', 'NASDAQ', 'ARCA'],            # exchanges
            now,                                    # last_snap
            '04:00:00',                            # pre_market_open
            '09:30:00',                            # market_open
            '16:00:00',                            # market_close
            '20:00:00'                             # post_market_close
        )
        
        logger.info(f"Created exchange metadata for {exch_id}")

    async def _create_exchange_user(self, conn, user_id: str, exch_id: str, initial_nav: float):
        """Create user in exch_us_equity.users"""
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
        """
        
        await conn.execute(
            query,
            user_id,                    # user_id
            exch_id,                    # exch_id
            'America/New_York',         # timezone
            'USD',                      # base_currency
            int(initial_nav),           # initial_nav (keep as integer, no cents conversion)
            0,                          # operation_id
            1,                          # engine_id
            0,                          # transaction_cost_model
            0                           # market_impact_model
        )
        
        logger.info(f"Created exchange user record for {user_id} on exchange {exch_id}")

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

    async def _create_initial_account_data(self, conn, user_id: str, initial_nav: float):
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
        
        # Create all account types with initial_nav as CREDIT amount
        account_types = [
            ('CREDIT', initial_nav, initial_nav, 0.0),
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

# source/db/exchange_repository.py
import logging
import time
import uuid
import datetime
from typing import Dict, Any, Optional

from source.db.connection_pool import DatabasePool
from source.utils.metrics import track_db_operation

logger = logging.getLogger('exchange_repository')

def round_down_to_minute(dt: datetime.datetime) -> datetime.datetime:
    """Round down datetime to the previous minute (remove seconds and microseconds)"""
    return dt.replace(second=0, microsecond=0)

class ExchangeRepository:
    """Repository for managing exchange metadata and user setup"""

    def __init__(self, db_pool=None):
        """Initialize the exchange repository"""
        logger.info("🏗️ Initializing ExchangeRepository")
        self.db_pool = db_pool or DatabasePool()
        logger.info(f"✅ ExchangeRepository initialized with db_pool: {self.db_pool is not None}")

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
        logger.info(f"🚀 EXCHANGE SETUP STARTING: book_id={book_id}, user_id={user_id}, initial_nav={initial_nav}")
        
        # Validate inputs
        if not user_id:
            logger.error("❌ User ID is empty or None")
            return False
        
        if not book_id:
            logger.error("❌ Book ID is empty or None")
            return False
        
        if initial_nav < 0:
            logger.error(f"❌ Initial NAV is negative: {initial_nav}")
            return False
        
        logger.info(f"✅ Input validation passed")
        
        # Generate unique exchange ID based on book ID
        exch_id = str(uuid.uuid4())
        logger.info(f"🆔 Generated exchange ID: {exch_id}")
        
        # Get database pool
        logger.info("🔌 Getting database connection pool...")
        try:
            pool = await self.db_pool.get_pool()
            logger.info("✅ Successfully retrieved database pool")
        except Exception as pool_error:
            logger.error(f"💥 Failed to get database pool: {pool_error}")
            logger.exception("Database pool exception:")
            return False
        
        start_time = time.time()
        
        try:
            logger.info("🔄 Starting database transaction...")
            async with pool.acquire() as conn:
                logger.info("✅ Successfully acquired database connection")
                
                async with conn.transaction():
                    logger.info("🔒 Transaction started")
                    
                    # 1. Create exchange metadata
                    logger.info(f"📋 Step 1: Creating exchange metadata for {exch_id}")
                    try:
                        await self._create_exchange_metadata(conn, exch_id)
                        logger.info("✅ Step 1 completed: Exchange metadata created")
                    except Exception as metadata_error:
                        logger.error(f"💥 Step 1 failed: {metadata_error}")
                        logger.exception("Exchange metadata creation exception:")
                        raise
                    
                    # 2. Create book in exchange
                    logger.info(f"👤 Step 2: Creating exchange book for {book_id}")
                    try:
                        await self._create_exchange_book(conn, book_id, exch_id, initial_nav)
                        logger.info("✅ Step 2 completed: Exchange book created")
                    except Exception as book_error:
                        logger.error(f"💥 Step 2 failed: {book_error}")
                        logger.exception("Exchange book creation exception:")
                        raise
                    
                    # 3. Create book operational parameters
                    logger.info(f"⚙️ Step 3: Creating operational parameters for {book_id}")
                    try:
                        await self._create_book_operational_parameters(conn, book_id)
                        logger.info("✅ Step 3 completed: Operational parameters created")
                    except Exception as params_error:
                        logger.error(f"💥 Step 3 failed: {params_error}")
                        logger.exception("Operational parameters creation exception:")
                        raise
                    
                    # 4. Create initial account data
                    logger.info(f"💰 Step 4: Creating initial account data for {book_id}")
                    try:
                        await self._create_initial_account_data(conn, book_id, initial_nav)
                        logger.info("✅ Step 4 completed: Initial account data created")
                    except Exception as account_error:
                        logger.error(f"💥 Step 4 failed: {account_error}")
                        logger.exception("Initial account data creation exception:")
                        raise
                    
                    logger.info("🔓 All steps completed, committing transaction...")
                    
                    duration = time.time() - start_time
                    track_db_operation("setup_exchange_for_book", True, duration)
                    
                    logger.info(f"🎉 Successfully set up exchange {exch_id} for book {book_id} in {duration:.2f}s")
                    return True
                    
        except Exception as e:
            duration = time.time() - start_time
            track_db_operation("setup_exchange_for_book", False, duration)
            logger.error(f"💥 EXCHANGE SETUP FAILED for book {book_id} after {duration:.2f}s: {e}")
            logger.exception("Full exchange setup exception:")
            return False

    async def _create_exchange_metadata(self, conn, exch_id: str):
        """Create exchange metadata entry"""
        logger.info(f"📋 Creating exchange metadata for {exch_id}")
        
        now_raw = datetime.datetime.now(datetime.timezone.utc)
        now = round_down_to_minute(now_raw)
        logger.info(f"⏰ Raw timestamp: {now_raw}")
        logger.info(f"⏰ Rounded timestamp: {now}")
        
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
        
        # Convert time strings to proper time objects
        import datetime as dt
        pre_market_open = dt.time(4, 0, 0)      # 04:00:00
        market_open = dt.time(9, 30, 0)         # 09:30:00  
        market_close = dt.time(16, 0, 0)        # 16:00:00
        post_market_close = dt.time(20, 0, 0)   # 20:00:00
        
        logger.info(f"🕐 Created time objects: pre_market={pre_market_open}, market_open={market_open}, market_close={market_close}, post_market={post_market_close}")
        
        values = (
            exch_id,                                # exch_id
            'US_EQUITIES',                          # exchange_type
            'placeholder_endpoint',                 # endpoint (placeholder)
            'placeholder_pod_name',                 # pod_name (placeholder)
            'placeholder_namespace',                # namespace (placeholder)
            'America/New_York',                     # timezone
            ['NYSE', 'NASDAQ', 'ARCA'],            # exchanges
            now,                                    # last_snap
            pre_market_open,                        # pre_market_open (TIME object)
            market_open,                            # market_open (TIME object)
            market_close,                           # market_close (TIME object)
            post_market_close                       # post_market_close (TIME object)
        )
        
        logger.debug(f"🔍 Executing metadata query with values: {values}")
        
        try:
            await conn.execute(query, *values)
            logger.info(f"✅ Exchange metadata created successfully for {exch_id}")
        except Exception as e:
            logger.error(f"💥 Failed to create exchange metadata for {exch_id}: {e}")
            logger.error(f"🔍 Query: {query}")
            logger.error(f"🔍 Values: {values}")
            raise

    async def _create_exchange_book(self, conn, book_id: str, exch_id: str, initial_nav: float):
        """Create book in exch_us_equity.bookb"""
        logger.info(f"👤 Creating exchange book: book_id={book_id}, exch_id={exch_id}, initial_nav={initial_nav}")
        
        # Convert initial_nav to proper decimal format
        logger.info(f"💰 Using initial_nav as: {initial_nav}")
        
        query = """
        INSERT INTO exch_us_equity.books (
            book_id,
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
        
        values = (
            book_id,                    # book_id
            exch_id,                    # exch_id
            'America/New_York',         # timezone
            'USD',                      # base_currency
            initial_nav,                # initial_nav (as decimal)
            0,                          # operation_id
            1,                          # engine_id
            0,                          # transaction_cost_model
            0                           # market_impact_model
        )
        
        logger.debug(f"🔍 Executing book query with values: {values}")
        
        try:
            await conn.execute(query, *values)
            logger.info(f"✅ Exchange book record created successfully for {book_id} on exchange {exch_id}")
        except Exception as e:
            logger.error(f"💥 Failed to create exchange book for {book_id}: {e}")
            logger.error(f"🔍 Query: {query}")
            logger.error(f"🔍 Values: {values}")
            raise

    async def _create_book_operational_parameters(self, conn, book_id: str):
        """Create book operational parameters"""
        logger.info(f"⚙️ Creating operational parameters for book {book_id}")
        
        query = """
        INSERT INTO exch_us_equity.book_operational_parameters (
            book_id,
            max_position_size_pct,
            min_position_size_pct,
            max_days_to_liquidate
        ) VALUES (
            $1, $2, $3, $4
        )
        ON CONFLICT (book_id) DO NOTHING
        """
        
        values = (
            book_id,    # book_id
            1.0,        # max_position_size_pct (100%)
            0.0,        # min_position_size_pct (0%)
            365         # max_days_to_liquidate
        )
        
        logger.debug(f"🔍 Executing operational parameters query with values: {values}")
        
        try:
            result = await conn.execute(query, *values)
            logger.info(f"✅ Operational parameters created for book {book_id} (result: {result})")
        except Exception as e:
            logger.error(f"💥 Failed to create operational parameters for {book_id}: {e}")
            logger.error(f"🔍 Query: {query}")
            logger.error(f"🔍 Values: {values}")
            raise

    async def _create_initial_account_data(self, conn, book_id: str, initial_nav: float):
        """Create initial account data records"""
        logger.info(f"💰 Creating initial account data for book {book_id} with initial_nav {initial_nav}")
        
        now_raw = datetime.datetime.now(datetime.timezone.utc)
        now = round_down_to_minute(now_raw)
        logger.info(f"⏰ Raw timestamp: {now_raw}")
        logger.info(f"⏰ Rounded timestamp: {now}")
        
        query = """
        INSERT INTO exch_us_equity.account_data (
            book_id,
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
        
        logger.info(f"📊 Creating {len(account_types)} account types: {[at[0] for at in account_types]}")
        
        for account_type, amount, previous_amount, change in account_types:
            values = (
                book_id,            # book_id
                now,                # timestamp
                account_type,       # type
                'USD',              # currency
                amount,             # amount
                previous_amount,    # previous_amount
                change              # change
            )
            
            logger.debug(f"🔍 Creating {account_type} account with values: {values}")
            
            try:
                await conn.execute(query, *values)
                logger.info(f"✅ Created {account_type} account for book {book_id} with amount {amount}")
            except Exception as e:
                logger.error(f"💥 Failed to create {account_type} account for {book_id}: {e}")
                logger.error(f"🔍 Query: {query}")
                logger.error(f"🔍 Values: {values}")
                raise
        
        logger.info(f"🎉 All initial account data created successfully for book {book_id}")

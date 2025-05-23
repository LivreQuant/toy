# source/db/conviction_repository.py
import logging
import time
import uuid
from typing import Dict, Any, List, Optional

from source.db.connection_pool import DatabasePool
from source.models.conviction import ConvictionData

from source.utils.metrics import track_db_operation, track_conviction_created, track_user_conviction


logger = logging.getLogger('conviction_repository')


class ConvictionRepository:
    """Data access layer for convictions"""

    def __init__(self):
        """Initialize the conviction repository"""
        self.db_pool = DatabasePool()
        
    async def save_convictions(self, convictions: List[ConvictionData]) -> Dict[str, List[str]]:
        """
        Save multiple convictions in a batch
        
        Returns:
            Dict with successful and failed conviction IDs
        """
        pool = await self.db_pool.get_pool()
        
        # Query exactly matching the schema
        query = """
        INSERT INTO trading.convictions (
            conviction_id, user_id, symbol, side, quantity, price, 
            conviction_type, status, filled_quantity, avg_price,
            created_at, updated_at, request_id, error_message
        ) VALUES (
            $1, $2, $3, $4, $5, $6, $7, $8, $9, $10,
            to_timestamp($11), to_timestamp($12), $13, $14
        )
        """
        
        successful_conviction_ids = []
        failed_conviction_ids = []
        
        start_time = time.time()
        try:
            async with pool.acquire() as conn:
                # Start a transaction
                async with conn.transaction():
                    for conviction in convictions:
                        try:
                            await conn.execute(
                                query,
                                conviction.conviction_id,
                                conviction.user_id,
                                conviction.symbol,
                                conviction.side.value,
                                conviction.quantity,
                                conviction.price,
                                conviction.conviction_type.value,
                                conviction.status.value,
                                conviction.filled_quantity,
                                conviction.avg_price,
                                conviction.created_at,
                                conviction.updated_at,
                                conviction.request_id,
                                conviction.error_message
                            )
                            successful_conviction_ids.append(conviction.conviction_id)
                        except Exception as conviction_error:
                            logger.error(f"Error saving conviction {conviction.conviction_id}: {conviction_error}")
                            failed_conviction_ids.append(conviction.conviction_id)
                    
                    duration = time.time() - start_time
                    track_db_operation("save_convictions_batch", True, duration)
                    
                    return {
                        "successful": successful_conviction_ids,
                        "failed": failed_conviction_ids
                    }
        except Exception as e:
            duration = time.time() - start_time
            track_db_operation("save_convictions_batch", False, duration)
            logger.error(f"Error batch saving convictions: {e}")
            
            return {
                "successful": successful_conviction_ids,
                "failed": failed_conviction_ids if failed_conviction_ids else [o.conviction_id for o in convictions]
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
                    request_id, conviction_id, status, created_at
                FROM trading.convictions
                WHERE user_id = $1 AND request_id = ANY($2::text[]) AND request_id IS NOT NULL
                ORDER BY request_id, created_at DESC
                """
                rows = await conn.fetch(query, user_id, request_ids)
                
                # Create mapping of request_id to basic response structure
                results = {}
                for row in rows:
                    results[row['request_id']] = {
                        "success": True,
                        "convictionId": row['conviction_id'],
                        "message": f"Conviction previously submitted with status: {row['status']}"
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
                SELECT conviction_id, status FROM trading.convictions
                WHERE request_id = $1 AND user_id = $2
                ORDER BY created_at DESC
                LIMIT 1
                """
                row = await conn.fetchrow(query, request_id, user_id)
                
                if row:
                    logger.info(f"Found duplicate request {request_id}")
                    return {
                        "success": True,
                        "convictionId": row['conviction_id'],
                        "message": f"Conviction previously submitted with status: {row['status']}"
                    }
                return None
        except Exception as e:
            logger.error(f"Error checking duplicate request: {e}")
            return None
      
    async def save_conviction(self, conviction: ConvictionData) -> bool:
        """Save a single conviction to the database"""
        pool = await self.db_pool.get_pool()
        
        query = """
        INSERT INTO trading.convictions (
            conviction_id, user_id, symbol, side, quantity, price, 
            conviction_type, status, filled_quantity, avg_price,
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
                    conviction.conviction_id,
                    conviction.user_id,
                    conviction.symbol,
                    conviction.side.value,
                    conviction.quantity,
                    conviction.price,
                    conviction.conviction_type.value,
                    conviction.status.value,
                    conviction.filled_quantity,
                    conviction.avg_price,
                    conviction.created_at,
                    conviction.updated_at,
                    conviction.request_id,
                    conviction.error_message
                )
                
                duration = time.time() - start_time
                track_db_operation("save_conviction", True, duration)
                
                # Track conviction creation metrics
                track_conviction_created(conviction.conviction_type, conviction.symbol, conviction.side)
                track_user_conviction(conviction.user_id)
                
                return True
        except Exception as e:
            duration = time.time() - start_time
            track_db_operation("save_conviction", False, duration)
            logger.error(f"Error saving conviction {conviction.conviction_id}: {e}")
            return False
            
    async def save_conviction_status(self, conviction_id: str, user_id: str, status: str, error_message: str = None) -> bool:
        """
        Create a new row with updated status for an conviction
        
        Args:
            conviction_id: Conviction ID
            user_id: User ID
            status: New status
            error_message: Optional error message
            
        Returns:
            Success flag
        """
        try:
            pool = await self.db_pool.get_pool()
            async with pool.acquire() as conn:
                # First get the current conviction data
                query_select = """
                WITH latest_conviction AS (
                    SELECT * FROM trading.convictions 
                    WHERE conviction_id = $1 
                    ORDER BY created_at DESC 
                    LIMIT 1
                )
                SELECT * FROM latest_conviction
                """
                
                conviction_data = await conn.fetchrow(query_select, conviction_id)
                
                if not conviction_data:
                    logger.error(f"Conviction not found: {conviction_id}")
                    return False
                    
                # Insert new row with updated status
                query_insert = """
                INSERT INTO trading.convictions (
                    conviction_id, status, user_id, symbol, side, quantity, price, 
                    oconviction_type, filled_quantity, avg_price, created_at, updated_at, 
                    request_id, error_message
                ) VALUES (
                    $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, 
                    to_timestamp($11), to_timestamp($12), $13, $14
                )
                """
                
                now = time.time()
                
                await conn.execute(
                    query_insert,
                    conviction_id,
                    status,
                    conviction_data['user_id'],
                    conviction_data['symbol'],
                    conviction_data['side'],
                    conviction_data['quantity'],
                    conviction_data['price'],
                    conviction_data['conviction_type'],
                    conviction_data['filled_quantity'],
                    conviction_data['avg_price'],
                    now,
                    now,
                    conviction_data['request_id'],
                    error_message or conviction_data['error_message']
                )
                
                return True
                
        except Exception as e:
            logger.error(f"Error saving conviction status: {e}")
            return False
    
    async def batch_save_conviction_status(self, conviction_ids: List[str], status: str, error_message: str = None) -> Dict[str, List[str]]:
        """
        Create new rows with updated status for multiple convictions
        
        Args:
            conviction_ids: List of conviction IDs
            status: New status
            error_message: Optional error message
            
        Returns:
            Dictionary with successful and failed conviction IDs
        """
        if not conviction_ids:
            return {"successful": [], "failed": []}
            
        successful = []
        failed = []
        
        try:
            pool = await self.db_pool.get_pool()
            async with pool.acquire() as conn:
                # Use a transaction for all updates
                async with conn.transaction():
                    for conviction_id in conviction_ids:
                        try:
                            # First get the current conviction data
                            query_select = """
                            WITH latest_conviction AS (
                                SELECT * FROM trading.convictions 
                                WHERE conviction_id = $1 
                                ORDER BY created_at DESC 
                                LIMIT 1
                            )
                            SELECT * FROM latest_conviction
                            """
                            
                            conviction_data = await conn.fetchrow(query_select, conviction_id)
                            
                            if not conviction_data:
                                logger.error(f"Conviction not found: {conviction_id}")
                                failed.append(conviction_id)
                                continue
                                
                            # Insert new row with updated status
                            query_insert = """
                            INSERT INTO trading.convictions (
                                conviction_id, status, user_id, symbol, side, quantity, price, 
                                conviction_type, filled_quantity, avg_price, created_at, updated_at, 
                                request_id, error_message
                            ) VALUES (
                                $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, 
                                to_timestamp($11), to_timestamp($12), $13, $14
                            )
                            """
                            
                            now = time.time()
                            
                            await conn.execute(
                                query_insert,
                                conviction_id,
                                status,
                                conviction_data['user_id'],
                                conviction_data['symbol'],
                                conviction_data['side'],
                                conviction_data['quantity'],
                                conviction_data['price'],
                                conviction_data['conviction_type'],
                                conviction_data['filled_quantity'],
                                conviction_data['avg_price'],
                                now,
                                now,
                                conviction_data['request_id'],
                                error_message or conviction_data['error_message']
                            )
                            
                            successful.append(conviction_id)
                        except Exception as e:
                            logger.error(f"Error updating conviction {conviction_id}: {e}")
                            failed.append(conviction_id)
                            
            return {"successful": successful, "failed": failed}
        except Exception as e:
            logger.error(f"Error in batch status update: {e}")
            return {"successful": successful, "failed": failed}
    
    async def get_convictions_info(self, conviction_ids: List[str]) -> List[Dict[str, Any]]:
        """
        Get information about multiple convictions in a single query
        
        Args:
            conviction_ids: List of conviction IDs to check
            
        Returns:
            List of conviction information dictionaries
        """
        if not conviction_ids:
            return []

        try:
            pool = await self.db_pool.get_pool()
            async with pool.acquire() as conn:
                # Use WITH to get the latest status of each conviction
                query = """
                WITH latest_convictions AS (
                    SELECT DISTINCT ON (conviction_id) *
                    FROM trading.convictions
                    WHERE conviction_id = ANY($1::uuid[])
                    ORDER BY conviction_id, created_at DESC
                )
                SELECT conviction_id, user_id, symbol, side, status
                FROM latest_convictions
                """
                rows = await conn.fetch(query, conviction_ids)
                return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Error getting conviction information: {e}")
            return []
            
    async def get_open_convictions_by_symbol(self, user_id: str, symbols: List[str]) -> List[Dict[str, Any]]:
        """
        Get all open convictions for a user by symbols
        
        Args:
            user_id: User ID
            symbols: List of symbols to find convictions for
            
        Returns:
            List of conviction information dictionaries
        """
        if not symbols:
            return []
            
        try:
            pool = await self.db_pool.get_pool()
            async with pool.acquire() as conn:
                # Find the most recent status for each conviction_id that matches our criteria
                query = """
                WITH latest_convictions AS (
                    SELECT DISTINCT ON (conviction_id) *
                    FROM trading.convictions
                    WHERE user_id = $1 AND symbol = ANY($2::text[])
                    ORDER BY conviction_id, created_at DESC
                )
                SELECT conviction_id, symbol, status
                FROM latest_convictions
                WHERE status IN ('NEW', 'PARTIALLY_FILLED')
                """
                
                rows = await conn.fetch(query, user_id, symbols)
                return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Error getting open convictions: {e}")
            return []
    
    async def get_conviction(self, conviction_id: str) -> Optional[ConvictionData]:
        """Get a single conviction by ID (latest status)"""
        pool = await self.db_pool.get_pool()
        
        query = """
        WITH latest_conviction AS (
            SELECT * FROM trading.convictions 
            WHERE conviction_id = $1 
            ORDER BY created_at DESC 
            LIMIT 1
        )
        SELECT * FROM latest_conviction
        """
        
        try:
            async with pool.acquire() as conn:
                row = await conn.fetchrow(query, conviction_id)
                if not row:
                    return None
                    
                # Create Conviction object from row
                conviction_data = dict(row)
                
                # Convert timestamp to float for created_at and updated_at
                if 'created_at' in conviction_data:
                    conviction_data['created_at'] = conviction_data['created_at'].timestamp()
                if 'updated_at' in conviction_data:
                    conviction_data['updated_at'] = conviction_data['updated_at'].timestamp()
                
                return Conviction.from_dict(conviction_data)
        except Exception as e:
            logger.error(f"Error getting conviction {conviction_id}: {e}")
            return None
    
    async def store_submit_conviction_data(self, tx_id: str, book_id: str, convictions_data: list) -> bool:
        """
        Store submission data in conv.submit table
        
        Args:
            tx_id: Transaction ID from crypto.txs
            book_id: Book ID
            convictions_data: List of conviction data dictionaries
            
        Returns:
            Success flag
        """
        pool = await self.db_pool.get_pool()
        
        submit_query = """
        INSERT INTO conv.submit (
            book_id, tx_id, ix, instrument_id, participation_rate, tag, conviction_id,
            side, score, quantity, zscore, target_percentage, target_notional, horizon_zscore
        ) VALUES (
            $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14
        )
        """
        
        start_time = time.time()
        try:
            async with pool.acquire() as conn:
                async with conn.transaction():
                    for ix, conviction in enumerate(convictions_data):
                        # Map ConvictionData fields to database columns
                        instrument_id = conviction.get('instrumentId', '')
                        participation_rate = str(conviction.get('participationRate', ''))
                        tag = conviction.get('tag', '')
                        conviction_id = conviction.get('convictionId', str(uuid.uuid4()))  # Generate if not provided
                        
                        # Optional fields
                        side = conviction.get('side')
                        score = conviction.get('score')
                        quantity = conviction.get('quantity')
                        zscore = conviction.get('zscore')
                        target_percentage = conviction.get('targetPercent')
                        target_notional = conviction.get('targetNotional')
                        
                        # Handle dynamic horizon z-scores (multi-horizon support)
                        horizon_zscore = None
                        horizon_fields = {k: v for k, v in conviction.items() 
                                        if k not in ['instrumentId', 'participationRate', 'tag', 'convictionId', 
                                                'side', 'score', 'quantity', 'zscore', 'targetPercent', 'targetNotional']}
                        if horizon_fields:
                            horizon_zscore = json.dumps(horizon_fields)
                        
                        await conn.execute(
                            submit_query,
                            book_id, tx_id, ix, instrument_id, participation_rate, tag, conviction_id,
                            side, score, quantity, zscore, target_percentage, target_notional, horizon_zscore
                        )
                    
                    duration = time.time() - start_time
                    track_db_operation("store_submit_conviction", True, duration)
                    logger.info(f"Stored {len(convictions_data)} conviction submit records for transaction {tx_id}")
                    return True
                    
        except Exception as e:
            duration = time.time() - start_time
            track_db_operation("store_submit_conviction", False, duration)
            logger.error(f"Error storing conviction submit data: {e}")
            return False

    async def store_cancel_conviction_data(self, tx_id: str, book_id: str, conviction_ids: list) -> bool:
        """
        Store cancellation data in conv.cancel table
        
        Args:
            tx_id: Transaction ID from crypto.txs
            book_id: Book ID
            conviction_ids: List of conviction IDs to cancel
            
        Returns:
            Success flag
        """
        pool = await self.db_pool.get_pool()
        
        cancel_query = """
        INSERT INTO conv.cancel (
            book_id, tx_id, ix, conviction_id
        ) VALUES (
            $1, $2, $3, $4
        )
        """
        
        start_time = time.time()
        try:
            async with pool.acquire() as conn:
                async with conn.transaction():
                    for ix, conviction_id in enumerate(conviction_ids):
                        await conn.execute(
                            cancel_query,
                            book_id, tx_id, ix, conviction_id
                        )
                    
                    duration = time.time() - start_time
                    track_db_operation("store_cancel_conviction", True, duration)
                    logger.info(f"Stored {len(conviction_ids)} conviction cancel records for transaction {tx_id}")
                    return True
                    
        except Exception as e:
            duration = time.time() - start_time
            track_db_operation("store_cancel_conviction", False, duration)
            logger.error(f"Error storing conviction cancel data: {e}")
            return False
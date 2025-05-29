# source/db/conviction_repository.py
import logging
import time
import uuid
import json
from typing import Dict, Any, List, Optional

from source.db.connection_pool import DatabasePool
from source.utils.metrics import track_db_operation

logger = logging.getLogger('conviction_repository')

class ConvictionRepository:
    """Data access layer for convictions"""

    def __init__(self):
        """Initialize the conviction repository"""
        self.db_pool = DatabasePool()
        
    async def check_duplicate_requests(self, user_id: str, request_ids: List[str]) -> Dict[str, Dict[str, Any]]:
        """Check multiple request IDs for duplicates in a single query"""
        if not request_ids:
            return {}

        start_time = time.time()
        try:
            pool = await self.db_pool.get_pool()
            async with pool.acquire() as conn:
                # Check for duplicate request_ids in conv.submit
                query = """
                SELECT DISTINCT ON (conviction_id) 
                    conviction_id, book_id, tx_id
                FROM conv.submit
                WHERE conviction_id = ANY($1::text[])
                ORDER BY conviction_id, tx_id DESC
                """
                rows = await conn.fetch(query, request_ids)
                
                # Create mapping of request_id to basic response structure
                results = {}
                for row in rows:
                    results[row['conviction_id']] = {
                        "success": True,
                        "convictionId": row['conviction_id'],
                        "message": f"Conviction previously submitted in transaction: {row['tx_id']}"
                    }
                    
                duration = time.time() - start_time
                track_db_operation("check_duplicate_requests", True, duration)
                return results
                
        except Exception as e:
            duration = time.time() - start_time
            track_db_operation("check_duplicate_requests", False, duration)
            logger.error(f"Error checking duplicate requests: {e}")
            return {}

    async def store_submit_conviction_data(self, tx_id: str, book_id: str, convictions_data: list) -> bool:
        """Store submission data in conv.submit table"""
        pool = await self.db_pool.get_pool()
        
        submit_query = """
        INSERT INTO conv.submit (
            book_id, tx_id, row, instrument_id, participation_rate, tag, conviction_id,
            side, score, quantity, zscore, target_percentage, target_notional, horizon_zscore
        ) VALUES (
            $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14
        )
        """
        
        start_time = time.time()
        try:
            async with pool.acquire() as conn:
                async with conn.transaction():
                    for row, conviction in enumerate(convictions_data):
                        # Map ConvictionData fields to database columns
                        instrument_id = conviction.get('instrumentId', '')
                        participation_rate = str(conviction.get('participationRate', ''))
                        tag = conviction.get('tag', '')
                        conviction_id = conviction.get('convictionId', str(uuid.uuid4()))
                        
                        # Optional fields
                        side = conviction.get('side')
                        score = conviction.get('score')
                        quantity = conviction.get('quantity')
                        zscore = conviction.get('zscore')
                        target_percentage = conviction.get('targetPercent')
                        target_notional = conviction.get('targetNotional')
                        
                        # Handle dynamic horizon z-scores
                        horizon_zscore = None
                        horizon_fields = {k: v for k, v in conviction.items() 
                                        if k not in ['instrumentId', 'participationRate', 'tag', 'convictionId', 
                                                'side', 'score', 'quantity', 'zscore', 'targetPercent', 'targetNotional']}
                        if horizon_fields:
                            horizon_zscore = json.dumps(horizon_fields)
                        
                        await conn.execute(
                            submit_query,
                            book_id, tx_id, row, instrument_id, participation_rate, tag, conviction_id,
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
        """Store cancellation data in conv.cancel table"""
        pool = await self.db_pool.get_pool()
        
        cancel_query = """
        INSERT INTO conv.cancel (
            book_id, tx_id, row, conviction_id
        ) VALUES (
            $1, $2, $3, $4
        )
        """
        
        start_time = time.time()
        try:
            async with pool.acquire() as conn:
                async with conn.transaction():
                    for row, conviction_id in enumerate(conviction_ids):
                        await conn.execute(
                            cancel_query,
                            book_id, tx_id, row, conviction_id
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

    async def get_conviction_history(self, book_id: str, instrument_id: str = None, limit: int = 100) -> List[Dict[str, Any]]:
        """Get conviction history for a book, optionally filtered by instrument"""
        pool = await self.db_pool.get_pool()
        
        start_time = time.time()
        try:
            if instrument_id:
                query = """
                SELECT s.*, 'SUBMIT' as action_type FROM conv.submit s
                WHERE s.book_id = $1 AND s.instrument_id = $2
                UNION ALL
                SELECT c.book_id, c.tx_id, c.row, NULL as instrument_id, NULL as participation_rate, 
                       NULL as tag, c.conviction_id, NULL as side, NULL as score, NULL as quantity, 
                       NULL as zscore, NULL as target_percentage, NULL as target_notional, 
                       NULL as horizon_zscore, 'CANCEL' as action_type 
                FROM conv.cancel c
                WHERE c.book_id = $1 AND c.conviction_id IN (
                    SELECT conviction_id FROM conv.submit WHERE book_id = $1 AND instrument_id = $2
                )
                ORDER BY tx_id DESC, row
                LIMIT $3
                """
                params = (book_id, instrument_id, limit)
            else:
                query = """
                SELECT s.*, 'SUBMIT' as action_type FROM conv.submit s
                WHERE s.book_id = $1
                UNION ALL
                SELECT c.book_id, c.tx_id, c.row, NULL as instrument_id, NULL as participation_rate, 
                       NULL as tag, c.conviction_id, NULL as side, NULL as score, NULL as quantity, 
                       NULL as zscore, NULL as target_percentage, NULL as target_notional, 
                       NULL as horizon_zscore, 'CANCEL' as action_type 
                FROM conv.cancel c
                WHERE c.book_id = $1
                ORDER BY tx_id DESC, row
                LIMIT $2
                """
                params = (book_id, limit)
        
            async with pool.acquire() as conn:
                rows = await conn.fetch(query, *params)
                
                duration = time.time() - start_time
                track_db_operation("get_conviction_history", True, duration)
                return [dict(row) for row in rows]
                
        except Exception as e:
            duration = time.time() - start_time
            track_db_operation("get_conviction_history", False, duration)
            logger.error(f"Error getting conviction history: {e}")
            return []

    async def get_active_convictions(self, book_id: str) -> List[Dict[str, Any]]:
        """Get active convictions for a book (submitted but not cancelled)"""
        pool = await self.db_pool.get_pool()
        
        query = """
        SELECT s.* FROM conv.submit s
        WHERE s.book_id = $1 
        AND s.conviction_id NOT IN (
            SELECT c.conviction_id FROM conv.cancel c 
            WHERE c.book_id = $1 AND c.conviction_id IS NOT NULL
        )
        ORDER BY s.tx_id DESC, s.row
        """
        
        start_time = time.time()
        try:
            async with pool.acquire() as conn:
                rows = await conn.fetch(query, book_id)
                
                duration = time.time() - start_time
                track_db_operation("get_active_convictions", True, duration)
                return [dict(row) for row in rows]
                
        except Exception as e:
            duration = time.time() - start_time
            track_db_operation("get_active_convictions", False, duration)
            logger.error(f"Error getting active convictions: {e}")
            return []

    async def get_conviction_by_id(self, conviction_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific conviction by ID"""
        pool = await self.db_pool.get_pool()
        
        query = """
        SELECT * FROM conv.submit
        WHERE conviction_id = $1
        ORDER BY tx_id DESC
        LIMIT 1
        """
        
        start_time = time.time()
        try:
            async with pool.acquire() as conn:
                row = await conn.fetchrow(query, conviction_id)
                
                duration = time.time() - start_time
                if row:
                    track_db_operation("get_conviction_by_id", True, duration)
                    return dict(row)
                else:
                    track_db_operation("get_conviction_by_id", False, duration)
                    return None
                    
        except Exception as e:
            duration = time.time() - start_time
            track_db_operation("get_conviction_by_id", False, duration)
            logger.error(f"Error getting conviction by ID: {e}")
            return None

    async def is_conviction_cancelled(self, conviction_id: str) -> bool:
        """Check if a conviction has been cancelled"""
        pool = await self.db_pool.get_pool()
        
        query = """
        SELECT COUNT(*) FROM conv.cancel
        WHERE conviction_id = $1
        """
        
        try:
            async with pool.acquire() as conn:
                count = await conn.fetchval(query, conviction_id)
                return count > 0
                
        except Exception as e:
            logger.error(f"Error checking if conviction is cancelled: {e}")
            return False

    async def get_book_conviction_stats(self, book_id: str) -> Dict[str, Any]:
        """Get conviction statistics for a book"""
        pool = await self.db_pool.get_pool()
        
        try:
            async with pool.acquire() as conn:
                # Get submit count
                submit_count = await conn.fetchval("""
                    SELECT COUNT(*) FROM conv.submit WHERE book_id = $1
                """, book_id)
                
                # Get cancel count
                cancel_count = await conn.fetchval("""
                    SELECT COUNT(*) FROM conv.cancel WHERE book_id = $1
                """, book_id)
                
                # Get active count
                active_count = await conn.fetchval("""
                    SELECT COUNT(*) FROM conv.submit s
                    WHERE s.book_id = $1 
                    AND s.conviction_id NOT IN (
                        SELECT c.conviction_id FROM conv.cancel c 
                        WHERE c.book_id = $1 AND c.conviction_id IS NOT NULL
                    )
                """, book_id)
                
                # Get unique instruments
                unique_instruments = await conn.fetchval("""
                    SELECT COUNT(DISTINCT instrument_id) FROM conv.submit WHERE book_id = $1
                """, book_id)
                
                return {
                    'book_id': book_id,
                    'total_submissions': submit_count,
                    'total_cancellations': cancel_count,
                    'active_convictions': active_count,
                    'unique_instruments': unique_instruments
                }
                
        except Exception as e:
            logger.error(f"Error getting book conviction stats: {e}")
            return {
                'book_id': book_id,
                'total_submissions': 0,
                'total_cancellations': 0,
                'active_convictions': 0,
                'unique_instruments': 0
            }
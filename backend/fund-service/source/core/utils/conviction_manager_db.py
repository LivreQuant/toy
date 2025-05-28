# source/core/record_manager.py
import logging
import time
import uuid
import json
from typing import Dict, Any, Optional

from source.models.conviction import ConvictionData
from source.db.conviction_repository import ConvictionRepository
from source.utils.metrics import track_conviction_created, track_user_conviction

logger = logging.getLogger('record_manager')


class RecordManager:
    """Manager for recording convictions and tracking request duplicates"""

    def __init__(
            self,
            conviction_repository: ConvictionRepository
    ):
        self.conviction_repository = conviction_repository

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
            pool = await self.conviction_repository.db_pool.get_pool()
            async with pool.acquire() as conn:
                query = """
                SELECT response FROM trading.convictions
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
            pool = await self.conviction_repository.db_pool.get_pool()
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
            pool = await self.conviction_repository.db_pool.get_pool()
            async with pool.acquire() as conn:
                query = """
                DELETE FROM trading.request_idempotency
                WHERE created_at < NOW() - INTERVAL '1 day'
                """
                result = await conn.execute(query)
                logger.info(f"Cleaned up old request records: {result}")
        except Exception as e:
            logger.error(f"Error cleaning up old requests: {e}")

    async def save_conviction(self, conviction_params: Dict[str, Any], user_id: str,
                           request_id: str = None,
                           simulator_id: str = None) -> ConvictionData:
        """
        Create a new conviction object and save it to database
        
        Args:
            conviction_params: Validated conviction parameters
            user_id: User ID
            request_id: Optional request ID for idempotency
            simulator_id: Optional simulator ID
            
        Returns:
            New conviction object
        """
        # Create conviction object with a new UUID
        conviction = ConvictionData(
            symbol=conviction_params.get('symbol'),
            side=conviction_params.get('side'),
            quantity=conviction_params.get('quantity'),
            conviction_type=conviction_params.get('conviction_type'),
            price=conviction_params.get('price'),
            user_id=user_id,
            request_id=request_id,
            conviction_id=str(uuid.uuid4()),  # Generate new conviction ID
            created_at=time.time(),
            updated_at=time.time(),
            simulator_id=simulator_id
        )

        # Track oconviction creation metrics
        track_conviction_created(conviction.conviction_type, conviction.symbol, conviction.side)
        track_user_conviction(user_id)

        # Save to database
        success = await self.conviction_repository.save_conviction(conviction)
        if not success:
            logger.error(f"Failed to save conviction {conviction.conviction_id} to database")
            raise Exception("Database error: Failed to save conviction")

        logger.info(f"Successfully created and saved conviction {conviction.conviction_id}")
        return conviction

    async def validate_conviction_parameters(self, conviction_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate conviction parameters with sensible defaults

        Args:
            conviction_data: Conviction data to validate

        Returns:
            Validation result with extracted parameters if valid
        """
        try:
            # Extract required fields
            instrument_id = conviction_data.get('instrumentId')
            
            # Basic validation - only instrumentId is truly required
            if not instrument_id:
                logger.warning(f"Conviction validation failed - missing instrumentId: {conviction_data}")
                return {
                    "valid": False,
                    "error": "instrumentId is required"
                }
            
            # Set defaults for missing fields
            side = conviction_data.get('side', 'BUY')
            score = conviction_data.get('score', 0.0)
            quantity = conviction_data.get('quantity', 100.0)
            zscore = conviction_data.get('zscore', 0.0)
            target_percent = conviction_data.get('targetPercent', 1.0)
            target_notional = conviction_data.get('targetNotional', 1000.0)
            participation_rate = conviction_data.get('participationRate', 'MEDIUM')
            tag = conviction_data.get('tag', 'default')
            conviction_id = conviction_data.get('convictionId', str(uuid.uuid4()))
            
            # Validate side
            if side not in ['BUY', 'SELL', 'CLOSE']:
                logger.warning(f"Invalid side '{side}', defaulting to BUY")
                side = 'BUY'
            
            # Validate participation rate
            if participation_rate not in ['LOW', 'MEDIUM', 'HIGH']:
                logger.warning(f"Invalid participationRate '{participation_rate}', defaulting to MEDIUM")
                participation_rate = 'MEDIUM'
            
            # Ensure numeric fields are numeric with defaults
            try:
                score = float(score)
            except (ValueError, TypeError):
                logger.warning(f"Invalid score '{score}', defaulting to 0.0")
                score = 0.0
                
            try:
                quantity = float(quantity)
            except (ValueError, TypeError):
                logger.warning(f"Invalid quantity '{quantity}', defaulting to 100.0")
                quantity = 100.0
                
            try:
                zscore = float(zscore)
            except (ValueError, TypeError):
                logger.warning(f"Invalid zscore '{zscore}', defaulting to 0.0")
                zscore = 0.0
                
            try:
                target_percent = float(target_percent)
            except (ValueError, TypeError):
                logger.warning(f"Invalid targetPercent '{target_percent}', defaulting to 1.0")
                target_percent = 1.0
                
            try:
                target_notional = float(target_notional)
            except (ValueError, TypeError):
                logger.warning(f"Invalid targetNotional '{target_notional}', defaulting to 1000.0")
                target_notional = 1000.0
            
            logger.info(f"Conviction validation successful for {instrument_id}")
            
            return {
                "valid": True,
                "instrumentId": instrument_id,
                "side": side,
                "score": score,
                "quantity": quantity,
                "zscore": zscore,
                "targetPercent": target_percent,
                "targetNotional": target_notional,
                "participationRate": participation_rate,
                "tag": tag,
                "convictionId": conviction_id
            }

        except Exception as e:
            logger.error(f"Error validating conviction parameters: {e}")
            return {
                "valid": False,
                "error": f"Validation error: {str(e)}"
            }


    async def store_submit_conviction_data(self, tx_id: str, book_id: str, convictions_data: list) -> bool:
        """Store submission data via repository"""
        try:
            return await self.conviction_repository.store_submit_conviction_data(
                tx_id=tx_id,
                book_id=book_id,
                convictions_data=convictions_data
            )
        except Exception as e:
            logger.error(f"Error storing submission data: {e}")
            return False

    async def store_cancel_conviction_data(self, tx_id: str, book_id: str, conviction_ids: list) -> bool:
        """Store cancellation data via repository"""
        try:
            return await self.conviction_repository.store_cancel_conviction_data(
                tx_id=tx_id,
                book_id=book_id,
                conviction_ids=conviction_ids
            )
        except Exception as e:
            logger.error(f"Error storing cancellation data: {e}")
            return False
        
    async def get_fund_id_for_user(self, user_id: str) -> str:
        """Get fund_id for a user via repository"""
        try:
            pool = await self.conviction_repository.db_pool.get_pool()
            async with pool.acquire() as conn:
                fund_id = await conn.fetchval(
                    "SELECT fund_id FROM fund.funds WHERE user_id = $1 LIMIT 1",
                    user_id
                )
                return str(fund_id) if fund_id else user_id  # fallback to user_id
        except Exception as e:
            logger.error(f"Error getting fund_id for user {user_id}: {e}")
            return user_id  # fallback to user_id

    async def store_submit_conviction_data(self, tx_id: str, book_id: str, convictions_data: list) -> bool:
        """Store submission data via repository"""
        try:
            return await self.conviction_repository.store_submit_conviction_data(
                tx_id=tx_id,
                book_id=book_id,
                convictions_data=convictions_data
            )
        except Exception as e:
            logger.error(f"Error storing submission data: {e}")
            return False

    async def store_cancel_conviction_data(self, tx_id: str, book_id: str, conviction_ids: list) -> bool:
        """Store cancellation data via repository"""
        try:
            return await self.conviction_repository.store_cancel_conviction_data(
                tx_id=tx_id,
                book_id=book_id,
                conviction_ids=conviction_ids
            )
        except Exception as e:
            logger.error(f"Error storing cancellation data: {e}")
            return False
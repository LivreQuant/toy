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
        Validate conviction parameters

        Args:
            conviction_data: Conviction data to validate

        Returns:
            Validation result with extracted parameters if valid
        """
        try:
            symbol = conviction_data.get('symbol')
            side = conviction_data.get('side')
            quantity = float(conviction_data.get('quantity', 0))
            conviction_type = conviction_data.get('type')
            price = float(conviction_data.get('price', 0)) if 'price' in conviction_data else None

            # Basic validation
            if not symbol or not side or not conviction_type or quantity <= 0:
                logger.warning(f"Conviction validation failed: {conviction_data}")
                return {
                    "valid": False,
                    "error": "Invalid conviction parameters"
                }

            # For limit convictions, price is required
            if conviction_type == 'LIMIT' and (price is None or price <= 0):
                return {
                    "valid": False,
                    "error": "Limit convictions require a valid price greater than zero"
                }

            # Return validated parameters
            return {
                "valid": True,
                "symbol": symbol,
                "side": side,
                "quantity": quantity,
                "conviction_type": conviction_type,
                "price": price
            }

        except ValueError:
            return {
                "valid": False,
                "error": "Invalid conviction parameters: quantity and price must be numeric"
            }

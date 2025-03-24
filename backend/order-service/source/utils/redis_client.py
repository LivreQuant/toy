import logging
import asyncio
import redis.asyncio as redis
from typing import Optional

from source.config import config

logger = logging.getLogger('redis_client')

class RedisClient:
    """Redis client for the order service"""
    
    def __init__(self, client: redis.Redis):
        """Initialize with a Redis client"""
        self.client = client
    
    @classmethod
    async def create(cls, max_retries: int = 5) -> 'RedisClient':
        """Create a Redis client with retry logic"""
        retry = 0
        while retry < max_retries:
            try:
                # Create Redis client
                redis_client = redis.Redis(
                    host=config.redis_host,
                    port=config.redis_port,
                    db=config.redis_db,
                    password=config.redis_password,
                    decode_responses=True,
                    socket_timeout=5.0,
                    socket_connect_timeout=5.0,
                    retry_on_timeout=True
                )
                
                # Test connection
                await redis_client.ping()
                logger.info("Connected to Redis successfully")
                return cls(redis_client)
            except Exception as e:
                retry += 1
                wait_time = 0.5 * (2 ** retry)  # Exponential backoff
                logger.warning(f"Redis connection attempt {retry} failed: {e}. Retrying in {wait_time}s")
                await asyncio.sleep(wait_time)
        
        logger.error(f"Failed to connect to Redis after {max_retries} attempts")
        raise ConnectionError("Could not connect to Redis")
    
    async def get(self, key: str) -> Optional[str]:
        """Get a value from Redis"""
        return await self.client.get(key)
    
    async def set(self, key: str, value: str, expiry: Optional[int] = None) -> bool:
        """Set a value in Redis with optional expiry"""
        return await self.client.set(key, value, ex=expiry)
    
    async def exists(self, key: str) -> bool:
        """Check if a key exists in Redis"""
        return await self.client.exists(key)
    
    async def delete(self, key: str) -> int:
        """Delete a key from Redis"""
        return await self.client.delete(key)
    
    async def ping(self) -> bool:
        """Check Redis connection"""
        try:
            return await self.client.ping()
        except Exception as e:
            logger.error(f"Redis ping failed: {e}")
            return False
    
    async def close(self) -> None:
        """Close Redis connection"""
        await self.client.close()
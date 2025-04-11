# data_access/stores/redis/redis_session_cache.py
"""
Redis cache for session information.
"""
import logging
import time
from typing import Optional

from source.db.stores.redis.redis_base import RedisBase

logger = logging.getLogger(__name__)


class RedisSessionCache(RedisBase):
    """Handles session caching in Redis"""

    async def cache_session(self, session_id: str, user_id: str, ttl_seconds: int = 3600) -> bool:
        """
        Cache session in Redis with expiration
        """
        try:
            redis = await self._get_redis()
            # Store session -> user mapping
            await redis.hset(f"session:{session_id}", mapping={
                'user_id': user_id,
                'pod_name': self.pod_name,
                'last_access': time.time()
            })

            # Set expiration
            await redis.expire(f"session:{session_id}", ttl_seconds)

            # Store user -> sessions mapping
            await redis.sadd(f"user_sessions:{user_id}", session_id)

            return True
        except Exception as e:
            logger.error(f"Error caching session in Redis: {e}")
            return False

    async def update_session_activity(self, session_id: str, ttl_seconds: int = 3600) -> bool:
        """
        Update session last activity time and extend TTL
        """
        try:
            redis = await self._get_redis()
            # Update last access time
            await redis.hset(f"session:{session_id}", "last_access", time.time())

            # Refresh expiration
            await redis.expire(f"session:{session_id}", ttl_seconds)

            return True
        except Exception as e:
            logger.error(f"Error updating session activity in Redis: {e}")
            return False

    async def get_session_user(self, session_id: str) -> Optional[str]:
        """
        Get user ID for a session from Redis cache
        """
        try:
            redis = await self._get_redis()
            return await redis.hget(f"session:{session_id}", "user_id")
        except Exception as e:
            logger.error(f"Error getting session user from Redis: {e}")
            return None

    async def get_session_pod(self, session_id: str) -> Optional[str]:
        """
        Get pod name for a session from Redis cache
        """
        try:
            redis = await self._get_redis()
            return await redis.hget(f"session:{session_id}", "pod_name")
        except Exception as e:
            logger.error(f"Error getting session pod from Redis: {e}")
            return None

    async def get_user_sessions(self, user_id: str) -> list:
        """
        Get all session IDs for a user from Redis
        """
        try:
            redis = await self._get_redis()
            sessions = await redis.smembers(f"user_sessions:{user_id}")
            return list(sessions)
        except Exception as e:
            logger.error(f"Error getting user sessions from Redis: {e}")
            return []

    async def invalidate_session(self, session_id: str, user_id: Optional[str] = None) -> bool:
        """
        Remove session from Redis cache
        """
        try:
            redis = await self._get_redis()
            # Remove session
            await redis.delete(f"session:{session_id}")

            # Remove from user's sessions if user_id provided
            if user_id:
                await redis.srem(f"user_sessions:{user_id}", session_id)

            return True
        except Exception as e:
            logger.error(f"Error invalidating session in Redis: {e}")
            return False

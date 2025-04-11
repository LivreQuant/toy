# data_access/stores/redis/redis_coordination.py
"""
Redis-based distributed coordination and tracking.
"""
import logging
import time
from typing import Dict, List, Any

from source.db.stores.redis.redis_base import RedisBase

logger = logging.getLogger(__name__)


class RedisCoordinationStore(RedisBase):
    """Handles distributed coordination tasks using Redis"""

    async def register_pod(self, pod_name: str, host: str, port: int) -> bool:
        """Register a pod in Redis"""
        try:
            redis = await self._get_redis()
            # Store pod info
            pod_info = {
                'name': pod_name,
                'host': host,
                'port': port,
                'started_at': time.time()
            }
            await redis.hset(f"pod:{pod_name}", mapping=pod_info)
            await redis.sadd("active_pods", pod_name)
            return True
        except Exception as e:
            logger.error(f"Error registering pod {pod_name} in Redis: {e}")
            return False

    async def unregister_pod(self, pod_name: str) -> bool:
        """Unregister a pod from Redis"""
        try:
            redis = await self._get_redis()
            await redis.srem("active_pods", pod_name)
            await redis.delete(f"pod:{pod_name}")
            return True
        except Exception as e:
            logger.error(f"Error unregistering pod {pod_name} from Redis: {e}")
            return False

    async def get_active_pods(self) -> List[str]:
        """Get all active pod names"""
        try:
            redis = await self._get_redis()
            pods = await redis.smembers("active_pods")
            return list(pods)
        except Exception as e:
            logger.error(f"Error getting active pods from Redis: {e}")
            return []

    async def get_pod_info(self, pod_name: str) -> Dict[str, Any]:
        """Get information about a specific pod"""
        try:
            redis = await self._get_redis()
            info = await redis.hgetall(f"pod:{pod_name}")
            return info
        except Exception as e:
            logger.error(f"Error getting pod info from Redis: {e}")
            return {}

    async def acquire_lock(self, lock_name: str, ttl_seconds: int = 30) -> bool:
        """Acquire a distributed lock"""
        try:
            redis = await self._get_redis()
            # Try to set the lock with NX (only if it doesn't exist)
            lock_value = f"{self.pod_name}:{time.time()}"
            result = await redis.set(f"lock:{lock_name}", lock_value, nx=True, ex=ttl_seconds)
            return result is not None
        except Exception as e:
            logger.error(f"Error acquiring Redis lock: {e}")
            return False

    async def release_lock(self, lock_name: str) -> bool:
        """Release a distributed lock"""
        try:
            redis = await self._get_redis()
            # Check if we own the lock
            lock_value = await redis.get(f"lock:{lock_name}")
            if lock_value and lock_value.startswith(f"{self.pod_name}:"):
                await redis.delete(f"lock:{lock_name}")
                return True
            return False
        except Exception as e:
            logger.error(f"Error releasing Redis lock: {e}")
            return False

    async def track_websocket_connection(self, session_id: str, client_id: str) -> bool:
        """Track WebSocket connection"""
        try:
            redis = await self._get_redis()
            # Add to session's connections
            await redis.sadd(f"session_ws:{session_id}", client_id)

            # Store connection info
            await redis.hset(f"ws_conn:{client_id}", mapping={
                'session_id': session_id,
                'pod_name': self.pod_name,
                'connected_at': time.time(),
                'last_activity': time.time()
            })

            # Update session ws connection count
            await redis.hincrby(f"session:{session_id}", "ws_connections", 1)

            return True
        except Exception as e:
            logger.error(f"Error tracking WebSocket connection in Redis: {e}")
            return False

    async def remove_websocket_connection(self, session_id: str, client_id: str) -> bool:
        """Remove WebSocket connection tracking"""
        try:
            redis = await self._get_redis()
            # Remove from session's connections
            await redis.srem(f"session_ws:{session_id}", client_id)

            # Remove connection info
            await redis.delete(f"ws_conn:{client_id}")

            # Update session ws connection count
            await redis.hincrby(f"session:{session_id}", "ws_connections", -1)

            return True
        except Exception as e:
            logger.error(f"Error removing WebSocket connection from Redis: {e}")
            return False

    async def get_session_websocket_connections(self, session_id: str) -> List[str]:
        """Get all WebSocket client IDs for a session"""
        try:
            redis = await self._get_redis()
            clients = await redis.smembers(f"session_ws:{session_id}")
            return list(clients)
        except Exception as e:
            logger.error(f"Error getting session WebSocket connections from Redis: {e}")
            return []

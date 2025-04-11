# data_access/stores/redis/redis_base.py
"""
Base class for Redis connection management.
"""
import logging
import asyncio
import redis.asyncio as aioredis
from typing import Optional

from opentelemetry import trace

from source.config import config
from source.utils.tracing import optional_trace_span
from source.utils.metrics import track_db_error

logger = logging.getLogger(__name__)


class RedisBase:
    """Base Redis connection handler"""

    def __init__(self, redis_config=None):
        """Initialize Redis base connection"""
        self.redis: Optional[aioredis.Redis] = None
        self.redis_config = redis_config or config.redis
        self._conn_lock = asyncio.Lock()
        self.tracer = trace.get_tracer("redis_base")
        self.pod_name = config.kubernetes.pod_name

    async def connect(self):
        """Connect to Redis"""
        with optional_trace_span(self.tracer, "redis_connect") as span:
            span.set_attribute("db.system", "redis")
            span.set_attribute("db.host", self.redis_config.host)

            async with self._conn_lock:
                if self.redis is not None:
                    return

                max_retries = 5
                retry_count = 0
                retry_delay = 1.0

                while retry_count < max_retries:
                    try:
                        self.redis = aioredis.Redis(
                            host=self.redis_config.host,
                            port=self.redis_config.port,
                            db=self.redis_config.db,
                            password=self.redis_config.password,
                            decode_responses=True,
                            socket_connect_timeout=5,
                            socket_keepalive=True,
                        )

                        # Verify connection
                        await self.redis.ping()
                        logger.info("Connected to Redis")
                        return

                    except Exception as e:
                        retry_count += 1
                        logger.error(f"Redis connection error (attempt {retry_count}/{max_retries}): {e}")
                        span.record_exception(e)

                        if retry_count < max_retries:
                            await asyncio.sleep(retry_delay)
                            retry_delay *= 2  # Exponential backoff
                        else:
                            logger.error("Maximum Redis connection retries reached")
                            span.set_attribute("success", False)
                            track_db_error("redis_connect")
                            raise

    async def close(self):
        """Close Redis connection"""
        if self.redis:
            await self.redis.close()
            self.redis = None
            logger.info("Closed Redis connection")

    async def check_connection(self) -> bool:
        """Check Redis connection health"""
        if not self.redis:
            try:
                await self.connect()
                return True
            except:
                return False

        try:
            await self.redis.ping()
            return True
        except Exception as e:
            logger.error(f"Redis connection check failed: {e}")
            return False

    async def _get_redis(self) -> aioredis.Redis:
        """Ensure Redis connection is established"""
        if self.redis is None:
            await self.connect()
        if self.redis is None:
            raise ConnectionError("Redis connection not initialized.")
        return self.redis

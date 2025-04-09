# source/db/redis_store.py
"""
Redis database access for ephemeral data and pub/sub events.
Handles session caching, real-time updates, and pod coordination.
"""
import logging
import asyncio
import json
import time
from typing import Dict, List, Any, Optional, Tuple, Set

import redis.asyncio as aioredis
from opentelemetry import trace

from source.utils.metrics import track_db_operation, track_db_error
from source.utils.tracing import optional_trace_span

from source.config import config

logger = logging.getLogger('redis_store')


class RedisStore:
    """Redis access for session service"""

    def __init__(self):
        """Initialize Redis database manager"""
        self.redis = None
        self.redis_config = config.redis
        self._conn_lock = asyncio.Lock()
        self.tracer = trace.get_tracer("redis_store")
        self.pubsub_task = None
        self.pubsub_handlers = {}  # Register handlers for different message types
        self.pod_name = config.kubernetes.pod_name
        self.event_subscribers = set()  # For broadcasting events

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

                        # Register pod with Redis
                        pod_info = {
                            'name': self.pod_name,
                            'host': config.server.host,
                            'port': config.server.port,
                            'started_at': time.time()
                        }
                        await self.redis.hset(f"pod:{self.pod_name}", mapping=pod_info)
                        await self.redis.sadd("active_pods", self.pod_name)
                        logger.info(f"Pod '{self.pod_name}' registered in Redis")

                        # Start pub/sub listener
                        self.pubsub_task = asyncio.create_task(self._run_pubsub())

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
        """Close Redis connections"""
        if self.pubsub_task and not self.pubsub_task.done():
            self.pubsub_task.cancel()
            try:
                await self.pubsub_task
            except asyncio.CancelledError:
                logger.info("Redis pub/sub task cancelled")
            except Exception as e:
                logger.error(f"Error during pub/sub task cancellation: {e}")

        if self.redis:
            # Unregister pod
            try:
                await self.redis.srem("active_pods", self.pod_name)
                logger.info(f"Pod '{self.pod_name}' unregistered from Redis")
            except Exception as e:
                logger.error(f"Error unregistering pod from Redis: {e}")

            # Close connection
            await self.redis.close()
            self.redis = None
            logger.info("Closed Redis connection")

    async def _run_pubsub(self):
        """Listen for and process Redis pub/sub messages"""
        if not self.redis:
            logger.error("Cannot start pub/sub listener: Redis not connected")
            return

        pubsub = self.redis.pubsub()
        channel = "session_events"
        await pubsub.subscribe(channel)
        logger.info(f"Subscribed to Redis channel: {channel}")

        try:
            while True:
                message = await pubsub.get_message(timeout=1.0)
                if message and message.get('type') == 'message':
                    await self._handle_pubsub_message(message)
                await asyncio.sleep(0.01)  # Prevent tight loop
        except asyncio.CancelledError:
            logger.info("Redis pub/sub listener task cancelled")
            raise
        except Exception as e:
            logger.error(f"Error in Redis pub/sub listener: {e}")
        finally:
            try:
                await pubsub.unsubscribe(channel)
                logger.info(f"Unsubscribed from Redis channel: {channel}")
            except Exception as e:
                logger.error(f"Error unsubscribing from Redis channel: {e}")

    async def _handle_pubsub_message(self, message):
        """Handle Redis pub/sub message"""
        try:
            data = json.loads(message.get('data', '{}'))
            event_type = data.get('type')
            source_pod = data.get('pod_name')

            # Skip messages from this pod
            if source_pod == self.pod_name:
                return

            logger.debug(f"Received pub/sub event '{event_type}' from pod '{source_pod}'")

            # Dispatch to registered handlers
            handler = self.pubsub_handlers.get(event_type)
            if handler:
                await handler(data)

            # Broadcast to subscribers
            if self.event_subscribers:
                for callback in self.event_subscribers:
                    try:
                        await callback(event_type, data)
                    except Exception as e:
                        logger.error(f"Error in event subscriber callback: {e}")

        except json.JSONDecodeError as e:
            logger.error(f"Error decoding JSON from pub/sub message: {e}")
        except Exception as e:
            logger.error(f"Error handling pub/sub message: {e}")

    def register_pubsub_handler(self, event_type: str, handler_func):
        """Register a handler for a specific pub/sub event type"""
        self.pubsub_handlers[event_type] = handler_func
        logger.info(f"Registered handler for pub/sub event type: {event_type}")

    def subscribe_to_events(self, callback):
        """Subscribe to all events"""
        self.event_subscribers.add(callback)
        return lambda: self.event_subscribers.remove(callback)  # Returns unsubscribe function

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

    # Session-related methods
    async def cache_session(self, session_id: str, user_id: str, ttl_seconds: int = 3600) -> bool:
        """
        Cache session in Redis with expiration
        
        Args:
            session_id: Session ID
            user_id: User ID
            ttl_seconds: Time to live in seconds
            
        Returns:
            Success flag
        """
        if not self.redis:
            await self.connect()

        try:
            # Store session -> user mapping
            await self.redis.hset(f"session:{session_id}", mapping={
                'user_id': user_id,
                'pod_name': self.pod_name,
                'last_access': time.time()
            })

            # Set expiration
            await self.redis.expire(f"session:{session_id}", ttl_seconds)

            # Store user -> sessions mapping
            await self.redis.sadd(f"user_sessions:{user_id}", session_id)

            return True
        except Exception as e:
            logger.error(f"Error caching session in Redis: {e}")
            return False

    async def update_session_activity(self, session_id: str, ttl_seconds: int = 3600) -> bool:
        """
        Update session last activity time and extend TTL
        
        Args:
            session_id: Session ID
            ttl_seconds: Time to live in seconds
            
        Returns:
            Success flag
        """
        if not self.redis:
            await self.connect()

        try:
            # Update last access time
            await self.redis.hset(f"session:{session_id}", "last_access", time.time())

            # Refresh expiration
            await self.redis.expire(f"session:{session_id}", ttl_seconds)

            return True
        except Exception as e:
            logger.error(f"Error updating session activity in Redis: {e}")
            return False

    async def get_session_user(self, session_id: str) -> Optional[str]:
        """
        Get user ID for a session from Redis cache
        
        Args:
            session_id: Session ID
            
        Returns:
            User ID or None
        """
        if not self.redis:
            await self.connect()

        try:
            return await self.redis.hget(f"session:{session_id}", "user_id")
        except Exception as e:
            logger.error(f"Error getting session user from Redis: {e}")
            return None

    async def get_session_pod(self, session_id: str) -> Optional[str]:
        """
        Get pod name for a session from Redis cache
        
        Args:
            session_id: Session ID
            
        Returns:
            Pod name or None
        """
        if not self.redis:
            await self.connect()

        try:
            return await self.redis.hget(f"session:{session_id}", "pod_name")
        except Exception as e:
            logger.error(f"Error getting session pod from Redis: {e}")
            return None

    async def get_user_sessions(self, user_id: str) -> List[str]:
        """
        Get all session IDs for a user from Redis
        
        Args:
            user_id: User ID
            
        Returns:
            List of session IDs
        """
        if not self.redis:
            await self.connect()

        try:
            sessions = await self.redis.smembers(f"user_sessions:{user_id}")
            return list(sessions)
        except Exception as e:
            logger.error(f"Error getting user sessions from Redis: {e}")
            return []

    async def invalidate_session(self, session_id: str, user_id: Optional[str] = None) -> bool:
        """
        Remove session from Redis cache
        
        Args:
            session_id: Session ID
            user_id: Optional user ID to remove from user->sessions mapping
            
        Returns:
            Success flag
        """
        if not self.redis:
            await self.connect()

        try:
            # Remove session
            await self.redis.delete(f"session:{session_id}")

            # Remove from user's sessions if user_id provided
            if user_id:
                await self.redis.srem(f"user_sessions:{user_id}", session_id)

            return True
        except Exception as e:
            logger.error(f"Error invalidating session in Redis: {e}")
            return False

    # Event publishing
    async def publish_session_event(self, event_type: str, data: Dict[str, Any]) -> bool:
        """
        Publish a session-related event to the pub/sub channel
        
        Args:
            event_type: Event type (e.g., 'session_created', 'simulator_started')
            data: Event data
            
        Returns:
            Success flag
        """
        if not self.redis:
            await self.connect()

        try:
            # Ensure required fields
            full_data = {
                'type': event_type,
                'pod_name': self.pod_name,
                'timestamp': time.time(),
                **data
            }

            # Publish to channel
            await self.redis.publish('session_events', json.dumps(full_data))
            return True
        except Exception as e:
            logger.error(f"Error publishing event to Redis: {e}")
            return False

    # Connection tracking
    async def track_websocket_connection(self, session_id: str, client_id: str) -> bool:
        """
        Track active WebSocket connection
        
        Args:
            session_id: Session ID
            client_id: Client ID
            
        Returns:
            Success flag
        """
        if not self.redis:
            await self.connect()

        try:
            # Add to session's connections
            await self.redis.sadd(f"session_ws:{session_id}", client_id)

            # Store connection info
            await self.redis.hset(f"ws_conn:{client_id}", mapping={
                'session_id': session_id,
                'pod_name': self.pod_name,
                'connected_at': time.time(),
                'last_activity': time.time()
            })

            # Update session ws connection count
            await self.redis.hincrby(f"session:{session_id}", "ws_connections", 1)

            return True
        except Exception as e:
            logger.error(f"Error tracking WebSocket connection in Redis: {e}")
            return False

    async def remove_websocket_connection(self, session_id: str, client_id: str) -> bool:
        """
        Remove WebSocket connection tracking
        
        Args:
            session_id: Session ID
            client_id: Client ID
            
        Returns:
            Success flag
        """
        if not self.redis:
            await self.connect()

        try:
            # Remove from session's connections
            await self.redis.srem(f"session_ws:{session_id}", client_id)

            # Remove connection info
            await self.redis.delete(f"ws_conn:{client_id}")

            # Update session ws connection count
            await self.redis.hincrby(f"session:{session_id}", "ws_connections", -1)

            return True
        except Exception as e:
            logger.error(f"Error removing WebSocket connection from Redis: {e}")
            return False

    async def get_session_websocket_connections(self, session_id: str) -> List[str]:
        """
        Get all WebSocket client IDs for a session
        
        Args:
            session_id: Session ID
            
        Returns:
            List of client IDs
        """
        if not self.redis:
            await self.connect()

        try:
            clients = await self.redis.smembers(f"session_ws:{session_id}")
            return list(clients)
        except Exception as e:
            logger.error(f"Error getting session WebSocket connections from Redis: {e}")
            return []

    # Active pods management
    async def get_active_pods(self) -> List[str]:
        """
        Get all active pod names
        
        Returns:
            List of pod names
        """
        if not self.redis:
            await self.connect()

        try:
            pods = await self.redis.smembers("active_pods")
            return list(pods)
        except Exception as e:
            logger.error(f"Error getting active pods from Redis: {e}")
            return []

    async def get_pod_info(self, pod_name: str) -> Dict[str, Any]:
        """
        Get information about a pod
        
        Args:
            pod_name: Pod name
            
        Returns:
            Pod information
        """
        if not self.redis:
            await self.connect()

        try:
            info = await self.redis.hgetall(f"pod:{pod_name}")
            return info
        except Exception as e:
            logger.error(f"Error getting pod info from Redis: {e}")
            return {}

    # Lock management for distributed coordination
    async def acquire_lock(self, lock_name: str, ttl_seconds: int = 30) -> bool:
        """
        Acquire a distributed lock
        
        Args:
            lock_name: Lock name
            ttl_seconds: Lock timeout in seconds
            
        Returns:
            True if lock acquired, False otherwise
        """
        if not self.redis:
            await self.connect()

        try:
            # Try to set the lock with NX (only if it doesn't exist)
            lock_value = f"{self.pod_name}:{time.time()}"
            result = await self.redis.set(f"lock:{lock_name}", lock_value, nx=True, ex=ttl_seconds)
            return result is not None
        except Exception as e:
            logger.error(f"Error acquiring Redis lock: {e}")
            return False

    async def release_lock(self, lock_name: str) -> bool:
        """
        Release a distributed lock
        
        Args:
            lock_name: Lock name
            
        Returns:
            Success flag
        """
        if not self.redis:
            await self.connect()

        try:
            # Check if we own the lock
            lock_value = await self.redis.get(f"lock:{lock_name}")
            if lock_value and lock_value.startswith(f"{self.pod_name}:"):
                await self.redis.delete(f"lock:{lock_name}")
                return True
            return False
        except Exception as e:
            logger.error(f"Error releasing Redis lock: {e}")
            return False

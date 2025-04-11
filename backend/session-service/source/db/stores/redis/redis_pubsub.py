# data_access/stores/redis/redis_pubsub.py
"""
Redis pub/sub functionality for event broadcasting.
"""
import logging
import json
import time
import asyncio
from typing import Dict, Any, Callable

from source.db.stores.redis.redis_base import RedisBase

logger = logging.getLogger(__name__)


class RedisPubSub(RedisBase):
    """Handles Redis pub/sub events"""

    def __init__(self, *args, **kwargs):
        """Initialize pub/sub with event tracking"""
        super().__init__(*args, **kwargs)
        self.pubsub_task = None
        self.pubsub_handlers = {}
        self.event_subscribers = set()

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

    async def publish_event(self, event_type: str, data: Dict[str, Any]) -> bool:
        """
        Publish an event to the pub/sub channel
        """
        try:
            redis = await self._get_redis()
            # Ensure required fields
            full_data = {
                'type': event_type,
                'pod_name': self.pod_name,
                'timestamp': time.time(),
                **data
            }

            # Publish to channel
            await redis.publish('session_events', json.dumps(full_data))
            return True
        except Exception as e:
            logger.error(f"Error publishing event to Redis: {e}")
            return False

    def register_pubsub_handler(self, event_type: str, handler_func: Callable):
        """Register a handler for a specific pub/sub event type"""
        self.pubsub_handlers[event_type] = handler_func
        logger.info(f"Registered handler for pub/sub event type: {event_type}")

    def subscribe_to_events(self, callback: Callable):
        """Subscribe to all events"""
        self.event_subscribers.add(callback)
        return lambda: self.event_subscribers.remove(callback)

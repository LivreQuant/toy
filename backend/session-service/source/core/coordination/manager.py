# data_access/managers/coordination_manager.py
"""
Provides a high-level interface for coordination tasks using Redis.
"""
import logging
import time
from typing import List, Dict, Any

from opentelemetry import trace

from source.config import config
from source.utils.tracing import optional_trace_span

from source.db.stores.redis.redis_coordination import RedisCoordinationStore
from source.db.stores.redis.redis_pubsub import RedisPubSub  # Needed for pod events

logger = logging.getLogger(__name__)


class CoordinationManager:
    """Handles distributed coordination tasks like locking and pod management."""

    def __init__(self,
                 redis_coordination_store: RedisCoordinationStore,
                 redis_pubsub: RedisPubSub):
        """
        Initialize CoordinationManager.

        Args:
            redis_coordination_store: Instance for Redis coordination operations.
            redis_pubsub: Instance for publishing pod events.
        """
        self.redis_store = redis_coordination_store
        self.redis_pubsub = redis_pubsub
        self.tracer = trace.get_tracer("coordination_manager")
        self.pod_name = config.kubernetes.pod_name  # Cache pod name
        logger.info("CoordinationManager initialized.")

    # --- Pod Management ---

    async def register_self_pod(self) -> bool:
        """Registers the current pod in Redis."""
        with optional_trace_span(self.tracer, "manager_register_pod") as span:
            span.set_attribute("pod_name", self.pod_name)
            # Assuming host/port are needed from config as well
            host = config.server.host  # Or pod IP if available
            port = config.server.port
            success = await self.redis_store.register_pod(self.pod_name, host, port)
            if success:
                # Publish event that this pod is online
                try:
                    await self.redis_pubsub.publish_event('pod_online', {
                        'pod_name': self.pod_name,
                        'host': host,
                        'port': port,
                        'timestamp': time.time()
                    })
                except Exception as e:
                    logger.warning(f"Failed to publish pod_online event for {self.pod_name}: {e}")
            return success

    async def unregister_self_pod(self) -> bool:
        """Unregisters the current pod from Redis and publishes offline event."""
        with optional_trace_span(self.tracer, "manager_unregister_pod") as span:
            span.set_attribute("pod_name", self.pod_name)

            # Publish offline event first
            try:
                await self.redis_pubsub.publish_event('pod_offline', {
                    'pod_name': self.pod_name,
                    'timestamp': time.time()
                })
                logger.info(f"Published pod_offline event for {self.pod_name}")
            except Exception as e:
                logger.error(f"Failed to publish pod_offline event for {self.pod_name}: {e}", exc_info=True)
                # Proceed with unregistration anyway

            # Then unregister
            success = await self.redis_store.unregister_pod(self.pod_name)
            return success

    async def get_active_pods(self) -> List[str]:
        """Get a list of names of currently active pods."""
        return await self.redis_store.get_active_pods()

    async def get_pod_info(self, pod_name: str) -> Dict[str, Any]:
        """Get stored information about a specific pod."""
        return await self.redis_store.get_pod_info(pod_name)

    # --- Distributed Locking ---

    async def acquire_lock(self, lock_name: str, ttl_seconds: int = 30) -> bool:
        """Acquire a distributed lock."""
        with optional_trace_span(self.tracer, "manager_acquire_lock") as span:
            span.set_attribute("lock_name", lock_name)
            span.set_attribute("ttl_seconds", ttl_seconds)
            return await self.redis_store.acquire_lock(lock_name, ttl_seconds)

    async def release_lock(self, lock_name: str) -> bool:
        """Release a distributed lock."""
        with optional_trace_span(self.tracer, "manager_release_lock") as span:
            span.set_attribute("lock_name", lock_name)
            return await self.redis_store.release_lock(lock_name)

    # --- WebSocket Tracking ---

    async def track_websocket_connection(self, session_id: str, client_id: str) -> bool:
        """Track a new WebSocket connection."""
        with optional_trace_span(self.tracer, "manager_track_websocket") as span:
            span.set_attribute("session_id", session_id)
            span.set_attribute("client_id", client_id)
            return await self.redis_store.track_websocket_connection(session_id, client_id)

    async def remove_websocket_connection(self, session_id: str, client_id: str) -> bool:
        """Remove tracking for a disconnected WebSocket."""
        with optional_trace_span(self.tracer, "manager_remove_websocket") as span:
            span.set_attribute("session_id", session_id)
            span.set_attribute("client_id", client_id)
            return await self.redis_store.remove_websocket_connection(session_id, client_id)

    async def get_session_websocket_connections(self, session_id: str) -> List[str]:
        """Get all tracked WebSocket client IDs for a given session."""
        return await self.redis_store.get_session_websocket_connections(session_id)

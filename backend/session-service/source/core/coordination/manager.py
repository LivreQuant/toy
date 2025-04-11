"""
Coordination manager for distributed coordination.
Handles pod registration, locking, and cross-pod communication.
"""
import logging
import asyncio
import time
from typing import List, Dict, Any, Callable, Optional

from opentelemetry import trace

from source.config import config
from source.utils.tracing import optional_trace_span

from source.db.stores.redis.redis_coordination import RedisCoordinationStore
from source.db.stores.redis.redis_pubsub import RedisPubSub

logger = logging.getLogger('coordination_manager')


class CoordinationManager:
    """Handles distributed coordination tasks like locking and pod management"""

    def __init__(self,
                 redis_coordination_store: RedisCoordinationStore,
                 redis_pubsub: RedisPubSub):
        """
        Initialize CoordinationManager.

        Args:
            redis_coordination_store: Instance for Redis coordination operations
            redis_pubsub: Instance for publishing pod events
        """
        # Stores
        self.redis_store = redis_coordination_store
        self.redis_pubsub = redis_pubsub

        # Background tasks
        self.pubsub_task = None
        self.health_check_task = None
        
        self.tracer = trace.get_tracer("coordination_manager")
        
        logger.info("CoordinationManager initialized")

    # ----- Pod Management -----

    async def register_self_pod(self) -> bool:
        """Register the current pod in Redis"""
        with optional_trace_span(self.tracer, "register_self_pod") as span:
            pod_name = config.kubernetes.pod_name
            host = config.server.host
            port = config.server.port
            span.set_attribute("pod_name", pod_name)
            success = await self.redis_store.register_pod(pod_name, host, port)
            if success:
                await self.redis_pubsub.publish_event('pod_online', {
                    'pod_name': pod_name,
                    'host': host,
                    'port': port,
                    'timestamp': time.time()
                })
            return success
        
    async def unregister_self_pod(self) -> bool:
        """Unregister the current pod from Redis"""
        with optional_trace_span(self.tracer, "unregister_self_pod") as span:
            pod_name = config.kubernetes.pod_name
            span.set_attribute("pod_name", pod_name)
            await self.redis_pubsub.publish_event('pod_offline', {
                'pod_name': pod_name,
                'timestamp': time.time()
            })
            return await self.redis_store.unregister_pod(pod_name)

    # ----- Distributed Locking -----

    async def acquire_lock(self, lock_name: str, ttl_seconds: int = 30) -> bool:
        """Acquire a distributed lock"""
        with optional_trace_span(self.tracer, "acquire_lock") as span:
            span.set_attribute("lock_name", lock_name)
            span.set_attribute("ttl_seconds", ttl_seconds)
            return await self.redis_store.acquire_lock(lock_name, ttl_seconds)

    async def release_lock(self, lock_name: str) -> bool:
        """Release a distributed lock"""
        with optional_trace_span(self.tracer, "release_lock") as span:
            span.set_attribute("lock_name", lock_name)
            return await self.redis_store.release_lock(lock_name)

    async def execute_with_lock(self, lock_name: str, operation_func, *args, ttl_seconds: int = 30, **kwargs):
        """Execute operation with a distributed lock"""
        with optional_trace_span(self.tracer, "execute_with_lock") as span:
            span.set_attribute("lock_name", lock_name)
            
            lock_acquired = await self.acquire_lock(lock_name, ttl_seconds)
            if not lock_acquired:
                span.set_attribute("lock_acquired", False)
                logger.warning(f"Failed to acquire lock '{lock_name}'")
                return None
                
            span.set_attribute("lock_acquired", True)
            try:
                result = await operation_func(*args, **kwargs)
                return result
            finally:
                await self.release_lock(lock_name)

    # ----- Connection Tracking -----

    async def remove_websocket_connection(self, session_id: str, client_id: str) -> bool:
        """Remove tracking for a disconnected WebSocket"""
        return await self.redis_store.remove_websocket_connection(session_id, client_id)

    async def get_session_websocket_connections(self, session_id: str) -> List[str]:
        """Get all tracked WebSocket client IDs for a given session"""
        return await self.redis_store.get_session_websocket_connections(session_id)
        
    # ----- Event Subscriptions -----
    
    async def start_background_tasks(self):
        """Start listening for Redis pub/sub events and health checks"""
        await self.start_pubsub_listener()
        await self.start_health_check_task()
    
    async def start_pubsub_listener(self):
        """Start listening for Redis pub/sub events"""
        if self.pubsub_task is None or self.pubsub_task.done():
            self.pubsub_task = asyncio.create_task(self.redis_pubsub._run_pubsub())
            logger.info("Started Redis pub/sub listener task")
    
    async def start_health_check_task(self):
        """Start periodic pod health check task"""
        if self.health_check_task is None or self.health_check_task.done():
            self.health_check_task = asyncio.create_task(self._run_health_check_loop())
            logger.info("Started pod health check task")
    
    async def stop_background_tasks(self):
        """Stop listening for Redis pub/sub events and health checks"""
        await self.stop_pubsub_listener()
        await self.stop_health_check_task()
    
    async def stop_pubsub_listener(self):
        """Stop listening for Redis pub/sub events"""
        if self.pubsub_task and not self.pubsub_task.done():
            self.pubsub_task.cancel()
            try:
                await self.pubsub_task
            except asyncio.CancelledError:
                logger.info("Redis pub/sub listener task cancelled")
            except Exception as e:
                logger.error(f"Error awaiting cancelled pub/sub task: {e}")
            self.pubsub_task = None
            logger.info("Redis pub/sub listener task stopped")
    
    async def stop_health_check_task(self):
        """Stop periodic pod health check task"""
        if self.health_check_task and not self.health_check_task.done():
            self.health_check_task.cancel()
            try:
                await self.health_check_task
            except asyncio.CancelledError:
                logger.info("Pod health check task cancelled")
            except Exception as e:
                logger.error(f"Error awaiting cancelled health check task: {e}")
            self.health_check_task = None
            logger.info("Pod health check task stopped")
    
    def register_event_handler(self, event_type: str, handler_func: Callable):
        """Register a handler for a specific event type"""
        self.redis_pubsub.register_pubsub_handler(event_type, handler_func)
        
    def subscribe_to_events(self, callback: Callable) -> Callable:
        """
        Subscribe to all events
        
        Returns:
            Unsubscribe function
        """
        return self.redis_pubsub.subscribe_to_events(callback)
        
    async def _run_health_check_loop(self):
        """Run periodic health checks for active pods"""
        logger.info("Starting pod health check loop")
        while True:
            try:
                await self._check_active_pods()
                # Run every minute
                await asyncio.sleep(60)
            except asyncio.CancelledError:
                logger.info("Pod health check loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in pod health check loop: {e}", exc_info=True)
                await asyncio.sleep(30)
                
    async def _check_active_pods(self):
        """Check if active pods are still responsive"""
        try:
            active_pods = await self.get_active_pods()
            logger.debug(f"Checking {len(active_pods)} active pods")
            
            stale_pods = []
            
            for pod_name in active_pods:
                # Skip self
                if pod_name == self.pod_name:
                    continue
                    
                # Get pod info
                pod_info = await self.redis_store.get_pod_info(pod_name)
                if not pod_info:
                    logger.warning(f"Pod {pod_name} is registered as active but has no info")
                    stale_pods.append(pod_name)
                    continue
                    
                # Check last heartbeat
                last_heartbeat = float(pod_info.get('last_heartbeat', 0))
                if last_heartbeat > 0:
                    stale_time = time.time() - last_heartbeat
                    # If no heartbeat for over 2 minutes, consider stale
                    if stale_time > 120:
                        logger.warning(f"Pod {pod_name} has stale heartbeat ({stale_time:.0f}s old)")
                        stale_pods.append(pod_name)
            
            # Clean up stale pods
            if stale_pods:
                await self._clean_stale_pods(stale_pods)
                
        except Exception as e:
            logger.error(f"Error checking active pods: {e}", exc_info=True)
            
    async def _clean_stale_pods(self, stale_pods: List[str]):
        """Clean up stale pods from Redis"""
        for pod_name in stale_pods:
            logger.info(f"Cleaning up stale pod: {pod_name}")
            try:
                # Remove from active pods
                await self.redis_store.unregister_pod(pod_name)
                
                # Publish offline event
                await self.redis_pubsub.publish_event('pod_offline', {
                    'pod_name': pod_name,
                    'timestamp': time.time(),
                    'reason': 'stale_heartbeat',
                    'detected_by': self.pod_name
                })
            except Exception as e:
                logger.error(f"Error cleaning up stale pod {pod_name}: {e}")
                
    async def update_self_heartbeat(self):
        """Update own heartbeat in Redis"""
        try:
            await self.redis_store.update_pod_heartbeat(self.pod_name)
        except Exception as e:
            logger.error(f"Error updating pod heartbeat: {e}")
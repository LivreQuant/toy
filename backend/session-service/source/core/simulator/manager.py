# source/core/simulator/manager.py
"""
Simple simulator manager - just connect to the pod name from database.
"""
import logging
import asyncio
import time
from typing import Optional, Tuple, Dict, Any

from opentelemetry import trace

from source.config import config
from source.utils.tracing import optional_trace_span
from source.utils.metrics import track_simulator_connection_attempt, track_simulator_connection_time
from source.models.exchange_data import ExchangeType
from source.clients.kubernetes import KubernetesClient

logger = logging.getLogger('simulator_manager')


class SimulatorManager:
    """Simple simulator manager - connect to pod by name"""

    def __init__(self, store_manager, exchange_client=None):
        self.store_manager = store_manager
        self.exchange_client = exchange_client
        
        # Current connection info
        self.current_simulator_id = None
        self.current_endpoint = None
        self.current_user_id = None
        
        # Data callback
        self.data_callback = None
        
        # Retry state
        self._connection_retry_task = None
        self._should_retry = False
        
        # Kubernetes client
        self.k8s_client = KubernetesClient()
        
        self.tracer = trace.get_tracer("simulator_manager")
        logger.info("Simple simulator manager initialized")

    def set_data_callback(self, callback):
        """Set callback for exchange data"""
        self.data_callback = callback

    async def find_user_simulator(self, user_id: str) -> Tuple[Optional[Dict], str]:
        """Find user's exchange pod from database"""
        with optional_trace_span(self.tracer, "find_user_simulator") as span:
            span.set_attribute("user_id", user_id)
            
            try:
                pool = await self.store_manager.session_store._get_pool()
                async with pool.acquire() as conn:
                    # Get user's exchange info INCLUDING ENDPOINT from database
                    row = await conn.fetchrow('''
                        SELECT u.user_id, u.exch_id, m.pod_name, m.namespace, 
                            m.exchange_type, m.endpoint
                        FROM exch_us_equity.users u
                        JOIN exch_us_equity.metadata m ON u.exch_id = m.exch_id
                        WHERE u.user_id = $1
                        LIMIT 1
                    ''', user_id)
                    
                    if not row:
                        return None, f"User {user_id} not found"
                    
                    pod_name = row['pod_name']
                    namespace = row['namespace'] or 'default'
                    endpoint = row['endpoint']  # GET FROM DATABASE
                    
                    if not pod_name:
                        return None, f"No pod name configured for user {user_id}"
                    
                    if not endpoint:
                        return None, f"No endpoint configured for user {user_id}"
                    
                    # REMOVE ALL KUBERNETES API CALLS - USE DATABASE ONLY
                    simulator_info = {
                        'simulator_id': f"sim-{pod_name}",
                        'user_id': user_id,
                        'exch_id': str(row['exch_id']),
                        'pod_name': pod_name,
                        'endpoint': endpoint,  # USE DATABASE ENDPOINT
                        'namespace': namespace,
                        'exchange_type': row['exchange_type'],
                        'status': 'RUNNING'
                    }
                    
                    logger.info(f"Found simulator for user {user_id}: {pod_name} -> {endpoint}")
                    return simulator_info, ""
                    
            except Exception as e:
                logger.error(f"Error finding simulator for user {user_id}: {e}", exc_info=True)
                return None, f"Database error: {str(e)}"
            

    async def connect_to_simulator(self, user_id: str) -> Tuple[bool, str]:
        """
        Connect to user's simulator pod
        
        Args:
            user_id: User ID
            
        Returns:
            Tuple of (success, error_message)
        """
        with optional_trace_span(self.tracer, "connect_to_simulator") as span:
            span.set_attribute("user_id", user_id)
            
            start_time = time.time()
            
            # Find the simulator
            simulator_info, error = await self.find_user_simulator(user_id)
            if not simulator_info:
                track_simulator_connection_attempt('failed_not_found')
                return False, error
            
            simulator_id = simulator_info['simulator_id']
            endpoint = simulator_info['endpoint']
            
            span.set_attribute("simulator_id", simulator_id)
            span.set_attribute("endpoint", endpoint)
            
            # Test connection
            try:
                heartbeat_result = await self.exchange_client.send_heartbeat(
                    endpoint, user_id, f"connect-{user_id}"
                )
                
                if not heartbeat_result.get('success', False):
                    error_msg = heartbeat_result.get('error', 'Heartbeat failed')
                    logger.warning(f"Cannot connect to simulator {simulator_id}: {error_msg}")
                    track_simulator_connection_attempt('failed_heartbeat')
                    track_simulator_connection_time(time.time() - start_time, 'failed')
                    return False, f"Simulator not responding: {error_msg}"
                
                # Success
                self.current_simulator_id = simulator_id
                self.current_endpoint = endpoint
                self.current_user_id = user_id
                
                track_simulator_connection_attempt('success')
                track_simulator_connection_time(time.time() - start_time, 'success')
                
                logger.info(f"Connected to simulator {simulator_id} for user {user_id}")
                return True, ""
                
            except Exception as e:
                logger.error(f"Error connecting to simulator {simulator_id}: {e}")
                track_simulator_connection_attempt('failed_error')
                track_simulator_connection_time(time.time() - start_time, 'failed')
                return False, f"Connection error: {str(e)}"

    async def connect_with_retry(self, user_id: str) -> None:
        """Connect with retry logic"""
        max_attempts = config.simulator.max_reconnect_attempts or 0
        base_delay = config.simulator.reconnect_delay
        backoff = config.simulator.connection_retry_backoff
        max_delay = config.simulator.max_retry_delay
        
        attempt = 0
        current_delay = base_delay
        self._should_retry = True
        
        while self._should_retry and (max_attempts == 0 or attempt < max_attempts):
            attempt += 1
            
            connected, error = await self.connect_to_simulator(user_id)
            
            if connected:
                logger.info(f"Connected to simulator for user {user_id} after {attempt} attempts")
                if self.data_callback:
                    await self._notify_connection_status("CONNECTED", None)
                return
            
            logger.warning(f"Connection attempt {attempt} failed for user {user_id}: {error}")
            if self.data_callback:
                await self._notify_connection_status("CONNECTING", f"Attempt {attempt} failed: {error}")
            
            if max_attempts > 0 and attempt >= max_attempts:
                logger.error(f"Failed to connect after {max_attempts} attempts")
                if self.data_callback:
                    await self._notify_connection_status("DISCONNECTED", f"Failed after {max_attempts} attempts")
                return
            
            if self._should_retry:
                logger.info(f"Retrying in {current_delay} seconds...")
                try:
                    await asyncio.sleep(current_delay)
                except asyncio.CancelledError:
                    break
                
                current_delay = min(current_delay * backoff, max_delay)

    async def _notify_connection_status(self, status: str, message: str = None):
        """Notify connection status via callback"""
        if not self.data_callback:
            return
            
        notification = {
            'type': 'simulator_connection_status',
            'status': status,
            'simulator_id': self.current_simulator_id,
            'user_id': self.current_user_id,
            'timestamp': int(time.time() * 1000)
        }
        
        if message:
            notification['message'] = message
            
        try:
            if asyncio.iscoroutinefunction(self.data_callback):
                await self.data_callback(notification)
            else:
                self.data_callback(notification)
        except Exception as e:
            logger.error(f"Error in connection status callback: {e}")

    async def start_connection_retry(self, user_id: str):
        """Start retry task"""
        if self._connection_retry_task and not self._connection_retry_task.done():
            self._connection_retry_task.cancel()
        
        self._connection_retry_task = asyncio.create_task(self.connect_with_retry(user_id))

    async def stop_connection_retry(self):
        """Stop retry task"""
        self._should_retry = False
        if self._connection_retry_task and not self._connection_retry_task.done():
            self._connection_retry_task.cancel()

    async def stream_exchange_data(self, session_id: str, client_id: str, user_id: str):
        """Stream data from connected simulator"""
        if not self.current_endpoint:
            raise ValueError("No simulator connected")
        
        logger.info(f"Starting data stream from simulator {self.current_simulator_id}")
        
        try:
            async for data in self.exchange_client.stream_exchange_data(
                self.current_endpoint, session_id, client_id, user_id, ExchangeType.EQUITIES
            ):
                if self.data_callback:
                    try:
                        if asyncio.iscoroutinefunction(self.data_callback):
                            await self.data_callback(data)
                        else:
                            self.data_callback(data)
                    except Exception as e:
                        logger.error(f"Error in data callback: {e}")
                
                yield data
                
        except Exception as e:
            logger.error(f"Stream error from simulator {self.current_simulator_id}: {e}")
            self.current_simulator_id = None
            self.current_endpoint = None
            self.current_user_id = None
            
            if self.data_callback:
                await self._notify_connection_status("DISCONNECTED", f"Stream error: {str(e)}")
            raise

    async def disconnect(self):
        """Disconnect from simulator"""
        if self.current_simulator_id:
            logger.info(f"Disconnecting from simulator {self.current_simulator_id}")
        
        await self.stop_connection_retry()
        self.current_simulator_id = None
        self.current_endpoint = None
        self.current_user_id = None

    def get_connection_info(self) -> Dict[str, Any]:
        """Get connection info"""
        return {
            'connected': self.current_simulator_id is not None,
            'simulator_id': self.current_simulator_id,
            'endpoint': self.current_endpoint,
            'user_id': self.current_user_id,
            'retrying': self._connection_retry_task is not None and not self._connection_retry_task.done()
        }

    async def close(self):
        """Close manager"""
        await self.stop_connection_retry()
        if self.k8s_client:
            await self.k8s_client.close()
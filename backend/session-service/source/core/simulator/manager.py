"""
Simplified simulator manager for connecting to existing simulators.
No longer responsible for creating/destroying simulators.
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

logger = logging.getLogger('simulator_manager')


class SimulatorManager:
    """Manager for connecting to existing exchange simulator instances"""

    def __init__(self, store_manager, exchange_client=None):
        """
        Initialize simulator manager for connection-only operations
        
        Args:
            store_manager: PostgreSQL store for simulator persistence
            exchange_client: Exchange client for communication with simulator
        """
        self.store_manager = store_manager
        self.exchange_client = exchange_client
        
        # Track the current connection
        self.current_simulator_id = None
        self.current_endpoint = None
        self.current_user_id = None
        
        # Data callback for streaming data
        self.data_callback = None
        
        # Connection retry state
        self._connection_retry_task = None
        self._should_retry = False
        
        self.tracer = trace.get_tracer("simulator_manager")
        logger.info("Simulator manager initialized for connection-only mode")

    def set_data_callback(self, callback):
        """Set callback function for exchange data"""
        self.data_callback = callback
        logger.debug("Data callback set for simulator manager")

    async def find_user_simulator(self, user_id: str) -> Tuple[Optional[Dict], str]:
        """
        Find the running simulator for a user
        
        Args:
            user_id: User ID to find simulator for
            
        Returns:
            Tuple of (simulator_info, error_message)
        """
        with optional_trace_span(self.tracer, "find_user_simulator") as span:
            span.set_attribute("user_id", user_id)
            
            try:
                pool = await self.store_manager.simulator_store._get_pool()
                async with pool.acquire() as conn:
                    row = await conn.fetchrow('''
                        SELECT si.simulator_id, si.user_id, si.exch_id, si.endpoint, 
                               si.pod_name, si.status, si.exchange_type,
                               m.group_id, m.timezone, m.exchanges
                        FROM exch_us_equity.simulator_instances si
                        JOIN exch_us_equity.users u ON si.user_id = u.user_id
                        JOIN exch_us_equity.metadata m ON si.exch_id = m.exch_id
                        WHERE si.user_id = $1 AND si.status = 'RUNNING'
                        LIMIT 1
                    ''', user_id)
                    
                    if not row:
                        return None, f"No running simulator found for user {user_id}"
                    
                    simulator_info = {
                        'simulator_id': str(row['simulator_id']),
                        'user_id': row['user_id'],
                        'exch_id': str(row['exch_id']),
                        'endpoint': row['endpoint'],
                        'pod_name': row['pod_name'],
                        'status': row['status'],
                        'exchange_type': row['exchange_type'],
                        'group_id': row['group_id'],
                        'timezone': row['timezone'],
                        'exchanges': row['exchanges']
                    }
                    
                    logger.info(f"Found simulator for user {user_id}: {simulator_info['simulator_id']}")
                    return simulator_info, ""
                    
            except Exception as e:
                logger.error(f"Error finding simulator for user {user_id}: {e}", exc_info=True)
                return None, f"Database error: {str(e)}"

    async def connect_to_simulator(self, user_id: str) -> Tuple[bool, str]:
        """
        Connect to the user's existing simulator
        
        Args:
            user_id: User ID to connect simulator for
            
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
            
            # Test connection with heartbeat
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
                
                # Connection successful
                self.current_simulator_id = simulator_id
                self.current_endpoint = endpoint
                self.current_user_id = user_id
                
                track_simulator_connection_attempt('success')
                track_simulator_connection_time(time.time() - start_time, 'success')
                
                logger.info(f"Successfully connected to simulator {simulator_id} for user {user_id}")
                return True, ""
                
            except Exception as e:
                logger.error(f"Error connecting to simulator {simulator_id}: {e}")
                track_simulator_connection_attempt('failed_error')
                track_simulator_connection_time(time.time() - start_time, 'failed')
                return False, f"Connection error: {str(e)}"

    async def connect_with_retry(self, user_id: str) -> None:
        """
        Connect to simulator with infinite retry and exponential backoff.
        This runs in background and notifies via data callback when status changes.
        
        Args:
            user_id: User ID to connect simulator for
        """
        max_attempts = config.simulator.max_reconnect_attempts  # 0 = infinite
        base_delay = config.simulator.reconnect_delay
        backoff_multiplier = config.simulator.connection_retry_backoff
        max_delay = config.simulator.max_retry_delay
        
        attempt = 0
        current_delay = base_delay
        self._should_retry = True
        
        while self._should_retry and (max_attempts == 0 or attempt < max_attempts):
            attempt += 1
            
            # Try to connect
            connected, error = await self.connect_to_simulator(user_id)
            
            if connected:
                logger.info(f"Successfully connected to simulator for user {user_id} after {attempt} attempts")
                # Notify via callback about successful connection
                if self.data_callback:
                    await self._notify_connection_status("CONNECTED", None)
                return
            
            # Log the failure and notify frontend
            logger.warning(f"Connection attempt {attempt} failed for user {user_id}: {error}")
            if self.data_callback:
                await self._notify_connection_status("CONNECTING", f"Attempt {attempt} failed: {error}")
            
            # If this is our last attempt and we have a limit, stop trying
            if max_attempts > 0 and attempt >= max_attempts:
                logger.error(f"Failed to connect to simulator for user {user_id} after {max_attempts} attempts")
                if self.data_callback:
                    await self._notify_connection_status("DISCONNECTED", f"Failed after {max_attempts} attempts")
                return
            
            # Wait before next attempt with exponential backoff
            if self._should_retry:
                logger.info(f"Retrying connection for user {user_id} in {current_delay} seconds...")
                try:
                    await asyncio.sleep(current_delay)
                except asyncio.CancelledError:
                    break
                
                # Increase delay for next attempt (exponential backoff)
                current_delay = min(current_delay * backoff_multiplier, max_delay)

    async def _notify_connection_status(self, status: str, message: str = None):
        """Notify about connection status changes via data callback"""
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
        """Start background connection retry task"""
        if self._connection_retry_task and not self._connection_retry_task.done():
            self._connection_retry_task.cancel()
        
        self._connection_retry_task = asyncio.create_task(self.connect_with_retry(user_id))
        self._connection_retry_task.set_name(f"simulator-retry-{user_id}")

    async def stop_connection_retry(self):
        """Stop background connection retry"""
        self._should_retry = False
        if self._connection_retry_task and not self._connection_retry_task.done():
            self._connection_retry_task.cancel()
            try:
                await self._connection_retry_task
            except asyncio.CancelledError:
                pass

    async def stream_exchange_data(self, session_id: str, client_id: str):
        """Stream exchange data from connected simulator"""
        if not self.current_endpoint:
            raise ValueError("No simulator connected")
        
        logger.info(f"Starting exchange data stream from simulator {self.current_simulator_id}")
        
        try:
            exchange_type = ExchangeType.EQUITIES
            
            async for data in self.exchange_client.stream_exchange_data(
                self.current_endpoint, session_id, client_id, exchange_type
            ):
                # Forward data via callback
                if self.data_callback:
                    try:
                        if asyncio.iscoroutinefunction(self.data_callback):
                            await self.data_callback(data)
                        else:
                            self.data_callback(data)
                    except Exception as e:
                        logger.error(f"Error in data callback: {e}", exc_info=True)
                
                yield data
                
        except Exception as e:
            logger.error(f"Stream error from simulator {self.current_simulator_id}: {e}")
            # Reset connection state on error
            self.current_simulator_id = None
            self.current_endpoint = None
            self.current_user_id = None
            
            # Notify about disconnection
            if self.data_callback:
                await self._notify_connection_status("DISCONNECTED", f"Stream error: {str(e)}")
            
            raise

    async def disconnect(self):
        """Disconnect from current simulator"""
        if self.current_simulator_id:
            logger.info(f"Disconnecting from simulator {self.current_simulator_id}")
            
        # Stop retry task
        await self.stop_connection_retry()
        
        # Clear connection state
        self.current_simulator_id = None
        self.current_endpoint = None
        self.current_user_id = None

    def get_connection_info(self) -> Dict[str, Any]:
        """Get current connection information"""
        return {
            'connected': self.current_simulator_id is not None,
            'simulator_id': self.current_simulator_id,
            'endpoint': self.current_endpoint,
            'user_id': self.current_user_id,
            'retrying': self._connection_retry_task is not None and not self._connection_retry_task.done()
        }
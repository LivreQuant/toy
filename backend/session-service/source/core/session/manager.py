"""
Session manager for handling a single user session.
Simplified for dedicated single-user service.
"""
import logging
import asyncio
import time
from typing import Optional, Dict, Any, Callable

from opentelemetry import trace

from source.db.manager import StoreManager

from source.clients.exchange import ExchangeClient

from source.core.stream.manager import StreamManager
from source.core.state.manager import StateManager
from source.core.simulator.manager import SimulatorManager

from source.core.session.connection import Connection

logger = logging.getLogger('session_manager')


class SessionManager:
    """Manager for a single user session - core of the session service"""

    def __init__(
            self,
            store_manager: StoreManager,
            exchange_client: ExchangeClient,
            stream_manager: StreamManager,
            state_manager: StateManager,
            simulator_manager: SimulatorManager,
    ):
        """
        Initialize session manager with a pre-defined session ID

        Args:
            store_manager: PostgreSQL store for session persistence
            exchange_client: Exchange client for simulator communication
            simulator_manager: Manager for simulator operations
            stream_manager: Stream manager for managing background streams
        """
        self.store_manager = store_manager
        self.exchange_client = exchange_client
        self.stream_manager = stream_manager
        self.state_manager = state_manager
        self.simulator_manager = simulator_manager

        # Track if we have a simulator
        self.simulator_active = False

        # Callbacks for exchange data
        self.exchange_data_callbacks = set()

        # Initialize connection component
        self.connection = Connection(self)

        # Create tracer
        self.tracer = trace.get_tracer("session_manager")

        # Set up data callback to simulator manager
        self.simulator_manager.set_data_callback(self._handle_exchange_data)

        # Add a recent data cache
        self._recent_data_cache = {}
        self._cache_max_size = 100  # Adjust as needed

        # Background simulator manager reference (set by server)
        self.background_simulator_manager = None

        logger.info(f"Session manager initialized!")

    def set_background_simulator_manager(self, bg_manager):
        """Set the background simulator manager reference"""
        self.background_simulator_manager = bg_manager

    # ----- Callback management -----

    def register_exchange_data_callback(self, callback: Callable[[Dict[str, Any]], None]):
        """
        Register a callback to receive exchange data

        Args:
            callback: Function that accepts exchange data dictionary
        """
        self.exchange_data_callbacks.add(callback)
        logger.debug(f"Registered exchange data callback, total: {len(self.exchange_data_callbacks)}")

    def unregister_exchange_data_callback(self, callback: Callable[[Dict[str, Any]], None]):
        """
        Unregister a previously registered callback

        Args:
            callback: The callback function to remove
        """
        if callback in self.exchange_data_callbacks:
            self.exchange_data_callbacks.remove(callback)
            logger.debug(f"Unregistered exchange data callback, remaining: {len(self.exchange_data_callbacks)}")

    async def _handle_exchange_data(self, data):
        """
        Handle incoming exchange data by forwarding to all registered callbacks

        Args:
            data: Exchange data (can be dict or ExchangeDataUpdate object)
        """
        # Handle both dict and ExchangeDataUpdate objects
        if hasattr(data, 'to_dict'):
            # It's a Pydantic model
            timestamp = getattr(data, 'timestamp', time.time())
            update_id = getattr(data, 'update_id', '')
            data_id = f"{timestamp}-{update_id}"
            
            # Convert to dict for processing if needed
            data_dict = data.to_dict() if hasattr(data, 'to_dict') and callable(data.to_dict) else {}
            logger.info(f"Session manager processing exchange data [ID: {data_id}] as ExchangeDataUpdate with {len(self.exchange_data_callbacks)} callbacks")
        else:
            # It's a dictionary
            data_id = f"{data.get('timestamp', time.time())}-{hash(str(data))}"
            data_dict = data
            logger.info(f"Session manager processing exchange data [ID: {data_id}] as dict with {len(self.exchange_data_callbacks)} callbacks")

        # Check if this data has already been processed recently
        if data_id in self._recent_data_cache:
            logger.debug(f"Skipping duplicate data [ID: {data_id}]")
            return

        # Add to recent cache
        self._recent_data_cache[data_id] = time.time()

        # Trim the cache if it gets too large
        if len(self._recent_data_cache) > self._cache_max_size:
            oldest_key = min(self._recent_data_cache, key=self._recent_data_cache.get)
            del self._recent_data_cache[oldest_key]

        # Check if there are any callbacks registered
        if len(self.exchange_data_callbacks) == 0:
            logger.warning("No callbacks registered for exchange data!")
            return

        # Log data details for debugging
        if hasattr(data, 'market_data'):
            has_market_data = len(getattr(data, 'market_data', [])) > 0
        elif isinstance(data, dict):
            has_market_data = 'market_data' in data_dict or 'marketData' in data_dict
        else:
            has_market_data = False
            
        logger.info(f"Data details: type={type(data)}, contains market data: {has_market_data}")

        tasks = []
        for idx, callback in enumerate(list(self.exchange_data_callbacks)):
            try:
                # Check if callback is a coroutine function
                if asyncio.iscoroutinefunction(callback):
                    logger.debug(f"Queuing async callback #{idx} for data [ID: {data_id}]")
                    tasks.append(asyncio.create_task(callback(data)))
                else:
                    logger.debug(f"Executing sync callback #{idx} for data [ID: {data_id}]")
                    callback(data)
            except Exception as e:
                logger.error(f"Error in exchange data callback: {e}")

        # Wait for all coroutine tasks to complete
        if tasks:
            logger.debug(f"Waiting for {len(tasks)} async callbacks to complete for data [ID: {data_id}]")
            await asyncio.gather(*tasks, return_exceptions=True)
            logger.debug(f"All async callbacks completed for data [ID: {data_id}]")
            
    # ----- Public API methods -----
    async def get_session(self):
        """
        Get the current session
        
        Args:
        """
        # Use provided session_id or fall back to the manager's session_id
        session_id = self.state_manager.get_active_session_id()
        return await self.store_manager.session_store.get_session_from_db(session_id)

    async def get_session_details(self) -> Optional[Dict[str, Any]]:
        """
        Get session details as a dictionary
        
        Args:
        """
        # Use provided session_id or fall back to the manager's session_id
        session = await self.get_session()
        if not session or not hasattr(session, 'details'):
            return None

        # Convert the SessionDetails object to a dictionary
        try:
            return session.details.dict()
        except Exception as e:
            logger.error(f"Error converting session details to dict: {e}")
            return {}

    async def update_session_activity(self):
        """
        Update session last activity time.
        
        Args:
        """
        # Use provided session_id or fall back to the manager's session_id
        session_id = self.state_manager.get_active_session_id()
        if session_id:
            return await self.store_manager.session_store.update_session_activity(session_id)

    async def update_session_details(self, details_updates: Dict[str, Any]):
        """Update session details"""
        session_id = self.state_manager.get_active_session_id()
        if session_id:
            return await self.store_manager.session_store.update_session_details(session_id, details_updates)

    # ----- Non-blocking simulator operations -----

    async def request_simulator_check(self, user_id: str) -> str:
        """
        Request a simulator check without blocking.
        Returns task_id for tracking.
        """
        if not self.background_simulator_manager:
            raise RuntimeError("Background simulator manager not initialized")
            
        session_id = self.state_manager.get_active_session_id()
        
        # Create callback to handle results
        async def simulator_result_callback(result):
            await self._handle_simulator_result(result)
            
        return self.background_simulator_manager.queue_simulator_check(
            session_id, user_id, simulator_result_callback
        )
        
    async def request_simulator_creation(self, user_id: str) -> str:
        """Request simulator creation without blocking"""
        if not self.background_simulator_manager:
            raise RuntimeError("Background simulator manager not initialized")
            
        session_id = self.state_manager.get_active_session_id()
        
        async def simulator_result_callback(result):
            await self._handle_simulator_result(result)
            
        return self.background_simulator_manager.queue_simulator_creation(
            session_id, user_id, simulator_result_callback
        )

    async def _handle_simulator_result(self, result: Dict):
        """Handle results from background simulator operations"""
        session_id = result['session_id']
        status = result['status']
        
        logger.info(f"Received simulator result for {session_id}: {status}")
        
        # Update simulator manager state if successful
        if status in ['RUNNING', 'STARTING'] and 'simulator_id' in result:
            self.simulator_manager.current_simulator_id = result['simulator_id']
            self.simulator_manager.current_endpoint = result.get('endpoint')
            
            # Start data streaming if simulator is running
            if status == 'RUNNING' and result.get('endpoint'):
                await self._start_data_streaming(result['simulator_id'], result['endpoint'])
        
        # Notify WebSocket clients
        await self._notify_simulator_status_change(result)

    async def _start_data_streaming(self, simulator_id: str, endpoint: str):
        """Start exchange data streaming for a simulator"""
        try:
            session_id = self.state_manager.get_active_session_id()
            
            # Create the exchange data stream task
            stream_task = asyncio.create_task(
                self._stream_simulator_data(endpoint, simulator_id)
            )
            stream_task.set_name(f"stream-{simulator_id}")

            # Register with stream manager
            if stream_task and self.stream_manager:
                self.stream_manager.register_stream(session_id, stream_task)
                
            self.simulator_active = True
            logger.info(f"Started data streaming for simulator {simulator_id}")
            
        except Exception as e:
            logger.error(f"Failed to start data streaming: {e}", exc_info=True)
        
    async def _notify_simulator_status_change(self, result: Dict):
        """Notify WebSocket clients of simulator status changes"""
        notification = {
            'type': 'simulator_status_update',
            'session_id': result['session_id'],
            'status': result['status'],
            'simulator_id': result.get('simulator_id'),
            'timestamp': int(time.time() * 1000)
        }
        
        if 'error' in result:
            notification['error'] = result['error']
            
        # Send to all registered callbacks (including WebSocket manager)
        await self._handle_exchange_data(notification)

    # ----- Legacy simulator operations (now delegated to background manager) -----

    async def start_simulator(self, user_id=None):
        """Start a simulator for the session - now uses background manager"""
        # Use user ID from the session if not specified
        if not user_id:
            session = await self.get_session()
            user_id = session.user_id if session else "default-user"

        try:
            task_id = await self.request_simulator_creation(user_id)
            logger.info(f"Requested simulator creation, task_id: {task_id}")
            
            # Return placeholder values - actual values will come via callback
            return "pending", "pending", ""
        except Exception as e:
            logger.error(f"Failed to request simulator creation: {e}")
            return None, None, str(e)

    async def _stream_simulator_data(self, endpoint: str, simulator_id: str):
        """Stream simulator data - data is handled via callback now"""
        try:
            session_id = self.state_manager.get_active_session_id()

            # Add readiness polling
            max_attempts = 10
            attempt = 0
            connected = False

            logger.info(f"Waiting for simulator {simulator_id} to be ready...")

            while attempt < max_attempts and not connected:
                try:
                    # Try to send a heartbeat to check readiness
                    heartbeat_result = await self.exchange_client.send_heartbeat(
                        endpoint,
                        session_id,
                        f"readiness-check-{session_id}"
                    )

                    if heartbeat_result.get('success', False):
                        connected = True
                        logger.info(f"Successfully connected to simulator {simulator_id}")

                        # Update status and notify clients
                        await self.update_simulator_status(simulator_id, 'RUNNING')
                        break
                    else:
                        logger.info(
                            f"Simulator {simulator_id} not ready yet (heartbeat failed), waiting... (attempt {attempt + 1}/{max_attempts})")
                except Exception as e:
                    logger.info(
                        f"Simulator {simulator_id} not ready yet, waiting... (attempt {attempt + 1}/{max_attempts}): {e}")

                attempt += 1
                await asyncio.sleep(5)  # Wait between attempts - 5 seconds should be enough

            if not connected:
                logger.error(f"Failed to connect to simulator {simulator_id} after {max_attempts} attempts")
                self.simulator_active = False
                return

            # Stream data with error handling
            try:
                logger.info(f"Starting exchange data stream for simulator {simulator_id}")

                # Stream data - handling will occur via callbacks
                async for data in self.simulator_manager.stream_exchange_data(
                        endpoint,
                        session_id,
                        f"stream-{session_id}"
                ):
                    # Just log that we received data - don't try to access properties directly
                    # This avoids the 'get' attribute error
                    logger.debug(f"Received data from exchange stream (simulator: {simulator_id})")
                    
                    # If we get here, we're successfully receiving data
                    # Ensure simulator_status is set to RUNNING on first data received
                    if not self.simulator_active:
                        logger.info(f"First data received from simulator {simulator_id}, ensuring status is RUNNING")
                        self.simulator_active = True
                        await self.update_simulator_status(simulator_id, 'RUNNING')
                    
                    # Note: We don't need to call _handle_exchange_data here
                    # The simulator_manager will take care of that through its callbacks
            except GeneratorExit:
                # Handle generator exit gracefully
                logger.info(f"Exchange data stream closed for simulator {simulator_id}")
                self.simulator_active = False
            except Exception as stream_error:
                logger.error(f"Error in simulator data stream: {stream_error}")
                # Attempt to recover
                self.simulator_active = False

                # Try to gracefully close the stream
                try:
                    await self.stream_manager.stop_stream(session_id)
                except Exception as stop_error:
                    logger.error(f"Error stopping stream: {stop_error}")

        except Exception as e:
            logger.error(f"Error in simulator data streaming: {e}")
            self.simulator_active = False

    async def update_simulator_status(self, simulator_id: str, status: str):
        """
        Update simulator status and notify websocket clients

        Args:
            simulator_id: The simulator ID
            status: The new status
        """
        # Log the status change
        logger.info(f"Updated simulator {simulator_id} status to {status}")

        # Create a payload that any connected code can use to notify clients
        update_payload = {
            'type': 'simulator_status_changed',
            'simulator_id': simulator_id,
            'status': status,
            'timestamp': int(time.time() * 1000)
        }

        # Call registered callbacks with this payload
        await self._handle_exchange_data(update_payload)

    async def stop_simulator(self, simulator_id: str, force=False):
        """Stop the current simulator"""
        # Stop via the simulator manager
        success, error = await self.simulator_manager.stop_simulator(simulator_id, force)

        # Update state tracking
        self.simulator_active = False

        session_id = self.state_manager.get_active_session_id()

        # Stop the stream if running
        if self.stream_manager:
            await self.stream_manager.stop_stream(session_id)

        # Even if the simulator_manager.stop_simulator failed, log and continue
        if success:
            logger.info(f"Successfully stopped simulator {simulator_id}")
        else:
            logger.error(f"Failed to stop simulator {simulator_id}: {error}")

        return success, error

    async def cleanup_session(self, keep_simulator=False):
        """
        Clean up the session resources - important for graceful shutdown.

        Args:
            keep_simulator: If True, don't stop the simulator
        """
        # Stop simulator if active and not keeping it
        if self.simulator_active and not keep_simulator:
            simulator_id = None
            if hasattr(self.simulator_manager, 'current_simulator_id'):
                simulator_id = self.simulator_manager.current_simulator_id

            if simulator_id:
                await self.stop_simulator(simulator_id, force=True)
            else:
                logger.warning("Simulator is active but no ID available")

        session_id = self.state_manager.get_active_session_id()

        # Make sure all streams are stopped
        if self.stream_manager:
            await self.stream_manager.stop_stream(session_id)

        logger.info(f"Cleaned up session {session_id}, keep_simulator={keep_simulator}")
        return True
        
    async def validate_device(self, device_id: str) -> tuple[bool, str, str]:
        """
        Validate if device ID matches the current session.
        
        Args:
            device_id: The device ID to validate
            
        Returns:
            Tuple of (is_valid, existing_device_id, error_message)
        """
        details = await self.get_session_details()
        if not details:
            return True, "", ""
            
        existing_device_id = details.get('device_id')
        if not existing_device_id:
            return True, "", ""
            
        if existing_device_id != device_id:
            return False, existing_device_id, "Session already active on another device"
        
        return True, existing_device_id, ""

    async def register_device(self, device_id: str, user_id: str) -> bool:
        """
        Register a device with the session.
        
        Args:
            device_id: The device ID to register
            user_id: The user ID
            
        Returns:
            True if successful
        """
        try:
            await self.update_session_details({
                'device_id': device_id,
                'last_device_update': time.time()
            })
            session_id = self.state_manager.get_active_session_id()
            logger.info(f"Registered device {device_id} for user {user_id} with session {session_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to register device: {e}")
            return False
"""
Simplified session manager - connects to existing simulators instead of creating them.
"""
import logging
import asyncio
import time
from typing import Optional, Dict, Any, Callable, Tuple

from opentelemetry import trace

logger = logging.getLogger('session_manager')


class SessionManager:
    """Simplified session manager for connecting to existing simulators"""

    def __init__(self, store_manager, exchange_client, stream_manager, 
                 state_manager, simulator_manager):
        """Initialize session manager"""
        self.store_manager = store_manager
        self.exchange_client = exchange_client
        self.stream_manager = stream_manager
        self.state_manager = state_manager
        self.simulator_manager = simulator_manager
        
        # Callbacks for exchange data
        self.exchange_data_callbacks = set()
        
        # Set up data callback to simulator manager
        self.simulator_manager.set_data_callback(self._handle_exchange_data)
        
        self.tracer = trace.get_tracer("session_manager")
        logger.info("Session manager initialized for connection-only mode")

    def register_exchange_data_callback(self, callback: Callable):
        """Register callback for exchange data"""
        self.exchange_data_callbacks.add(callback)
        logger.debug(f"Registered exchange data callback, total: {len(self.exchange_data_callbacks)}")

    def unregister_exchange_data_callback(self, callback: Callable):
        """Unregister callback for exchange data"""
        self.exchange_data_callbacks.discard(callback)
        logger.debug(f"Unregistered exchange data callback, remaining: {len(self.exchange_data_callbacks)}")

    async def _handle_exchange_data(self, data):
        """Handle incoming exchange data by forwarding to callbacks"""
        if not self.exchange_data_callbacks:
            logger.debug("No callbacks registered for exchange data")
            return
            
        # Handle both dict and ExchangeDataUpdate objects
        if hasattr(data, 'to_dict'):
            data_id = f"{getattr(data, 'timestamp', time.time())}-{getattr(data, 'update_id', '')}"
        else:
            data_id = f"{data.get('timestamp', time.time())}-{hash(str(data))}"
            
        logger.debug(f"Processing exchange data [ID: {data_id}] with {len(self.exchange_data_callbacks)} callbacks")
            
        tasks = []
        for callback in list(self.exchange_data_callbacks):
            try:
                if asyncio.iscoroutinefunction(callback):
                    tasks.append(asyncio.create_task(callback(data)))
                else:
                    callback(data)
            except Exception as e:
                logger.error(f"Error in exchange data callback: {e}")
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def start_session(self, user_id: str, device_id: str) -> Tuple[bool, str]:
        """
        Start a session by connecting to the user's existing simulator
        
        Args:
            user_id: User ID
            device_id: Device ID
            
        Returns:
            Tuple of (success, error_message)
        """
        logger.info(f"Starting session for user {user_id}, device {device_id}")
        
        # Set service to active state
        await self.state_manager.set_active(user_id=user_id)
        session_id = self.state_manager.get_active_session_id()
        
        # Create session in database
        success = await self.store_manager.session_store.create_session(
            session_id, user_id, device_id, ip_address="127.0.0.1"
        )
        
        if not success:
            return False, "Failed to create session in database"
        
        # Start connection attempt with retry (non-blocking)
        await self.simulator_manager.start_connection_retry(user_id)
        
        # Start data streaming task
        await self._start_data_streaming(session_id)
        
        logger.info(f"Session started successfully for user {user_id}")
        return True, ""

    async def _start_data_streaming(self, session_id: str):
        """Start exchange data streaming task"""
        try:
            stream_task = asyncio.create_task(
                self._stream_simulator_data(session_id)
            )
            stream_task.set_name(f"stream-{session_id}")
            
            if self.stream_manager:
                self.stream_manager.register_stream(session_id, stream_task)
                
            logger.info(f"Started data streaming task for session {session_id}")
            
        except Exception as e:
            logger.error(f"Failed to start data streaming: {e}", exc_info=True)

    async def _stream_simulator_data(self, session_id: str):
        """Stream data from connected simulator (with retry logic)"""
        while True:
            try:
                # Wait for connection to be established
                connection_info = self.simulator_manager.get_connection_info()
                while not connection_info['connected']:
                    logger.debug(f"Waiting for simulator connection for session {session_id}")
                    await asyncio.sleep(1)
                    connection_info = self.simulator_manager.get_connection_info()
                
                logger.info(f"Starting data stream for session {session_id}")
                
                # Stream data while connected
                async for data in self.simulator_manager.stream_exchange_data(
                    session_id, f"stream-{session_id}"
                ):
                    # Data is automatically forwarded via callback
                    pass
                    
            except Exception as e:
                logger.error(f"Error in simulator data streaming: {e}")
                # Wait before retrying
                await asyncio.sleep(5)
                continue

    async def get_session(self):
        """Get the current session"""
        session_id = self.state_manager.get_active_session_id()
        if not session_id:
            return None
        return await self.store_manager.session_store.get_session_from_db(session_id)

    async def get_session_details(self) -> Optional[Dict[str, Any]]:
        """Get session details as dictionary"""
        session = await self.get_session()
        if not session or not hasattr(session, 'details'):
            return None
        try:
            return session.details.dict()
        except Exception as e:
            logger.error(f"Error converting session details to dict: {e}")
            return {}

    async def update_session_activity(self):
        """Update session last activity time"""
        session_id = self.state_manager.get_active_session_id()
        if session_id:
            return await self.store_manager.session_store.update_session_activity(session_id)

    async def update_session_details(self, details_updates: Dict[str, Any]):
        """Update session details"""
        session_id = self.state_manager.get_active_session_id()
        if session_id:
            return await self.store_manager.session_store.update_session_details(session_id, details_updates)

    async def cleanup_session(self):
        """Clean up session resources"""
        session_id = self.state_manager.get_active_session_id()
        
        # Stop streams
        if self.stream_manager:
            await self.stream_manager.stop_stream(session_id)
        
        # Disconnect from simulator
        await self.simulator_manager.disconnect()
        
        logger.info(f"Cleaned up session {session_id}")
        return True

    def get_simulator_status(self) -> str:
        """Get current simulator connection status"""
        connection_info = self.simulator_manager.get_connection_info()
        if connection_info['connected']:
            return "CONNECTED"
        elif connection_info['retrying']:
            return "CONNECTING"
        else:
            return "DISCONNECTED"
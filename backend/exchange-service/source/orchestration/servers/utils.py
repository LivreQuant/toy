import logging
import queue
import grpc
from typing import Optional, Any, Callable
from google.protobuf.empty_pb2 import Empty


class BaseServiceImpl:
    def __init__(self, service_name: Optional[str] = None):
        self.logger = logging.getLogger(service_name or self.__class__.__name__)
        self._stream_queue: Optional[queue.Queue] = None

    def _init_stream_queue(self) -> None:
        """Initialize queue for streaming data if needed"""
        self._stream_queue = queue.Queue()

    def _check_manager(self, manager: Any, manager_name: str, context: grpc.ServicerContext) -> None:
        """Validate manager initialization"""
        if not manager:
            context.abort(grpc.StatusCode.UNAVAILABLE, f"{manager_name} not initialized")

    def _check_system_initialized(self, context: grpc.ServicerContext) -> None:
        """Validate system initialization"""
        # Import here to avoid circular import
        from source.orchestration.app_state.state_manager import app_state
        if not app_state.is_initialized():
            context.abort(grpc.StatusCode.UNAVAILABLE, "System initializing")

    def _stream_data(self,
                     context: grpc.ServicerContext,
                     update_callback: Callable,
                     manager: Any,
                     manager_name: str,
                     timeout: float = 1.0,
                     callback_method: str = 'register_update_callback'):
        """Common streaming implementation"""
        try:
            self._check_manager(manager, manager_name, context)

            # Get the appropriate registration method
            register_method = getattr(manager, callback_method)
            if not register_method:
                raise AttributeError(f"{manager_name} does not have method {callback_method}")

            # Register for updates
            register_method(update_callback)

            # Send initial state if manager has get_all method
            if hasattr(manager, 'get_all_data'):
                update_callback(manager.get_all_data())

            # Stream updates
            while context.is_active():
                try:
                    update = self._stream_queue.get(timeout=timeout)
                    yield update
                except queue.Empty:
                    continue

        except Exception as e:
            self.logger.error(f"Error streaming data: {e}", exc_info=True)
            context.abort(grpc.StatusCode.INTERNAL, str(e))

    def _handle_request(self, context: grpc.ServicerContext, func: Callable, *args, **kwargs) -> Any:
        """Common request handling with error handling"""
        try:
            return func(*args, **kwargs)
        except Exception as e:
            self.logger.error(f"Error processing request: {e}", exc_info=True)
            context.abort(grpc.StatusCode.INTERNAL, str(e))
            return Empty()
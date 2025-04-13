# source/api/rest/decorators.py
from functools import wraps
from typing import Callable
from aiohttp import web
from opentelemetry import trace

from source.utils.metrics import track_session_operation, track_simulator_operation
from source.api.rest.utils import validate_auth_token


def with_auth_validation(operation_type: str = None, metrics_category: str = "api"):
    """
    Decorator for REST endpoints that need authentication validation.

    Args:
        operation_type: Type of operation for metrics tracking
        metrics_category: Category for metrics tracking (session/simulator)

    Returns:
        Decorator function
    """

    def decorator(handler_func: Callable):
        @wraps(handler_func)
        async def wrapper(request: web.Request):
            tracer = trace.get_tracer("rest_handlers")
            handler_name = handler_func.__name__

            with tracer.start_as_current_span(handler_name) as span:
                # Validate auth token
                user_id, validation, error_response = await validate_auth_token(request, span)

                if error_response:
                    # Track error based on operation category
                    if metrics_category == "session":
                        track_session_operation(operation_type, "error_auth")
                    elif metrics_category == "simulator":
                        track_simulator_operation(operation_type, "error_auth")
                    return error_response

                # Get session manager
                session_manager = request.app['session_manager']

                # Set common span attributes
                span.set_attribute("user_id", user_id)
                span.set_attribute("session_id", session_manager.session_id)

                # Call the actual handler with validated user_id
                return await handler_func(request, user_id)

        return wrapper

    return decorator

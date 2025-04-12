# source/utils/middleware.py
import time
import uuid
import logging
from aiohttp import web
from opentelemetry import trace

from source.utils.metrics import track_rest_request

logger = logging.getLogger('middleware')


@web.middleware
async def tracing_middleware(request, handler):
    """Middleware for OpenTelemetry tracing of HTTP requests"""
    tracer = trace.get_tracer("http_server")

    # Extract route name for the span name
    route_name = request.match_info.route.name or 'unknown'
    span_name = f"{request.method} {route_name}"

    with tracer.start_as_current_span(span_name) as span:
        # Add common attributes
        span.set_attribute("http.method", request.method)
        span.set_attribute("http.url", str(request.url))
        span.set_attribute("http.route", route_name)
        span.set_attribute("http.host", request.host)
        span.set_attribute("http.user_agent", request.headers.get('User-Agent', 'unknown'))

        # Add client IP
        client_ip = request.remote
        if client_ip:
            span.set_attribute("http.client_ip", client_ip)

        # Process the request
        try:
            response = await handler(request)

            # Add response attributes
            span.set_attribute("http.status_code", response.status)

            return response
        except Exception as e:
            # Record the exception and re-raise
            span.record_exception(e)
            span.set_attribute("error", str(e))
            span.set_attribute("http.status_code", 500)
            raise


def _get_route_name(request: web.Request) -> str:
    """
    Extract a meaningful route name from the request for metrics and logging.

    Args:
        request: The web request

    Returns:
        String representing the route name
    """
    # Default if route cannot be determined
    route_name = 'unknown_route'

    # Try to get route information
    if request.match_info.route:
        route = request.match_info.route
        route_name = route.name
        if not route_name and route.resource:
            route_name = route.resource.canonical

    # If still no meaningful name, use the request path (less ideal for aggregation)
    if not route_name or route_name == 'unknown_route':
        route_name = request.path

    return route_name


@web.middleware
async def metrics_middleware(request: web.Request, handler):
    """
    Aiohttp middleware to track REST request metrics (e.g., latency, status codes).

    Uses the `track_rest_request` utility function to update Prometheus metrics.
    Also adds a request_id to the request object for tracing.
    """
    # Generate request ID for tracing
    request_id = str(uuid.uuid4())
    request['request_id'] = request_id

    start_time = time.time()
    method = request.method
    route_name = _get_route_name(request)

    logger.debug(f"Request Started: {method} {route_name} [id:{request_id}]")

    try:
        # Process the request through the next middleware or the handler
        response = await handler(request)

        # Calculate metrics
        status_code = response.status
        duration = time.time() - start_time

        # Add request ID to response headers for client-side tracing
        response.headers['X-Request-ID'] = request_id

        # Track metrics for successful request (or handled HTTP errors)
        track_rest_request(method, route_name, status_code, duration)

        # Categorize response as success/error for logging level
        if status_code >= 400:
            logger.warning(
                f"Request Error: {method} {route_name} -> {status_code} ({duration:.4f}s) [id:{request_id}]"
            )
        else:
            logger.debug(
                f"Request Success: {method} {route_name} -> {status_code} ({duration:.4f}s) [id:{request_id}]"
            )

        return response

    except Exception as e:
        # This block catches exceptions raised from downstream middleware or the handler
        duration = time.time() - start_time
        status_code = 500  # Default status code for unhandled exceptions

        # If the exception is a known aiohttp HTTP exception, use its status code
        if isinstance(e, web.HTTPException):
            status_code = e.status_code

        # Track metrics for the failed request
        error_type = type(e).__name__
        track_rest_request(method, route_name, status_code, duration)

        logger.error(
            f"Request Failed: {method} {route_name} -> {status_code} ({duration:.4f}s) [id:{request_id}]. "
            f"Error: {error_type}: {e}"
        )

        # Re-raise the exception for aiohttp's default error handling
        raise


@web.middleware
async def error_handling_middleware(request: web.Request, handler):
    """
    Middleware to handle exceptions and convert them to appropriate JSON responses.
    This provides a consistent error format for API clients.
    """
    try:
        return await handler(request)
    except web.HTTPException as ex:
        # For HTTP exceptions, keep the status code but format as JSON
        status = ex.status
        message = ex.reason if hasattr(ex, 'reason') else str(ex)

        return web.json_response({
            'success': False,
            'error': message,
            'status': status
        }, status=status)
    except Exception as e:
        # For unexpected exceptions, return 500 Internal Server Error
        logger.exception(f"Unhandled exception in request handler: {e}")

        return web.json_response({
            'success': False,
            'error': 'Internal server error',
            'status': 500
        }, status=500)

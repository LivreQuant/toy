# source/api/rest/middleware.py
"""
Aiohttp middleware functions for REST API.
"""

import time
import logging
from aiohttp import web

from source.utils.metrics import track_rest_request

logger = logging.getLogger(__name__)  # Logger specific to this middleware file


@web.middleware
async def metrics_middleware(request: web.Request, handler):
    """
    Aiohttp middleware to track REST request metrics (e.g., latency, status codes).

    Uses the `track_rest_request` utility function to update Prometheus metrics.
    """
    start_time = time.time()
    method = request.method
    route_name = 'unknown_route'  # Default if route cannot be determined

    try:
        # Attempt to get a meaningful route name for labeling metrics
        # Prefer route name, fallback to canonical path (template), fallback to raw path
        if request.match_info.route:
            route = request.match_info.route
            route_name = route.name
            if not route_name and route.resource:
                route_name = route.resource.canonical
        # If still no meaningful name, use the request path (less ideal for aggregation)
        if not route_name or route_name == 'unknown_route':
            route_name = request.path

        # --- Process the request through the next middleware or the handler ---
        response = await handler(request)
        # ---------------------------------------------------------------------

        status_code = response.status
        duration = time.time() - start_time

        # Track metrics for successful request (or handled HTTP errors)
        track_rest_request(method, route_name, status_code, duration)
        logger.debug(f"Request Handled: {method} {route_name} -> {status_code} ({duration:.4f}s)")

        return response

    except Exception as e:
        # This block catches exceptions raised from downstream middleware or the handler
        duration = time.time() - start_time
        status_code = 500  # Default status code for unhandled exceptions

        # If the exception is a known aiohttp HTTP exception, use its status code
        if isinstance(e, web.HTTPException):
            status_code = e.status_code

        # Try to determine route name again in case exception happened early
        # (though usually match_info is available before handler runs)
        if route_name == 'unknown_route' and request.match_info.route:
            route = request.match_info.route
            route_name = route.name
            if not route_name and route.resource:
                route_name = route.resource.canonical
            if not route_name:
                route_name = request.path  # Last resort

        # Track metrics for the failed request
        track_rest_request(method, route_name, status_code, duration)
        logger.warning(
            f"Request Failed: {method} {route_name} -> {status_code} ({duration:.4f}s). Error: {type(e).__name__}: {e}"
        )

        # IMPORTANT: Re-raise the exception so aiohttp's default error handling
        # or other error-handling middleware can process it.
        raise

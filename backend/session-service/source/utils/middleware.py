# source/utils/middleware.py
import asyncio
import time
import logging
from aiohttp import web
from opentelemetry import trace

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
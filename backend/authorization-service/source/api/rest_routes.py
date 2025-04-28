# source/api/rest_routes.py
import logging
import aiohttp_cors
import os
import time
from aiohttp import web

from opentelemetry import trace
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

from source.utils.tracing import optional_trace_span

from source.api.handlers.auth_handlers import handle_login, handle_logout, handle_refresh_token, handle_validate_token
from source.api.handlers.feedback_handlers import handle_feedback
from source.api.handlers.password_handlers import handle_reset_password, handle_forgot_password, handle_forgot_username
from source.api.handlers.profile_handlers import handle_update_profile
from source.api.handlers.signup_handlers import handle_signup, handle_verify_email, handle_resend_verification

logger = logging.getLogger('rest_api')


def setup_rest_app(auth_manager):
    """Set up the REST API application with routes and middleware"""
    app = web.Application()

    # Add routes
    app.router.add_post('/api/auth/login', handle_login(auth_manager))
    app.router.add_post('/api/auth/logout', handle_logout(auth_manager))
    app.router.add_post('/api/auth/refresh', handle_refresh_token(auth_manager))
    app.router.add_post('/api/auth/validate', handle_validate_token(auth_manager))

    app.router.add_post('/api/auth/signup', handle_signup(auth_manager))
    app.router.add_post('/api/auth/verify-email', handle_verify_email(auth_manager))
    app.router.add_post('/api/auth/resend-verification', handle_resend_verification(auth_manager))
    app.router.add_post('/api/auth/forgot-username', handle_forgot_username(auth_manager))
    app.router.add_post('/api/auth/forgot-password', handle_forgot_password(auth_manager))
    app.router.add_post('/api/auth/reset-password', handle_reset_password(auth_manager))
    app.router.add_put('/api/auth/profile', handle_update_profile(auth_manager))
    app.router.add_post('/api/auth/feedback', handle_feedback(auth_manager))

    app.router.add_get('/health', handle_health_check)
    app.router.add_get('/readiness', handle_readiness_check(auth_manager))

    # Add this new route for metrics
    app.router.add_get('/metrics', handle_metrics)

    # Set up CORS
    cors = aiohttp_cors.setup(app, defaults={
        "*": aiohttp_cors.ResourceOptions(
            allow_credentials=True,
            expose_headers="*",
            allow_headers=["Content-Type", "Authorization", "X-Requested-With", "Origin", "Accept"],
            allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"]
        )
    })

    # Apply CORS to all routes
    for route in list(app.router.routes()):
        cors.add(route)

    return app


# Then add this new handler function:
async def handle_metrics(request):
    """Expose Prometheus metrics"""
    return web.Response(
        body=generate_latest(),
        content_type=CONTENT_TYPE_LATEST
    )


async def handle_health_check(request):
    """Simple health check endpoint"""
    tracer = trace.get_tracer("rest_api")

    with optional_trace_span(tracer, "health_check") as span:
        span.set_attribute("http.method", "GET")
        span.set_attribute("http.route", "/health")

        # Check if monitoring services are properly configured
        monitoring_status = {
            "metrics": os.getenv('METRICS_PORT', '9090').isdigit(),  # Check if metrics port is configured
            "tracing": os.getenv('ENABLE_TRACING', 'true').lower() == 'true'
        }

        return web.json_response({
            'status': 'UP',
            'timestamp': int(time.time())
        })


def handle_readiness_check(auth_manager):
    """Readiness check endpoint that verifies database connection"""
    tracer = trace.get_tracer("rest_api")

    async def readiness_handler(request):
        with optional_trace_span(tracer, "readiness_check") as span:
            span.set_attribute("http.method", "GET")
            span.set_attribute("http.route", "/readiness")

            try:
                # Check database connection
                connection_alive = await auth_manager.db.check_connection()
                span.set_attribute("db.connection_alive", connection_alive)

                if connection_alive:
                    return web.json_response({
                        'status': 'READY',
                        'timestamp': int(time.time())
                    })
                else:
                    span.set_attribute("error", "Database connection failed")
                    return web.json_response({
                        'status': 'NOT READY',
                        'reason': 'Database connection failed'
                    }, status=503)
            except Exception as e:
                logger.error(f"Readiness check failed: {e}")
                span.record_exception(e)
                span.set_attribute("error", str(e))
                return web.json_response({
                    'status': 'NOT READY',
                    'reason': str(e)
                }, status=503)

    return readiness_handler

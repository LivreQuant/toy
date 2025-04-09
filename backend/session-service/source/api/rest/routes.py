# source/api/rest/routes.py
"""
REST API route setup.
Configures the simplified REST API routes for the session and simulator services.
"""
# Import handlers from their new specific files
from .session_handlers import (
    handle_create_session,
    handle_end_session,
)
from .simulator_handlers import (
    handle_start_simulator,
    handle_stop_simulator,
)
# Health/Readiness/Metrics routes are typically added in server.py or middleware setup

def setup_rest_routes(app):
    """
    Set up simplified REST API routes using the refactored handlers.

    Args:
        app: The aiohttp web application instance.
    """
    # Session routes (as defined in the original example)
    app.router.add_post('/api/sessions', handle_create_session, name='create_session')
    app.router.add_delete('/api/sessions', handle_end_session, name='end_session')

    # Simulator routes (as defined in the original example)
    # GET for start, DELETE for stop. Consider if POST/DELETE for start/stop is more conventional.
    app.router.add_get('/api/simulators', handle_start_simulator, name='start_simulator') # Uses query params + Auth header
    app.router.add_delete('/api/simulators', handle_stop_simulator, name='stop_simulator') # Uses body

    # Note: The original setup explicitly removed debug routes like list_routes.
    # Note: Health, Readiness, Metrics endpoints are usually added elsewhere (e.g., server.py).
    # Note: Ensure the metrics_middleware is applied at the Application level:
    #       e.g., app = web.Application(middlewares=[metrics_middleware]) in your server setup.

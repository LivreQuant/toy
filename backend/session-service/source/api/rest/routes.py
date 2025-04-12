# source/api/rest/routes.py
"""
REST API route setup.
Configures the RESTful API routes for the session and simulator services.
"""
from source.api.rest.session_handlers import (
    handle_start_session,
    handle_stop_session,
)
from source.api.rest.simulator_handlers import (
    handle_start_simulator,
    handle_stop_simulator,
)


def setup_rest_routes(app):
    """
    Set up REST API routes with proper HTTP methods.

    Args:
        app: The aiohttp web application instance.
    """
    # Session routes
    app.router.add_post('/api/sessions', handle_start_session, name='start_session')
    app.router.add_delete('/api/sessions', handle_stop_session, name='stop_session')

    # Simulator routes with proper REST methods
    app.router.add_post('/api/simulators', handle_start_simulator, name='start_simulator')
    app.router.add_delete('/api/simulators', handle_stop_simulator, name='stop_simulator')

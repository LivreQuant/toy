# source/api/rest/routes.py
"""
REST API route setup.
Configures the RESTful API routes for the session and simulator services.
"""
from source.api.rest.session_handlers import (
    handle_session_info,
    handle_stop_session,
)
from source.api.rest.simulator_handlers import (
    handle_start_simulator,
    handle_stop_simulator,
)
from source.api.rest.admin_handlers import (
    handle_reset_service,  # Added missing import
)


def setup_rest_routes(app):
    """
    Set up REST API routes with proper HTTP methods.

    Args:
        app: The aiohttp web application instance.
    """
    # Session routes
    app.router.add_get('/api/session', handle_session_info, name='session_info')
    app.router.add_delete('/api/session', handle_stop_session, name='stop_session')

    # Simulator routes with proper REST methods
    app.router.add_post('/api/simulator', handle_start_simulator, name='start_simulator')
    app.router.add_delete('/api/simulator', handle_stop_simulator, name='stop_simulator')

    # Admin routes
    app.router.add_post('/api/admin/reset', handle_reset_service, name='reset_service')
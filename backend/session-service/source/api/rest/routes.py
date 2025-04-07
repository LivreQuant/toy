"""
REST API route setup.
Configures the REST API routes for the session service.
"""
from source.api.rest.handlers import (
    handle_create_session,
    handle_end_session,
    handle_reconnect_session,
    handle_list_routes,
    handle_stop_simulator,
    handle_start_simulator
)

def setup_rest_routes(app):
    """
    Set up REST API routes
    
    Args:
        app: The web application
    """
    # Session routes
    app.router.add_post('/api/sessions/{device_id}', handle_create_session)
    app.router.add_delete('/api/sessions', handle_end_session)
    app.router.add_post('/api/sessions/{device_id}/reconnect', handle_reconnect_session)
    
    app.router.add_get('/debug/routes', handle_list_routes)

    # Simulator routes
    app.router.add_delete('/api/simulators', handle_stop_simulator)
    app.router.add_get('/api/simulators', handle_start_simulator)
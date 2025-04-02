"""
REST API route setup.
Configures the REST API routes for the session service.
"""
from source.api.rest.handlers import (
    handle_create_session,
    handle_get_session,
    handle_end_session,
    handle_session_ready,
    handle_start_simulator,
    handle_stop_simulator,
    handle_get_simulator_status,
    handle_reconnect_session,
    handle_list_routes,
    handle_get_session_state
)

def setup_rest_routes(app):
    """
    Set up REST API routes
    
    Args:
        app: The web application
    """
    # Session routes
    app.router.add_post('/api/sessions', handle_create_session)
    app.router.add_get('/api/sessions/{session_id}', handle_get_session)
    app.router.add_get('/api/sessions/{session_id}/ready', handle_session_ready)  # Add this
    app.router.add_delete('/api/sessions/{session_id}', handle_end_session)
    app.router.add_post('/api/sessions/{session_id}/reconnect', handle_reconnect_session)
    
    app.router.add_get('/debug/routes', handle_list_routes)
    app.router.add_get('/api/sessions/state', handle_get_session_state)

    # Simulator routes - updated to not use simulator_id in URLs
    app.router.add_post('/api/simulators', handle_start_simulator)
    app.router.add_delete('/api/simulators', handle_stop_simulator)
    app.router.add_get('/api/simulators', handle_get_simulator_status)
    
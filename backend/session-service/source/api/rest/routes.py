"""
REST API route setup.
Configures the REST API routes for the session service.
"""
from source.api.rest.handlers import (
    handle_create_session,
    handle_get_session,
    handle_end_session,
    handle_start_simulator,
    handle_stop_simulator,
    handle_get_simulator_status,
    handle_reconnect_session
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
    app.router.add_delete('/api/sessions/{session_id}', handle_end_session)
    app.router.add_post('/api/sessions/{session_id}/reconnect', handle_reconnect_session)
    
    # Simulator routes
    app.router.add_post('/api/simulators', handle_start_simulator)
    app.router.add_delete('/api/simulators/{simulator_id}', handle_stop_simulator)
    app.router.add_get('/api/simulators/{simulator_id}', handle_get_simulator_status)
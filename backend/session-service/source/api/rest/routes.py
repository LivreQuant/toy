"""
REST API route setup.
Configures the simplified REST API routes for the session service.
"""
from source.api.rest.handlers import (
    handle_create_session,
    handle_end_session,
    handle_start_simulator, # Assuming GET /api/simulators maps here
    handle_stop_simulator # Assuming DELETE /api/simulators maps here
)
# Health/Readiness/Metrics routes are typically added in server.py

def setup_rest_routes(app):
    """
    Set up simplified REST API routes

    Args:
        app: The web application
    """
    # Session routes
    app.router.add_post('/api/sessions', handle_create_session, name='create_session')
    app.router.add_delete('/api/sessions', handle_end_session, name='end_session')

    # Simulator routes (Using GET for start, DELETE for stop as specified)
    app.router.add_get('/api/simulators', handle_start_simulator, name='start_simulator')
    app.router.add_delete('/api/simulators', handle_stop_simulator, name='stop_simulator')

    # Note: Health, Readiness, Metrics endpoints are usually added in server.py
    # Note: Debug routes like list_routes are removed for simplification.
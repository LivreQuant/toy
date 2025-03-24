def setup_routes(app):
    """Set up API routes"""
    app.router.add_post('/rest/session', handle_create_session)
    app.router.add_get('/rest/session/{session_id}', handle_get_session)
    app.router.add_delete('/rest/session/{session_id}', handle_end_session)
    app.router.add_post('/rest/session/{session_id}/keep-alive', handle_keep_alive)
    
    # Simulator routes
    app.router.add_post('/rest/simulator', handle_start_simulator)
    app.router.add_delete('/rest/simulator/{simulator_id}', handle_stop_simulator)
    app.router.add_get('/rest/simulator/{simulator_id}', handle_get_simulator_status)
    app.router.add_post('/rest/session/{session_id}/reconnect', handle_reconnect_session)
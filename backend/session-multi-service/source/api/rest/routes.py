# source/api/rest/routes.py
"""
REST API route setup.
Only essential endpoints remain, with session/simulator operations moved to WebSocket.
"""

def setup_rest_routes(app):
    """
    Set up REST API routes with proper HTTP methods.

    Args:
        app: The aiohttp web application instance.
    """
    # Keep only essential REST endpoints
    # Health check, metrics, etc. are handled by the main server.py
    pass
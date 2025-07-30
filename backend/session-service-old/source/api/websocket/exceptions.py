# websocket/exceptions.py
"""
Simplified custom exceptions for WebSocket operations.
"""


class WebSocketError(Exception):
    """Base class for WebSocket related errors."""

    def __init__(self, message: str, error_code: str = "ERROR", details: dict = None):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.details = details or {}


class ClientError(WebSocketError):
    """Error due to invalid client input or state."""

    def __init__(self, message: str, error_code: str = "CLIENT_ERROR", details: dict = None):
        super().__init__(message, error_code, details)


class ServerError(WebSocketError):
    """Internal server-side error."""

    def __init__(self, message: str = "Internal server error", error_code: str = "SERVER_ERROR", details: dict = None):
        super().__init__(message, error_code, details)

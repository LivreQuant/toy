# websocket/exceptions.py
"""
Custom exceptions for WebSocket operations.
"""

class WebSocketError(Exception):
    """Base class for WebSocket related errors."""
    def __init__(self, message: str, error_code: str = "UNKNOWN_ERROR", details: dict = None):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.details = details or {}


class WebSocketClientError(WebSocketError):
    """Error due to invalid client input or state."""
    def __init__(self, message: str, error_code: str = "CLIENT_ERROR", details: dict = None):
        super().__init__(message, error_code, details)


class WebSocketSessionError(WebSocketError):
    """Error related to session validation or state."""
    def __init__(self, message: str, error_code: str = "SESSION_ERROR", details: dict = None):
        super().__init__(message, error_code, details)


class WebSocketServerError(WebSocketError):
    """Internal server-side error."""
    def __init__(self, message: str = "Internal server error", error_code: str = "SERVER_ERROR", details: dict = None):
        # Default message hides internal details from client
        super().__init__(message, error_code, details)


# Specific examples
class InvalidMessageFormatError(WebSocketClientError):
    def __init__(self, message: str = "Invalid message format", details: dict = None):
        super().__init__(message, "INVALID_MESSAGE_FORMAT", details)


class AuthenticationError(WebSocketSessionError):
    def __init__(self, message: str = "Authentication failed", details: dict = None):
        super().__init__(message, "AUTH_FAILED", details)


class DeviceMismatchError(WebSocketSessionError):
    def __init__(self, message: str = "Device ID mismatch", expected: str = None, received: str = None):
        details = {'expected': expected, 'received': received}
        super().__init__(message, "DEVICE_MISMATCH", details)


class ConnectionLimitError(WebSocketSessionError):
    def __init__(self, message: str = "Connection limit reached", details: dict = None):
        super().__init__(message, "CONNECTION_LIMIT_REACHED", details)


class ConnectionReplacedError(WebSocketSessionError):
    def __init__(self, message: str = "Connection replaced by new device connection", details: dict = None):
        super().__init__(message, "CONNECTION_REPLACED", details)


class InvalidSessionStateError(WebSocketSessionError):
    def __init__(self, message: str = "Invalid session state for this operation", current_state: str = None, details: dict = None):
        if current_state and not details:
            details = {'current_state': current_state}
        super().__init__(message, "INVALID_SESSION_STATE", details)


class SimulatorError(WebSocketError):
    """Error related to simulator operations."""
    def __init__(self, message: str, error_code: str = "SIMULATOR_ERROR", details: dict = None):
        super().__init__(message, error_code, details)
        
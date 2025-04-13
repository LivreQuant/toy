# source/utils/errors.py

from enum import Enum
from typing import Dict, Any, Optional, Type


class ErrorCategory(str, Enum):
    """Categories for system errors"""
    AUTHENTICATION = "AUTHENTICATION"
    AUTHORIZATION = "AUTHORIZATION"
    VALIDATION = "VALIDATION"
    DATABASE = "DATABASE"
    EXTERNAL_SERVICE = "EXTERNAL_SERVICE"
    WEBSOCKET = "WEBSOCKET"
    NETWORK = "NETWORK"
    SYSTEM = "SYSTEM"
    SIMULATOR = "SIMULATOR"
    SESSION = "SESSION"
    UNKNOWN = "UNKNOWN"


class ServiceError(Exception):
    """Base class for all service errors"""

    def __init__(
            self,
            message: str,
            error_code: str,
            category: ErrorCategory = ErrorCategory.UNKNOWN,
            http_status: int = 500,
            details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.category = category
        self.http_status = http_status
        self.details = details or {}

    def to_dict(self) -> Dict[str, Any]:
        """Convert error to dictionary for JSON response"""
        return {
            'success': False,
            'error': self.message,
            'errorCode': self.error_code,
            'category': self.category,
            'details': self.details
        }


# Authentication Errors
class AuthenticationError(ServiceError):
    """Authentication errors"""

    def __init__(
            self,
            message: str = "Authentication failed",
            error_code: str = "AUTH_FAILED",
            details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message,
            error_code,
            category=ErrorCategory.AUTHENTICATION,
            http_status=401,
            details=details
        )


class ValidationError(ServiceError):
    """Input validation errors"""

    def __init__(
            self,
            message: str = "Validation failed",
            error_code: str = "VALIDATION_ERROR",
            details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message,
            error_code,
            category=ErrorCategory.VALIDATION,
            http_status=400,
            details=details
        )


class DatabaseError(ServiceError):
    """Database errors"""

    def __init__(
            self,
            message: str = "Database operation failed",
            error_code: str = "DATABASE_ERROR",
            details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message,
            error_code,
            category=ErrorCategory.DATABASE,
            http_status=500,
            details=details
        )


class SimulatorError(ServiceError):
    """Simulator-related errors"""

    def __init__(
            self,
            message: str = "Simulator operation failed",
            error_code: str = "SIMULATOR_ERROR",
            details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message,
            error_code,
            category=ErrorCategory.SIMULATOR,
            http_status=500,
            details=details
        )


class SessionError(ServiceError):
    """Session-related errors"""

    def __init__(
            self,
            message: str = "Session operation failed",
            error_code: str = "SESSION_ERROR",
            details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message,
            error_code,
            category=ErrorCategory.SESSION,
            http_status=400,
            details=details
        )


class WebSocketError(ServiceError):
    """WebSocket connection errors"""

    def __init__(
            self,
            message: str = "WebSocket error",
            error_code: str = "WEBSOCKET_ERROR",
            details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message,
            error_code,
            category=ErrorCategory.WEBSOCKET,
            http_status=400,
            details=details
        )


# Error handler functions
def handle_error(error: Exception) -> Dict[str, Any]:
    """Convert any exception to a standard error response format"""
    if isinstance(error, ServiceError):
        # Use the error's dict method
        return error.to_dict()

    # For standard exceptions, create a generic error
    return {
        'success': False,
        'error': str(error),
        'errorCode': 'INTERNAL_ERROR',
        'category': ErrorCategory.SYSTEM,
        'details': {}
    }


# Update the middleware to use the new error handler
def error_middleware(app):
    @web.middleware
    async def middleware(request, handler):
        try:
            return await handler(request)
        except Exception as e:
            error_dict = handle_error(e)
            status = e.http_status if isinstance(e, ServiceError) else 500
            return web.json_response(error_dict, status=status)

    return middleware
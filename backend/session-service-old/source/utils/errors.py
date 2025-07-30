# source/errors.py
from enum import Enum, auto
from dataclasses import dataclass


class ErrorCategory(Enum):
    """Simplified error categories"""
    AUTHENTICATION = auto()
    AUTHORIZATION = auto()
    VALIDATION = auto()
    INTERNAL = auto()
    EXTERNAL = auto()


@dataclass
class AppError(Exception):
    """Base application error with categorization"""
    message: str
    category: ErrorCategory = ErrorCategory.INTERNAL
    code: str = None
    details: dict = None

    def to_dict(self):
        """Convert error to standardized dictionary"""
        return {
            'message': self.message,
            'category': self.category.name,
            'code': self.code,
            'details': self.details or {}
        }


# Specific error types
class AuthenticationError(AppError):
    def __init__(self, message="Authentication failed"):
        super().__init__(
            message=message,
            category=ErrorCategory.AUTHENTICATION,
            code="AUTH_FAILED"
        )


class ValidationError(AppError):
    def __init__(self, message="Validation failed", details=None):
        super().__init__(
            message=message,
            category=ErrorCategory.VALIDATION,
            code="VALIDATION_ERROR",
            details=details
        )


# Global error handler
def handle_error(error: Exception):
    """Convert exceptions to standardized error response"""
    if isinstance(error, AppError):
        return error.to_dict()

    # Convert unknown errors
    return AppError(
        message=str(error),
        category=ErrorCategory.INTERNAL
    ).to_dict()

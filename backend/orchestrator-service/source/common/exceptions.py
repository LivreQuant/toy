# source/common/exceptions.py
"""Custom exceptions for the trading orchestrator system"""


class OrchestratorException(Exception):
    """Base exception for orchestrator errors"""
    pass


class ConfigurationError(OrchestratorException):
    """Raised when there are configuration issues"""
    pass


class DependencyError(OrchestratorException):
    """Raised when dependencies are not satisfied"""
    pass


class WorkflowError(OrchestratorException):
    """Raised when workflow execution fails"""
    pass


class DatabaseError(OrchestratorException):
    """Raised when database operations fail"""
    pass


class KubernetesError(OrchestratorException):
    """Raised when Kubernetes operations fail"""
    pass


class SODError(OrchestratorException):
    """Raised when Start of Day operations fail"""
    pass


class EODError(OrchestratorException):
    """Raised when End of Day operations fail"""
    pass

class NotificationError(OrchestratorException):
    """Raised when notifications fail to send"""
    pass


class ValidationError(OrchestratorException):
    """Raised when data validation fails"""
    pass


class ReferenceLDataError(OrchestratorException):
    """Raised when reference data operations fail"""
    pass


class CorporateActionError(OrchestratorException):
    """Raised when corporate action processing fails"""
    pass


class PortfolioReconciliationError(OrchestratorException):
    """Raised when portfolio reconciliation fails"""
    pass


class ReportingError(OrchestratorException):
    """Raised when report generation fails"""
    pass


class SecurityMasterError(OrchestratorException):
    """Raised when security master operations fail"""
    pass

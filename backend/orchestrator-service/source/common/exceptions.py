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

class RiskCalculationError(OrchestratorException):
    """Raised when risk calculations fail"""
    pass

class SettlementError(OrchestratorException):
    """Raised when trade settlement fails"""
    pass

class ArchivalError(OrchestratorException):
    """Raised when data archival fails"""
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

class UniverseBuilderError(OrchestratorException):
    """Raised when universe building fails"""
    pass

class CorporateActionError(OrchestratorException):
    """Raised when corporate action processing fails"""
    pass

class PositionReconciliationError(OrchestratorException):
    """Raised when position reconciliation fails"""
    pass

class CashReconciliationError(OrchestratorException):
    """Raised when cash reconciliation fails"""
    pass

class PerformanceAttributionError(OrchestratorException):
    """Raised when performance attribution fails"""
    pass

class FactorModelError(OrchestratorException):
    """Raised when factor model building fails"""
    pass

class PricingError(OrchestratorException):
    """Raised when pricing operations fail"""
    pass

class MarketDataError(OrchestratorException):
    """Raised when market data operations fail"""
    pass

class ReportingError(OrchestratorException):
    """Raised when report generation fails"""
    pass

class SecurityMasterError(OrchestratorException):
    """Raised when security master operations fail"""
    pass
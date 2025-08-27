# source/common/exceptions.py


class OrchestratorException(Exception):
    """Base orchestrator exception"""
    pass


class WorkflowException(OrchestratorException):
    """Workflow execution failed"""
    pass


class DatabaseException(OrchestratorException):
    """Database operation failed"""
    pass


class KubernetesException(OrchestratorException):
    """Kubernetes operation failed"""
    pass


class SchedulerException(OrchestratorException):
    """Scheduler operation failed"""
    pass


class ConfigurationException(OrchestratorException):
    """Configuration error"""
    pass


class ValidationException(OrchestratorException):
    """Data validation failed"""
    pass
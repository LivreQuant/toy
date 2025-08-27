# source/common/dependencies.py
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class DependencyContainer:
    """Simple dependency container - no fancy DI framework bullshit"""

    def __init__(self):
        self._services: Dict[str, Any] = {}

    def register(self, name: str, service: Any):
        """Register a service"""
        self._services[name] = service
        logger.info(f"📦 Registered service: {name}")

    def get(self, name: str) -> Optional[Any]:
        """Get a service"""
        return self._services.get(name)

    def get_required(self, name: str) -> Any:
        """Get a required service - throws if not found"""
        service = self._services.get(name)
        if service is None:
            raise ValueError(f"Required service '{name}' not found")
        return service


# Global container instance
container = DependencyContainer()


def get_service(name: str) -> Optional[Any]:
    """Get service from global container"""
    return container.get(name)


def register_service(name: str, service: Any):
    """Register service in global container"""
    container.register(name, service)
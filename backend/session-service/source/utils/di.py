# source/di.py
from dataclasses import dataclass
from typing import Dict, Any, Callable


@dataclass
class ServiceContainer:
    """Lightweight dependency injection container"""
    _services: Dict[str, Any] = None
    _factories: Dict[str, Callable] = None

    def __post_init__(self):
        self._services = {}
        self._factories = {}

    def register(self, name: str, service: Any = None, factory: Callable = None):
        """
        Register a service or a factory for creating services

        Args:
            name: Service identifier
            service: Existing service instance
            factory: Function to create service on-demand
        """
        if service is not None:
            self._services[name] = service
        if factory is not None:
            self._factories[name] = factory

    def get(self, name: str) -> Any:
        """
        Retrieve or create a service

        Args:
            name: Service identifier

        Returns:
            Service instance
        """
        if name in self._services:
            return self._services[name]

        if name in self._factories:
            service = self._factories[name]()
            self._services[name] = service
            return service

        raise KeyError(f"Service {name} not found")


# Example usage
def create_service_container() -> ServiceContainer:
    container = ServiceContainer()

    # Register services
    container.register('session_service', factory=lambda: SessionService())
    container.register('websocket_manager', factory=lambda: WebSocketManager(
        container.get('session_service'),
        container.get('simulator_service')
    ))

    return container

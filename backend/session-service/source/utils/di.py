# source/utils/di.py
"""
Simple dependency injection container for managing service dependencies.
"""
import logging
from typing import Dict, Any, TypeVar, Callable

logger = logging.getLogger("dependency_injection")

T = TypeVar('T')


class DependencyContainer:
    """A simple dependency injection container that resolves dependencies for components."""

    def __init__(self):
        """Initialize the container."""
        self._factories: Dict[str, Callable[..., Any]] = {}
        self._instances: Dict[str, Any] = {}
        self._dependencies: Dict[str, list] = {}

    def register(self, name: str, factory: Callable[..., Any], dependencies: list = None):
        """
        Register a component factory with its dependencies.
        
        Args:
            name: The component name to register
            factory: Factory function to create the component
            dependencies: List of dependency names this component needs
        """
        self._factories[name] = factory
        self._dependencies[name] = dependencies or []
        logger.debug(f"Registered component: {name} with dependencies: {dependencies}")

    def register_instance(self, name: str, instance: Any):
        """
        Register an already instantiated component.
        
        Args:
            name: The component name
            instance: The component instance
        """
        self._instances[name] = instance
        logger.debug(f"Registered instance: {name}")

    def get(self, name: str) -> Any:
        """
        Get a component by name, instantiating it and its dependencies if needed.
        
        Args:
            name: The component name to retrieve
            
        Returns:
            The component instance
            
        Raises:
            KeyError: If the component is not registered
            ValueError: If there's a circular dependency
        """
        # Return existing instance if available
        if name in self._instances:
            return self._instances[name]

        # Check if component is registered
        if name not in self._factories:
            raise KeyError(f"Component '{name}' not registered")

        # Detect circular dependencies with a simple visited set
        return self._resolve_dependencies(name, set())

    def _resolve_dependencies(self, name: str, resolution_path: set) -> Any:
        """
        Recursively resolve dependencies.
        
        Args:
            name: Component to resolve
            resolution_path: Set of components being resolved (for cycle detection)
            
        Returns:
            The component instance
        """
        # Check for circular dependencies
        if name in resolution_path:
            path = " -> ".join(resolution_path) + f" -> {name}"
            raise ValueError(f"Circular dependency detected: {path}")

        # Add to resolution path
        resolution_path.add(name)

        # Get dependencies
        dependency_instances = {}
        for dep_name in self._dependencies.get(name, []):
            # Resolve dependency recursively if not already instantiated
            if dep_name not in self._instances:
                self._instances[dep_name] = self._resolve_dependencies(dep_name, resolution_path.copy())

            # Add to dependency dict
            dependency_instances[dep_name] = self._instances[dep_name]

        # Create instance
        factory = self._factories[name]
        instance = factory(**dependency_instances)
        self._instances[name] = instance

        logger.debug(f"Instantiated component: {name}")
        return instance

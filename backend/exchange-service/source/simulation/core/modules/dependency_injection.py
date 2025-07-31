from typing import Dict, Any
from source.simulation.core.interfaces.exchange import Exchange_ABC


class DependencyContainer:
    def __init__(self):
        self._bindings: Dict[type, Any] = {}

    def bind(self, interface: type, instance: Any):
        self._bindings[interface] = instance

    def get(self, interface: type) -> Any:
        return self._bindings.get(interface)


class ExchangeSimulatorModule:
    def __init__(self, exchange: Exchange_ABC):
        self.exchange = exchange
        self.container = DependencyContainer()

    def configure(self):
        self.container.bind(Exchange_ABC, self.exchange)

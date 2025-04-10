"""
Simulator manager for handling exchange simulator lifecycle.
Coordinates the creation, monitoring, and termination of simulator instances.
"""
import logging
from typing import List, Dict, Any, Optional, Tuple
from opentelemetry import trace

from source.models.simulator import Simulator
from source.db.session_store import DatabaseManager
from source.api.clients.exchange_client import ExchangeClient
from source.utils.k8s_client import KubernetesClient
from source.config import config

from source.core.simulator.simulator_creator import SimulatorCreator
from source.core.simulator.simulator_operations import SimulatorLifecycle
from source.core.simulator.cleanup_tasks import CleanupOperations

logger = logging.getLogger('simulator_manager')


class SimulatorManager:
    """Manager for exchange simulator instances"""

    def __init__(
            self,
            db_manager: DatabaseManager,
            exchange_client: ExchangeClient
    ):
        """
        Initialize simulator manager
        
        Args:
            db_manager: Database manager for simulator persistence
            exchange_client: Exchange client for gRPC communication
        """
        self.db_manager = db_manager
        self.exchange_client = exchange_client
        self.k8s_client = KubernetesClient()
        self.max_simulators_per_user = config.simulator.max_per_user
        self.inactivity_timeout = config.simulator.inactivity_timeout

        # Initialize component modules
        self.creator = SimulatorCreator(self)
        self.lifecycle = SimulatorLifecycle(self)
        self.cleanup = CleanupOperations(self)

        self.tracer = trace.get_tracer("simulator_manager")

    async def create_simulator(
            self,
            session_id: str,
            user_id: str,
    ) -> Tuple[Optional[Simulator], str]:
        """Delegate to simulator creator component"""
        return await self.creator.create_simulator(
            session_id, user_id)

    async def stop_simulator(self, simulator_id: str) -> Tuple[bool, str]:
        """Delegate to simulator lifecycle component"""
        return await self.lifecycle.stop_simulator(simulator_id)

    async def check_simulator_ready(self, simulator_id: str) -> bool:
        """Delegate to simulator lifecycle component"""
        return await self.lifecycle.check_simulator_ready(simulator_id)

    async def get_simulator_status(self, simulator_id: str) -> Dict[str, Any]:
        """Delegate to simulator lifecycle component"""
        return await self.lifecycle.get_simulator_status(simulator_id)

    async def get_active_user_simulators(self, user_id: str) -> List[Simulator]:
        """Delegate to simulator lifecycle component"""
        return await self.lifecycle.get_active_user_simulators(user_id)

    async def get_all_simulators(self):
        """Delegate to simulator lifecycle component"""
        return await self.lifecycle.get_all_simulators()

    async def cleanup_inactive_simulators(self):
        """Delegate to cleanup operations component"""
        return await self.cleanup.cleanup_inactive_simulators()

"""
Simulator manager for handling exchange simulator lifecycle.
Coordinates the creation, monitoring, and termination of simulator instances.
"""
import logging
from typing import List, Dict, Any, Optional, Tuple
from opentelemetry import trace

from source.utils.tracing import optional_trace_span
from source.models.simulator import Simulator, SimulatorStatus

from source.db.stores.postgres.postgres_simulator_store import PostgresSimulatorStore
from source.db.stores.redis.redis_pubsub import RedisPubSub

from source.core.simulator.lifecycle import SimulatorLifecycle
from source.core.simulator.operations import SimulatorOperations
from source.core.simulator.tasks import SimulatorTasks

logger = logging.getLogger('simulator_manager')


class SimulatorManager:
    """Manager for exchange simulator instances"""

    def __init__(
        self,
        postgres_store: PostgresSimulatorStore,
        redis_pubsub: RedisPubSub
    ):
        """
        Initialize simulator manager
        
        Args:
            exchange_client: Exchange client for gRPC communication
        """
        self.postgres_store = postgres_store
        self.redis_pubsub = redis_pubsub

        self.lifecycle = SimulatorLifecycle(self)
        self.operations = SimulatorOperations(self)
        self.tasks = SimulatorTasks(self)

        self.tracer = trace.get_tracer("simulator_manager")

    async def create_simulator(self, session_id: str, user_id: str,) -> Tuple[Optional[Simulator], str]:
        """Delegate to simulator creator component"""
        return await self.creator.create_simulator(session_id, user_id)

    async def delete_simulator(self, simulator_id: str) -> Tuple[bool, str]:
        """Delegate to simulator lifecycle component"""
        return await self.creator.delete_simulator(simulator_id)

    async def cleanup_inactive_simulators(self):
        """Delegate to cleanup operations component"""
        return await self.creator.cleanup_inactive_simulators()

    # --- Methods primarily passing through to PostgreSQL Store ---

    async def update_simulator_endpoint(self, simulator_id: str, endpoint: str) -> bool:
        """Update simulator endpoint in PostgreSQL."""
        return await self.postgres_store.update_simulator_endpoint(simulator_id, endpoint)

    async def update_simulator_activity(self, simulator_id: str) -> bool:
        """Update simulator last active time in PostgreSQL."""
        return await self.postgres_store.update_simulator_activity(simulator_id)

    async def get_simulator(self, simulator_id: str) -> Optional[Simulator]:
        """Get simulator by ID from PostgreSQL."""
        return await self.postgres_store.get_simulator(simulator_id)

    async def get_simulator_by_session(self, session_id: str) -> Optional[Simulator]:
        """Get simulator for a session from PostgreSQL."""
        return await self.postgres_store.get_simulator_by_session(session_id)

    async def get_active_user_simulators(self, user_id: str) -> List[Simulator]:
        """Get active simulators (status RUNNING) for a user from PostgreSQL."""
        return await self.postgres_store.get_active_user_simulators(user_id)

    async def get_all_simulators(self) -> List[Simulator]:
        """Get all simulators from PostgreSQL."""
        return await self.postgres_store.get_all_simulators()

    async def get_active_simulator_count(self) -> int:
        """Get count of active (not STOPPED or ERROR) simulators from PostgreSQL."""
        return await self.postgres_store.get_active_simulator_count()

    async def update_simulator_last_active(self, simulator_id: str, timestamp: float) -> bool:
        """Directly update simulator last active time in PostgreSQL."""
        return await self.postgres_store.update_simulator_last_active(simulator_id, timestamp)

    async def get_simulators_with_status(self, status: SimulatorStatus) -> List[Simulator]:
        """Get simulators with a specific status from PostgreSQL."""
        return await self.postgres_store.get_simulators_with_status(status)

    async def check_simulator_ready(self, simulator_id: str) -> bool:
        """Delegate to simulator lifecycle component"""
        return await self.lifecycle.check_simulator_ready(simulator_id)

    async def get_simulator_status(self, simulator_id: str) -> Dict[str, Any]:
        """Delegate to simulator lifecycle component"""
        return await self.lifecycle.get_simulator_status(simulator_id)


import asyncio
import logging
import time
from typing import List, Optional

from source.models.simulator import Simulator
from source.db.session_store import DatabaseManager

logger = logging.getLogger('simulator_manager')

class SimulatorManager:
    def __init__(
        self, 
        db_manager: DatabaseManager,
        max_simulators_per_user: int = 2,
        simulator_timeout: int = 3600  # 1 hour of inactivity
    ):
        self.db_manager = db_manager
        self.max_simulators_per_user = max_simulators_per_user
        self.simulator_timeout = simulator_timeout
    
    async def create_simulator(
        self, 
        session_id: str, 
        user_id: str, 
        initial_symbols: Optional[List[str]] = None, 
        initial_cash: float = 100000.0
    ) -> Simulator:
        """Create a simulator for a specific session"""
        # Check existing simulators for this user
        existing_simulators = await self.get_user_active_simulators(user_id)
        
        if len(existing_simulators) >= self.max_simulators_per_user:
            raise ValueError(f"Maximum simulator limit ({self.max_simulators_per_user}) reached")
        
        # Create simulator
        simulator = Simulator(
            session_id=session_id,
            user_id=user_id,
            initial_symbols=initial_symbols or [],
            initial_cash=initial_cash
        )
        
        # Store in database
        await self.db_manager.create_simulator(simulator.to_dict())
        
        return simulator
    
    def _create_simulator_deployment(self, simulator):
        # Use Kubernetes Python client to dynamically create deployment
        deployment = client.V1Deployment(
            metadata=client.V1ObjectMeta(
                name=f"simulator-{simulator.simulator_id}",
                labels={
                    "app": "exchange-simulator",
                    "simulator_id": simulator.simulator_id,
                    "session_id": simulator.session_id,
                    "user_id": simulator.user_id
                }
            ),
            spec=client.V1DeploymentSpec(
                replicas=1,
                selector={"matchLabels": {"simulator_id": simulator.simulator_id}},
                template=client.V1PodTemplateSpec(
                    metadata=client.V1ObjectMeta(
                        labels={
                            "app": "exchange-simulator",
                            "simulator_id": simulator.simulator_id,
                            "session_id": simulator.session_id,
                            "user_id": simulator.user_id
                        }
                    ),
                    spec=client.V1PodSpec(
                        containers=[
                            client.V1Container(
                                name="exchange-simulator",
                                image="opentp/exchange-simulator:latest",
                                ports=[client.V1ContainerPort(container_port=50055)]
                            )
                        ]
                    )
                )
            )
        )
        
        # Create deployment
        apps_v1 = client.AppsV1Api()
        apps_v1.create_namespaced_deployment(namespace="default", body=deployment)
        
    async def get_user_active_simulators(self, user_id: str) -> List[Simulator]:
        """Retrieve active simulators for a user"""
        # Fetch active simulators from database
        simulator_dicts = await self.db_manager.get_active_user_simulators(user_id)
        return [Simulator(**sim_dict) for sim_dict in simulator_dicts]
    
    async def cleanup_inactive_simulators(self):
        """Clean up simulators that have been inactive beyond the timeout"""
        current_time = time.time()
        
        # Fetch all active simulators
        active_simulators = await self.db_manager.get_all_active_simulators()
        
        for simulator_dict in active_simulators:
            # Check if simulator is past inactivity timeout
            if current_time - simulator_dict['last_active'] > self.simulator_timeout:
                # Mark as inactive in database
                await self.db_manager.update_simulator_status(
                    simulator_dict['simulator_id'], 
                    status='INACTIVE'
                )
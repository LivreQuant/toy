"""
Simulator manager for handling exchange simulator lifecycle.
Manages the creation, monitoring, and termination of simulator instances.
"""
import logging
import time
import asyncio
from typing import List, Dict, Any, Optional, Tuple

from source.models.simulator import Simulator, SimulatorStatus
from source.db.session_store import DatabaseManager
from source.api.clients.exchange_client import ExchangeClient
from source.utils.k8s_client import KubernetesClient
from source.config import config

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
    
    async def create_simulator(
        self, 
        session_id: str, 
        user_id: str, 
        initial_symbols: Optional[List[str]] = None, 
        initial_cash: float = 100000.0
    ) -> Tuple[Optional[Simulator], str]:
        """
        Create a new simulator instance
        
        Args:
            session_id: The session ID
            user_id: The user ID
            initial_symbols: Initial symbols to track
            initial_cash: Initial cash amount
            
        Returns:
            Tuple of (simulator, error_message)
        """
        # Check user simulator limits
        existing_simulators = await self.db_manager.get_active_user_simulators(user_id)
        
        if len(existing_simulators) >= self.max_simulators_per_user:
            return None, f"Maximum simulator limit ({self.max_simulators_per_user}) reached"
        
        # Check if there's an existing simulator for this session
        existing_simulator = await self.db_manager.get_simulator_by_session(session_id)
        if existing_simulator and existing_simulator.status != SimulatorStatus.STOPPED:
            logger.info(f"Returning existing simulator for session {session_id}")
            return existing_simulator, ""
        
        # Create new simulator
        simulator = Simulator(
            session_id=session_id,
            user_id=user_id,
            status=SimulatorStatus.CREATING,
            initial_symbols=initial_symbols or [],
            initial_cash=initial_cash
        )
        
        try:
            # Save to database
            await self.db_manager.create_simulator(simulator)
            
            # Create Kubernetes deployment
            endpoint = await self.k8s_client.create_simulator_deployment(
                simulator.simulator_id,
                session_id,
                user_id,
                initial_symbols,
                initial_cash
            )
            
            # Update simulator with endpoint
            simulator.endpoint = endpoint
            simulator.status = SimulatorStatus.STARTING
            await self.db_manager.update_simulator_endpoint(simulator.simulator_id, endpoint)
            await self.db_manager.update_simulator_status(simulator.simulator_id, SimulatorStatus.STARTING)
            
            # Start the simulator via the exchange manager
            exchange_manager_endpoint = config.services.exchange_manager_service
            result = await self.exchange_client.start_simulator(
                exchange_manager_endpoint,
                session_id,
                user_id,
                initial_symbols,
                initial_cash
            )
            
            if not result.get('success'):
                logger.error(f"Failed to start simulator: {result.get('error')}")
                simulator.status = SimulatorStatus.ERROR
                await self.db_manager.update_simulator_status(simulator.simulator_id, SimulatorStatus.ERROR)
                
                # Clean up Kubernetes resources
                await self.k8s_client.delete_simulator_deployment(simulator.simulator_id)
                
                return None, result.get('error') or "Failed to start simulator"
            
            # Update simulator status
            simulator.status = SimulatorStatus.RUNNING
            await self.db_manager.update_simulator_status(simulator.simulator_id, SimulatorStatus.RUNNING)
            
            logger.info(f"Created simulator {simulator.simulator_id} for session {session_id}")
            return simulator, ""
            
        except Exception as e:
            logger.error(f"Error creating simulator: {e}")
            
            # Update simulator status
            if simulator:
                simulator.status = SimulatorStatus.ERROR
                await self.db_manager.update_simulator_status(simulator.simulator_id, SimulatorStatus.ERROR)
                
                # Clean up Kubernetes resources if needed
                if hasattr(simulator, 'endpoint') and simulator.endpoint:
                    await self.k8s_client.delete_simulator_deployment(simulator.simulator_id)
            
            return None, str(e)
    
    async def stop_simulator(self, simulator_id: str) -> Tuple[bool, str]:
        """
        Stop a simulator
        
        Args:
            simulator_id: ID of the simulator to stop
            
        Returns:
            Tuple of (success, error_message)
        """
        # Get simulator details
        simulator = await self.db_manager.get_simulator(simulator_id)
        
        if not simulator:
            return False, "Simulator not found"
        
        try:
            # Update status
            simulator.status = SimulatorStatus.STOPPING
            await self.db_manager.update_simulator_status(simulator.simulator_id, SimulatorStatus.STOPPING)
            
            # Stop the simulator
            result = await self.exchange_client.stop_simulator(
                simulator.endpoint,
                simulator.session_id
            )
            
            if not result.get('success'):
                logger.warning(f"Failed to stop simulator via gRPC: {result.get('error')}")
                # Continue with cleanup anyway
            
            # Delete Kubernetes resources
            await self.k8s_client.delete_simulator_deployment(simulator.simulator_id)
            
            # Update status
            simulator.status = SimulatorStatus.STOPPED
            await self.db_manager.update_simulator_status(simulator.simulator_id, SimulatorStatus.STOPPED)
            
            logger.info(f"Stopped simulator {simulator_id}")
            return True, ""
            
        except Exception as e:
            logger.error(f"Error stopping simulator: {e}")
            return False, str(e)
    
    async def get_simulator_status(self, simulator_id: str) -> Dict[str, Any]:
        """
        Get the status of a simulator
        
        Args:
            simulator_id: ID of the simulator
            
        Returns:
            Dict with simulator status info
        """
        simulator = await self.db_manager.get_simulator(simulator_id)
        
        if not simulator:
            return {'status': 'NOT_FOUND'}
        
        # Get Kubernetes status
        k8s_status = await self.k8s_client.check_simulator_status(simulator_id)
        
        # If Kubernetes status doesn't match our DB status, update it
        if k8s_status == "RUNNING" and simulator.status != SimulatorStatus.RUNNING:
            simulator.status = SimulatorStatus.RUNNING
            await self.db_manager.update_simulator_status(simulator_id, SimulatorStatus.RUNNING)
        elif k8s_status in ["FAILED", "NOT_FOUND"] and simulator.status not in [
            SimulatorStatus.ERROR, SimulatorStatus.STOPPED
        ]:
            simulator.status = SimulatorStatus.ERROR
            await self.db_manager.update_simulator_status(simulator_id, SimulatorStatus.ERROR)
        
        return {
            'simulator_id': simulator.simulator_id,
            'session_id': simulator.session_id,
            'status': simulator.status.value,
            'endpoint': simulator.endpoint,
            'created_at': simulator.created_at,
            'last_active': simulator.last_active,
            'k8s_status': k8s_status
        }
    
    async def cleanup_inactive_simulators(self):
        """Clean up simulators that have been inactive beyond the timeout"""
        # Get inactive simulators from database
        count = await self.db_manager.cleanup_inactive_simulators(self.inactivity_timeout)
        
        if count > 0:
            logger.info(f"Marked {count} inactive simulators as STOPPED")
            
            # Get all active simulators
            active_simulators = await self.db_manager.get_all_active_simulators()
            
            # Filter for those that exceeded timeout
            current_time = time.time()
            inactive_ids = [
                sim['simulator_id'] for sim in active_simulators
                if current_time - sim['last_active'] > self.inactivity_timeout
                and sim['status'] != SimulatorStatus.STOPPED.value
            ]
            
            # Clean up Kubernetes resources for each
            for simulator_id in inactive_ids:
                try:
                    # Just clean Kubernetes resources, DB already updated
                    await self.k8s_client.delete_simulator_deployment(simulator_id)
                    logger.info(f"Deleted Kubernetes resources for inactive simulator {simulator_id}")
                except Exception as e:
                    logger.error(f"Error cleaning up simulator {simulator_id}: {e}")
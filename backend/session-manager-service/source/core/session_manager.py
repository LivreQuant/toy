import asyncio
import logging
import time
import uuid
from typing import Dict, Any, Optional, Tuple

from source.core.simulator_manager import SimulatorManager
from source.api.auth_client import AuthClient
from source.db.session_store import DatabaseManager

logger = logging.getLogger('session_manager')

class SessionManager:
    def __init__(
        self, 
        db_manager: DatabaseManager, 
        auth_client: AuthClient,
    ):
        self.db_manager = db_manager
        self.auth_client = auth_client
        
        # Integrated Simulator Manager
        self.simulator_manager = SimulatorManager(db_manager)
    
    
    async def create_simulator(
        self, 
        session_id: str, 
        user_id: str, 
        initial_symbols: Optional[List[str]] = None, 
        initial_cash: float = 100000.0
    ) -> Simulator:
        """
        Create a simulator for a specific session
        
        Workflow:
        1. Check user's existing simulators
        2. Validate simulator creation limits
        3. Generate unique simulator ID
        4. Create simulator record in database
        5. Trigger simulator pod creation (TODO: Implement K8s integration)
        """
        # Check existing simulators for this user
        existing_simulators = await self._get_user_active_simulators(user_id)
        
        # Validate simulator creation limits
        if len(existing_simulators) >= self.max_simulators_per_user:
            raise ValueError(f"Maximum simulator limit ({self.max_simulators_per_user}) reached")
        
        # Generate unique simulator ID
        simulator_id = str(uuid.uuid4())
        
        # Create simulator record
        simulator = Simulator(
            simulator_id=simulator_id,
            session_id=session_id,
            user_id=user_id,
            initial_symbols=initial_symbols or [],
            initial_cash=initial_cash
        )
        
        try:
            # Store simulator in database
            await self.db_manager.create_simulator(simulator.to_dict())
            
            # TODO: Implement K8s pod creation logic
            # This would involve:
            # 1. Creating a unique Kubernetes deployment
            # 2. Setting environment variables
            # 3. Launching the simulator pod
            await self._create_simulator_pod(simulator)
            
            return simulator
        
        except Exception as e:
            logger.error(f"Failed to create simulator: {e}")
            raise
    
    async def _create_simulator_pod(self, simulator: Simulator):
        """
        Placeholder for Kubernetes pod creation
        
        In a real implementation, this would:
        1. Use Kubernetes API to create a deployment
        2. Set unique identifiers
        3. Configure pod resources
        4. Handle pod creation errors
        """
        # Simulate pod creation logging
        logger.info(f"Creating simulator pod for {simulator.simulator_id}")
        # Actual K8s integration would go here
    
    async def _get_user_active_simulators(self, user_id: str) -> List[Simulator]:
        """Retrieve active simulators for a user"""
        # Fetch active simulators from database
        simulator_dicts = await self.db_manager.get_active_user_simulators(user_id)
        return [Simulator(**sim_dict) for sim_dict in simulator_dicts]
    
    async def cleanup_inactive_simulators(self):
        """
        Clean up simulators that have been inactive beyond the timeout
        
        Workflow:
        1. Fetch all active simulators
        2. Check each simulator's last activity
        3. Mark inactive simulators
        4. Terminate corresponding K8s pods
        """
        current_time = time.time()
        
        # Fetch all active simulators
        active_simulators = await self.db_manager.get_all_active_simulators()
        
        for simulator_dict in active_simulators:
            # Check if simulator is past inactivity timeout
            if current_time - simulator_dict['last_active'] > self.simulator_timeout:
                simulator_id = simulator_dict['simulator_id']
                
                # Mark as inactive in database
                await self.db_manager.update_simulator_status(
                    simulator_id, 
                    status='INACTIVE'
                )
                
                # TODO: Implement K8s pod termination
                await self._terminate_simulator_pod(simulator_id)
    
    async def _terminate_simulator_pod(self, simulator_id: str):
        """
        Placeholder for Kubernetes pod termination
        
        In a real implementation, this would:
        1. Use Kubernetes API to delete the deployment
        2. Remove associated services
        3. Handle termination errors
        """
        logger.info(f"Terminating simulator pod {simulator_id}")
        # Actual K8s termination logic would go here
    
    async def update_simulator_activity(self, simulator_id: str):
        """
        Update last activity timestamp for a simulator
        
        Workflow:
        1. Update database record
        2. Potentially update K8s pod metadata
        """
        current_time = time.time()
        
        # Update in database
        await self.db_manager.update_simulator_last_active(
            simulator_id, 
            current_time
        )
        
        # TODO: Potential K8s pod metadata update
        logger.info(f"Updated activity for simulator {simulator_id}")
        
    async def validate_session(self, session_id: str, token: str) -> Optional[str]:
        """
        Validate an existing session
        
        Args:
            session_id: Session to validate
            token: Authentication token
        
        Returns:
            User ID if session is valid, None otherwise
        """
        # Validate token with auth service
        validate_result = await self.auth_client.validate_token(token)
        if not validate_result.get('valid', False):
            logger.warning(f"Invalid authentication token for session {session_id}")
            return None
        
        # Get user ID from token validation
        user_id = validate_result.get('user_id')
        
        # Verify session exists and belongs to user
        session = await self.db_manager.get_session(session_id)
        if not session or str(session['user_id']) != str(user_id):
            logger.warning(f"Session {session_id} does not exist or does not belong to user {user_id}")
            return None
        
        # Update session activity
        await self.db_manager.update_session_activity(session_id)
        
        return user_id
    
    async def start_simulator(self, session_id: str, token: str) -> Tuple[Optional[str], Optional[str], str]:
        """
        Start a trading simulator for a session
        
        Args:
            session_id: Active session ID
            token: Authentication token
        
        Returns:
            Tuple of (simulator_id, simulator_endpoint, error_message)
        """
        # Validate session
        user_id = await self.validate_session(session_id, token)
        if not user_id:
            return None, None, "Invalid session or token"
        
        try:
            # Create simulator through integrated SimulatorManager
            simulator = await self.simulator_manager.create_simulator(
                session_id, 
                user_id
            )
            
            # Update session metadata with simulator info
            await self.db_manager.update_session_metadata(session_id, {
                'simulator_id': simulator.simulator_id,
                'simulator_status': 'ACTIVE'
            })
            
            # Endpoint format for internal K8s service discovery
            endpoint = f'simulator-{simulator.simulator_id}.exchangesvc.default.svc.cluster.local:50055'
            
            logger.info(f"Started simulator {simulator.simulator_id} for session {session_id}")
            
            return simulator.simulator_id, endpoint, ""
        
        except ValueError as e:
            logger.warning(f"Failed to start simulator for session {session_id}: {e}")
            return None, None, str(e)
    
    async def stop_simulator(self, session_id: str, token: str) -> Tuple[bool, str]:
        """
        Stop the active simulator for a session
        
        Args:
            session_id: Active session ID
            token: Authentication token
        
        Returns:
            Tuple of (success, error_message)
        """
        # Validate session
        user_id = await self.validate_session(session_id, token)
        if not user_id:
            return False, "Invalid session or token"
        
        # Get current session metadata
        session = await self.db_manager.get_session(session_id)
        simulator_id = session.get('simulator_id')
        
        if not simulator_id:
            return False, "No active simulator for this session"
        
        try:
            # Mark simulator as inactive in database
            await self.db_manager.update_simulator_status(
                simulator_id, 
                status='INACTIVE'
            )
            
            # Clear simulator metadata from session
            await self.db_manager.update_session_metadata(session_id, {
                'simulator_id': None,
                'simulator_status': 'STOPPED'
            })
            
            logger.info(f"Stopped simulator {simulator_id} for session {session_id}")
            return True, ""
        
        except Exception as e:
            logger.error(f"Error stopping simulator {simulator_id}: {e}")
            return False, str(e)
    
    async def periodic_simulator_cleanup(self):
        """Background task for cleaning up inactive simulators"""
        while True:
            try:
                await self.simulator_manager.cleanup_inactive_simulators()
                await asyncio.sleep(3600)  # Run every hour
            except Exception as e:
                logger.error(f"Simulator cleanup failed: {e}")
                await asyncio.sleep(600)  # Wait 10 minutes on error
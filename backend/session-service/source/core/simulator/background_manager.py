"""
Background simulator management that doesn't block session operations.
Handles all simulator lifecycle operations asynchronously.
"""
import asyncio
import logging
import time
from typing import Dict, Optional, Callable
from enum import Enum

from source.models.simulator import SimulatorStatus

logger = logging.getLogger('background_simulator_manager')


class SimulatorTaskType(str, Enum):
    """Types of simulator management tasks"""
    CHECK_EXISTING = "check_existing"
    VALIDATE_HEALTH = "validate_health"
    CREATE_NEW = "create_new"
    CLEANUP = "cleanup"


class SimulatorTask:
    """Represents a simulator management task"""
    def __init__(self, task_type: SimulatorTaskType, session_id: str, user_id: str, 
                 callback: Optional[Callable] = None, priority: int = 1):
        self.task_type = task_type
        self.session_id = session_id
        self.user_id = user_id
        self.callback = callback
        self.priority = priority
        self.created_at = time.time()
        self.task_id = f"{task_type}_{session_id}_{int(self.created_at)}"


class BackgroundSimulatorManager:
    """
    Manages simulator operations in the background without blocking session service.
    Uses a priority queue and worker tasks to handle simulator lifecycle.
    """
    
    def __init__(self, simulator_manager, websocket_manager):
        self.simulator_manager = simulator_manager
        self.websocket_manager = websocket_manager
        
        # Task queue and worker management
        self.task_queue = asyncio.PriorityQueue()
        self.workers = []
        self.running = False
        self.worker_count = 2  # Number of background workers
        
        # Track active tasks to avoid duplicates
        self.active_tasks: Dict[str, SimulatorTask] = {}
        
        # Status tracking for sessions
        self.session_status: Dict[str, str] = {}
        
    async def start(self):
        """Start the background simulator management workers"""
        if self.running:
            return
            
        self.running = True
        
        # Start worker tasks
        for i in range(self.worker_count):
            worker = asyncio.create_task(self._worker(f"simulator-worker-{i}"))
            worker.set_name(f"simulator-worker-{i}")
            self.workers.append(worker)
            
        logger.info(f"Started {self.worker_count} background simulator management workers")
        
    async def stop(self):
        """Stop all background workers"""
        if not self.running:
            return
            
        self.running = False
        
        # Cancel all workers
        for worker in self.workers:
            worker.cancel()
            
        # Wait for workers to finish
        await asyncio.gather(*self.workers, return_exceptions=True)
        self.workers.clear()
        
        logger.info("Stopped background simulator management workers")
        
    def queue_simulator_check(self, session_id: str, user_id: str, 
                            callback: Optional[Callable] = None) -> str:
        """
        Queue a task to check for existing simulators for a session.
        Returns immediately without blocking.
        
        Returns:
            task_id for tracking
        """
        task = SimulatorTask(
            SimulatorTaskType.CHECK_EXISTING,
            session_id,
            user_id,
            callback,
            priority=1  # High priority
        )
        
        # Avoid duplicate tasks
        task_key = f"{task.task_type}_{session_id}"
        if task_key in self.active_tasks:
            logger.debug(f"Task {task_key} already active, skipping duplicate")
            return self.active_tasks[task_key].task_id
            
        self.active_tasks[task_key] = task
        self.session_status[session_id] = "CHECKING"
        
        # Queue the task (priority queue uses tuple: (priority, task))
        self.task_queue.put_nowait((task.priority, task))
        
        logger.info(f"Queued simulator check task for session {session_id}")
        return task.task_id
        
    def queue_simulator_creation(self, session_id: str, user_id: str,
                               callback: Optional[Callable] = None) -> str:
        """Queue a task to create a new simulator"""
        task = SimulatorTask(
            SimulatorTaskType.CREATE_NEW,
            session_id,
            user_id,
            callback,
            priority=2  # Medium priority
        )
        
        task_key = f"{task.task_type}_{session_id}"
        if task_key in self.active_tasks:
            return self.active_tasks[task_key].task_id
            
        self.active_tasks[task_key] = task
        self.session_status[session_id] = "CREATING"
        
        self.task_queue.put_nowait((task.priority, task))
        
        logger.info(f"Queued simulator creation task for session {session_id}")
        return task.task_id
        
    def get_session_status(self, session_id: str) -> str:
        """Get current simulator status for a session"""
        return self.session_status.get(session_id, "NONE")
        
    async def _worker(self, worker_name: str):
        """Background worker that processes simulator tasks"""
        logger.info(f"Background simulator worker {worker_name} started")
        
        while self.running:
            try:
                # Wait for a task with timeout
                try:
                    priority, task = await asyncio.wait_for(
                        self.task_queue.get(), timeout=5.0
                    )
                except asyncio.TimeoutError:
                    continue  # Check if still running
                    
                logger.info(f"Worker {worker_name} processing task {task.task_id}")
                
                # Process the task
                await self._process_task(task, worker_name)
                
                # Mark task as done
                self.task_queue.task_done()
                
                # Remove from active tasks
                task_key = f"{task.task_type}_{task.session_id}"
                self.active_tasks.pop(task_key, None)
                
            except Exception as e:
                logger.error(f"Worker {worker_name} error: {e}", exc_info=True)
                
        logger.info(f"Background simulator worker {worker_name} stopped")
        
    async def _process_task(self, task: SimulatorTask, worker_name: str):
        """Process a specific simulator task"""
        session_id = task.session_id
        user_id = task.user_id
        
        try:
            if task.task_type == SimulatorTaskType.CHECK_EXISTING:
                await self._check_existing_simulators(task, worker_name)
            elif task.task_type == SimulatorTaskType.CREATE_NEW:
                await self._create_new_simulator(task, worker_name)
            elif task.task_type == SimulatorTaskType.CLEANUP:
                await self._cleanup_simulators(task, worker_name)
            else:
                logger.warning(f"Unknown task type: {task.task_type}")
                
        except Exception as e:
            logger.error(f"Error processing task {task.task_id}: {e}", exc_info=True)
            
            # Update status to error
            self.session_status[session_id] = "ERROR"
            
            # Notify via callback if provided
            if task.callback:
                try:
                    await task.callback({
                        'session_id': session_id,
                        'status': 'ERROR',
                        'error': str(e)
                    })
                except Exception as cb_error:
                    logger.error(f"Callback error: {cb_error}")
                    
    async def _check_existing_simulators(self, task: SimulatorTask, worker_name: str):
        """Check for existing simulators and validate their health"""
        session_id = task.session_id
        user_id = task.user_id
        
        logger.info(f"Worker {worker_name}: Checking existing simulators for user {user_id}")
        
        # This can take time, but doesn't block the main session service
        existing_simulator, error = await self.simulator_manager.find_and_validate_simulator(
            session_id, user_id
        )
        
        if existing_simulator:
            logger.info(f"Worker {worker_name}: Found healthy simulator {existing_simulator.simulator_id}")
            
            # Update tracking
            self.simulator_manager.current_simulator_id = existing_simulator.simulator_id
            self.simulator_manager.current_endpoint = existing_simulator.endpoint
            self.session_status[session_id] = "RUNNING"
            
            # Notify via callback
            if task.callback:
                await task.callback({
                    'session_id': session_id,
                    'status': 'RUNNING',
                    'simulator_id': existing_simulator.simulator_id,
                    'endpoint': existing_simulator.endpoint
                })
                
        else:
            logger.info(f"Worker {worker_name}: No healthy simulators found, will need to create new one")
            self.session_status[session_id] = "NONE"
            
            # Notify that we need to create a new simulator
            if task.callback:
                await task.callback({
                    'session_id': session_id,
                    'status': 'NONE',
                    'message': 'No healthy simulators found'
                })
                
    async def _create_new_simulator(self, task: SimulatorTask, worker_name: str):
        """Create a new simulator"""
        session_id = task.session_id
        user_id = task.user_id
        
        logger.info(f"Worker {worker_name}: Creating new simulator for session {session_id}")
        
        # This includes K8s operations which can take time
        simulator, error = await self.simulator_manager.create_simulator(session_id, user_id)
        
        if simulator:
            logger.info(f"Worker {worker_name}: Successfully created simulator {simulator.simulator_id}")
            
            self.session_status[session_id] = "STARTING"
            
            # Notify success
            if task.callback:
                await task.callback({
                    'session_id': session_id,
                    'status': 'STARTING',
                    'simulator_id': simulator.simulator_id,
                    'endpoint': simulator.endpoint
                })
        else:
            logger.error(f"Worker {worker_name}: Failed to create simulator: {error}")
            
            self.session_status[session_id] = "ERROR"
            
            # Notify error
            if task.callback:
                await task.callback({
                    'session_id': session_id,
                    'status': 'ERROR',
                    'error': error
                })
                
    async def _cleanup_simulators(self, task: SimulatorTask, worker_name: str):
        """Clean up simulators"""
        logger.info(f"Worker {worker_name}: Cleaning up simulators for session {task.session_id}")
        
        # Implement cleanup logic here
        # This can also take time with K8s operations
        pass
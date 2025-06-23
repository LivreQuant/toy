# backend/session-service/source/core/simulator/background_manager.py
"""
Background simulator management that doesn't block session operations.
Uses gRPC heartbeat to determine real simulator status.
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
    Uses gRPC heartbeat to determine real simulator status instead of database status.
    """
    
    def __init__(self, simulator_manager, websocket_manager):
        self.simulator_manager = simulator_manager
        self.websocket_manager = websocket_manager
        
        # Task queue and worker management
        self.task_queue = asyncio.PriorityQueue()
        self.workers = []
        self.running = False
        self.worker_count = 2
        
        # Track active tasks to avoid duplicates
        self.active_tasks: Dict[str, SimulatorTask] = {}
        
        # Real-time status tracking based on gRPC heartbeats
        self.session_status: Dict[str, str] = {}
        self.session_endpoints: Dict[str, str] = {}
        
        # Health monitoring tasks
        self.health_monitors: Dict[str, asyncio.Task] = {}
        
        logger.info("Background simulator manager initialized with gRPC status tracking")
        
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
        """Stop all background workers and health monitors"""
        if not self.running:
            return
            
        self.running = False
        
        # Cancel all health monitoring tasks
        for session_id, task in self.health_monitors.items():
            logger.info(f"Stopping health monitor for session {session_id}")
            task.cancel()
        
        if self.health_monitors:
            await asyncio.gather(*self.health_monitors.values(), return_exceptions=True)
        self.health_monitors.clear()
        
        # Cancel all workers
        for worker in self.workers:
            worker.cancel()
            
        # Wait for workers to finish
        await asyncio.gather(*self.workers, return_exceptions=True)
        self.workers.clear()
        
        logger.info("Stopped background simulator management workers")
        
    def queue_simulator_check(self, session_id: str, user_id: str, 
                            callback: Optional[Callable] = None) -> str:
        """Queue a task to check for existing simulators"""
        task = SimulatorTask(
            SimulatorTaskType.CHECK_EXISTING,
            session_id,
            user_id,
            callback,
            priority=1
        )
        
        task_key = f"{task.task_type}_{session_id}"
        if task_key in self.active_tasks:
            logger.debug(f"Task {task_key} already active, skipping duplicate")
            return self.active_tasks[task_key].task_id
            
        self.active_tasks[task_key] = task
        self.session_status[session_id] = "CHECKING"
        
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
            priority=2
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
        """Get current simulator status for a session (from gRPC heartbeat)"""
        return self.session_status.get(session_id, "NONE")
        
    async def _start_health_monitoring(self, session_id: str, simulator_id: str, endpoint: str):
        """Start continuous health monitoring for a simulator via gRPC heartbeat"""
        if session_id in self.health_monitors:
            # Cancel existing monitor
            self.health_monitors[session_id].cancel()
        
        monitor_task = asyncio.create_task(
            self._health_monitor_loop(session_id, simulator_id, endpoint)
        )
        monitor_task.set_name(f"health-monitor-{session_id}")
        self.health_monitors[session_id] = monitor_task
        
        logger.info(f"Started health monitoring for session {session_id}, simulator {simulator_id}")
        
    async def _health_monitor_loop(self, session_id: str, simulator_id: str, endpoint: str):
        """Continuous health monitoring loop using gRPC heartbeat"""
        logger.info(f"Health monitor started for session {session_id}")
        
        while self.running:
            try:
                # Send heartbeat via exchange client
                heartbeat_result = await self.simulator_manager.exchange_client.send_heartbeat(
                    endpoint, session_id, f"health-monitor-{session_id}"
                )
                
                if heartbeat_result.get('success', False):
                    # Get status from heartbeat response
                    grpc_status = heartbeat_result.get('status', 'UNKNOWN')
                    
                    # Update our tracking
                    old_status = self.session_status.get(session_id, 'UNKNOWN')
                    self.session_status[session_id] = grpc_status
                    self.session_endpoints[session_id] = endpoint
                    
                    # Log status changes
                    if old_status != grpc_status:
                        logger.info(f"Session {session_id} simulator status: {old_status} -> {grpc_status}")
                        
                        # Notify callback if status changed to RUNNING
                        if grpc_status == 'RUNNING' and old_status != 'RUNNING':
                            # Notify that simulator is now running
                            await self._notify_status_change(session_id, simulator_id, grpc_status, endpoint)
                    
                else:
                    # Heartbeat failed
                    error = heartbeat_result.get('error', 'Unknown error')
                    logger.warning(f"Heartbeat failed for session {session_id}: {error}")
                    
                    # Mark as error and stop monitoring
                    self.session_status[session_id] = 'ERROR'
                    await self._notify_status_change(session_id, simulator_id, 'ERROR', endpoint)
                    break
                
                # Wait before next heartbeat
                await asyncio.sleep(10)  # Check every 10 seconds
                
            except asyncio.CancelledError:
                logger.info(f"Health monitor cancelled for session {session_id}")
                break
            except Exception as e:
                logger.error(f"Error in health monitor for session {session_id}: {e}")
                self.session_status[session_id] = 'ERROR'
                await asyncio.sleep(5)  # Wait before retrying
                
        # Clean up
        if session_id in self.health_monitors:
            del self.health_monitors[session_id]
        logger.info(f"Health monitor stopped for session {session_id}")
        
    async def _notify_status_change(self, session_id: str, simulator_id: str, status: str, endpoint: str):
        """Notify about simulator status changes"""
        try:
            # Notify WebSocket clients
            notification = {
                'type': 'simulator_status_update',
                'session_id': session_id,
                'simulator_id': simulator_id,
                'status': status,
                'endpoint': endpoint,
                'timestamp': int(time.time() * 1000)
            }
            
            # Send to all connected clients
            if self.websocket_manager:
                await self.websocket_manager.broadcast_to_session(notification)
                
        except Exception as e:
            logger.error(f"Error notifying status change: {e}")
        
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
        """Check for existing simulators and validate their health via gRPC"""
        session_id = task.session_id
        user_id = task.user_id
        
        logger.info(f"Worker {worker_name}: Checking existing simulators for user {user_id}")
        
        # Find existing simulators in database
        existing_simulator, error = await self.simulator_manager.find_and_validate_simulator(
            session_id, user_id
        )
        
        if existing_simulator and existing_simulator.endpoint:
            logger.info(f"Worker {worker_name}: Found simulator {existing_simulator.simulator_id}, testing gRPC connection")
            
            # Test gRPC connection with heartbeat
            try:
                heartbeat_result = await self.simulator_manager.exchange_client.send_heartbeat(
                    existing_simulator.endpoint, session_id, f"check-{session_id}"
                )
                
                if heartbeat_result.get('success', False):
                    grpc_status = heartbeat_result.get('status', 'UNKNOWN')
                    
                    logger.info(f"Worker {worker_name}: Simulator {existing_simulator.simulator_id} is reachable, status: {grpc_status}")
                    
                    # Update tracking
                    self.simulator_manager.current_simulator_id = existing_simulator.simulator_id
                    self.simulator_manager.current_endpoint = existing_simulator.endpoint
                    self.session_status[session_id] = grpc_status
                    self.session_endpoints[session_id] = existing_simulator.endpoint
                    
                    # Start health monitoring
                    await self._start_health_monitoring(
                        session_id, existing_simulator.simulator_id, existing_simulator.endpoint
                    )
                    
                    # Notify via callback
                    if task.callback:
                        await task.callback({
                            'session_id': session_id,
                            'status': grpc_status,
                            'simulator_id': existing_simulator.simulator_id,
                            'endpoint': existing_simulator.endpoint
                        })
                    return
                else:
                    logger.warning(f"Worker {worker_name}: Simulator {existing_simulator.simulator_id} not responding to heartbeat")
                    
            except Exception as e:
                logger.error(f"Worker {worker_name}: Error testing simulator {existing_simulator.simulator_id}: {e}")
        
        # No healthy simulator found
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
        """Create a new simulator and wait for it to be ready"""
        session_id = task.session_id
        user_id = task.user_id
        
        logger.info(f"Worker {worker_name}: Creating new simulator for session {session_id}")
        
        # Create simulator via simulator manager
        simulator, error = await self.simulator_manager.create_simulator(session_id, user_id)
        
        if not simulator or not simulator.endpoint:
            logger.error(f"Worker {worker_name}: Failed to create simulator: {error}")
            self.session_status[session_id] = "ERROR"
            
            if task.callback:
                await task.callback({
                    'session_id': session_id,
                    'status': 'ERROR',
                    'error': error
                })
            return
        
        logger.info(f"Worker {worker_name}: Created simulator {simulator.simulator_id}, waiting for readiness...")
        
        # Update tracking
        self.simulator_manager.current_simulator_id = simulator.simulator_id
        self.simulator_manager.current_endpoint = simulator.endpoint
        self.session_status[session_id] = "STARTING"
        self.session_endpoints[session_id] = simulator.endpoint
        
        # PROPER STARTUP WAITING - Check both Kubernetes readiness AND gRPC
        max_startup_wait = 120  # 2 minutes max startup time
        check_interval = 5      # Check every 5 seconds
        elapsed = 0
        
        readiness_ready = False
        grpc_ready = False
        
        while elapsed < max_startup_wait and not (readiness_ready and grpc_ready):
            try:
                # 1. Check Kubernetes readiness probe first
                if not readiness_ready:
                    try:
                        # Use the k8s client to check pod readiness
                        k8s_status = await self.simulator_manager.k8s_client.check_simulator_status(simulator.simulator_id)
                        if k8s_status == "RUNNING":
                            readiness_ready = True
                            logger.info(f"Worker {worker_name}: Simulator {simulator.simulator_id} Kubernetes readiness OK")
                    except Exception as e:
                        logger.debug(f"Worker {worker_name}: K8s readiness check failed: {e}")
                
                # 2. If K8s is ready, test gRPC connection
                if readiness_ready and not grpc_ready:
                    try:
                        heartbeat_result = await self.simulator_manager.exchange_client.send_heartbeat(
                            simulator.endpoint, session_id, f"startup-check-{elapsed}"
                        )
                        
                        if heartbeat_result.get('success', False):
                            grpc_ready = True
                            grpc_status = heartbeat_result.get('status', 'RUNNING')
                            logger.info(f"Worker {worker_name}: Simulator {simulator.simulator_id} gRPC ready, status: {grpc_status}")
                            
                            # Update to actual status from simulator
                            self.session_status[session_id] = grpc_status
                            break
                            
                    except Exception as e:
                        logger.debug(f"Worker {worker_name}: gRPC check failed: {e}")
                
            except Exception as e:
                logger.warning(f"Worker {worker_name}: Readiness check error: {e}")
            
            # Wait before next check
            await asyncio.sleep(check_interval)
            elapsed += check_interval
            
            # Log progress every 15 seconds
            if elapsed % 15 == 0:
                logger.info(f"Worker {worker_name}: Waiting for simulator {simulator.simulator_id}... ({elapsed}s elapsed, K8s: {readiness_ready}, gRPC: {grpc_ready})")
        
        # Check final status
        if readiness_ready and grpc_ready:
            logger.info(f"Worker {worker_name}: Simulator {simulator.simulator_id} is fully ready after {elapsed}s")
            
            # Start ongoing health monitoring
            await self._start_health_monitoring(
                session_id, simulator.simulator_id, simulator.endpoint
            )
            
            # Notify success with actual status
            if task.callback:
                await task.callback({
                    'session_id': session_id,
                    'status': self.session_status[session_id],
                    'simulator_id': simulator.simulator_id,
                    'endpoint': simulator.endpoint
                })
        else:
            # Startup timeout - mark as error and clean up
            logger.error(f"Worker {worker_name}: Simulator {simulator.simulator_id} failed to become ready within {max_startup_wait}s (K8s: {readiness_ready}, gRPC: {grpc_ready})")
            
            self.session_status[session_id] = "ERROR"
            
            # Try to clean up the failed simulator
            try:
                await self.simulator_manager.k8s_client.delete_simulator_deployment(simulator.simulator_id)
                logger.info(f"Worker {worker_name}: Cleaned up failed simulator {simulator.simulator_id}")
            except Exception as cleanup_error:
                logger.error(f"Worker {worker_name}: Failed to clean up simulator: {cleanup_error}")
            
            # Notify failure
            if task.callback:
                await task.callback({
                    'session_id': session_id,
                    'status': 'ERROR',
                    'error': f'Simulator startup timeout after {max_startup_wait}s'
                })
                
    async def _cleanup_simulators(self, task: SimulatorTask, worker_name: str):
        """Clean up simulators"""
        logger.info(f"Worker {worker_name}: Cleaning up simulators for session {task.session_id}")
        
        # Stop health monitoring
        if task.session_id in self.health_monitors:
            self.health_monitors[task.session_id].cancel()
            del self.health_monitors[task.session_id]
        
        # Clean up status tracking
        self.session_status.pop(task.session_id, None)
        self.session_endpoints.pop(task.session_id, None)
# source/workflows/workflow_engine.py
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass
from enum import Enum
import uuid

logger = logging.getLogger(__name__)

class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"

class TaskPriority(Enum):
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4

@dataclass
class WorkflowTask:
    id: str
    name: str
    function: Callable
    dependencies: List[str]
    priority: TaskPriority = TaskPriority.MEDIUM
    timeout_seconds: int = 300
    retry_count: int = 3
    retry_delay: int = 30
    skip_flag: bool = False
    status: TaskStatus = TaskStatus.PENDING
    result: Any = None
    error: str = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None

@dataclass 
class WorkflowResult:
    success: bool
    execution_time: float
    completed_tasks: int
    failed_tasks: int
    skipped_tasks: int = 0  # NEW: Track skipped tasks
    error: Optional[str] = None
    task_results: Dict[str, Any] = None
    workflow_execution_id: Optional[str] = None

class WorkflowEngine:
    """Manages workflow execution with dependencies, retries, and error handling"""
    
    def __init__(self, db_manager=None):
        self.db_manager = db_manager
        self.workflows: Dict[str, List[WorkflowTask]] = {}
        self.running_workflows: Dict[str, bool] = {}
        
        # NEW: Global skip configuration for debugging
        self.global_skip_config: Dict[str, bool] = {}
        
    async def initialize(self):
        """Initialize workflow engine"""
        logger.info("⚙️ Workflow engine initialized")
    
    def register_workflow(self, workflow_name: str, tasks: List[WorkflowTask]):
        """Register a workflow definition"""
        self.workflows[workflow_name] = tasks
        logger.info(f"📋 Workflow '{workflow_name}' registered with {len(tasks)} tasks")
    
    def configure_task_skipping(self, skip_config: Dict[str, bool]):
        """Configure which tasks to skip globally for debugging
        
        Args:
            skip_config: Dict mapping task_id to skip boolean
            Example: {"system_health_check": True, "database_validation": False}
        """
        self.global_skip_config = skip_config.copy()
        skipped_tasks = [task_id for task_id, skip in skip_config.items() if skip]
        logger.info(f"🚧 Debug mode: Configured to skip tasks: {skipped_tasks}")
    
    def skip_task(self, task_id: str, skip: bool = True):
        """Skip or unskip a specific task for debugging"""
        self.global_skip_config[task_id] = skip
        action = "skip" if skip else "unskip"
        logger.info(f"🚧 Debug mode: Configured to {action} task '{task_id}'")
    
    def _should_skip_task(self, task: WorkflowTask, context: Dict[str, Any]) -> bool:
        """Determine if a task should be skipped"""
        # Check individual task skip flag
        if task.skip:
            return True
        
        # Check global skip configuration
        if self.global_skip_config.get(task.id, False):
            return True
        
        # Check context-based skip configuration
        context_skip_config = context.get('skip_tasks', {})
        if context_skip_config.get(task.id, False):
            return True
        
        # Check if task should be skipped based on environment
        debug_mode = context.get('debug_mode', False)
        if debug_mode:
            # In debug mode, check for debug-specific skip patterns
            debug_skip_patterns = context.get('debug_skip_patterns', [])
            for pattern in debug_skip_patterns:
                if pattern in task.id or pattern in task.name.lower():
                    return True
        
        return False

    async def execute_workflow(self, workflow_name: str, context: Dict[str, Any] = None) -> WorkflowResult:
        """Execute a complete workflow with enhanced database logging and skip support"""
        if workflow_name not in self.workflows:
            raise ValueError(f"Workflow '{workflow_name}' not registered")
        
        if workflow_name in self.running_workflows:
            raise RuntimeError(f"Workflow '{workflow_name}' is already running")
        
        workflow_execution_id = None
        start_time = datetime.utcnow()
        tasks = self.workflows[workflow_name].copy()  # Copy to avoid modifying original
        context = context or {}
        
        # Reset task status
        for task in tasks:
            task.status = TaskStatus.PENDING
            task.result = None
            task.error = None
            task.start_time = None
            task.end_time = None
        
        try:
            self.running_workflows[workflow_name] = True
            
            # Log skip configuration if any tasks are configured to be skipped
            skip_summary = self._get_skip_summary(tasks, context)
            if skip_summary['total_skipped'] > 0:
                logger.info(f"🚧 Debug mode active: {skip_summary['total_skipped']} tasks will be skipped: {skip_summary['skipped_tasks']}")
            
            # Create workflow execution record if we have database access
            if self.db_manager and hasattr(self.db_manager, 'workflows'):
                execution_context = context.copy()
                execution_context['skip_summary'] = skip_summary  # Add skip info to context
                
                workflow_execution_id = await self.db_manager.workflows.create_workflow_execution(
                    workflow_name=workflow_name,
                    workflow_type=context.get('workflow_type', 'GENERAL'),
                    execution_date=context.get('execution_date', start_time.date()),
                    total_tasks=len(tasks),
                    execution_context=execution_context
                )
                logger.info(f"📝 Created workflow execution record: {workflow_execution_id}")
            
            logger.info(f"🚀 Starting workflow '{workflow_name}' with {len(tasks)} tasks")
            
            completed_tasks = 0
            failed_tasks = 0
            skipped_tasks = 0
            task_results = {}
            
            # Execute tasks with dependency resolution
            executed_tasks = set()
            
            while len(executed_tasks) < len(tasks):
                ready_tasks = [
                    task for task in tasks 
                    if (task.status == TaskStatus.PENDING and 
                        all(dep in executed_tasks for dep in task.dependencies))
                ]
                
                if not ready_tasks:
                    # Check if we have any running tasks
                    running_tasks = [task for task in tasks if task.status == TaskStatus.RUNNING]
                    if not running_tasks:
                        # No ready tasks and no running tasks - possible circular dependency
                        remaining_tasks = [task for task in tasks if task.id not in executed_tasks]
                        error_msg = f"Circular dependency or unresolved dependencies for tasks: {[t.id for t in remaining_tasks]}"
                        logger.error(f"❌ {error_msg}")
                        break
                    
                    # Wait a bit for running tasks to complete
                    await asyncio.sleep(0.1)
                    continue
                
                # Sort by priority
                ready_tasks.sort(key=lambda t: t.priority.value, reverse=True)
                
                # Execute ready tasks (can be parallel for independent tasks)
                tasks_to_execute = ready_tasks[:5]  # Limit concurrent execution
                
                task_coroutines = []
                for task in tasks_to_execute:
                    if self._should_skip_task(task, context):
                        # Handle skipped task immediately
                        task.status = TaskStatus.SKIPPED
                        task.start_time = datetime.utcnow()
                        task.end_time = task.start_time
                        task.result = {"status": "skipped", "reason": "debug_skip"}
                        executed_tasks.add(task.id)
                        skipped_tasks += 1
                        task_results[task.id] = task.result
                        logger.info(f"⏭️ Task '{task.id}' skipped for debugging")
                        
                        # Create skipped task record
                        if workflow_execution_id and self.db_manager and hasattr(self.db_manager, 'workflows'):
                            task_id = await self.db_manager.workflows.create_workflow_task(
                                workflow_execution_id=workflow_execution_id,
                                task_name=task.name,
                                task_order=hash(task.id) % 1000,
                                started_at=task.start_time
                            )
                            await self.db_manager.workflows.update_workflow_task(
                                task_id,
                                status='SKIPPED',
                                completed_at=task.end_time,
                                duration_seconds=0,
                                task_result=task.result
                            )
                    else:
                        task_coroutines.append(self._execute_task(task, context, workflow_execution_id))
                
                # Wait for all non-skipped tasks to complete
                if task_coroutines:
                    task_execution_results = await asyncio.gather(*task_coroutines, return_exceptions=True)
                    
                    # Process results for non-skipped tasks
                    coroutine_index = 0
                    for task in tasks_to_execute:
                        if task.status == TaskStatus.SKIPPED:
                            continue  # Already handled above
                        
                        result = task_execution_results[coroutine_index]
                        executed_tasks.add(task.id)
                        coroutine_index += 1
                        
                        if isinstance(result, Exception):
                            task.status = TaskStatus.FAILED
                            task.error = str(result)
                            failed_tasks += 1
                            logger.error(f"❌ Task '{task.id}' failed with exception: {result}")
                            
                            # Stop execution if critical task fails
                            logger.error(f"💥 Critical task '{task.id}' failed, stopping workflow")
                            break
                        else:
                            task.status = TaskStatus.COMPLETED
                            task.result = result
                            task_results[task.id] = result
                            completed_tasks += 1
                            logger.info(f"✅ Task '{task.id}' completed successfully")
            
            end_time = datetime.utcnow()
            execution_time = (end_time - start_time).total_seconds()
            
            # Determine success - skipped tasks don't count as failures
            success = (failed_tasks == 0 or 
                      all(False for task in tasks if task.status == TaskStatus.FAILED))
            
            # Update workflow execution record
            if workflow_execution_id and self.db_manager:
                await self.db_manager.workflows.update_workflow_execution(
                    workflow_execution_id,
                    status='SUCCESS' if success else 'FAILED',
                    completed_at=end_time,
                    completed_tasks=completed_tasks,
                    failed_tasks=failed_tasks,
                    error_message=None if success else f"Workflow failed with {failed_tasks} failed tasks"
                )
            
            result = WorkflowResult(
                success=success,
                execution_time=execution_time,
                completed_tasks=completed_tasks,
                failed_tasks=failed_tasks,
                skipped_tasks=skipped_tasks,
                error=None if success else f"Workflow failed with {failed_tasks} failed tasks",
                task_results=task_results,
                workflow_execution_id=workflow_execution_id
            )
            
            status_emoji = "✅" if success else "❌"
            skip_info = f", Skipped: {skipped_tasks}" if skipped_tasks > 0 else ""
            logger.info(f"{status_emoji} Workflow '{workflow_name}' completed in {execution_time:.2f}s - "
                       f"Success: {completed_tasks}, Failed: {failed_tasks}{skip_info}")
            
            return result
            
        except Exception as e:
            logger.error(f"💥 Workflow '{workflow_name}' execution failed: {e}", exc_info=True)
            
            # Update workflow execution record with error
            if workflow_execution_id and self.db_manager:
                await self.db_manager.workflows.update_workflow_execution(
                    workflow_execution_id,
                    status='FAILED',
                    completed_at=datetime.utcnow(),
                    error_message=str(e)
                )
            
            return WorkflowResult(
                success=False,
                execution_time=(datetime.utcnow() - start_time).total_seconds(),
                completed_tasks=0,
                failed_tasks=len([t for t in tasks if not self._should_skip_task(t, context)]),
                skipped_tasks=len([t for t in tasks if self._should_skip_task(t, context)]),
                error=str(e),
                workflow_execution_id=workflow_execution_id
            )
        finally:
            self.running_workflows.pop(workflow_name, None)
    
    def _get_skip_summary(self, tasks: List[WorkflowTask], context: Dict[str, Any]) -> Dict[str, Any]:
        """Get summary of which tasks will be skipped"""
        skipped_tasks = []
        for task in tasks:
            if self._should_skip_task(task, context):
                skipped_tasks.append(task.id)
        
        return {
            "total_tasks": len(tasks),
            "total_skipped": len(skipped_tasks),
            "skipped_tasks": skipped_tasks,
            "skip_percentage": (len(skipped_tasks) / len(tasks)) * 100 if tasks else 0
        }

    async def _execute_task(self, task: WorkflowTask, context: Dict[str, Any], workflow_execution_id: str = None) -> Any:
        """Execute a single task with retries and timeout"""
        # Note: Skip checking is now handled in execute_workflow before this method is called
        task.status = TaskStatus.RUNNING
        task.start_time = datetime.utcnow()
        
        # Create task record if we have database access
        task_id = None
        if workflow_execution_id and self.db_manager and hasattr(self.db_manager, 'workflows'):
            task_id = await self.db_manager.workflows.create_workflow_task(
                workflow_execution_id=workflow_execution_id,
                task_name=task.name,
                task_order=hash(task.id) % 1000,  # Simple ordering
                started_at=task.start_time
            )
        
        logger.info(f"🔄 Executing task '{task.id}' - {task.name}")
        
        last_exception = None
        
        for attempt in range(task.retry_count + 1):
            try:
                if attempt > 0:
                    logger.info(f"🔁 Retry attempt {attempt} for task '{task.id}'")
                    await asyncio.sleep(task.retry_delay)
                
                # Execute with timeout
                result = await asyncio.wait_for(
                    task.function(context),
                    timeout=task.timeout_seconds
                )
                
                task.end_time = datetime.utcnow()
                duration = (task.end_time - task.start_time).total_seconds()
                
                # Update task record
                if task_id and self.db_manager:
                    await self.db_manager.workflows.update_workflow_task(
                        task_id,
                        status='SUCCESS',
                        completed_at=task.end_time,
                        duration_seconds=int(duration),
                        task_result=result if isinstance(result, (dict, list, str, int, float)) else str(result)
                    )
                
                logger.info(f"✅ Task '{task.id}' completed in {duration:.2f}s")
                return result
                
            except asyncio.TimeoutError:
                last_exception = f"Task '{task.id}' timed out after {task.timeout_seconds}s"
                logger.warning(f"⏰ {last_exception}")
                
            except Exception as e:
                last_exception = e
                logger.warning(f"⚠️ Task '{task.id}' failed on attempt {attempt + 1}: {e}")
        
        # All retries exhausted
        task.end_time = datetime.utcnow()
        duration = (task.end_time - task.start_time).total_seconds()
        
        # Update task record with failure
        if task_id and self.db_manager:
            await self.db_manager.workflows.update_workflow_task(
                task_id,
                status='FAILED',
                completed_at=task.end_time,
                duration_seconds=int(duration),
                error_message=str(last_exception)
            )
        
        raise last_exception
    
    def get_workflow_status(self, workflow_name: str) -> Dict[str, Any]:
        """Get current status of a workflow"""
        if workflow_name not in self.workflows:
            return {"error": f"Workflow '{workflow_name}' not found"}
        
        tasks = self.workflows[workflow_name]
        
        return {
            "workflow_name": workflow_name,
            "is_running": workflow_name in self.running_workflows,
            "total_tasks": len(tasks),
            "skip_config": self.global_skip_config,
            "task_statuses": {
                task.id: {
                    "name": task.name,
                    "status": task.status.value,
                    "skip": task.skip,
                    "will_skip": self._should_skip_task(task, {}),
                    "start_time": task.start_time.isoformat() if task.start_time else None,
                    "end_time": task.end_time.isoformat() if task.end_time else None,
                    "error": task.error
                }
                for task in tasks
            }
        }
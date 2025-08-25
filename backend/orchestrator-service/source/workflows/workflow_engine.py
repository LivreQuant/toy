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
    required: bool = True
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
    error: Optional[str] = None
    task_results: Dict[str, Any] = None

class WorkflowEngine:
    """Manages workflow execution with dependencies, retries, and error handling"""
    
    def __init__(self):
        self.workflows: Dict[str, List[WorkflowTask]] = {}
        self.running_workflows: Dict[str, bool] = {}
        
    async def initialize(self):
        """Initialize workflow engine"""
        logger.info("⚙️ Workflow engine initialized")
    
    def register_workflow(self, workflow_name: str, tasks: List[WorkflowTask]):
        """Register a workflow definition"""
        self.workflows[workflow_name] = tasks
        logger.info(f"📋 Workflow '{workflow_name}' registered with {len(tasks)} tasks")
    
    async def execute_workflow(self, workflow_name: str, context: Dict[str, Any] = None) -> WorkflowResult:
        """Execute a workflow with dependency resolution"""
        if workflow_name not in self.workflows:
            raise ValueError(f"Workflow '{workflow_name}' not found")
        
        if workflow_name in self.running_workflows:
            raise ValueError(f"Workflow '{workflow_name}' is already running")
        
        logger.info(f"🚀 Starting workflow execution: {workflow_name}")
        start_time = datetime.utcnow()
        
        tasks = self.workflows[workflow_name].copy()
        self.running_workflows[workflow_name] = True
        
        # Reset task states
        for task in tasks:
            task.status = TaskStatus.PENDING
            task.result = None
            task.error = None
            task.start_time = None
            task.end_time = None
        
        try:
            completed_tasks = 0
            failed_tasks = 0
            task_results = {}
            
            # Execute tasks in dependency order
            while tasks:
                # Find tasks ready to execute (dependencies met)
                ready_tasks = self._get_ready_tasks(tasks, task_results)
                
                if not ready_tasks:
                    # Check if we have any non-failed tasks left
                    pending_tasks = [t for t in tasks if t.status == TaskStatus.PENDING]
                    if pending_tasks:
                        # Dependency deadlock - fail remaining required tasks
                        for task in pending_tasks:
                            if task.required:
                                task.status = TaskStatus.FAILED
                                task.error = "Dependency deadlock"
                                failed_tasks += 1
                            else:
                                task.status = TaskStatus.SKIPPED
                                logger.warning(f"⏭️ Skipping optional task {task.name} due to dependency deadlock")
                    break
                
                # Execute ready tasks in parallel
                task_futures = []
                for task in ready_tasks:
                    future = asyncio.create_task(self._execute_task(task, context or {}))
                    task_futures.append((task, future))
                
                # Wait for all tasks to complete
                for task, future in task_futures:
                    try:
                        result = await future
                        task.result = result
                        task_results[task.id] = result
                        completed_tasks += 1
                        logger.info(f"✅ Task completed: {task.name}")
                        
                    except Exception as e:
                        task.status = TaskStatus.FAILED
                        task.error = str(e)
                        logger.error(f"❌ Task failed: {task.name} - {e}")
                        
                        if task.required:
                            failed_tasks += 1
                        else:
                            logger.warning(f"⚠️ Optional task failed: {task.name}")
                
                # Remove completed/failed tasks
                tasks = [t for t in tasks if t.status in [TaskStatus.PENDING]]
            
            end_time = datetime.utcnow()
            execution_time = (end_time - start_time).total_seconds()
            
            success = failed_tasks == 0
            
            result = WorkflowResult(
                success=success,
                execution_time=execution_time,
                completed_tasks=completed_tasks,
                failed_tasks=failed_tasks,
                task_results=task_results
            )
            
            if success:
                logger.info(f"✅ Workflow '{workflow_name}' completed successfully in {execution_time:.2f}s")
            else:
                result.error = f"{failed_tasks} required tasks failed"
                logger.error(f"❌ Workflow '{workflow_name}' failed: {result.error}")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Workflow execution error: {e}", exc_info=True)
            return WorkflowResult(
                success=False,
                execution_time=(datetime.utcnow() - start_time).total_seconds(),
                completed_tasks=0,
                failed_tasks=len(self.workflows[workflow_name]),
                error=str(e)
            )
        finally:
            self.running_workflows.pop(workflow_name, None)
    
    def _get_ready_tasks(self, tasks: List[WorkflowTask], completed_results: Dict[str, Any]) -> List[WorkflowTask]:
        """Get tasks that are ready to execute (dependencies satisfied)"""
        ready = []
        
        for task in tasks:
            if task.status != TaskStatus.PENDING:
                continue
            
            # Check if all dependencies are satisfied
            dependencies_met = all(dep_id in completed_results for dep_id in task.dependencies)
            
            if dependencies_met:
                ready.append(task)
        
        # Sort by priority
        ready.sort(key=lambda t: t.priority.value, reverse=True)
        return ready
    
    async def _execute_task(self, task: WorkflowTask, context: Dict[str, Any]) -> Any:
        """Execute a single task with retry logic"""
        task.status = TaskStatus.RUNNING
        task.start_time = datetime.utcnow()
        
        logger.info(f"🔄 Executing task: {task.name}")
        
        for attempt in range(task.retry_count):
            try:
                # Set timeout for task execution
                result = await asyncio.wait_for(
                    task.function(context),
                    timeout=task.timeout_seconds
                )
                
                task.status = TaskStatus.COMPLETED
                task.end_time = datetime.utcnow()
                return result
                
            except asyncio.TimeoutError:
                error_msg = f"Task '{task.name}' timed out after {task.timeout_seconds}s"
                logger.error(error_msg)
                
                if attempt < task.retry_count - 1:
                    logger.info(f"🔄 Retrying task '{task.name}' (attempt {attempt + 2}/{task.retry_count})")
                    await asyncio.sleep(task.retry_delay)
                else:
                    task.error = error_msg
                    raise asyncio.TimeoutError(error_msg)
                    
            except Exception as e:
                logger.error(f"❌ Task '{task.name}' failed on attempt {attempt + 1}: {e}")
                
                if attempt < task.retry_count - 1:
                    logger.info(f"🔄 Retrying task '{task.name}' (attempt {attempt + 2}/{task.retry_count})")
                    await asyncio.sleep(task.retry_delay)
                else:
                    task.error = str(e)
                    task.end_time = datetime.utcnow()
                    raise
        
        # This shouldn't be reached, but just in case
        raise RuntimeError(f"Task '{task.name}' failed after all retry attempts")
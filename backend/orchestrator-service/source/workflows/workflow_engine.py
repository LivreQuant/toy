# source/workflows/workflow_engine.py
import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass
from enum import Enum

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
    skipped_tasks: int = 0
    error: Optional[str] = None
    task_results: Dict[str, Any] = None
    workflow_execution_id: Optional[str] = None


class WorkflowEngine:
    """Simple workflow engine that just runs tasks"""

    def __init__(self, db_manager=None):
        self.db_manager = db_manager
        self.workflows: Dict[str, List[WorkflowTask]] = {}

    async def initialize(self):
        """Initialize workflow engine"""
        logger.info("⚙️ Simple workflow engine initialized")

    def register_workflow(self, workflow_name: str, tasks: List[WorkflowTask]):
        """Register a workflow definition"""
        self.workflows[workflow_name] = tasks
        logger.info(f"📋 Workflow '{workflow_name}' registered with {len(tasks)} tasks")

    async def execute_workflow(self, workflow_name: str, context: Dict[str, Any] = None) -> WorkflowResult:
        """Execute a workflow - simple as fuck"""
        if workflow_name not in self.workflows:
            raise ValueError(f"Workflow '{workflow_name}' not found")

        tasks = self.workflows[workflow_name]
        context = context or {}
        start_time = datetime.utcnow()

        logger.info(f"🚀 Starting workflow '{workflow_name}' with {len(tasks)} tasks")

        completed_tasks = 0
        failed_tasks = 0
        skipped_tasks = 0
        task_results = {}
        executed_task_ids = set()

        # Execute tasks in dependency order
        while len(executed_task_ids) < len(tasks):
            # Find tasks ready to run (dependencies satisfied)
            ready_tasks = []
            for task in tasks:
                if (task.status == TaskStatus.PENDING and
                        all(dep in executed_task_ids for dep in task.dependencies)):
                    ready_tasks.append(task)

            if not ready_tasks:
                # No more tasks can run - check if we're done
                remaining = [t for t in tasks if t.id not in executed_task_ids]
                if remaining:
                    error = f"Cannot execute remaining tasks due to dependencies: {[t.id for t in remaining]}"
                    logger.error(f"❌ {error}")
                    failed_tasks += len(remaining)
                    break
                else:
                    break

            # Execute ready tasks one by one
            for task in ready_tasks:
                # Check if task should be skipped
                if task.skip_flag:
                    logger.info(f"⏭️ Skipping task '{task.id}' - {task.name}")
                    task.status = TaskStatus.SKIPPED
                    skipped_tasks += 1
                    executed_task_ids.add(task.id)
                    task_results[task.id] = {"status": "skipped"}
                    continue

                # Execute the task
                try:
                    logger.info(f"🔄 Executing task '{task.id}' - {task.name}")
                    task.status = TaskStatus.RUNNING
                    task.start_time = datetime.utcnow()

                    # Run the task function
                    result = await task.function(context)

                    task.end_time = datetime.utcnow()
                    task.status = TaskStatus.COMPLETED
                    task.result = result
                    task_results[task.id] = result
                    completed_tasks += 1
                    executed_task_ids.add(task.id)

                    duration = (task.end_time - task.start_time).total_seconds()
                    logger.info(f"✅ Task '{task.id}' completed in {duration:.2f}s")

                except Exception as e:
                    task.end_time = datetime.utcnow()
                    task.status = TaskStatus.FAILED
                    task.error = str(e)
                    failed_tasks += 1
                    executed_task_ids.add(task.id)

                    duration = (task.end_time - task.start_time).total_seconds() if task.start_time else 0
                    logger.error(f"❌ Task '{task.id}' failed after {duration:.2f}s: {e}")

                    # Stop on first failure
                    break

            # If we had a failure, stop the workflow
            if failed_tasks > 0:
                break

        end_time = datetime.utcnow()
        execution_time = (end_time - start_time).total_seconds()
        success = failed_tasks == 0

        result = WorkflowResult(
            success=success,
            execution_time=execution_time,
            completed_tasks=completed_tasks,
            failed_tasks=failed_tasks,
            skipped_tasks=skipped_tasks,
            task_results=task_results,
            error=None if success else f"Workflow failed with {failed_tasks} failed tasks"
        )

        status_emoji = "✅" if success else "❌"
        logger.info(f"{status_emoji} Workflow '{workflow_name}' finished in {execution_time:.2f}s - "
                    f"Completed: {completed_tasks}, Failed: {failed_tasks}, Skipped: {skipped_tasks}")

        return result
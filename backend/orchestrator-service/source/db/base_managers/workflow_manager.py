# source/db/base_managers/workflow_manager.py
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, date
from .base_manager import BaseManager

logger = logging.getLogger(__name__)


class WorkflowManager(BaseManager):
    """Simple workflow manager - just track workflow executions"""

    async def create_workflow_execution(self, workflow_name: str, workflow_type: str,
                                        execution_date: date, total_tasks: int,
                                        execution_context: Dict[str, Any] = None) -> str:
        """Create workflow execution record"""
        result = await self.execute_returning("""
            INSERT INTO workflows.workflow_executions
            (workflow_name, workflow_type, execution_date, total_tasks, started_at, workflow_status)
            VALUES ($1, $2, $3, $4, $5, 'RUNNING')
            RETURNING execution_id
        """, workflow_name, workflow_type, execution_date, total_tasks, datetime.utcnow())

        return str(result['execution_id']) if result else None

    async def update_workflow_execution(self, execution_id: str, status: str,
                                        completed_at: datetime = None,
                                        completed_tasks: int = None,
                                        failed_tasks: int = None,
                                        error_message: str = None):
        """Update workflow execution"""
        await self.execute("""
            UPDATE workflows.workflow_executions
            SET workflow_status = $2, completed_at = $3, completed_tasks = $4, 
                failed_tasks = $5, error_message = $6
            WHERE execution_id = $1
        """, execution_id, status, completed_at, completed_tasks, failed_tasks, error_message)

    async def create_workflow_task(self, workflow_execution_id: str, task_name: str,
                                   task_order: int, started_at: datetime) -> str:
        """Create workflow task record"""
        result = await self.execute_returning("""
            INSERT INTO workflows.workflow_tasks
            (workflow_execution_id, task_name, task_order, started_at, task_status)
            VALUES ($1, $2, $3, $4, 'RUNNING')
            RETURNING task_id
        """, workflow_execution_id, task_name, task_order, started_at)

        return str(result['task_id']) if result else None

    async def update_workflow_task(self, task_id: str, status: str,
                                   completed_at: datetime = None,
                                   duration_seconds: int = None,
                                   error_message: str = None,
                                   task_result: Any = None):
        """Update workflow task"""
        await self.execute("""
            UPDATE workflows.workflow_tasks
            SET task_status = $2, completed_at = $3, duration_seconds = $4,
                error_message = $5, task_result = $6
            WHERE task_id = $1
        """, task_id, status, completed_at, duration_seconds, error_message, str(task_result))

    async def get_workflow_executions(self, workflow_name: str = None, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent workflow executions"""
        if workflow_name:
            return await self.fetch_all("""
                SELECT * FROM workflows.workflow_executions
                WHERE workflow_name = $1
                ORDER BY started_at DESC LIMIT $2
            """, workflow_name, limit)
        else:
            return await self.fetch_all("""
                SELECT * FROM workflows.workflow_executions
                ORDER BY started_at DESC LIMIT $1
            """, limit)
# db/managers/workflow_manager.py
from typing import Dict, List, Any, Optional, Union
from datetime import date, datetime
import json
from .base_manager import BaseManager

class WorkflowManager(BaseManager):
    """Manages workflow execution database operations"""
    
    async def initialize_tables(self):
        """Create workflow tables"""
        await self.create_schema_if_not_exists('workflows')
        
        # Create workflow status enum
        await self.execute("""
            DO $$ BEGIN
                CREATE TYPE workflow_status AS ENUM ('PENDING', 'RUNNING', 'SUCCESS', 'FAILED', 'CANCELLED');
            EXCEPTION
                WHEN duplicate_object THEN null;
            END $$
        """)
        
        # Workflow executions
        await self.execute("""
            CREATE TABLE IF NOT EXISTS workflows.workflow_executions (
                execution_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                workflow_name VARCHAR(200) NOT NULL,
                workflow_type VARCHAR(100) NOT NULL,
                execution_date DATE NOT NULL,
                workflow_status workflow_status DEFAULT 'PENDING',
                started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                completed_at TIMESTAMP WITH TIME ZONE,
                total_tasks INTEGER DEFAULT 0,
                completed_tasks INTEGER DEFAULT 0,
                failed_tasks INTEGER DEFAULT 0,
                execution_context JSONB,
                error_message TEXT,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            )
        """)
        
        # Workflow tasks
        await self.execute("""
            CREATE TABLE IF NOT EXISTS workflows.workflow_tasks (
                task_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                workflow_execution_id UUID REFERENCES workflows.workflow_executions(execution_id) ON DELETE CASCADE,
                task_name VARCHAR(200) NOT NULL,
                task_order INTEGER NOT NULL DEFAULT 0,
                task_status workflow_status DEFAULT 'PENDING',
                started_at TIMESTAMP WITH TIME ZONE,
                completed_at TIMESTAMP WITH TIME ZONE,
                duration_seconds INTEGER,
                task_result JSONB,
                error_message TEXT,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            )
        """)
        
        # Create indexes
        await self.execute("""
            CREATE INDEX IF NOT EXISTS idx_workflow_executions_name_date 
            ON workflows.workflow_executions(workflow_name, execution_date DESC)
        """)
        
        await self.execute("""
            CREATE INDEX IF NOT EXISTS idx_workflow_executions_status 
            ON workflows.workflow_executions(workflow_status, started_at DESC)
        """)
        
        await self.execute("""
            CREATE INDEX IF NOT EXISTS idx_workflow_tasks_execution_id 
            ON workflows.workflow_tasks(workflow_execution_id, task_order)
        """)
    
    async def create_schema_if_not_exists(self, schema_name: str):
        """Create schema if it doesn't exist"""
        await self.execute(f"CREATE SCHEMA IF NOT EXISTS {schema_name}")
    
    async def create_workflow_execution(self, workflow_name: str, workflow_type: str,
                                      execution_date: date, **kwargs) -> str:
        """Create workflow execution record"""
        result = await self.execute_returning("""
            INSERT INTO workflows.workflow_executions
            (workflow_name, workflow_type, execution_date, total_tasks, execution_context)
            VALUES ($1, $2, $3, $4, $5)
            RETURNING execution_id
        """, workflow_name, workflow_type, execution_date,
        kwargs.get('total_tasks', 0), 
        json.dumps(kwargs.get('execution_context')) if kwargs.get('execution_context') else None)
        
        return str(result['execution_id']) if result else None
    
    async def update_workflow_execution(self, execution_id: str, status: str = None,
                                      completed_at: datetime = None, completed_tasks: int = None,
                                      failed_tasks: int = None, error_message: str = None):
        """Update workflow execution record"""
        updates = []
        params = [execution_id]
        param_count = 1
        
        if status:
            param_count += 1
            updates.append(f"workflow_status = ${param_count}")
            params.append(status)
        
        if completed_at:
            param_count += 1
            updates.append(f"completed_at = ${param_count}")
            params.append(completed_at)
        
        if completed_tasks is not None:
            param_count += 1
            updates.append(f"completed_tasks = ${param_count}")
            params.append(completed_tasks)
        
        if failed_tasks is not None:
            param_count += 1
            updates.append(f"failed_tasks = ${param_count}")
            params.append(failed_tasks)
        
        if error_message:
            param_count += 1
            updates.append(f"error_message = ${param_count}")
            params.append(error_message)
        
        if updates:
            query = f"""
                UPDATE workflows.workflow_executions 
                SET {', '.join(updates)}
                WHERE execution_id = $1
            """
            await self.execute(query, *params)
    
    async def create_workflow_task(self, workflow_execution_id: str, task_name: str,
                                 task_order: int = 0, started_at: datetime = None) -> str:
        """Create workflow task record"""
        if started_at is None:
            started_at = datetime.utcnow()
        
        result = await self.execute_returning("""
            INSERT INTO workflows.workflow_tasks
            (workflow_execution_id, task_name, task_order, started_at)
            VALUES ($1, $2, $3, $4)
            RETURNING task_id
        """, workflow_execution_id, task_name, task_order, started_at)
        
        return str(result['task_id']) if result else None
    
    async def update_workflow_task(self, task_id: str, status: str = None,
                                 completed_at: datetime = None, duration_seconds: int = None,
                                 task_result: Any = None, error_message: str = None):
        """Update workflow task record"""
        updates = []
        params = [task_id]
        param_count = 1
        
        if status:
            param_count += 1
            updates.append(f"task_status = ${param_count}")
            params.append(status)
        
        if completed_at:
            param_count += 1
            updates.append(f"completed_at = ${param_count}")
            params.append(completed_at)
        
        if duration_seconds is not None:
            param_count += 1
            updates.append(f"duration_seconds = ${param_count}")
            params.append(duration_seconds)
        
        if task_result is not None:
            param_count += 1
            updates.append(f"task_result = ${param_count}")
            params.append(json.dumps(task_result) if not isinstance(task_result, str) else task_result)
        
        if error_message:
            param_count += 1
            updates.append(f"error_message = ${param_count}")
            params.append(error_message)
        
        if updates:
            query = f"""
                UPDATE workflows.workflow_tasks 
                SET {', '.join(updates)}
                WHERE task_id = $1
            """
            await self.execute(query, *params)
    
    async def get_workflow_execution(self, execution_id: str) -> Optional[Dict[str, Any]]:
        """Get workflow execution by ID"""
        return await self.fetch_one("""
            SELECT * FROM workflows.workflow_executions
            WHERE execution_id = $1
        """, execution_id)
    
    async def get_workflow_executions(self, workflow_name: str = None,
                                    execution_date: date = None,
                                    limit: int = 50) -> List[Dict[str, Any]]:
        """Get workflow executions with optional filtering"""
        conditions = []
        params = []
        param_count = 0
        
        if workflow_name:
            param_count += 1
            conditions.append(f"workflow_name = ${param_count}")
            params.append(workflow_name)
        
        if execution_date:
            param_count += 1
            conditions.append(f"execution_date = ${param_count}")
            params.append(execution_date)
        
        where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""
        param_count += 1
        
        query = f"""
            SELECT * FROM workflows.workflow_executions
            {where_clause}
            ORDER BY started_at DESC
            LIMIT ${param_count}
        """
        params.append(limit)
        
        return await self.fetch_all(query, *params)
    
    async def get_workflow_tasks(self, workflow_execution_id: str) -> List[Dict[str, Any]]:
        """Get all tasks for a workflow execution"""
        return await self.fetch_all("""
            SELECT * FROM workflows.workflow_tasks
            WHERE workflow_execution_id = $1
            ORDER BY task_order, created_at
        """, workflow_execution_id)
    
    async def get_workflow_summary(self, workflow_name: str, days_back: int = 30) -> Dict[str, Any]:
        """Get workflow execution summary statistics"""
        cutoff_date = date.today() - timedelta(days=days_back)
        
        summary = await self.fetch_one("""
            SELECT 
                COUNT(*) as total_executions,
                COUNT(*) FILTER (WHERE workflow_status = 'SUCCESS') as successful_executions,
                COUNT(*) FILTER (WHERE workflow_status = 'FAILED') as failed_executions,
                COUNT(*) FILTER (WHERE workflow_status = 'RUNNING') as running_executions,
                AVG(EXTRACT(EPOCH FROM (completed_at - started_at))) as avg_duration_seconds,
                MAX(started_at) as last_execution
            FROM workflows.workflow_executions
            WHERE workflow_name = $1 AND execution_date >= $2
        """, workflow_name, cutoff_date)
        
        return summary if summary else {}
    
    async def cleanup_old_executions(self, days_to_keep: int = 90) -> int:
        """Clean up old workflow execution records"""
        cutoff_date = date.today() - timedelta(days=days_to_keep)
        
        result = await self.execute("""
            DELETE FROM workflows.workflow_executions
            WHERE execution_date < $1 AND workflow_status IN ('SUCCESS', 'FAILED')
        """, cutoff_date)
        
        # Parse the result to get the number of deleted rows
        if result.startswith('DELETE '):
            return int(result.split(' ')[1])
        return 0
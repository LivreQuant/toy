# db/managers/workflow_manager.py
from typing import Dict, List, Any, Optional
from datetime import date, datetime
from .base_manager import BaseManager

class WorkflowManager(BaseManager):
    """Manages workflow execution database operations"""
    
    async def initialize_tables(self):
        """Create workflow tables"""
        await self.create_schema_if_not_exists('workflows')
        
        # Workflow executions
        await self.execute("""
            CREATE TABLE IF NOT EXISTS workflows.workflow_executions (
                execution_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                workflow_name VARCHAR(200) NOT NULL,
                workflow_type VARCHAR(100) NOT NULL,
                execution_date DATE NOT NULL,
                workflow_status VARCHAR(20) DEFAULT 'PENDING',
                started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                completed_at TIMESTAMP WITH TIME ZONE,
                total_tasks INTEGER DEFAULT 0,
                completed_tasks INTEGER DEFAULT 0,
                failed_tasks INTEGER DEFAULT 0,
                execution_context JSONB,
                error_message TEXT
            )
        """)
        
        # Workflow tasks
        await self.execute("""
            CREATE TABLE IF NOT EXISTS workflows.workflow_tasks (
                task_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                workflow_execution_id UUID REFERENCES workflows.workflow_executions(execution_id),
                task_name VARCHAR(200) NOT NULL,
                task_order INTEGER NOT NULL,
                task_status VARCHAR(20) DEFAULT 'PENDING',
                started_at TIMESTAMP WITH TIME ZONE,
                completed_at TIMESTAMP WITH TIME ZONE,
                duration_seconds INTEGER,
                task_result JSONB,
                error_message TEXT
            )
        """)
    
    async def create_workflow_execution(self, workflow_name: str, workflow_type: str,
                                      execution_date: date, **kwargs) -> str:
        """Create workflow execution record"""
        query = """
            INSERT INTO workflows.workflow_executions
            (workflow_name, workflow_type, execution_date, total_tasks, execution_context)
            VALUES ($1, $2, $3, $4, $5)
            RETURNING execution_id
        """
        
        result = await self.execute_returning(
            query, workflow_name, workflow_type, execution_date,
            kwargs.get('total_tasks', 0), kwargs.get('execution_context')
        )
        
        return str(result['execution_id']) if result else None
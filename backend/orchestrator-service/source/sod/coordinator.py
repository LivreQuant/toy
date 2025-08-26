# source/sod/coordinator.py
import logging
from datetime import datetime
from typing import Dict, Any
from workflows.workflow_engine import WorkflowEngine, WorkflowResult
from workflows.sod_workflow import create_sod_workflow
from sod.universe.universe_builder import UniverseBuilder
from sod.risk_model.risk_calculator import RiskCalculator
from sod.corporate_actions.ca_processor import CorporateActionsProcessor
from sod.reference_data.security_master import SecurityMasterManager
from sod.reconciliation.position_reconciler import PositionReconciler

logger = logging.getLogger(__name__)

class SODCoordinator:
    """Coordinates Start of Day operations"""
    
    def __init__(self, orchestrator):
        self.orchestrator = orchestrator
        self.workflow_engine = WorkflowEngine(orchestrator.db_manager)
        
        # SOD components
        self.universe_builder = UniverseBuilder(orchestrator.db_manager)
        self.risk_calculator = RiskCalculator(orchestrator.db_manager)
        self.ca_processor = CorporateActionsProcessor(orchestrator.db_manager)
        self.security_master = SecurityMasterManager(orchestrator.db_manager)
        self.position_reconciler = PositionReconciler(orchestrator.db_manager)
        
    async def initialize(self):
        """Initialize SOD coordinator and components"""
        await self.workflow_engine.initialize()
        
        # Register SOD workflow
        sod_tasks = create_sod_workflow()
        self.workflow_engine.register_workflow("sod_main", sod_tasks)
        
        # Initialize components
        await self.universe_builder.initialize()
        await self.risk_calculator.initialize()
        await self.ca_processor.initialize()
        await self.security_master.initialize()
        await self.position_reconciler.initialize()
        
        logger.info("🌅 SOD Coordinator initialized")
    
    async def execute_sod_workflow(self) -> WorkflowResult:
        """Execute the complete SOD workflow"""
        logger.info("🚀 Starting SOD workflow execution")
        start_time = datetime.utcnow()
        
        try:
            # Log operation start
            await self.orchestrator.state_manager.save_operation_log(
                "SOD", "STARTED", start_time
            )
            
            # Create context with orchestrator reference
            context = {
                "orchestrator": self.orchestrator,
                "sod_coordinator": self,
                "execution_date": datetime.utcnow().date(),
                "start_time": start_time,
                "workflow_type": "SOD"
            }
            
            # Execute workflow
            result = await self.workflow_engine.execute_workflow("sod_main", context)
            end_time = datetime.utcnow()
            
            # Handle workflow completion
            if result.success:
                # Save SOD completion state
                await self.orchestrator.state_manager.save_sod_completion(
                    end_time,
                    {
                        "execution_time": result.execution_time, 
                        "task_results": result.task_results,
                        "workflow_execution_id": result.workflow_execution_id
                    }
                )
                
                # Log successful operation
                await self.orchestrator.state_manager.save_operation_log(
                    "SOD", "SUCCESS", start_time, end_time,
                    {
                        "tasks_completed": result.completed_tasks,
                        "execution_time": result.execution_time,
                        "workflow_execution_id": result.workflow_execution_id
                    }
                )
                
                logger.info(f"✅ SOD workflow completed successfully in {result.execution_time:.2f}s")
            else:
                # Log failure
                await self.orchestrator.state_manager.save_operation_log(
                    "SOD", "FAILED", start_time, end_time,
                    {
                        "error": result.error, 
                        "failed_tasks": result.failed_tasks,
                        "completed_tasks": result.completed_tasks,
                        "workflow_execution_id": result.workflow_execution_id
                    }
                )
                
                # Create system alert for SOD failure
                if hasattr(self.orchestrator.db_manager, 'state'):
                    await self.orchestrator.db_manager.state.create_system_alert(
                        alert_type="SOD_FAILURE",
                        severity="CRITICAL",
                        title="SOD Workflow Failed",
                        message=f"SOD workflow failed with error: {result.error}",
                        alert_data={
                            "workflow_execution_id": result.workflow_execution_id,
                            "failed_tasks": result.failed_tasks,
                            "execution_time": result.execution_time
                        }
                    )
                
                logger.error(f"❌ SOD workflow failed: {result.error}")
            
            return result
            
        except Exception as e:
            end_time = datetime.utcnow()
            logger.error(f"❌ SOD workflow execution failed: {e}", exc_info=True)
            
            # Log error
            await self.orchestrator.state_manager.save_operation_log(
                "SOD", "ERROR", start_time, end_time,
                {"error": str(e)}
            )
            
            # Save error state
            await self.orchestrator.state_manager.save_error_state(
                f"SOD workflow execution failed: {str(e)}"
            )
            
            return WorkflowResult(
                success=False,
                execution_time=(end_time - start_time).total_seconds(),
                completed_tasks=0,
                failed_tasks=1,
                error=str(e)
            )
    
    async def get_sod_status(self) -> Dict[str, Any]:
        """Get current SOD status"""
        if hasattr(self.orchestrator.db_manager, 'workflows'):
            recent_executions = await self.orchestrator.db_manager.workflows.get_workflow_executions(
                workflow_name="sod_main",
                limit=1
            )
            
            if recent_executions:
                latest = recent_executions[0]
                return {
                    "last_execution": {
                        "execution_id": latest["execution_id"],
                        "status": latest["workflow_status"],
                        "started_at": latest["started_at"],
                        "completed_at": latest["completed_at"],
                        "execution_time": latest.get("execution_time"),
                        "completed_tasks": latest["completed_tasks"],
                        "failed_tasks": latest["failed_tasks"]
                    },
                    "workflow_status": self.workflow_engine.get_workflow_status("sod_main")
                }
        
        return {
            "last_execution": None,
            "workflow_status": self.workflow_engine.get_workflow_status("sod_main")
        }
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
        self.workflow_engine = WorkflowEngine()
        
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
            # Create context with orchestrator reference
            context = {
                "orchestrator": self.orchestrator,
                "sod_coordinator": self,
                "execution_date": datetime.utcnow().date(),
                "start_time": start_time
            }
            
            # Execute workflow
            result = await self.workflow_engine.execute_workflow("sod_main", context)
            
            # Save SOD completion state
            if result.success:
                await self.orchestrator.state_manager.save_sod_completion(
                    datetime.utcnow(),
                    {"execution_time": result.execution_time, "task_results": result.task_results}
                )
                
                # Log operation
                await self.orchestrator.state_manager.save_operation_log(
                    "SOD", "SUCCESS", start_time, datetime.utcnow(),
                    {"tasks_completed": result.completed_tasks}
                )
            else:
                # Log failure
                await self.orchestrator.state_manager.save_operation_log(
                    "SOD", "FAILED", start_time, datetime.utcnow(),
                    {"error": result.error, "failed_tasks": result.failed_tasks}
                )
            
            return result
            
        except Exception as e:
            logger.error(f"❌ SOD workflow execution failed: {e}", exc_info=True)
            
            # Log failure
            await self.orchestrator.state_manager.save_operation_log(
                "SOD", "ERROR", start_time, datetime.utcnow(),
                {"error": str(e)}
            )
            
            return WorkflowResult(
                success=False,
                execution_time=(datetime.utcnow() - start_time).total_seconds(),
                completed_tasks=0,
                failed_tasks=1,
                error=str(e)
            )
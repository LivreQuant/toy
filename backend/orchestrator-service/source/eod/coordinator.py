# source/eod/coordinator.py
import logging
from datetime import datetime
from typing import Dict, Any
from workflows.workflow_engine import WorkflowEngine, WorkflowResult
from workflows.eod_workflow import create_eod_workflow
from eod.settlement.trade_settler import TradeSettler
from eod.marking.position_marker import PositionMarker
from eod.pnl.pnl_calculator import PnLCalculator
from eod.risk_metrics.risk_reporter import RiskReporter
from eod.reporting.report_generator import ReportGenerator
from eod.archival.data_archiver import DataArchiver

logger = logging.getLogger(__name__)

class EODCoordinator:
   """Coordinates End of Day operations"""
   
   def __init__(self, orchestrator):
       self.orchestrator = orchestrator
       self.workflow_engine = WorkflowEngine(orchestrator.db_manager)
       
       # EOD components
       self.trade_settler = TradeSettler(orchestrator.db_manager)
       self.position_marker = PositionMarker(orchestrator.db_manager)
       self.pnl_calculator = PnLCalculator(orchestrator.db_manager)
       self.risk_reporter = RiskReporter(orchestrator.db_manager)
       self.report_generator = ReportGenerator(orchestrator.db_manager)
       self.data_archiver = DataArchiver(orchestrator.db_manager)
       
   async def initialize(self):
       """Initialize EOD coordinator and components"""
       await self.workflow_engine.initialize()
       
       # Register EOD workflow
       eod_tasks = create_eod_workflow()
       self.workflow_engine.register_workflow("eod_main", eod_tasks)
       
       # Initialize components
       await self.trade_settler.initialize()
       await self.position_marker.initialize()
       await self.pnl_calculator.initialize()
       await self.risk_reporter.initialize()
       await self.report_generator.initialize()
       await self.data_archiver.initialize()
       
       logger.info("🌆 EOD Coordinator initialized")
   
   async def execute_eod_workflow(self) -> WorkflowResult:
       """Execute the complete EOD workflow"""
       logger.info("🚀 Starting EOD workflow execution")
       start_time = datetime.utcnow()
       
       try:
           # Log operation start
           await self.orchestrator.state_manager.save_operation_log(
               "EOD", "STARTED", start_time
           )
           
           # Create context with orchestrator reference
           context = {
               "orchestrator": self.orchestrator,
               "eod_coordinator": self,
               "execution_date": datetime.utcnow().date(),
               "start_time": start_time,
               "workflow_type": "EOD"
           }
           
           # Execute workflow
           result = await self.workflow_engine.execute_workflow("eod_main", context)
           end_time = datetime.utcnow()
           
           # Handle workflow completion
           if result.success:
               # Save EOD completion state
               await self.orchestrator.state_manager.save_eod_completion(
                   end_time,
                   {
                       "execution_time": result.execution_time,
                       "task_results": result.task_results,
                       "workflow_execution_id": result.workflow_execution_id
                   }
               )
               
               # Log successful operation
               await self.orchestrator.state_manager.save_operation_log(
                   "EOD", "SUCCESS", start_time, end_time,
                   {
                       "tasks_completed": result.completed_tasks,
                       "execution_time": result.execution_time,
                       "workflow_execution_id": result.workflow_execution_id
                   }
               )
               
               # Create recovery checkpoint for EOD completion
               if hasattr(self.orchestrator.db_manager, 'state'):
                   await self.orchestrator.db_manager.state.create_recovery_checkpoint(
                       checkpoint_name=f"eod_complete_{datetime.utcnow().date()}",
                       checkpoint_type="EOD_COMPLETE",
                       checkpoint_data={
                           "completion_time": end_time.isoformat(),
                           "workflow_execution_id": result.workflow_execution_id,
                           "tasks_completed": result.completed_tasks,
                           "execution_time": result.execution_time
                       }
                   )
               
               logger.info(f"✅ EOD workflow completed successfully in {result.execution_time:.2f}s")
           else:
               # Log failure
               await self.orchestrator.state_manager.save_operation_log(
                   "EOD", "FAILED", start_time, end_time,
                   {
                       "error": result.error,
                       "failed_tasks": result.failed_tasks,
                       "completed_tasks": result.completed_tasks,
                       "workflow_execution_id": result.workflow_execution_id
                   }
               )
               
               # Create system alert for EOD failure
               if hasattr(self.orchestrator.db_manager, 'state'):
                   await self.orchestrator.db_manager.state.create_system_alert(
                       alert_type="EOD_FAILURE",
                       severity="CRITICAL",
                       title="EOD Workflow Failed",
                       message=f"EOD workflow failed with error: {result.error}",
                       alert_data={
                           "workflow_execution_id": result.workflow_execution_id,
                           "failed_tasks": result.failed_tasks,
                           "execution_time": result.execution_time
                       }
                   )
               
               logger.error(f"❌ EOD workflow failed: {result.error}")
           
           return result
           
       except Exception as e:
           end_time = datetime.utcnow()
           logger.error(f"❌ EOD workflow execution failed: {e}", exc_info=True)
           
           # Log error
           await self.orchestrator.state_manager.save_operation_log(
               "EOD", "ERROR", start_time, end_time,
               {"error": str(e)}
           )
           
           # Save error state
           await self.orchestrator.state_manager.save_error_state(
               f"EOD workflow execution failed: {str(e)}"
           )
           
           return WorkflowResult(
               success=False,
               execution_time=(end_time - start_time).total_seconds(),
               completed_tasks=0,
               failed_tasks=1,
               error=str(e)
           )
   
   async def get_eod_status(self) -> Dict[str, Any]:
       """Get current EOD status"""
       if hasattr(self.orchestrator.db_manager, 'workflows'):
           recent_executions = await self.orchestrator.db_manager.workflows.get_workflow_executions(
               workflow_name="eod_main",
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
                   "workflow_status": self.workflow_engine.get_workflow_status("eod_main")
               }
       
       return {
           "last_execution": None,
           "workflow_status": self.workflow_engine.get_workflow_status("eod_main")
       }
   
   async def generate_eod_reports(self) -> Dict[str, Any]:
       """Generate all EOD reports"""
       logger.info("📊 Generating EOD reports")
       
       try:
           # Get latest workflow execution for report context
           report_context = {
               "execution_date": datetime.utcnow().date(),
               "generated_at": datetime.utcnow()
           }
           
           if hasattr(self.orchestrator.db_manager, 'workflows'):
               recent_executions = await self.orchestrator.db_manager.workflows.get_workflow_executions(
                   workflow_name="eod_main",
                   limit=1
               )
               if recent_executions:
                   report_context["workflow_execution_id"] = recent_executions[0]["execution_id"]
           
           # Generate reports through the report generator
           reports = await self.report_generator.generate_all_reports(report_context)
           
           logger.info(f"✅ Generated {len(reports)} EOD reports")
           return reports
           
       except Exception as e:
           logger.error(f"❌ Failed to generate EOD reports: {e}", exc_info=True)
           return {"error": str(e)}
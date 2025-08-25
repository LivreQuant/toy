# source/eod/coordinator.py
import logging
from datetime import datetime, date
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
        self.workflow_engine = WorkflowEngine()
        
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
            # Create context with orchestrator reference
            context = {
                "orchestrator": self.orchestrator,
                "eod_coordinator": self,
                "execution_date": datetime.utcnow().date(),
                "start_time": start_time
            }
            
            # Execute workflow
            result = await self.workflow_engine.execute_workflow("eod_main", context)
            
            # Save EOD completion state
            if result.success:
                await self.orchestrator.state_manager.save_eod_completion(
                    datetime.utcnow(),
                    {"execution_time": result.execution_time, "task_results": result.task_results}
                )
                
                # Log operation
                await self.orchestrator.state_manager.save_operation_log(
                    "EOD", "SUCCESS", start_time, datetime.utcnow(),
                    {"tasks_completed": result.completed_tasks}
                )
            else:
                # Log failure
                await self.orchestrator.state_manager.save_operation_log(
                    "EOD", "FAILED", start_time, datetime.utcnow(),
                    {"error": result.error, "failed_tasks": result.failed_tasks}
                )
            
            return result
            
        except Exception as e:
            logger.error(f"❌ EOD workflow execution failed: {e}", exc_info=True)
            
            # Log failure
            await self.orchestrator.state_manager.save_operation_log(
                "EOD", "ERROR", start_time, datetime.utcnow(),
                {"error": str(e)}
            )
            
            return WorkflowResult(
                success=False,
                execution_time=(datetime.utcnow() - start_time).total_seconds(),
                completed_tasks=0,
                failed_tasks=1,
                error=str(e)
            )
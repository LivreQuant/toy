# source/eod/coordinator.py
import logging
from datetime import datetime

from source.workflows.workflow_engine import WorkflowEngine, WorkflowResult
from source.workflows.eod_workflow import create_eod_workflow
from source.eod.reporting.report_generator import ReportGenerator

logger = logging.getLogger(__name__)


class EODCoordinator:
    """Coordinates End of Day operations"""

    def __init__(self, orchestrator):
        self.orchestrator = orchestrator
        self.workflow_engine = WorkflowEngine(orchestrator.db_manager)

        # EOD components
        self.report_generator = ReportGenerator(orchestrator.db_manager)

    async def initialize(self):
        """Initialize EOD coordinator and components"""
        await self.workflow_engine.initialize()

        # Register EOD workflow
        eod_tasks = create_eod_workflow()
        self.workflow_engine.register_workflow("eod_main", eod_tasks)

        # Initialize components
        await self.report_generator.initialize()

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

            return WorkflowResult(
                success=False,
                execution_time=(end_time - start_time).total_seconds(),
                completed_tasks=0,
                failed_tasks=1,
                error=str(e)
            )
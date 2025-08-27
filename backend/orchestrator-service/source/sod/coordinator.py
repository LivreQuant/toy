# source/sod/coordinator.py
import logging
from datetime import datetime

from source.workflows.workflow_engine import WorkflowEngine, WorkflowResult
from source.workflows.sod_workflow import create_sod_workflow

from source.sod.corporate_actions.ca_processor import CorporateActionsProcessor
from source.sod.reference_data.security_master import SecurityMasterManager
from source.sod.reference_data.raw_data_validator import RawDataValidator
from source.sod.reconciliation.portfolios_reconciler import PortfoliosReconciler

# NEW: Import the new system components
from source.sod.system.health_checker import SystemHealthChecker
from source.sod.system.database_validator import DatabaseValidator
from source.sod.system.readiness_validator import SystemReadinessValidator

logger = logging.getLogger(__name__)


class SODCoordinator:
    """Coordinates Start of Day operations"""

    def __init__(self, orchestrator):
        self.orchestrator = orchestrator
        self.workflow_engine = WorkflowEngine(orchestrator.db_manager)

        # SOD components
        self.ca_processor = CorporateActionsProcessor(orchestrator.db_manager)
        self.security_master = SecurityMasterManager(orchestrator.db_manager)
        self.portfolios_reconciler = PortfoliosReconciler(orchestrator.db_manager)

        # NEW: System validation components
        self.system_health_checker = SystemHealthChecker(orchestrator.db_manager, orchestrator.k8s_manager)
        self.database_validator = DatabaseValidator(orchestrator.db_manager)
        self.raw_data_validator = RawDataValidator(orchestrator.db_manager)
        self.system_readiness_validator = SystemReadinessValidator(orchestrator.db_manager)

    async def initialize(self):
        """Initialize SOD coordinator and components"""
        await self.workflow_engine.initialize()

        # Register SOD workflow
        sod_tasks = create_sod_workflow()
        self.workflow_engine.register_workflow("sod_main", sod_tasks)

        # Initialize all SOD components
        components = [
            ("Corporate Actions Processor", self.ca_processor),
            ("Security Master Manager", self.security_master),
            ("Portfolios Reconciler", self.portfolios_reconciler),
            ("System Health Checker", self.system_health_checker),
            ("Database Validator", self.database_validator),
            ("Raw Data Validator", self.raw_data_validator),
            ("System Readiness Validator", self.system_readiness_validator)
        ]

        for name, component in components:
            try:
                await component.initialize()
                logger.info(f"✅ {name} initialized")
            except Exception as e:
                logger.error(f"❌ Failed to initialize {name}: {e}")

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

            return WorkflowResult(
                success=False,
                execution_time=(end_time - start_time).total_seconds(),
                completed_tasks=0,
                failed_tasks=1,
                error=str(e)
            )
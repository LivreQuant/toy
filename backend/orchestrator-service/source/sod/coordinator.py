# source/sod/coordinator.py
import logging
from datetime import datetime
from typing import Dict, Any, List
from workflows.workflow_engine import WorkflowEngine, WorkflowResult
from workflows.sod_workflow import create_sod_workflow, create_debug_sod_workflow, create_minimal_sod_workflow
from sod.universe.universe_builder import UniverseBuilder
from sod.corporate_actions.ca_processor import CorporateActionsProcessor
from sod.reference_data.security_master import SecurityMasterManager
from sod.reconciliation.position_reconciler import PositionReconciler

logger = logging.getLogger(__name__)

class SODCoordinator:
    """Coordinates Start of Day operations with enhanced debugging and skip capabilities"""
    
    def __init__(self, orchestrator):
        self.orchestrator = orchestrator
        self.workflow_engine = WorkflowEngine(orchestrator.db_manager)
        
        # SOD components
        self.universe_builder = UniverseBuilder(orchestrator.db_manager)
        self.risk_calculator = RiskCalculator(orchestrator.db_manager)
        self.ca_processor = CorporateActionsProcessor(orchestrator.db_manager)
        self.security_master = SecurityMasterManager(orchestrator.db_manager)
        self.position_reconciler = PositionReconciler(orchestrator.db_manager)
        
        # Debug and skip configuration
        self.debug_mode = False
        self.custom_skip_config = {}
        self.workflow_type = "standard"  # standard, debug, minimal
        
    async def initialize(self):
        """Initialize SOD coordinator and components"""
        await self.workflow_engine.initialize()
        
        # Register different workflow variants
        await self._register_workflow_variants()
        
        # Initialize SOD components
        await self._initialize_sod_components()
        
        logger.info("🌅 SOD Coordinator initialized with workflow variants")
    
    async def _register_workflow_variants(self):
        """Register different SOD workflow variants"""
        # Standard production workflow
        standard_tasks = create_sod_workflow(debug_mode=False)
        self.workflow_engine.register_workflow("sod_standard", standard_tasks)
        
        # Debug workflow with many tasks skipped
        debug_tasks = create_debug_sod_workflow()
        self.workflow_engine.register_workflow("sod_debug", debug_tasks)
        
        # Minimal workflow for quick testing
        minimal_tasks = create_minimal_sod_workflow()
        self.workflow_engine.register_workflow("sod_minimal", minimal_tasks)
        
        # Register the main workflow (defaults to standard)
        self.workflow_engine.register_workflow("sod_main", standard_tasks)
        
        logger.info("📋 Registered SOD workflow variants: standard, debug, minimal")
    
    async def _initialize_sod_components(self):
        """Initialize all SOD components"""
        components = [
            ("Universe Builder", self.universe_builder),
            ("Corporate Actions Processor", self.ca_processor),
            ("Security Master Manager", self.security_master),
            ("Position Reconciler", self.position_reconciler)
        ]
        
        for name, component in components:
            try:
                await component.initialize()
                logger.info(f"✅ {name} initialized")
            except Exception as e:
                logger.error(f"❌ Failed to initialize {name}: {e}")
                # Continue initialization even if some components fail
    
    def configure_debug_mode(self, debug_mode: bool = True, skip_config: Dict[str, bool] = None):
        """Configure debug mode and task skipping for testing
        
        Args:
            debug_mode: Enable debug mode for simplified operations
            skip_config: Dict of task_id -> skip boolean for fine-grained control
        """
        self.debug_mode = debug_mode
        
        if skip_config:
            self.custom_skip_config = skip_config
            self.workflow_engine.configure_task_skipping(skip_config)
        
        # Set workflow type based on debug mode
        if debug_mode:
            self.workflow_type = "debug"
            logger.info("🚧 SOD Coordinator: Debug mode enabled")
        else:
            self.workflow_type = "standard"
            logger.info("🏭 SOD Coordinator: Production mode enabled")
    
    def set_workflow_type(self, workflow_type: str):
        """Set the workflow type to use
        
        Args:
            workflow_type: One of 'standard', 'debug', 'minimal'
        """
        valid_types = ['standard', 'debug', 'minimal']
        if workflow_type not in valid_types:
            raise ValueError(f"Invalid workflow type '{workflow_type}'. Must be one of: {valid_types}")
        
        self.workflow_type = workflow_type
        logger.info(f"🔄 SOD Coordinator: Workflow type set to '{workflow_type}'")
    
    def skip_tasks(self, task_ids: List[str]):
        """Skip specific tasks for debugging"""
        skip_config = {task_id: True for task_id in task_ids}
        self.custom_skip_config.update(skip_config)
        self.workflow_engine.configure_task_skipping(skip_config)
        logger.info(f"🚧 SOD Coordinator: Configured to skip tasks: {task_ids}")
    
    def unskip_tasks(self, task_ids: List[str]):
        """Unskip specific tasks"""
        skip_config = {task_id: False for task_id in task_ids}
        self.custom_skip_config.update(skip_config)
        self.workflow_engine.configure_task_skipping(skip_config)
        logger.info(f"🔄 SOD Coordinator: Configured to unskip tasks: {task_ids}")
    
    def reset_skip_config(self):
        """Reset all skip configurations"""
        self.custom_skip_config = {}
        self.workflow_engine.configure_task_skipping({})
        logger.info("🔄 SOD Coordinator: Reset all skip configurations")
    
    def get_skip_status(self) -> Dict[str, Any]:
        """Get current skip configuration status"""
        workflow_status = self.workflow_engine.get_workflow_status("sod_main")
        
        return {
            "debug_mode": self.debug_mode,
            "workflow_type": self.workflow_type,
            "custom_skip_config": self.custom_skip_config,
            "global_skip_config": self.workflow_engine.global_skip_config,
            "workflow_status": workflow_status
        }
    
    async def execute_sod_workflow(self, 
                                 workflow_type: str = None, 
                                 debug_mode: bool = None, 
                                 skip_config: Dict[str, bool] = None) -> WorkflowResult:
        """Execute the complete SOD workflow with optional debug configuration
        
        Args:
            workflow_type: Override workflow type ('standard', 'debug', 'minimal')
            debug_mode: Override debug mode setting
            skip_config: Runtime skip configuration for specific tasks
        """
        logger.info("🚀 Starting SOD workflow execution")
        start_time = datetime.utcnow()
        
        # Determine which workflow to use
        actual_workflow_type = workflow_type or self.workflow_type
        workflow_name = f"sod_{actual_workflow_type}"
        
        # Use provided debug mode or fall back to instance setting
        actual_debug_mode = debug_mode if debug_mode is not None else self.debug_mode
        
        try:
            # Log operation start
            await self.orchestrator.state_manager.save_operation_log(
                "SOD", "STARTED", start_time
            )
            
            # Create execution context
            context = {
                "orchestrator": self.orchestrator,
                "sod_coordinator": self,
                "execution_date": datetime.utcnow().date(),
                "start_time": start_time,
                "workflow_type": "SOD",
                "debug_mode": actual_debug_mode,
                "workflow_variant": actual_workflow_type,
                "skip_tasks": skip_config or self.custom_skip_config
            }
            
            # Apply any runtime skip configuration
            if skip_config:
                runtime_config = self.custom_skip_config.copy()
                runtime_config.update(skip_config)
                self.workflow_engine.configure_task_skipping(runtime_config)
            
            logger.info(f"🎯 Executing SOD workflow variant: '{actual_workflow_type}' "
                       f"(debug_mode: {actual_debug_mode})")
            
            # Execute the selected workflow
            result = await self.workflow_engine.execute_workflow(workflow_name, context)
            end_time = datetime.utcnow()
            
            # Handle workflow completion
            await self._handle_workflow_completion(result, start_time, end_time, actual_debug_mode)
            return result
            
        except Exception as e:
            end_time = datetime.utcnow()
            logger.error(f"❌ SOD workflow execution failed: {e}", exc_info=True)
            
            # Log error
            await self.orchestrator.state_manager.save_operation_log(
                "SOD", "ERROR", start_time, end_time,
                {
                    "error": str(e),
                    "workflow_type": actual_workflow_type,
                    "debug_mode": actual_debug_mode
                }
            )
            
            # Save error state
            await self.orchestrator.state_manager.save_error_state(
                f"SOD workflow execution failed: {str(e)}"
            )
            
            # Create system alert for critical failure
            if hasattr(self.orchestrator.db_manager, 'state'):
                await self.orchestrator.db_manager.state.create_system_alert(
                    alert_type="SOD_FAILURE",
                    severity="CRITICAL",
                    title="SOD Workflow Execution Failed",
                    message=f"SOD workflow '{actual_workflow_type}' failed with error: {str(e)}",
                    alert_data={
                        "workflow_type": actual_workflow_type,
                        "debug_mode": actual_debug_mode,
                        "execution_time": (end_time - start_time).total_seconds()
                    }
                )
            
            return WorkflowResult(
                success=False,
                execution_time=(end_time - start_time).total_seconds(),
                completed_tasks=0,
                failed_tasks=1,
                skipped_tasks=0,
                error=str(e)
            )
    
    async def _handle_workflow_completion(self, result: WorkflowResult, start_time: datetime, 
                                        end_time: datetime, debug_mode: bool):
        """Handle workflow completion - success or failure"""
        if result.success:
            # Save SOD completion state
            await self.orchestrator.state_manager.save_sod_completion(
                end_time,
                {
                    "execution_time": result.execution_time,
                    "task_results": result.task_results,
                    "workflow_execution_id": result.workflow_execution_id,
                    "completed_tasks": result.completed_tasks,
                    "failed_tasks": result.failed_tasks,
                    "skipped_tasks": result.skipped_tasks,
                    "debug_mode": debug_mode,
                    "workflow_type": self.workflow_type
                }
            )
            
            # Log successful operation
            await self.orchestrator.state_manager.save_operation_log(
                "SOD", "SUCCESS", start_time, end_time,
                {
                    "tasks_completed": result.completed_tasks,
                    "tasks_skipped": result.skipped_tasks,
                    "tasks_failed": result.failed_tasks,
                    "execution_time": result.execution_time,
                    "workflow_execution_id": result.workflow_execution_id,
                    "debug_mode": debug_mode,
                    "workflow_type": self.workflow_type
                }
            )
            
            # Create success checkpoint
            if hasattr(self.orchestrator.db_manager, 'state'):
                await self.orchestrator.db_manager.state.create_recovery_checkpoint(
                    checkpoint_name=f"sod_success_{datetime.utcnow().date()}",
                    checkpoint_type="SOD_COMPLETE",
                    checkpoint_data={
                        "completion_time": end_time.isoformat(),
                        "workflow_execution_id": result.workflow_execution_id,
                        "tasks_completed": result.completed_tasks,
                        "tasks_skipped": result.skipped_tasks,
                        "debug_mode": debug_mode
                    }
                )
            
            skip_info = f", Skipped: {result.skipped_tasks}" if result.skipped_tasks > 0 else ""
            logger.info(f"✅ SOD workflow completed successfully in {result.execution_time:.2f}s "
                        f"(Completed: {result.completed_tasks}, Failed: {result.failed_tasks}{skip_info})")
        else:
            # Log failure
            await self.orchestrator.state_manager.save_operation_log(
                "SOD", "FAILED", start_time, end_time,
                {
                    "error": result.error,
                    "failed_tasks": result.failed_tasks,
                    "completed_tasks": result.completed_tasks,
                    "skipped_tasks": result.skipped_tasks,
                    "workflow_execution_id": result.workflow_execution_id,
                    "debug_mode": debug_mode,
                    "workflow_type": self.workflow_type
                }
            )
            
            # Create system alert for failure
            if hasattr(self.orchestrator.db_manager, 'state'):
                await self.orchestrator.db_manager.state.create_system_alert(
                    alert_type="SOD_FAILURE",
                    severity="CRITICAL" if result.failed_tasks > 0 else "HIGH",
                    title="SOD Workflow Failed",
                    message=f"SOD workflow failed with {result.failed_tasks} failed tasks: {result.error}",
                    alert_data={
                        "workflow_execution_id": result.workflow_execution_id,
                        "failed_tasks": result.failed_tasks,
                        "completed_tasks": result.completed_tasks,
                        "skipped_tasks": result.skipped_tasks,
                        "execution_time": result.execution_time,
                        "debug_mode": debug_mode
                    }
                )
            
            logger.error(f"❌ SOD workflow failed: {result.error} "
                        f"(Completed: {result.completed_tasks}, Failed: {result.failed_tasks}, "
                        f"Skipped: {result.skipped_tasks})")
    
    async def get_sod_status(self) -> Dict[str, Any]:
        """Get comprehensive SOD status including workflow and skip information"""
        status = {
            "coordinator_info": {
                "debug_mode": self.debug_mode,
                "workflow_type": self.workflow_type,
                "custom_skip_config": self.custom_skip_config
            },
            "workflow_engine_status": self.workflow_engine.get_workflow_status("sod_main"),
            "skip_configuration": self.get_skip_status(),
            "last_execution": None,
            "component_status": {}
        }
        
        # Get latest workflow execution info
        if hasattr(self.orchestrator.db_manager, 'workflows'):
            try:
                recent_executions = await self.orchestrator.db_manager.workflows.get_workflow_executions(
                    workflow_name="sod_main",
                    limit=1
                )
                
                if recent_executions:
                    latest = recent_executions[0]
                    status["last_execution"] = {
                        "execution_id": latest["execution_id"],
                        "status": latest["workflow_status"],
                        "started_at": latest["started_at"],
                        "completed_at": latest["completed_at"],
                        "total_tasks": latest["total_tasks"],
                        "completed_tasks": latest["completed_tasks"],
                        "failed_tasks": latest["failed_tasks"]
                    }
            except Exception as e:
                logger.error(f"Failed to get recent executions: {e}")
        
        # Get component status
        components = {
            "universe_builder": self.universe_builder,
            "risk_calculator": self.risk_calculator,
            "ca_processor": self.ca_processor,
            "security_master": self.security_master,
            "position_reconciler": self.position_reconciler
        }
        
        for name, component in components.items():
            try:
                # Most components would have a get_status method
                if hasattr(component, 'get_status'):
                    status["component_status"][name] = await component.get_status()
                else:
                    status["component_status"][name] = {"status": "initialized"}
            except Exception as e:
                status["component_status"][name] = {"status": "error", "error": str(e)}
        
        return status
    
    async def run_debug_workflow(self, skip_tasks: List[str] = None) -> WorkflowResult:
        """Run SOD workflow in debug mode with optional task skipping
        
        Args:
            skip_tasks: List of task IDs to skip for debugging
        """
        logger.info("🚧 Running SOD workflow in debug mode")
        
        skip_config = {}
        if skip_tasks:
            skip_config = {task_id: True for task_id in skip_tasks}
            logger.info(f"🚧 Debug run will skip tasks: {skip_tasks}")
        
        return await self.execute_sod_workflow(
            workflow_type="debug",
            debug_mode=True,
            skip_config=skip_config
        )
    
    async def run_minimal_workflow(self) -> WorkflowResult:
        """Run minimal SOD workflow with only critical tasks"""
        logger.info("⚡ Running minimal SOD workflow (critical tasks only)")
        
        return await self.execute_sod_workflow(workflow_type="minimal")
    
    async def run_production_workflow(self) -> WorkflowResult:
        """Run full production SOD workflow"""
        logger.info("🏭 Running production SOD workflow (all tasks)")
        
        return await self.execute_sod_workflow(
            workflow_type="standard",
            debug_mode=False
        )
    
    def get_available_workflows(self) -> List[str]:
        """Get list of available workflow variants"""
        return ["standard", "debug", "minimal"]
    
    def get_task_list(self, workflow_type: str = None) -> List[Dict[str, Any]]:
        """Get list of tasks in a workflow with their current skip status
        
        Args:
            workflow_type: Which workflow to examine ('standard', 'debug', 'minimal')
        """
        workflow_type = workflow_type or self.workflow_type
        workflow_name = f"sod_{workflow_type}"
        
        if workflow_name not in self.workflow_engine.workflows:
            return []
        
        tasks = self.workflow_engine.workflows[workflow_name]
        
        task_list = []
        for task in tasks:
            task_info = {
                "id": task.id,
                "name": task.name,
                "priority": task.priority.name,
                "timeout_seconds": task.timeout_seconds,
                "required": task.required,
                "dependencies": task.dependencies,
                "skip": task.skip,
                "will_skip": self.workflow_engine._should_skip_task(task, {
                    "debug_mode": self.debug_mode,
                    "skip_tasks": self.custom_skip_config
                }),
                "status": task.status.value if task.status else "pending"
            }
            task_list.append(task_info)
        
        return task_list
    
    async def validate_workflow_readiness(self, workflow_type: str = None) -> Dict[str, Any]:
        """Validate that SOD coordinator is ready to execute workflow
        
        Args:
            workflow_type: Which workflow to validate ('standard', 'debug', 'minimal')
        """
        workflow_type = workflow_type or self.workflow_type
        
        validation = {
            "ready": True,
            "workflow_type": workflow_type,
            "issues": [],
            "component_status": {},
            "database_status": "unknown",
            "skip_configuration": self.get_skip_status()
        }
        
        # Check database connectivity
        try:
            if self.orchestrator and self.orchestrator.db_manager:
                await self.orchestrator.db_manager.state.fetch_one("SELECT 1")
                validation["database_status"] = "connected"
        except Exception as e:
            validation["ready"] = False
            validation["database_status"] = "disconnected"
            validation["issues"].append(f"Database connectivity issue: {e}")
        
        # Check if workflow is registered
        workflow_name = f"sod_{workflow_type}"
        if workflow_name not in self.workflow_engine.workflows:
            validation["ready"] = False
            validation["issues"].append(f"Workflow '{workflow_name}' not registered")
        
        # Check component readiness (simplified check)
        components = {
            "universe_builder": self.universe_builder,
            "risk_calculator": self.risk_calculator,
            "ca_processor": self.ca_processor,
            "security_master": self.security_master,
            "position_reconciler": self.position_reconciler
        }
        
        for name, component in components.items():
            try:
                # Basic availability check
                validation["component_status"][name] = "available" if component else "unavailable"
                if not component:
                    validation["issues"].append(f"Component {name} not available")
            except Exception as e:
                validation["component_status"][name] = f"error: {e}"
                validation["issues"].append(f"Component {name} error: {e}")
        
        # Check for potential issues with skip configuration
        if self.debug_mode and not any(self.custom_skip_config.values()):
            validation["issues"].append("Debug mode enabled but no tasks configured to skip")
        
        return validation
    
    async def generate_execution_report(self, workflow_execution_id: str = None) -> Dict[str, Any]:
        """Generate detailed execution report for a workflow run
        
        Args:
            workflow_execution_id: Specific execution to report on, or latest if None
        """
        if not workflow_execution_id:
            # Get the latest execution
            if hasattr(self.orchestrator.db_manager, 'workflows'):
                recent_executions = await self.orchestrator.db_manager.workflows.get_workflow_executions(
                    workflow_name="sod_main",
                    limit=1
                )
                if recent_executions:
                    workflow_execution_id = recent_executions[0]["execution_id"]
        
        if not workflow_execution_id:
            return {"error": "No workflow execution found"}
        
        try:
            # Get workflow execution details
            execution = await self.orchestrator.db_manager.workflows.get_workflow_execution(workflow_execution_id)
            
            # Get task details
            tasks = await self.orchestrator.db_manager.workflows.get_workflow_tasks(workflow_execution_id)
            
            # Generate report
            report = {
                "execution_id": workflow_execution_id,
                "execution_summary": execution,
                "task_details": tasks,
                "performance_metrics": {
                    "total_duration": execution.get("completed_at") - execution.get("started_at") if execution.get("completed_at") else None,
                    "average_task_duration": sum(t.get("duration_seconds", 0) for t in tasks) / len(tasks) if tasks else 0,
                    "slowest_task": max(tasks, key=lambda t: t.get("duration_seconds", 0)) if tasks else None,
                    "fastest_task": min(tasks, key=lambda t: t.get("duration_seconds", 0)) if tasks else None
                },
                "skip_analysis": {
                    "total_tasks": len(tasks),
                    "skipped_tasks": len([t for t in tasks if t.get("task_status") == "SKIPPED"]),
                    "completed_tasks": len([t for t in tasks if t.get("task_status") == "SUCCESS"]),
                    "failed_tasks": len([t for t in tasks if t.get("task_status") == "FAILED"])
                }
            }
            
            return report
            
        except Exception as e:
            logger.error(f"Failed to generate execution report: {e}")
            return {"error": f"Failed to generate report: {e}"}
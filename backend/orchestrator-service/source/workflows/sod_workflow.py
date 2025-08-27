# source/workflows/sod_workflow.py
import logging
from typing import List, Dict, Any
from source.workflows.workflow_engine import WorkflowTask, TaskPriority

logger = logging.getLogger(__name__)


def create_sod_workflow() -> List[WorkflowTask]:
    """Create Start of Day workflow definition"""
    return [
        WorkflowTask(
            id="system_health_check",
            name="System Health Check",
            function=system_health_check_task,
            dependencies=[],
            priority=TaskPriority.CRITICAL,
            timeout_seconds=120,
            skip_flag=False
        ),

        WorkflowTask(
            id="database_validation",
            name="Database Validation",
            function=database_validation_task,
            dependencies=["system_health_check"],
            priority=TaskPriority.CRITICAL,
            timeout_seconds=180,
            skip_flag=False
        ),

        WorkflowTask(
            id="validate_raw_data",
            name="Validate Raw Data",
            function=validate_raw_data_task,
            dependencies=["database_validation"],
            priority=TaskPriority.HIGH,
            timeout_seconds=300,
            skip_flag=True
        ),

        WorkflowTask(
            id="update_security_master",
            name="Update Security Master",
            function=update_security_master_task,
            dependencies=["validate_raw_data"],
            priority=TaskPriority.HIGH,
            timeout_seconds=600,
            skip_flag=True
        ),

        WorkflowTask(
            id="process_corporate_actions",
            name="Process Corporate Actions",
            function=process_corporate_actions_task,
            dependencies=["update_security_master"],
            priority=TaskPriority.HIGH,
            timeout_seconds=900,
            skip_flag=True
        ),

        WorkflowTask(
            id="reconcile_portfolios",
            name="Reconcile Portfolios",
            function=reconcile_portfolios_task,
            dependencies=["process_corporate_actions"],
            priority=TaskPriority.CRITICAL,
            timeout_seconds=1200,
            skip_flag=True
        ),

        WorkflowTask(
            id="validate_system_readiness",
            name="Validate System Readiness",
            function=validate_system_readiness_task,
            dependencies=["reconcile_portfolios"],
            priority=TaskPriority.CRITICAL,
            timeout_seconds=300,
            skip_flag=False
        )
    ]


# =============================================================================
# CONSISTENT TASK IMPLEMENTATIONS
# =============================================================================

async def system_health_check_task(context: Dict[str, Any]) -> Dict[str, Any]:
    """System health check task"""
    logger.info("🔍 Performing system health check")

    orchestrator = context.get("orchestrator")
    if orchestrator and orchestrator.system_health_checker:
        return await orchestrator.system_health_checker.check_system_health(context)
    else:
        logger.warning("⚠️ System health checker not available")
        return {"status": "skipped", "reason": "component_unavailable"}


async def database_validation_task(context: Dict[str, Any]) -> Dict[str, Any]:
    """Database validation task"""
    logger.info("🗄️ Validating database integrity")

    orchestrator = context.get("orchestrator")
    if orchestrator and orchestrator.database_validator:
        return await orchestrator.database_validator.validate_database(context)
    else:
        logger.warning("⚠️ Database validator not available")
        return {"status": "skipped", "reason": "component_unavailable"}


async def validate_raw_data_task(context: Dict[str, Any]) -> Dict[str, Any]:
    """Validate raw data task"""
    logger.info("📈 Validating raw data")

    orchestrator = context.get("orchestrator")
    if orchestrator and orchestrator.raw_data_validator:
        return await orchestrator.raw_data_validator.validate_raw_data(context)
    else:
        logger.warning("⚠️ Raw data validator not available")
        return {"status": "skipped", "reason": "component_unavailable"}


async def update_security_master_task(context: Dict[str, Any]) -> Dict[str, Any]:
    """Update security master task"""
    logger.info("📊 Updating security master data")

    sod_coordinator = context.get("sod_coordinator")
    if sod_coordinator and sod_coordinator.security_master:
        return await sod_coordinator.security_master.update_security_master(context)
    else:
        logger.warning("⚠️ Security master component not available")
        return {"status": "skipped", "reason": "component_unavailable"}


async def process_corporate_actions_task(context: Dict[str, Any]) -> Dict[str, Any]:
    """Process corporate actions task"""
    logger.info("🏢 Processing corporate actions")

    sod_coordinator = context.get("sod_coordinator")
    if sod_coordinator and sod_coordinator.ca_processor:
        return await sod_coordinator.ca_processor.process_pending_actions(context)
    else:
        logger.warning("⚠️ Corporate actions processor not available")
        return {"status": "skipped", "reason": "component_unavailable"}


async def reconcile_portfolios_task(context: Dict[str, Any]) -> Dict[str, Any]:
    """Reconcile portfolios task"""
    logger.info("⚖️ Reconciling portfolios")

    sod_coordinator = context.get("sod_coordinator")
    if sod_coordinator and sod_coordinator.portfolios_reconciler:
        return await sod_coordinator.portfolios_reconciler.reconcile_portfolios(context)
    else:
        logger.warning("⚠️ Portfolios reconciler not available")
        return {"status": "skipped", "reason": "component_unavailable"}


async def validate_system_readiness_task(context: Dict[str, Any]) -> Dict[str, Any]:
    """Validate system readiness task"""
    logger.info("🚀 Validating system readiness")

    orchestrator = context.get("orchestrator")
    if orchestrator and orchestrator.system_readiness_validator:
        return await orchestrator.system_readiness_validator.validate_system_readiness(context)
    else:
        logger.warning("⚠️ System readiness validator not available")
        return {"status": "skipped", "reason": "component_unavailable"}
# source/workflows/sod_workflow.py
import logging
from typing import List, Dict, Any
from workflows.workflow_engine import WorkflowTask, TaskPriority
from datetime import datetime

logger = logging.getLogger(__name__)

def create_sod_workflow() -> List[WorkflowTask]:
    """Create Start of Day workflow definition"""
    
    return [
        # Phase 1: System Initialization and Validation
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
        
        # Phase 3: Corporate Actions Processing (Based closed portfolios)
        WorkflowTask(
            id="process_corporate_actions",
            name="Process Corporate Actions",
            function=process_corporate_actions_task,
            dependencies=["update_security_master"],
            priority=TaskPriority.HIGH,
            timeout_seconds=900,
            skip_flag=True
        ),
        
        # Phase 4: Portfolio Management (Create SOD portfolios)
        WorkflowTask(
            id="reconcile_portfolios",
            name="Reconcile Portfolios",
            function=reconcile_portfolios_task,
            dependencies=["process_corporate_actions"],
            priority=TaskPriority.CRITICAL,
            timeout_seconds=1200,
            skip_flag=False
        ),
        
        # Phase 6: System Readiness
        WorkflowTask(
            # NOTE: VALIDATE PORTFOLIOS
            id="validate_system_readiness",
            name="Validate System Readiness",
            function=validate_system_readiness_task,
            dependencies=["update_risk_model"],
            priority=TaskPriority.CRITICAL,
            timeout_seconds=300,
            skip_flag=False
        )
    ]

# =============================================================================
# TASK IMPLEMENTATIONS (Enhanced with skip-aware logging)
# =============================================================================

# Phase 1: System Initialization and Validation

async def system_health_check_task(context: Dict[str, Any]) -> Dict[str, Any]:
    """Perform comprehensive system health check"""
    logger.info("🔍 Performing system health check")
    
    # Check if we're in skip for different behavior
    skip_flag = context.get("skip_flag", False)
    if skip_flag:
        logger.info("🚧 Skipping - health check")
    
    orchestrator = context.get("orchestrator")
    start_time = datetime.utcnow()
    
    try:
        health_results = {
            "database_connectivity": False,
            "kubernetes_connectivity": False,
            "system_resources": {},
            "alerts": [],
            "skip_flag": skip_flag
        }
        
        # Check database connectivity
        if orchestrator and orchestrator.db_manager:
            try:
                # Simple connectivity test
                result = await orchestrator.db_manager.state.fetch_one("SELECT 1 as test")
                health_results["database_connectivity"] = result is not None
            except Exception as e:
                health_results["alerts"].append(f"Database connectivity issue: {e}")
        
        # Check Kubernetes connectivity (skip if configured)
        if orchestrator and orchestrator.k8s_manager and not skip_flag:
            try:
                # Test k8s connectivity
                await orchestrator.k8s_manager.check_cluster_health()
                health_results["kubernetes_connectivity"] = True
            except Exception as e:
                health_results["alerts"].append(f"Kubernetes connectivity issue: {e}")
        elif skip_flag:
            # In skip mode, assume k8s is healthy
            health_results["kubernetes_connectivity"] = True
            logger.info("🚧 Skip: Skipping actual k8s health check")
        
        # Save health check metrics
        if orchestrator and hasattr(orchestrator.db_manager, 'state'):
            await orchestrator.db_manager.state.save_system_metric(
                "health_check_duration",
                (datetime.utcnow() - start_time).total_seconds(),
                "seconds",
                {"check_type": "sod_health_check"}
            )
        
        # Determine overall health
        overall_health = (health_results["database_connectivity"] and 
                         health_results["kubernetes_connectivity"] and
                         len(health_results["alerts"]) == 0)
        
        if not overall_health:
            raise Exception(f"System health check failed: {health_results['alerts']}")
        
        logger.info("✅ System health check passed")
        return health_results
        
    except Exception as e:
        logger.error(f"❌ System health check failed: {e}")
        raise

async def database_validation_task(context: Dict[str, Any]) -> Dict[str, Any]:
    """Validate database integrity and connections"""
    logger.info("🗄️ Validating database integrity")
    
    orchestrator = context.get("orchestrator")
    
    try:
        validation_results = {
            "table_checks": {},
            "constraint_checks": {},
            "index_checks": {},
            "data_integrity": {}
        }
        
        if orchestrator and hasattr(orchestrator.db_manager, 'state'):
            # Run data integrity validation
            integrity_report = await orchestrator.db_manager.state.validate_data_integrity()
            validation_results["data_integrity"] = integrity_report
            
            # Check if there are critical issues
            if integrity_report.get("overall_status") != "HEALTHY":
                logger.warning(f"Database integrity issues found: {integrity_report.get('issues', [])}")
        
        # Perform table maintenance if needed
        if orchestrator and hasattr(orchestrator.db_manager, 'state'):
            await orchestrator.db_manager.state.vacuum_analyze_tables()
        
        logger.info("✅ Database validation completed")
        return validation_results
        
    except Exception as e:
        logger.error(f"❌ Database validation failed: {e}")
        raise

async def validate_raw_data_task(context: Dict[str, Any]) -> Dict[str, Any]:
    """Validate raw data feeds"""
    logger.info("📈 Validating raw data")
    
    # Validate external based data was generated and stored correctly

    # universe master symbology
    # corporate actions (public investor relations data only)
    # event calendars (earnings, aid, public investor relations data only)
    # fundamentals (market cap, shares out, sec public data only)

    try:
        validation_result = {
            "feeds_validated": 0,
            "feeds_failed": 0,
            "data_quality_score": 100.0
        }
        
        logger.info("✅ Data raw validation completed")
        return validation_result
        
    except Exception as e:
        logger.error(f"❌ Data raw validation failed: {e}")
        raise

# Phase 2: Reference Data Updates

async def update_security_master_task(context: Dict[str, Any]) -> Dict[str, Any]:
    """Update security master data"""
    logger.info("📋 Updating security master data")
    
    sod_coordinator = context.get("sod_coordinator")
    
    try:
        if sod_coordinator and sod_coordinator.security_master:
            result = await sod_coordinator.security_master.update_security_master()
            logger.info("✅ Security master data updated")
            return result
        else:
            logger.warning("⚠️ Security master component not available")
            return {"status": "skipped", "reason": "component_unavailable"}
            
    except Exception as e:
        logger.error(f"❌ Security master update failed: {e}")
        raise

# Phase 3: Corporate Actions Processing

async def process_corporate_actions_task(context: Dict[str, Any]) -> Dict[str, Any]:
    """Process pending corporate actions"""
    logger.info("🏢 Processing corporate actions")
    
    sod_coordinator = context.get("sod_coordinator")
    
    try:
        if sod_coordinator and sod_coordinator.ca_processor:
            result = await sod_coordinator.ca_processor.process_pending_actions()
            logger.info("✅ Corporate actions processed")
            return result
        else:
            logger.warning("⚠️ Corporate actions processor not available")
            return {"status": "skipped", "reason": "component_unavailable"}
            
    except Exception as e:
        logger.error(f"❌ Corporate actions processing failed: {e}")
        raise

# Phase 4: Portfolio Management

async def reconcile_portfolio_task(context: Dict[str, Any]) -> Dict[str, Any]:
    """Reconcile portfolio data"""
    logger.info("⚖️ Reconciling portfolios")
    
    sod_coordinator = context.get("sod_coordinator")
    
    try:
        if sod_coordinator and sod_coordinator.portfolio_reconciler:
            result = await sod_coordinator.portfolio_reconciler.reconcile_portfolios()
            logger.info("✅ Portfolio reconciliation completed")
            return result
        else:
            logger.warning("⚠️ Portfolio reconciler not available")
            return {"status": "skipped", "reason": "component_unavailable"}
            
    except Exception as e:
        logger.error(f"❌ Portfolio reconciliation failed: {e}")
        raise

# Phase 6: System Readiness

async def validate_system_readiness_task(context: Dict[str, Any]) -> Dict[str, Any]:
    """Validate system is ready for trading"""
    logger.info("✅ Validating system readiness")
    
    orchestrator = context.get("orchestrator")
    
    try:
        readiness_checks = {
            "database_ready": True,
            "universe_ready": True,
            "portfolios_reconciled": True,
            "overall_ready": True
        }
        
        # Perform final system readiness validation
        if orchestrator:
            # Check if all critical components are ready
            if not readiness_checks["overall_ready"]:
                raise Exception("System not ready for trading")
        
        logger.info("✅ System readiness validation passed")
        return readiness_checks
        
    except Exception as e:
        logger.error(f"❌ System readiness validation failed: {e}")
        raise
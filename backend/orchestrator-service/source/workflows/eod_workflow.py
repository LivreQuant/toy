# source/workflows/eod_workflow.py
import logging
from typing import List, Dict, Any
from workflows.workflow_engine import WorkflowTask, TaskPriority
from datetime import datetime

logger = logging.getLogger(__name__)

# EOD DAILY REPORT
# ?? EOD CORPORATE ACTIONS (MIGHT OCCUR MID-DAY LIKE M&A)

def create_eod_workflow() -> List[WorkflowTask]:
    """Create End of Day workflow definition"""
    
    return [

        WorkflowTask(
            id="generate_eod_summary_task",
            name="Prepare EOD Summary report",
            function=generate_eod_summary_task,
            dependencies=[],
            priority=TaskPriority.MEDIUM,
            timeout_seconds=300,
            skip_flag=False
        )
    ]

# =============================================================================
# TASK IMPLEMENTATIONS
# =============================================================================

async def generate_eod_summary_task(context: Dict[str, Any]) -> Dict[str, Any]:
    """Generate comprehensive EOD summary report"""
    logger.info("📋 Generating EOD summary")
    
    eod_coordinator = context.get("eod_coordinator")
    orchestrator = context.get("orchestrator")
    
    try:
        summary_data = {
            "execution_date": context.get("execution_date").isoformat() if context.get("execution_date") else None,
            "summary_timestamp": datetime.utcnow().isoformat(),
            "workflow_performance": {},
            "system_health": {}
        }
        
        # Get workflow execution summary
        if orchestrator and hasattr(orchestrator.db_manager, 'workflows'):
            recent_executions = await orchestrator.db_manager.workflows.get_workflow_executions(
                workflow_name="eod_main",
                limit=1
            )
            if recent_executions:
                summary_data["workflow_performance"] = recent_executions[0]
        
        # Get system health summary
        if orchestrator and hasattr(orchestrator.db_manager, 'state'):
            health_summary = await orchestrator.db_manager.state.get_system_health_summary()
            summary_data["system_health"] = health_summary
        
        # Generate summary report
        if eod_coordinator and eod_coordinator.report_generator:
            summary_report = await eod_coordinator.report_generator.generate_eod_summary(summary_data)
            summary_data.update(summary_report)
        
        logger.info("✅ EOD summary generated")
        return summary_data
        
    except Exception as e:
        logger.error(f"❌ EOD summary generation failed: {e}")
        raise

        
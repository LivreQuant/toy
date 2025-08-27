# source/workflows/eod_workflow.py
import logging
from typing import List, Dict, Any
from source.workflows.workflow_engine import WorkflowTask, TaskPriority
from datetime import datetime

logger = logging.getLogger(__name__)


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
            skip_flag=True
        )
    ]


# =============================================================================
# TASK IMPLEMENTATIONS
# =============================================================================

async def generate_eod_summary_task(context: Dict[str, Any]) -> Dict[str, Any]:
    """Generate comprehensive EOD summary report"""
    logger.info("📋 Generating EOD summary")

    eod_coordinator = context.get("eod_coordinator")

    try:
        if eod_coordinator and eod_coordinator.report_generator:
            # Just pass the whole fucking context and let report_generator handle it
            summary_report = await eod_coordinator.report_generator.generate_eod_summary(context)
            logger.info("✅ EOD summary generated")
            return summary_report
        else:
            logger.warning("⚠️ Report generator not available")
            return {"status": "skipped", "reason": "component_unavailable"}

    except Exception as e:
        logger.error(f"❌ EOD summary generation failed: {e}")
        raise
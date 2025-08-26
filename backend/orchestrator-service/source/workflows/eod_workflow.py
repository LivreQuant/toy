# source/workflows/eod_workflow.py
import logging
from typing import List, Dict, Any
from workflows.workflow_engine import WorkflowTask, TaskPriority
from datetime import datetime

logger = logging.getLogger(__name__)

def create_eod_workflow() -> List[WorkflowTask]:
    """Create End of Day workflow definition"""
    
    return [
        # Phase 1: Trading Halt and Data Collection
        """
        WorkflowTask(
            id="halt_trading_activities",
            name="Halt Trading Activities",
            function=halt_trading_activities_task,
            dependencies=[],
            priority=TaskPriority.CRITICAL,
            timeout_seconds=300
        ),
        """
        
        WorkflowTask(
            id="collect_eod_market_data",
            name="Collect EOD Market Data",
            function=collect_eod_market_data_task,
            dependencies=[""],
            priority=TaskPriority.CRITICAL,
            timeout_seconds=600,
            skip_flag=False
        ),
        
        # Phase 2: Trade Settlement
        WorkflowTask(
            id="match_trades",
            name="Match Trades",
            function=match_trades_task,
            dependencies=["halt_trading_activities"],
            priority=TaskPriority.CRITICAL,
            timeout_seconds=900,
            skip_flag=False
        ),
        
        WorkflowTask(
            id="calculate_settlement_amounts",
            name="Calculate Settlement Amounts",
            function=calculate_settlement_amounts_task,
            dependencies=["match_trades"],
            priority=TaskPriority.HIGH,
            timeout_seconds=600,
            skip_flag=False
        ),
        
        WorkflowTask(
            id="process_trade_settlements",
            name="Process Trade Settlements", 
            function=process_trade_settlements_task,
            dependencies=["calculate_settlement_amounts"],
            priority=TaskPriority.HIGH,
            timeout_seconds=1200,
            skip_flag=False
        ),
        
        # Phase 3: Position Marking and Valuation
        WorkflowTask(
            id="mark_positions_to_market",
            name="Mark Positions to Market",
            function=mark_positions_to_market_task,
            dependencies=["collect_eod_market_data", "process_trade_settlements"],
            priority=TaskPriority.CRITICAL,
            timeout_seconds=900,
            skip_flag=False
        ),
        
        # Phase 4: P&L Calculation
        WorkflowTask(
            id="calculate_realized_pnl",
            name="Calculate Realized P&L",
            function=calculate_realized_pnl_task,
            dependencies=["process_trade_settlements"],
            priority=TaskPriority.HIGH,
            timeout_seconds=600,
            skip_flag=False
        ),
        
        WorkflowTask(
            id="calculate_unrealized_pnl",
            name="Calculate Unrealized P&L",
            function=calculate_unrealized_pnl_task,
            dependencies=["mark_positions_to_market"],
            priority=TaskPriority.HIGH,
            timeout_seconds=600,
            skip_flag=False
        ),
        
        WorkflowTask(
            id="perform_pnl_attribution",
            name="Perform P&L Attribution",
            function=perform_pnl_attribution_task,
            dependencies=["calculate_realized_pnl", "calculate_unrealized_pnl"],
            priority=TaskPriority.HIGH,
            timeout_seconds=900,
            skip_flag=False
        ),
        
        # Phase 5: Risk Metrics and Reporting
        WorkflowTask(
            id="calculate_portfolio_var",
            name="Calculate Portfolio VaR",
            function=calculate_portfolio_var_task,
            dependencies=["mark_positions_to_market"],
            priority=TaskPriority.HIGH,
            timeout_seconds=1200,
            skip_flag=False
        ),
        
        WorkflowTask(
            id="generate_risk_metrics",
            name="Generate Risk Metrics",
            function=generate_risk_metrics_task,
            dependencies=["calculate_portfolio_var", "perform_pnl_attribution"],
            priority=TaskPriority.HIGH,
            timeout_seconds=600,
            skip_flag=False
        ),
        
        WorkflowTask(
            id="generate_exposure_reports",
            name="Generate Exposure Reports",
            function=generate_exposure_reports_task,
            dependencies=["mark_positions_to_market"],
            priority=TaskPriority.HIGH,
            timeout_seconds=600,
            skip_flag=False
        ),
        
        # Phase 6: Regulatory Reporting
        WorkflowTask(
            id="generate_regulatory_reports",
            name="Generate Regulatory Reports",
            function=generate_regulatory_reports_task,
            dependencies=["perform_pnl_attribution", "calculate_portfolio_var"],
            priority=TaskPriority.HIGH,
            timeout_seconds=1800,
            skip_flag=False
        ),
        
        WorkflowTask(
            id="submit_regulatory_filings",
            name="Submit Regulatory Filings",
            function=submit_regulatory_filings_task,
            dependencies=["generate_regulatory_reports"],
            priority=TaskPriority.HIGH,
            timeout_seconds=600,
            skip_flag=False
        ),
        
        # Phase 7: Data Archival and Backup
        WorkflowTask(
            id="archive_daily_data",
            name="Archive Daily Data",
            function=archive_daily_data_task,
            dependencies=["perform_pnl_attribution", "generate_exposure_reports"],
            priority=TaskPriority.MEDIUM,
            timeout_seconds=1800,
            skip_flag=False
        ),
        
        WorkflowTask(
            id="backup_system_state",
            name="Backup System State",
            function=backup_system_state_task,
            dependencies=["archive_daily_data"],
            priority=TaskPriority.MEDIUM,
            timeout_seconds=900,
            skip_flag=False
        ),
        
        # Phase 8: Final Reports and Notifications
        WorkflowTask(
            id="generate_eod_summary",
            name="Generate EOD Summary",
            function=generate_eod_summary_task,
            dependencies=[
                "perform_pnl_attribution",
                "calculate_portfolio_var", 
                "generate_exposure_reports"
            ],
            priority=TaskPriority.MEDIUM,
            timeout_seconds=300,
            skip_flag=False
        ),
        
        WorkflowTask(
            id="send_eod_notifications",
            name="Send EOD Notifications",
            function=send_eod_notifications_task,
            dependencies=["generate_eod_summary"],
            priority=TaskPriority.MEDIUM,
            timeout_seconds=180,
            skip_flag=False
        ),
        
        # Phase 9: System Cleanup and Preparation
        WorkflowTask(
            id="cleanup_temporary_data",
            name="Cleanup Temporary Data",
            function=cleanup_temporary_data_task,
            dependencies=["backup_system_state"],
            priority=TaskPriority.LOW,
            timeout_seconds=600,
            skip_flag=False
        ),
        
        WorkflowTask(
            id="prepare_next_day",
            name="Prepare for Next Day",
            function=prepare_next_day_task,
            dependencies=["cleanup_temporary_data"],
            priority=TaskPriority.MEDIUM,
            timeout_seconds=300,
            skip_flag=False
        )
    ]

# =============================================================================
# TASK IMPLEMENTATIONS
# =============================================================================

"""
async def halt_trading_activities_task(context: Dict[str, Any]) -> Dict[str, Any]:
    """Halt all trading activities and prepare for EOD processing"""
    logger.info("🛑 Halting trading activities")
    
    orchestrator = context.get("orchestrator")
    start_time = datetime.utcnow()
    
    try:
        halt_results = {
            "exchanges_stopped": 0,
            "trading_sessions_closed": 0,
            "pending_orders_cancelled": 0,
            "halt_timestamp": start_time.isoformat()
        }
        
        # Stop all running exchanges
        if orchestrator and orchestrator.k8s_manager:
            try:
                await orchestrator.stop_all_exchanges()
                halt_results["exchanges_stopped"] = len(orchestrator.k8s_manager.get_running_exchanges())
                logger.info(f"✅ Stopped {halt_results['exchanges_stopped']} exchanges")
            except Exception as e:
                logger.error(f"❌ Failed to stop exchanges: {e}")
                raise
        
        # Log halt operation
        if orchestrator and hasattr(orchestrator.db_manager, 'state'):
            await orchestrator.db_manager.state.save_system_metric(
                "trading_halt_duration",
                (datetime.utcnow() - start_time).total_seconds(),
                "seconds",
                {"halt_type": "eod_halt"}
            )
        
        logger.info("✅ Trading activities halted successfully")
        return halt_results
        
    except Exception as e:
        logger.error(f"❌ Failed to halt trading activities: {e}")
        raise
"""

async def collect_eod_market_data_task(context: Dict[str, Any]) -> Dict[str, Any]:
    """Collect end-of-day market data for all securities"""
    logger.info("📊 Collecting EOD market data")
    
    try:
        collection_results = {
            "securities_processed": 0,
            "price_updates": 0,
            "failed_updates": 0,
            "data_sources": []
        }
        
        # Implementation would collect EOD prices from various sources
        # This is a placeholder for the actual market data collection logic
        
        logger.info("✅ EOD market data collection completed")
        return collection_results
        
    except Exception as e:
        logger.error(f"❌ EOD market data collection failed: {e}")
        raise

async def match_trades_task(context: Dict[str, Any]) -> Dict[str, Any]:
    """Match trades with counterparties and external systems"""
    logger.info("🔄 Matching trades")
    
    eod_coordinator = context.get("eod_coordinator")
    
    try:
        if eod_coordinator and eod_coordinator.trade_settler:
            result = await eod_coordinator.trade_settler.match_trades()
            logger.info("✅ Trade matching completed")
            return result
        else:
            logger.warning("⚠️ Trade settler not available")
            return {"status": "skipped", "reason": "component_unavailable"}
            
    except Exception as e:
        logger.error(f"❌ Trade matching failed: {e}")
        raise

async def calculate_settlement_amounts_task(context: Dict[str, Any]) -> Dict[str, Any]:
    """Calculate settlement amounts for all matched trades"""
    logger.info("💰 Calculating settlement amounts")
    
    eod_coordinator = context.get("eod_coordinator")
    
    try:
        if eod_coordinator and eod_coordinator.trade_settler:
            result = await eod_coordinator.trade_settler.calculate_settlement_amounts()
            logger.info("✅ Settlement amounts calculated")
            return result
        else:
            logger.warning("⚠️ Trade settler not available")
            return {"status": "skipped", "reason": "component_unavailable"}
            
    except Exception as e:
        logger.error(f"❌ Settlement amount calculation failed: {e}")
        raise

async def process_trade_settlements_task(context: Dict[str, Any]) -> Dict[str, Any]:
    """Process trade settlements and update positions"""
    logger.info("🏦 Processing trade settlements")
    
    eod_coordinator = context.get("eod_coordinator")
    
    try:
        if eod_coordinator and eod_coordinator.trade_settler:
            result = await eod_coordinator.trade_settler.process_settlements()
            logger.info("✅ Trade settlements processed")
            return result
        else:
            logger.warning("⚠️ Trade settler not available")
            return {"status": "skipped", "reason": "component_unavailable"}
            
    except Exception as e:
        logger.error(f"❌ Trade settlement processing failed: {e}")
        raise

async def mark_positions_to_market_task(context: Dict[str, Any]) -> Dict[str, Any]:
    """Mark all positions to market using EOD prices"""
    logger.info("📈 Marking positions to market")
    
    eod_coordinator = context.get("eod_coordinator")
    
    try:
        if eod_coordinator and eod_coordinator.position_marker:
            result = await eod_coordinator.position_marker.mark_to_market()
            logger.info("✅ Positions marked to market")
            return result
        else:
            logger.warning("⚠️ Position marker not available")
            return {"status": "skipped", "reason": "component_unavailable"}
            
    except Exception as e:
        logger.error(f"❌ Position marking failed: {e}")
        raise

async def calculate_realized_pnl_task(context: Dict[str, Any]) -> Dict[str, Any]:
    """Calculate realized P&L from settled trades"""
    logger.info("💹 Calculating realized P&L")
    
    eod_coordinator = context.get("eod_coordinator")
    
    try:
        if eod_coordinator and eod_coordinator.pnl_calculator:
            result = await eod_coordinator.pnl_calculator.calculate_realized_pnl()
            logger.info("✅ Realized P&L calculated")
            return result
        else:
            logger.warning("⚠️ P&L calculator not available")
            return {"status": "skipped", "reason": "component_unavailable"}
            
    except Exception as e:
        logger.error(f"❌ Realized P&L calculation failed: {e}")
        raise

async def calculate_unrealized_pnl_task(context: Dict[str, Any]) -> Dict[str, Any]:
    """Calculate unrealized P&L from position marking"""
    logger.info("📊 Calculating unrealized P&L")
    
    eod_coordinator = context.get("eod_coordinator")
    
    try:
        if eod_coordinator and eod_coordinator.pnl_calculator:
            result = await eod_coordinator.pnl_calculator.calculate_unrealized_pnl()
            logger.info("✅ Unrealized P&L calculated")
            return result
        else:
            logger.warning("⚠️ P&L calculator not available")
            return {"status": "skipped", "reason": "component_unavailable"}
            
    except Exception as e:
        logger.error(f"❌ Unrealized P&L calculation failed: {e}")
        raise

async def perform_pnl_attribution_task(context: Dict[str, Any]) -> Dict[str, Any]:
    """Perform P&L attribution analysis"""
    logger.info("🎯 Performing P&L attribution")
    
    eod_coordinator = context.get("eod_coordinator")
    
    try:
        if eod_coordinator and eod_coordinator.pnl_calculator:
            result = await eod_coordinator.pnl_calculator.perform_attribution()
            logger.info("✅ P&L attribution completed")
            return result
        else:
            logger.warning("⚠️ P&L calculator not available")
            return {"status": "skipped", "reason": "component_unavailable"}
            
    except Exception as e:
        logger.error(f"❌ P&L attribution failed: {e}")
        raise

async def calculate_portfolio_var_task(context: Dict[str, Any]) -> Dict[str, Any]:
    """Calculate portfolio Value at Risk metrics"""
    logger.info("⚠️ Calculating portfolio VaR")
    
    eod_coordinator = context.get("eod_coordinator")
    
    try:
        if eod_coordinator and eod_coordinator.risk_reporter:
            result = await eod_coordinator.risk_reporter.calculate_portfolio_var()
            logger.info("✅ Portfolio VaR calculated")
            return result
        else:
            logger.warning("⚠️ Risk reporter not available")
            return {"status": "skipped", "reason": "component_unavailable"}
            
    except Exception as e:
        logger.error(f"❌ Portfolio VaR calculation failed: {e}")
        raise

async def generate_risk_metrics_task(context: Dict[str, Any]) -> Dict[str, Any]:
    """Generate comprehensive risk metrics"""
    logger.info("📋 Generating risk metrics")
    
    eod_coordinator = context.get("eod_coordinator")
    
    try:
        if eod_coordinator and eod_coordinator.risk_reporter:
            result = await eod_coordinator.risk_reporter.generate_risk_metrics()
            logger.info("✅ Risk metrics generated")
            return result
        else:
            logger.warning("⚠️ Risk reporter not available")
            return {"status": "skipped", "reason": "component_unavailable"}
            
    except Exception as e:
        logger.error(f"❌ Risk metrics generation failed: {e}")
        raise

async def generate_exposure_reports_task(context: Dict[str, Any]) -> Dict[str, Any]:
    """Generate exposure reports by sector, geography, etc."""
    logger.info("🌍 Generating exposure reports")
    
    eod_coordinator = context.get("eod_coordinator")
    
    try:
        if eod_coordinator and eod_coordinator.report_generator:
            result = await eod_coordinator.report_generator.generate_exposure_reports()
            logger.info("✅ Exposure reports generated")
            return result
        else:
            logger.warning("⚠️ Report generator not available")
            return {"status": "skipped", "reason": "component_unavailable"}
            
    except Exception as e:
        logger.error(f"❌ Exposure report generation failed: {e}")
        raise

async def generate_regulatory_reports_task(context: Dict[str, Any]) -> Dict[str, Any]:
    """Generate regulatory compliance reports"""
    logger.info("📋 Generating regulatory reports")
    
    eod_coordinator = context.get("eod_coordinator")
    
    try:
        if eod_coordinator and eod_coordinator.report_generator:
            result = await eod_coordinator.report_generator.generate_regulatory_reports()
            logger.info("✅ Regulatory reports generated")
            return result
        else:
            logger.warning("⚠️ Report generator not available")
            return {"status": "skipped", "reason": "component_unavailable"}
            
    except Exception as e:
        logger.error(f"❌ Regulatory report generation failed: {e}")
        raise

async def submit_regulatory_filings_task(context: Dict[str, Any]) -> Dict[str, Any]:
    """Submit regulatory filings to relevant authorities"""
    logger.info("📤 Submitting regulatory filings")
    
    try:
        submission_results = {
            "filings_submitted": 0,
            "submissions_failed": 0,
            "submission_confirmations": []
        }
        
        # Implementation would submit required regulatory filings
        # This is a placeholder for the actual submission logic
        
        logger.info("✅ Regulatory filings submitted")
        return submission_results
        
    except Exception as e:
        logger.error(f"❌ Regulatory filing submission failed: {e}")
        raise

async def archive_daily_data_task(context: Dict[str, Any]) -> Dict[str, Any]:
    """Archive daily trading data for long-term storage"""
    logger.info("🗄️ Archiving daily data")
    
    eod_coordinator = context.get("eod_coordinator")
    
    try:
        if eod_coordinator and eod_coordinator.data_archiver:
            result = await eod_coordinator.data_archiver.archive_daily_data()
            logger.info("✅ Daily data archived")
            return result
        else:
            logger.warning("⚠️ Data archiver not available")
            return {"status": "skipped", "reason": "component_unavailable"}
            
    except Exception as e:
        logger.error(f"❌ Data archival failed: {e}")
        raise

async def backup_system_state_task(context: Dict[str, Any]) -> Dict[str, Any]:
    """Backup system state and configuration"""
    logger.info("💾 Backing up system state")
    
    orchestrator = context.get("orchestrator")
    execution_date = context.get("execution_date")
    
    try:
        backup_results = {
            "backup_timestamp": datetime.utcnow().isoformat(),
            "backup_size_mb": 0,
            "backup_location": None
        }
        
        # Create system state backup
        if orchestrator and hasattr(orchestrator.db_manager, 'state'):
            # Export state data for backup
            state_data = await orchestrator.db_manager.state.export_state_data(
                start_date=execution_date,
                end_date=execution_date
            )
            
            # Create recovery checkpoint
            await orchestrator.db_manager.state.create_recovery_checkpoint(
                checkpoint_name=f"eod_backup_{execution_date}",
                checkpoint_type="SYSTEM_BACKUP",
                checkpoint_data=state_data
            )
            
            backup_results["backup_size_mb"] = len(str(state_data)) / (1024 * 1024)  # Rough size estimate
        
        logger.info("✅ System state backup completed")
        return backup_results
        
    except Exception as e:
        logger.error(f"❌ System state backup failed: {e}")
        raise

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

async def send_eod_notifications_task(context: Dict[str, Any]) -> Dict[str, Any]:
    """Send EOD completion notifications"""
    logger.info("📧 Sending EOD notifications")
    
    orchestrator = context.get("orchestrator")
    
    try:
        notification_results = {
            "notifications_sent": 0,
            "notifications_failed": 0,
            "recipients": []
        }
        
        # Send notifications through the notification manager
        if orchestrator and orchestrator.notifications:
            await orchestrator.notifications.send_eod_completion_notification(
                execution_date=context.get("execution_date"),
                summary_data=context.get("eod_summary", {})
            )
            notification_results["notifications_sent"] = 1
        
        logger.info("✅ EOD notifications sent")
        return notification_results
        
    except Exception as e:
        logger.error(f"❌ EOD notification sending failed: {e}")
        raise

async def cleanup_temporary_data_task(context: Dict[str, Any]) -> Dict[str, Any]:
    """Clean up temporary data and optimize database"""
    logger.info("🧹 Cleaning up temporary data")
    
    orchestrator = context.get("orchestrator")
    
    try:
        cleanup_results = {
            "temp_records_deleted": 0,
            "disk_space_freed_mb": 0,
            "tables_optimized": 0
        }
        
        # Perform database cleanup
        if orchestrator and hasattr(orchestrator.db_manager, 'state'):
            # Clean up old operations
            deleted_count = await orchestrator.db_manager.state.cleanup_old_operations(days_to_keep=90)
            cleanup_results["temp_records_deleted"] = deleted_count
            
            # Vacuum analyze tables
            await orchestrator.db_manager.state.vacuum_analyze_tables()
            cleanup_results["tables_optimized"] = 5  # Approximate number of tables
        
        logger.info("✅ Temporary data cleanup completed")
        return cleanup_results
        
    except Exception as e:
        logger.error(f"❌ Temporary data cleanup failed: {e}")
        raise

async def prepare_next_day_task(context: Dict[str, Any]) -> Dict[str, Any]:
    """Prepare system for next trading day"""
    logger.info("🌅 Preparing for next day")
    
    orchestrator = context.get("orchestrator")
    
    try:
        preparation_results = {
            "system_state_reset": False,
            "configurations_updated": False,
            "next_day_ready": False
        }
        
        # Reset system state flags for next day
        if orchestrator:
            orchestrator.sod_complete = False
            orchestrator.eod_complete = True  # Keep EOD complete flag
            preparation_results["system_state_reset"] = True
        
        # Save preparation completion
        if orchestrator and hasattr(orchestrator.db_manager, 'state'):
            await orchestrator.db_manager.state.save_system_metric(
                "next_day_preparation",
                1.0,
                "boolean",
                {"preparation_date": datetime.utcnow().date().isoformat()}
            )
        
        preparation_results["next_day_ready"] = True
        
        logger.info("✅ Next day preparation completed")
        return preparation_results
        
    except Exception as e:
        logger.error(f"❌ Next day preparation failed: {e}")
        raise
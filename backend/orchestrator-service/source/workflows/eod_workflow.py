# source/workflows/eod_workflow.py
import logging
from typing import List
from workflows.workflow_engine import WorkflowTask, TaskPriority

logger = logging.getLogger(__name__)

def create_eod_workflow() -> List[WorkflowTask]:
    """Create End of Day workflow definition"""
    
    return [
        # Phase 1: Trading Halt and Data Collection
        WorkflowTask(
            id="halt_trading_activities",
            name="Halt Trading Activities",
            function=halt_trading_activities_task,
            dependencies=[],
            priority=TaskPriority.CRITICAL,
            timeout_seconds=300
        ),
        
        WorkflowTask(
            id="collect_eod_market_data",
            name="Collect EOD Market Data",
            function=collect_eod_market_data_task,
            dependencies=["halt_trading_activities"],
            priority=TaskPriority.CRITICAL,
            timeout_seconds=600
        ),
        
        # Phase 2: Trade Settlement
        WorkflowTask(
            id="match_trades",
            name="Match Trades",
            function=match_trades_task,
            dependencies=["halt_trading_activities"],
            priority=TaskPriority.CRITICAL,
            timeout_seconds=900
        ),
        
        WorkflowTask(
            id="calculate_settlement_amounts",
            name="Calculate Settlement Amounts",
            function=calculate_settlement_amounts_task,
            dependencies=["match_trades"],
            priority=TaskPriority.HIGH,
            timeout_seconds=600
        ),
        
        WorkflowTask(
            id="process_trade_settlements",
            name="Process Trade Settlements", 
            function=process_trade_settlements_task,
            dependencies=["calculate_settlement_amounts"],
            priority=TaskPriority.HIGH,
            timeout_seconds=1200
        ),
        
        # Phase 3: Position Marking and Valuation
        WorkflowTask(
            id="mark_positions_to_market",
            name="Mark Positions to Market",
            function=mark_positions_to_market_task,
            dependencies=["collect_eod_market_data", "process_trade_settlements"],
            priority=TaskPriority.CRITICAL,
            timeout_seconds=900
        ),
        
        WorkflowTask(
            id="calculate_accrued_interest",
            name="Calculate Accrued Interest",
            function=calculate_accrued_interest_task,
            dependencies=["collect_eod_market_data"],
            priority=TaskPriority.HIGH,
            timeout_seconds=300
        ),
        
        WorkflowTask(
            id="apply_fair_value_adjustments",
            name="Apply Fair Value Adjustments",
            function=apply_fair_value_adjustments_task,
            dependencies=["mark_positions_to_market"],
            priority=TaskPriority.MEDIUM,
            timeout_seconds=600
        ),
        
        # Phase 4: P&L Calculation
        WorkflowTask(
            id="calculate_realized_pnl",
            name="Calculate Realized P&L",
            function=calculate_realized_pnl_task,
            dependencies=["process_trade_settlements"],
            priority=TaskPriority.HIGH,
            timeout_seconds=600
        ),
        
        WorkflowTask(
            id="calculate_unrealized_pnl",
            name="Calculate Unrealized P&L",
            function=calculate_unrealized_pnl_task,
            dependencies=["mark_positions_to_market", "apply_fair_value_adjustments"],
            priority=TaskPriority.HIGH,
            timeout_seconds=600
        ),
        
        WorkflowTask(
            id="perform_pnl_attribution",
            name="Perform P&L Attribution",
            function=perform_pnl_attribution_task,
            dependencies=["calculate_realized_pnl", "calculate_unrealized_pnl"],
            priority=TaskPriority.HIGH,
            timeout_seconds=900
        ),
        
        # Phase 5: Risk Calculations
        WorkflowTask(
            id="calculate_portfolio_var",
            name="Calculate Portfolio VaR",
            function=calculate_portfolio_var_task,
            dependencies=["mark_positions_to_market"],
            priority=TaskPriority.HIGH,
            timeout_seconds=900
        ),
        
        WorkflowTask(
            id="run_stress_tests",
            name="Run Stress Tests",
            function=run_stress_tests_task,
            dependencies=["mark_positions_to_market"],
            priority=TaskPriority.MEDIUM,
            timeout_seconds=1200
        ),
        
        WorkflowTask(
            id="generate_exposure_reports",
            name="Generate Exposure Reports",
            function=generate_exposure_reports_task,
            dependencies=["mark_positions_to_market"],
            priority=TaskPriority.HIGH,
            timeout_seconds=600
        ),
        
        # Phase 6: Regulatory Reporting
        WorkflowTask(
            id="generate_regulatory_reports",
            name="Generate Regulatory Reports",
            function=generate_regulatory_reports_task,
            dependencies=["perform_pnl_attribution", "calculate_portfolio_var"],
            priority=TaskPriority.HIGH,
            timeout_seconds=1800
        ),
        
        WorkflowTask(
            id="submit_regulatory_filings",
            name="Submit Regulatory Filings",
            function=submit_regulatory_filings_task,
            dependencies=["generate_regulatory_reports"],
            priority=TaskPriority.HIGH,
            timeout_seconds=600
        ),
        
        # Phase 7: Data Archival and Backup
        WorkflowTask(
            id="archive_daily_data",
            name="Archive Daily Data",
            function=archive_daily_data_task,
            dependencies=["perform_pnl_attribution", "generate_exposure_reports"],
            priority=TaskPriority.MEDIUM,
            timeout_seconds=1800
        ),
        
        WorkflowTask(
            id="backup_system_state",
            name="Backup System State",
            function=backup_system_state_task,
            dependencies=["archive_daily_data"],
            priority=TaskPriority.MEDIUM,
            timeout_seconds=900
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
            timeout_seconds=300
        ),
        
        WorkflowTask(
            id="send_eod_notifications",
            name="Send EOD Notifications",
            function=send_eod_notifications_task,
            dependencies=["generate_eod_summary"],
            priority=TaskPriority.LOW,
            timeout_seconds=120,
            required=False
        )
    ]

# Task implementations
async def halt_trading_activities_task(context):
    logger.info("🛑 Halting all trading activities...")
    await asyncio.sleep(5)
    return {"exchanges_halted": 3, "active_orders_cancelled": 125, "positions_locked": True}

async def collect_eod_market_data_task(context):
    logger.info("📊 Collecting end-of-day market data...")
    await asyncio.sleep(10)
    return {"securities_priced": 2500, "fx_rates": 12, "index_levels": 25}

async def match_trades_task(context):
    logger.info("🔄 Matching trades...")
    await asyncio.sleep(15)
    return {"trades_matched": 1250, "unmatched_trades": 3, "match_rate": 99.8}

async def calculate_settlement_amounts_task(context):
    logger.info("💰 Calculating settlement amounts...")
    await asyncio.sleep(10)
    return {"settlements_calculated": 1250, "gross_amount": "125.5M", "net_amount": "45.2M"}

async def process_trade_settlements_task(context):
    logger.info("📋 Processing trade settlements...")
    await asyncio.sleep(20)
    return {"settlements_processed": 1250, "failed_settlements": 0, "cash_movements": "45.2M"}

async def mark_positions_to_market_task(context):
    logger.info("📈 Marking positions to market...")
    await asyncio.sleep(15)
    return {"positions_marked": 1850, "market_value": "2.5B", "price_changes": 1850}

async def calculate_accrued_interest_task(context):
    logger.info("💸 Calculating accrued interest...")
    await asyncio.sleep(5)
    return {"bonds_processed": 450, "accrued_interest": "2.1M", "currencies": 5}

async def apply_fair_value_adjustments_task(context):
    logger.info("⚖️ Applying fair value adjustments...")
    await asyncio.sleep(10)
    return {"adjustments_applied": 25, "illiquid_securities": 25, "adjustment_amount": "1.2M"}

async def calculate_realized_pnl_task(context):
    logger.info("📊 Calculating realized P&L...")
    await asyncio.sleep(10)
    return {"realized_pnl": "8.5M", "winning_trades": 650, "losing_trades": 600}

async def calculate_unrealized_pnl_task(context):
    logger.info("📉 Calculating unrealized P&L...")
    await asyncio.sleep(10)
    return {"unrealized_pnl": "-2.1M", "positions_analyzed": 1850, "currencies": 8}

async def perform_pnl_attribution_task(context):
    logger.info("🎯 Performing P&L attribution...")
    await asyncio.sleep(15)
    return {
        "total_pnl": "6.4M",
        "security_selection": "4.2M", 
        "asset_allocation": "1.8M",
        "timing": "0.4M"
    }

async def calculate_portfolio_var_task(context):
    logger.info("⚡ Calculating portfolio VaR...")
    await asyncio.sleep(15)
    return {"var_1d_95": "12.5M", "var_10d_99": "45.2M", "component_var": True}

async def run_stress_tests_task(context):
    logger.info("🧪 Running stress tests...")
    await asyncio.sleep(20)
    return {"scenarios_run": 15, "worst_case_loss": "85.5M", "stressed_var": "25.8M"}

async def generate_exposure_reports_task(context):
    logger.info("📊 Generating exposure reports...")
    await asyncio.sleep(10)
    return {"sector_exposures": 11, "geographic_exposures": 8, "currency_exposures": 8}

async def generate_regulatory_reports_task(context):
    logger.info("📋 Generating regulatory reports...")
    await asyncio.sleep(30)
    return {"reports_generated": 8, "forms": ["13F", "CFTC", "SEC"], "pages": 125}

async def submit_regulatory_filings_task(context):
    logger.info("📤 Submitting regulatory filings...")
    await asyncio.sleep(10)
    return {"filings_submitted": 8, "submission_status": "success", "confirmation_ids": 8}

async def archive_daily_data_task(context):
    logger.info("🗄️ Archiving daily data...")
    await asyncio.sleep(30)
    return {"data_archived": "15.5GB", "compression_ratio": 0.85, "archive_location": "s3://backup"}

async def backup_system_state_task(context):
    logger.info("💾 Backing up system state...")
    await asyncio.sleep(15)
    return {"backup_size": "2.1GB", "backup_location": "s3://backup", "verification": "passed"}

async def generate_eod_summary_task(context):
    logger.info("📄 Generating EOD summary report...")
    await asyncio.sleep(5)
    return {"summary_generated": True, "kpis": 25, "charts": 15}

async def send_eod_notifications_task(context):
    logger.info("📧 Sending EOD notifications...")
    await asyncio.sleep(3)
    return {"notifications_sent": 45, "channels": ["email", "slack", "sms"]}
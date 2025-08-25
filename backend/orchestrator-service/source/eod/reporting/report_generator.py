# source/eod/reporting/report_generator.py
import logging
from typing import Dict, List, Any, Optional
from datetime import date, datetime, timedelta
from decimal import Decimal
from enum import Enum
import asyncio
import json

logger = logging.getLogger(__name__)

class ReportType(Enum):
    DAILY_PNL = "daily_pnl"
    POSITION_SUMMARY = "position_summary"
    RISK_REPORT = "risk_report"
    PERFORMANCE_ATTRIBUTION = "performance_attribution"
    REGULATORY_13F = "regulatory_13f"
    TRADE_SUMMARY = "trade_summary"
    COMPLIANCE_REPORT = "compliance_report"

class ReportFormat(Enum):
    JSON = "json"
    CSV = "csv"
    PDF = "pdf"
    HTML = "html"

class ReportGenerator:
    """Generates various EOD reports"""
    
    def __init__(self, db_manager):
        self.db_manager = db_manager
        
    async def initialize(self):
        """Initialize report generator"""
        await self._create_reporting_tables()
        logger.info("📄 Report Generator initialized")
    
    async def _create_reporting_tables(self):
        """Create reporting tables"""
        async with self.db_manager.pool.acquire() as conn:
            await conn.execute("""
                CREATE SCHEMA IF NOT EXISTS reporting
            """)
            
            # Report metadata table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS reporting.report_catalog (
                    report_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    report_type VARCHAR(50) NOT NULL,
                    report_name VARCHAR(200) NOT NULL,
                    account_id VARCHAR(50),
                    report_date DATE NOT NULL,
                    generation_time TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    report_format VARCHAR(20) NOT NULL,
                    file_path VARCHAR(500),
                    file_size BIGINT,
                    status VARCHAR(20) DEFAULT 'GENERATED',
                    parameters JSONB,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                )
            """)
            
            # Regulatory filings table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS reporting.regulatory_filings (
                    filing_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    filing_type VARCHAR(50) NOT NULL,
                    filing_period_end DATE NOT NULL,
                    filing_due_date DATE NOT NULL,
                    submission_date TIMESTAMP WITH TIME ZONE,
                    status VARCHAR(20) DEFAULT 'PENDING',
                    confirmation_number VARCHAR(100),
                    filing_data JSONB NOT NULL,
                    submission_method VARCHAR(50),
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                )
            """)
            
            # Report subscriptions (who gets what reports)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS reporting.report_subscriptions (
                    subscription_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    user_id VARCHAR(50) NOT NULL,
                    report_type VARCHAR(50) NOT NULL,
                    account_filter VARCHAR(50),
                    delivery_method VARCHAR(20) DEFAULT 'EMAIL',
                    delivery_address VARCHAR(200) NOT NULL,
                    schedule_cron VARCHAR(100),
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                )
            """)
            
            # Create indices
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_report_catalog_date_type 
                ON reporting.report_catalog (report_date, report_type)
            """)
            
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_regulatory_filings_due_date 
                ON reporting.regulatory_filings (filing_due_date, status)
            """)
    
    async def generate_eod_reports(self, report_date: date) -> Dict[str, Any]:
        """Generate all standard EOD reports"""
        logger.info(f"📄 Generating EOD reports for {report_date}")
        
        try:
            results = {
                "reports_generated": 0,
                "reports_failed": 0,
                "regulatory_filings": 0,
                "report_details": []
            }
            
            # Get list of active portfolios
            portfolios = await self._get_active_portfolios(report_date)
            
            # Generate reports for each portfolio
            for portfolio in portfolios:
                account_id = portfolio['account_id']
                
                # Generate core reports
                report_types = [
                    ReportType.DAILY_PNL,
                    ReportType.POSITION_SUMMARY,
                    ReportType.RISK_REPORT,
                    ReportType.PERFORMANCE_ATTRIBUTION,
                    ReportType.TRADE_SUMMARY
                ]
                
                for report_type in report_types:
                    try:
                        report_result = await self._generate_single_report(
                            report_type, account_id, report_date
                        )
                        
                        if report_result['success']:
                            results["reports_generated"] += 1
                            results["report_details"].append({
                                "report_type": report_type.value,
                                "account_id": account_id,
                                "status": "success",
                                "report_id": report_result['report_id']
                            })
                        else:
                            results["reports_failed"] += 1
                            logger.error(f"Failed to generate {report_type.value} for {account_id}: {report_result.get('error')}")
                            
                    except Exception as e:
                        results["reports_failed"] += 1
                        logger.error(f"Error generating {report_type.value} for {account_id}: {e}", exc_info=True)
            
            # Generate regulatory reports
            regulatory_results = await self._generate_regulatory_reports(report_date)
            results["regulatory_filings"] = regulatory_results["filings_generated"]
            
            # Send scheduled reports
            await self._send_scheduled_reports(report_date)
            
            logger.info(f"✅ EOD report generation complete: {results}")
            return results
            
        except Exception as e:
            logger.error(f"❌ Failed to generate EOD reports: {e}", exc_info=True)
            raise
    
    async def _get_active_portfolios(self, report_date: date) -> List[Dict[str, Any]]:
        """Get all portfolios that need reports"""
        async with self.db_manager.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT DISTINCT account_id,
                       COUNT(*) as position_count,
                       SUM(market_value) as total_value
                FROM positions.current_positions
                WHERE position_date = $1 AND quantity != 0
                GROUP BY account_id
                HAVING SUM(market_value) > 1000  -- Only portfolios with >$1k value
                ORDER BY total_value DESC
            """, report_date)
            
            return [dict(row) for row in rows]
    
    async def _generate_single_report(self, report_type: ReportType, 
                                    account_id: str, report_date: date) -> Dict[str, Any]:
        """Generate a single report"""
        logger.info(f"📊 Generating {report_type.value} report for {account_id}")
        
        try:
            if report_type == ReportType.DAILY_PNL:
                report_data = await self._generate_daily_pnl_report(account_id, report_date)
            elif report_type == ReportType.POSITION_SUMMARY:
                report_data = await self._generate_position_summary_report(account_id, report_date)
            elif report_type == ReportType.RISK_REPORT:
                report_data = await self._generate_risk_report(account_id, report_date)
            elif report_type == ReportType.PERFORMANCE_ATTRIBUTION:
                report_data = await self._generate_performance_attribution_report(account_id, report_date)
            elif report_type == ReportType.TRADE_SUMMARY:
                report_data = await self._generate_trade_summary_report(account_id, report_date)
            else:
                raise ValueError(f"Unsupported report type: {report_type}")
            
            # Store report in catalog
            report_id = await self._store_report_metadata(
                report_type, account_id, report_date, report_data
            )
            
            return {
                "success": True,
                "report_id": report_id,
                "report_type": report_type.value
            }
            
        except Exception as e:
            logger.error(f"Error generating {report_type.value} report: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _generate_daily_pnl_report(self, account_id: str, report_date: date) -> Dict[str, Any]:
        """Generate daily P&L report"""
        async with self.db_manager.pool.acquire() as conn:
            # Overall P&L summary
            summary = await conn.fetchrow("""
                SELECT 
                    SUM(realized_pnl) as total_realized_pnl,
                    SUM(unrealized_pnl) as total_unrealized_pnl,
                    SUM(total_pnl) as total_pnl,
                    COUNT(*) as positions_count
                FROM pnl.daily_pnl
                WHERE account_id = $1 AND pnl_date = $2 AND symbol IS NOT NULL
            """, account_id, report_date)
            
            # Position-level P&L
            positions = await conn.fetch("""
                SELECT symbol, realized_pnl, unrealized_pnl, total_pnl
                FROM pnl.daily_pnl
                WHERE account_id = $1 AND pnl_date = $2 AND symbol IS NOT NULL
                ORDER BY total_pnl DESC
            """, account_id, report_date)
            
            # Attribution breakdown
            attribution = await conn.fetch("""
                SELECT attribution_type, attribution_value, attribution_pct
                FROM pnl.performance_attribution
                WHERE account_id = $1 AND attribution_date = $2
                ORDER BY ABS(attribution_value) DESC
            """, account_id, report_date)
            
            return {
                "report_type": "daily_pnl",
                "account_id": account_id,
                "report_date": str(report_date),
                "summary": dict(summary) if summary else {},
                "positions": [dict(row) for row in positions],
                "attribution": [dict(row) for row in attribution],
                "generation_time": datetime.utcnow().isoformat()
            }
    
    async def _generate_position_summary_report(self, account_id: str, report_date: date) -> Dict[str, Any]:
        """Generate position summary report"""
        async with self.db_manager.pool.acquire() as conn:
            # Current positions
            positions = await conn.fetch("""
                SELECT 
                    cp.symbol,
                    cp.quantity,
                    cp.avg_cost,
                    cp.market_value,
                    cp.unrealized_pnl,
                    cp.last_price,
                    s.sector,
                    s.exchange,
                    s.security_name
                FROM positions.current_positions cp
                LEFT JOIN reference_data.securities s ON cp.symbol = s.symbol
                WHERE cp.account_id = $1 AND cp.position_date = $2 AND cp.quantity != 0
                ORDER BY cp.market_value DESC
            """, account_id, report_date)
            
            # Portfolio summary
            summary = await conn.fetchrow("""
                SELECT 
                    COUNT(*) as total_positions,
                    SUM(market_value) as total_market_value,
                    SUM(unrealized_pnl) as total_unrealized_pnl,
                    SUM(CASE WHEN quantity > 0 THEN market_value ELSE 0 END) as long_value,
                    SUM(CASE WHEN quantity < 0 THEN ABS(market_value) ELSE 0 END) as short_value
                FROM positions.current_positions
                WHERE account_id = $1 AND position_date = $2 AND quantity != 0
            """, account_id, report_date)
            
            # Sector breakdown
            sector_breakdown = await conn.fetch("""
                SELECT 
                    COALESCE(s.sector, 'UNKNOWN') as sector,
                    COUNT(*) as position_count,
                    SUM(cp.market_value) as sector_value,
                    SUM(cp.market_value) / SUM(SUM(cp.market_value)) OVER () * 100 as sector_percentage
                FROM positions.current_positions cp
                LEFT JOIN reference_data.securities s ON cp.symbol = s.symbol
                WHERE cp.account_id = $1 AND cp.position_date = $2 AND cp.quantity != 0
                GROUP BY s.sector
                ORDER BY sector_value DESC
            """, account_id, report_date)
            
            return {
                "report_type": "position_summary",
                "account_id": account_id,
                "report_date": str(report_date),
                "summary": dict(summary) if summary else {},
                "positions": [dict(row) for row in positions],
                "sector_breakdown": [dict(row) for row in sector_breakdown],
                "generation_time": datetime.utcnow().isoformat()
            }
    
    async def _generate_risk_report(self, account_id: str, report_date: date) -> Dict[str, Any]:
        """Generate risk report"""
        # Use the risk reporter to get comprehensive risk data
        from eod.risk_metrics.risk_reporter import RiskReporter
        risk_reporter = RiskReporter(self.db_manager)
        
        risk_data = await risk_reporter.get_risk_summary(account_id, report_date)
        
        return {
            "report_type": "risk_report",
            **risk_data,
            "generation_time": datetime.utcnow().isoformat()
        }
    
    async def _generate_performance_attribution_report(self, account_id: str, report_date: date) -> Dict[str, Any]:
        """Generate performance attribution report"""
        async with self.db_manager.pool.acquire() as conn:
            # Get attribution data
            attribution = await conn.fetch("""
                SELECT 
                    attribution_type,
                    attribution_value,
                    attribution_pct,
                    benchmark_return,
                    active_return
                FROM pnl.performance_attribution
                WHERE account_id = $1 AND attribution_date = $2
                ORDER BY ABS(attribution_value) DESC
            """, account_id, report_date)
            
            # Get historical performance (last 30 days)
            historical_performance = await conn.fetch("""
                SELECT 
                    pnl_date,
                    total_pnl
                FROM pnl.daily_pnl
                WHERE account_id = $1 
                  AND pnl_date BETWEEN $2 - INTERVAL '30 days' AND $2
                  AND symbol IS NULL
                ORDER BY pnl_date
            """, account_id, report_date)
            
            # Get risk-adjusted metrics
            risk_metrics = await conn.fetchrow("""
                SELECT 
                    total_return,
                    volatility,
                    sharpe_ratio,
                    sortino_ratio
                FROM pnl.risk_adjusted_returns
                WHERE account_id = $1 AND calculation_date = $2 AND period_days = 30
            """, account_id, report_date)
            
            return {
                "report_type": "performance_attribution",
                "account_id": account_id,
                "report_date": str(report_date),
                "attribution": [dict(row) for row in attribution],
                "historical_performance": [dict(row) for row in historical_performance],
                "risk_adjusted_metrics": dict(risk_metrics) if risk_metrics else {},
                "generation_time": datetime.utcnow().isoformat()
            }
    
    async def _generate_trade_summary_report(self, account_id: str, report_date: date) -> Dict[str, Any]:
        """Generate trade summary report"""
        async with self.db_manager.pool.acquire() as conn:
            # Trading activity summary
            trade_summary = await conn.fetchrow("""
                SELECT 
                    COUNT(*) as total_trades,
                    COUNT(CASE WHEN side = 'BUY' THEN 1 END) as buy_trades,
                    COUNT(CASE WHEN side = 'SELL' THEN 1 END) as sell_trades,
                    SUM(trade_value) as total_trade_value,
                    SUM(commission) as total_commissions,
                    AVG(trade_value) as avg_trade_size
                FROM settlement.trades
                WHERE account_id = $1 AND trade_date = $2
            """, account_id, report_date)
            
            # Individual trades
            trades = await conn.fetch("""
                SELECT 
                    symbol,
                    side,
                    quantity,
                    price,
                    trade_value,
                    commission,
                    execution_time,
                    settlement_status
                FROM settlement.trades
                WHERE account_id = $1 AND trade_date = $2
                ORDER BY execution_time
            """, account_id, report_date)
            
            # Settlement status
            settlement_summary = await conn.fetchrow("""
                SELECT 
                    COUNT(CASE WHEN settlement_status = 'SETTLED' THEN 1 END) as settled_trades,
                    COUNT(CASE WHEN settlement_status = 'PENDING' THEN 1 END) as pending_trades,
                    COUNT(CASE WHEN settlement_status = 'FAILED' THEN 1 END) as failed_trades
                FROM settlement.trades
                WHERE account_id = $1 AND settlement_date = $2
            """, account_id, report_date)
            
            return {
                "report_type": "trade_summary",
                "account_id": account_id,
                "report_date": str(report_date),
                "trade_summary": dict(trade_summary) if trade_summary else {},
                "trades": [dict(row) for row in trades],
                "settlement_summary": dict(settlement_summary) if settlement_summary else {},
                "generation_time": datetime.utcnow().isoformat()
            }
    
    async def _generate_regulatory_reports(self, report_date: date) -> Dict[str, Any]:
        """Generate regulatory reports (13F, etc.)"""
        logger.info(f"📋 Generating regulatory reports for {report_date}")
        
        results = {
            "filings_generated": 0
        }
        
        # Check if quarterly 13F filing is due
        if self._is_quarter_end(report_date):
            filing_result = await self._generate_13f_filing(report_date)
            if filing_result['success']:
                results["filings_generated"] += 1
        
        return results
    
    def _is_quarter_end(self, check_date: date) -> bool:
        """Check if date is end of quarter"""
        return check_date.month in [3, 6, 9, 12] and check_date.day == 31 or (
            check_date.month == 3 and check_date.day == 30
        )
    
    async def _generate_13f_filing(self, quarter_end_date: date) -> Dict[str, Any]:
        """Generate 13F regulatory filing"""
        logger.info(f"📋 Generating 13F filing for quarter ending {quarter_end_date}")
        
        try:
            async with self.db_manager.pool.acquire() as conn:
                # Get all positions > $200k threshold for 13F reporting
                positions = await conn.fetch("""
                    SELECT 
                        cp.symbol,
                        SUM(cp.quantity) as total_quantity,
                        SUM(cp.market_value) as total_market_value,
                        s.cusip,
                        s.security_name,
                        'COM' as security_type
                    FROM positions.current_positions cp
                    JOIN reference_data.securities s ON cp.symbol = s.symbol
                    WHERE cp.position_date = $1 
                      AND cp.quantity > 0  -- Long positions only
                    GROUP BY cp.symbol, s.cusip, s.security_name
                    HAVING SUM(cp.market_value) >= 200000  -- $200k threshold
                    ORDER BY total_market_value DESC
                """, quarter_end_date)
                
                if not positions:
                    return {"success": False, "error": "No positions meet 13F threshold"}
                
                # Calculate total portfolio value
                total_value = sum(float(pos['total_market_value']) for pos in positions)
                
                # Create 13F filing data
                filing_data = {
                    "filing_type": "13F-HR",
                    "period_end": str(quarter_end_date),
                    "total_value": total_value,
                    "position_count": len(positions),
                    "positions": []
                }
                
                for pos in positions:
                    filing_data["positions"].append({
                        "cusip": pos['cusip'],
                        "security_name": pos['security_name'],
                        "security_type": pos['security_type'],
                        "shares": float(pos['total_quantity']),
                        "market_value": float(pos['total_market_value']),
                        "voting_authority": "SOLE",
                        "investment_discretion": "DFND"
                    })
                
                # Store filing
                filing_due_date = quarter_end_date + timedelta(days=45)  # 45 days after quarter end
                
                await conn.execute("""
                    INSERT INTO reporting.regulatory_filings
                    (filing_type, filing_period_end, filing_due_date, status, filing_data)
                    VALUES ($1, $2, $3, $4, $5)
                """, "13F-HR", quarter_end_date, filing_due_date, "PENDING", 
                json.dumps(filing_data))
                
                logger.info(f"✅ 13F filing generated: {len(positions)} positions, ${total_value:,.0f} total value")
                
                return {
                    "success": True,
                    "filing_type": "13F-HR",
                    "position_count": len(positions),
                    "total_value": total_value
                }
                
        except Exception as e:
            logger.error(f"❌ Failed to generate 13F filing: {e}", exc_info=True)
            return {"success": False, "error": str(e)}
    
    async def _store_report_metadata(self, report_type: ReportType, account_id: str,
                                   report_date: date, report_data: Dict[str, Any]) -> str:
        """Store report metadata in catalog"""
        async with self.db_manager.pool.acquire() as conn:
            # Store report data as JSON
            file_size = len(json.dumps(report_data).encode('utf-8'))
            
            result = await conn.fetchrow("""
                INSERT INTO reporting.report_catalog
                (report_type, report_name, account_id, report_date, report_format,
                 file_size, parameters)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                RETURNING report_id
            """, report_type.value, f"{report_type.value}_{account_id}_{report_date}",
            account_id, report_date, ReportFormat.JSON.value, file_size, 
            json.dumps(report_data))
            
            return str(result['report_id'])
    
    async def _send_scheduled_reports(self, report_date: date):
        """Send reports to subscribed users"""
        logger.info(f"📧 Sending scheduled reports for {report_date}")
        
        async with self.db_manager.pool.acquire() as conn:
            # Get active subscriptions
            subscriptions = await conn.fetch("""
                SELECT * FROM reporting.report_subscriptions
                WHERE is_active = TRUE
            """)
            
            for subscription in subscriptions:
                # This would integrate with email/notification service
                # For now, just log the action
                logger.info(f"📧 Would send {subscription['report_type']} report to {subscription['delivery_address']}")
    
    async def get_report(self, report_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a specific report"""
        async with self.db_manager.pool.acquire() as conn:
            report = await conn.fetchrow("""
                SELECT * FROM reporting.report_catalog
                WHERE report_id = $1
            """, report_id)
            
            if report:
                return dict(report)
            return None
    
    async def list_reports(self, account_id: str = None, report_date: date = None,
                          report_type: ReportType = None) -> List[Dict[str, Any]]:
        """List reports with optional filters"""
        async with self.db_manager.pool.acquire() as conn:
            query = "SELECT * FROM reporting.report_catalog WHERE 1=1"
            params = []
            
            if account_id:
                query += " AND account_id = $" + str(len(params) + 1)
                params.append(account_id)
            
            if report_date:
                query += " AND report_date = $" + str(len(params) + 1)
                params.append(report_date)
            
            if report_type:
                query += " AND report_type = $" + str(len(params) + 1)
                params.append(report_type.value)
            
            query += " ORDER BY generation_time DESC LIMIT 100"
            
            rows = await conn.fetch(query, *params)
            return [dict(row) for row in rows]
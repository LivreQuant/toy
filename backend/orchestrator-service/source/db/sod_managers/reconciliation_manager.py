# db/managers/reconciliation_manager.py
from typing import Dict, List, Any, Optional
from datetime import date, datetime, timedelta
from decimal import Decimal
import json
from .base_manager import BaseManager

class ReconciliationManager(BaseManager):
    """Database manager for reconciliation operations"""
    
    # =================================================================
    # POSITION RECONCILIATION OPERATIONS
    # =================================================================
    
    async def get_primary_positions(self, recon_date: date) -> List[Dict[str, Any]]:
        """Get positions from primary system"""
        return await self.fetch_all("""
            SELECT 
                account_id,
                symbol,
                quantity,
                avg_cost,
                market_value,
                last_price,
                position_date
            FROM positions.current_positions
            WHERE position_date = $1 AND quantity != 0
            ORDER BY account_id, symbol
        """, recon_date)
    
    async def get_unique_accounts(self) -> List[Dict[str, Any]]:
        """Get all unique account IDs"""
        return await self.fetch_all("""
            SELECT DISTINCT account_id FROM positions.current_positions
            ORDER BY account_id
        """)
    
    async def save_position_reconciliation_results(self, recon_results: List[Dict[str, Any]], recon_date: date):
        """Save position reconciliation results"""
        # Clear existing results for this date
        await self.execute("""
            DELETE FROM reconciliation.position_recon WHERE recon_date = $1
        """, recon_date)
        
        # Insert new results
        if recon_results:
            insert_data = []
            for result in recon_results:
                insert_data.append((
                    recon_date,
                    result['account_id'],
                    result['symbol'],
                    result['source_system'],
                    result['target_system'],
                    float(result.get('source_quantity', 0)),
                    float(result.get('target_quantity', 0)),
                    float(result.get('quantity_difference', 0)),
                    float(result.get('source_market_value', 0)),
                    float(result.get('target_market_value', 0)),
                    float(result.get('value_difference', 0)),
                    result['reconciliation_status'],
                    result.get('tolerance_breached', False),
                    result.get('comments')
                ))
            
            await self.bulk_insert(
                'reconciliation.position_recon',
                ['recon_date', 'account_id', 'symbol', 'source_system', 'target_system',
                 'source_quantity', 'target_quantity', 'quantity_difference',
                 'source_market_value', 'target_market_value', 'value_difference',
                 'reconciliation_status', 'tolerance_breached', 'comments'],
                insert_data
            )
    
    async def save_reconciliation_breaks(self, breaks: List[Dict[str, Any]], recon_date: date):
        """Save reconciliation breaks"""
        # Clear existing breaks for this date
        await self.execute("""
            DELETE FROM reconciliation.recon_breaks WHERE recon_date = $1
        """, recon_date)
        
        # Insert new breaks
        if breaks:
            insert_data = []
            for break_record in breaks:
                insert_data.append((
                    recon_date,
                    break_record['account_id'],
                    break_record['symbol'],
                    break_record['break_type'],
                    break_record['break_description'],
                    float(break_record.get('impact_amount', 0)),
                    break_record.get('resolution_status', 'OPEN')
                ))
            
            await self.bulk_insert(
                'reconciliation.recon_breaks',
                ['recon_date', 'account_id', 'symbol', 'break_type', 'break_description',
                 'impact_amount', 'resolution_status'],
                insert_data
            )
    
    async def save_position_recon_summary(self, summary: Dict[str, Any], recon_date: date):
        """Save position reconciliation summary"""
        await self.execute("""
            INSERT INTO reconciliation.recon_summary
            (recon_date, total_positions, matched_positions, discrepancy_positions,
             missing_positions, total_market_value, total_discrepancy_value, reconciliation_rate)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            ON CONFLICT (recon_date)
            DO UPDATE SET
                total_positions = EXCLUDED.total_positions,
                matched_positions = EXCLUDED.matched_positions,
                discrepancy_positions = EXCLUDED.discrepancy_positions,
                missing_positions = EXCLUDED.missing_positions,
                total_market_value = EXCLUDED.total_market_value,
                total_discrepancy_value = EXCLUDED.total_discrepancy_value,
                reconciliation_rate = EXCLUDED.reconciliation_rate
        """, 
        recon_date, 
        summary['total_positions'],
        summary['matched_positions'], 
        summary['discrepancy_positions'],
        summary['missing_positions'],
        float(summary.get('total_market_value', 0)),
        float(summary.get('total_discrepancy_value', 0)),
        float(summary.get('reconciliation_rate', 0))
        )
    
    async def get_position_recon_summary(self, recon_date: date) -> Optional[Dict[str, Any]]:
        """Get position reconciliation summary"""
        summary = await self.fetch_one("""
            SELECT * FROM reconciliation.recon_summary
            WHERE recon_date = $1
        """, recon_date)
        
        if not summary:
            return None
        
        # Get break details
        breaks = await self.fetch_all("""
            SELECT 
                break_type,
                COUNT(*) as count,
                SUM(impact_amount) as total_impact,
                AVG(impact_amount) as avg_impact
            FROM reconciliation.recon_breaks
            WHERE recon_date = $1
            GROUP BY break_type
            ORDER BY total_impact DESC
        """, recon_date)
        
        # Get top discrepancies
        top_discrepancies = await self.fetch_all("""
            SELECT 
                account_id,
                symbol,
                quantity_difference,
                value_difference,
                reconciliation_status
            FROM reconciliation.position_recon
            WHERE recon_date = $1 AND tolerance_breached = TRUE
            ORDER BY ABS(value_difference) DESC
            LIMIT 10
        """, recon_date)
        
        result = dict(summary)
        result['break_details'] = breaks
        result['top_discrepancies'] = top_discrepancies
        
        return result
    
    async def get_position_breaks(self, recon_date: date, resolution_status: str = None) -> List[Dict[str, Any]]:
        """Get position reconciliation breaks"""
        if resolution_status:
            return await self.fetch_all("""
                SELECT * FROM reconciliation.recon_breaks
                WHERE recon_date = $1 AND resolution_status = $2
                ORDER BY impact_amount DESC
            """, recon_date, resolution_status)
        else:
            return await self.fetch_all("""
                SELECT * FROM reconciliation.recon_breaks
                WHERE recon_date = $1
                ORDER BY impact_amount DESC
            """, recon_date)
    
    # =================================================================
    # CASH RECONCILIATION OPERATIONS
    # =================================================================
    
    async def get_account_cash_transactions(self, account_id: str, transaction_date: date) -> List[Dict[str, Any]]:
        """Get cash transactions for an account"""
        return await self.fetch_all("""
            SELECT 
                trade_id,
                symbol,
                side,
                quantity,
                price,
                commission,
                trade_value,
                settlement_date
            FROM trades.executed_trades
            WHERE account_id = $1 AND settlement_date <= $2
            ORDER BY settlement_date
        """, account_id, transaction_date)
    
    async def get_account_dividends(self, account_id: str, payment_date: date) -> List[Dict[str, Any]]:
        """Get dividends for an account"""
        return await self.fetch_all("""
            SELECT 
                symbol,
                dividend_amount,
                shares_held,
                total_dividend
            FROM dividends.dividend_payments
            WHERE account_id = $1 AND payment_date <= $2
            ORDER BY payment_date
        """, account_id, payment_date)
    
    async def save_cash_balances(self, balances: List[Dict[str, Any]], source_system: str, balance_date: date):
        """Save cash balances"""
        # Clear existing balances for this date and source
        await self.execute("""
            DELETE FROM reconciliation.cash_balances 
            WHERE balance_date = $1 AND source_system = $2
        """, balance_date, source_system)
        
        # Insert new balances
        if balances:
            insert_data = []
            for balance in balances:
                insert_data.append((
                    balance_date,
                    balance['account_id'],
                    balance['currency'],
                    balance['balance_type'],
                    float(balance['balance_amount']),
                    source_system
                ))
            
            await self.bulk_insert(
                'reconciliation.cash_balances',
                ['balance_date', 'account_id', 'currency', 'balance_type', 'balance_amount', 'source_system'],
                insert_data
            )
    
    async def save_cash_reconciliation_results(self, recon_results: List[Dict[str, Any]], recon_date: date):
        """Save cash reconciliation results"""
        # Clear existing results for this date
        await self.execute("""
            DELETE FROM reconciliation.cash_recon WHERE recon_date = $1
        """, recon_date)
        
        # Insert new results
        if recon_results:
            insert_data = []
            for result in recon_results:
                insert_data.append((
                    recon_date,
                    result['account_id'],
                    result['currency'],
                    result['balance_type'],
                    float(result.get('source_balance', 0)),
                    float(result.get('target_balance', 0)),
                    float(result.get('balance_difference', 0)),
                    result['reconciliation_status'],
                    result.get('tolerance_breached', False),
                    result.get('comments')
                ))
            
            await self.bulk_insert(
                'reconciliation.cash_recon',
                ['recon_date', 'account_id', 'currency', 'balance_type', 'source_balance',
                 'target_balance', 'balance_difference', 'reconciliation_status',
                 'tolerance_breached', 'comments'],
                insert_data
            )
    
    async def record_cash_movement(self, movement_date: date, account_id: str, currency: str,
                                 movement_type: str, amount: Decimal, reference_id: str = None,
                                 description: str = None) -> str:
        """Record a cash movement"""
        result = await self.execute_returning("""
            INSERT INTO reconciliation.cash_movements
            (movement_date, account_id, currency, movement_type, movement_amount,
             reference_id, description, source_system)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            RETURNING movement_id
        """, movement_date, account_id, currency, movement_type, float(amount),
        reference_id, description, 'INTERNAL')
        
        return str(result['movement_id']) if result else None
    
    async def get_cash_reconciliation_summary(self, recon_date: date) -> Dict[str, Any]:
        """Get cash reconciliation summary for a date"""
        # Overall statistics
        overall = await self.fetch_one("""
            SELECT 
                COUNT(*) as total_reconciliations,
                COUNT(CASE WHEN reconciliation_status = 'MATCHED' THEN 1 END) as matched,
                COUNT(CASE WHEN tolerance_breached THEN 1 END) as discrepancies,
                SUM(ABS(balance_difference)) as total_discrepancy_amount
            FROM reconciliation.cash_recon
            WHERE recon_date = $1
        """, recon_date)
        
        # By account breakdown
        by_account = await self.fetch_all("""
            SELECT 
                account_id,
                currency,
                COUNT(*) as balance_types,
                SUM(ABS(balance_difference)) as account_discrepancy
            FROM reconciliation.cash_recon
            WHERE recon_date = $1
            GROUP BY account_id, currency
            ORDER BY account_discrepancy DESC
        """, recon_date)
        
        # Largest discrepancies
        top_discrepancies = await self.fetch_all("""
            SELECT 
                account_id,
                currency,
                balance_type,
                source_balance,
                target_balance,
                balance_difference,
                comments
            FROM reconciliation.cash_recon
            WHERE recon_date = $1 AND tolerance_breached = TRUE
            ORDER BY ABS(balance_difference) DESC
            LIMIT 10
        """, recon_date)
        
        return {
            "recon_date": str(recon_date),
            "overall_statistics": dict(overall) if overall else {},
            "by_account": by_account,
            "top_discrepancies": top_discrepancies
        }
    
    async def get_cash_movements(self, account_id: str = None, start_date: date = None,
                               end_date: date = None, movement_type: str = None) -> List[Dict[str, Any]]:
        """Get cash movements with optional filters"""
        where_conditions = []
        params = []
        
        if account_id:
            where_conditions.append(f"account_id = ${len(params) + 1}")
            params.append(account_id)
        
        if start_date:
            where_conditions.append(f"movement_date >= ${len(params) + 1}")
            params.append(start_date)
        
        if end_date:
            where_conditions.append(f"movement_date <= ${len(params) + 1}")
            params.append(end_date)
        
        if movement_type:
            where_conditions.append(f"movement_type = ${len(params) + 1}")
            params.append(movement_type)
        
        where_clause = " AND ".join(where_conditions) if where_conditions else "1=1"
        
        return await self.fetch_all(f"""
            SELECT * FROM reconciliation.cash_movements
            WHERE {where_clause}
            ORDER BY movement_date DESC, created_at DESC
            LIMIT 1000
        """, *params)
    
    # =================================================================
    # GENERAL RECONCILIATION OPERATIONS
    # =================================================================
    
    async def cleanup_old_reconciliation_data(self, cutoff_date: date) -> Dict[str, int]:
        """Clean up old reconciliation data"""
        # Clean up position reconciliation data
        pos_recon_result = await self.execute("""
            DELETE FROM reconciliation.position_recon
            WHERE recon_date < $1
        """, cutoff_date)
        
        pos_recon_deleted = int(pos_recon_result.split()[1]) if pos_recon_result and 'DELETE' in pos_recon_result else 0
        
        # Clean up breaks
        breaks_result = await self.execute("""
            DELETE FROM reconciliation.recon_breaks
            WHERE recon_date < $1 AND resolution_status IN ('RESOLVED', 'IGNORED')
        """, cutoff_date)
        
        breaks_deleted = int(breaks_result.split()[1]) if breaks_result and 'DELETE' in breaks_result else 0
        
        # Clean up cash reconciliation data
        cash_result = await self.execute("""
            DELETE FROM reconciliation.cash_recon
            WHERE recon_date < $1
        """, cutoff_date)
        
        cash_deleted = int(cash_result.split()[1]) if cash_result and 'DELETE' in cash_result else 0
        
        # Clean up cash balances
        cash_bal_result = await self.execute("""
            DELETE FROM reconciliation.cash_balances
            WHERE balance_date < $1
        """, cutoff_date)
        
        cash_bal_deleted = int(cash_bal_result.split()[1]) if cash_bal_result and 'DELETE' in cash_bal_result else 0
        
        return {
            "position_recon_deleted": pos_recon_deleted,
            "breaks_deleted": breaks_deleted,
            "cash_recon_deleted": cash_deleted,
            "cash_balances_deleted": cash_bal_deleted,
            "total_deleted": pos_recon_deleted + breaks_deleted + cash_deleted + cash_bal_deleted
        }
    
    async def get_reconciliation_statistics(self, days_back: int = 30) -> Dict[str, Any]:
        """Get reconciliation statistics"""
        end_date = date.today()
        start_date = end_date - timedelta(days=days_back)
        
        # Position reconciliation stats
        pos_stats = await self.fetch_one("""
            SELECT 
                COUNT(*) as total_position_recons,
                AVG(reconciliation_rate) as avg_reconciliation_rate,
                COUNT(DISTINCT recon_date) as recon_dates,
                SUM(total_discrepancy_value) as total_discrepancy_value
            FROM reconciliation.recon_summary
            WHERE recon_date BETWEEN $1 AND $2
        """, start_date, end_date)
        
        # Cash reconciliation stats
        cash_stats = await self.fetch_one("""
            SELECT 
                COUNT(*) as total_cash_recons,
                COUNT(CASE WHEN reconciliation_status = 'MATCHED' THEN 1 END) as cash_matched,
                SUM(ABS(balance_difference)) as total_cash_discrepancy
            FROM reconciliation.cash_recon
            WHERE recon_date BETWEEN $1 AND $2
        """, start_date, end_date)
        
        return {
            "period": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "days": days_back
            },
            "position_statistics": dict(pos_stats) if pos_stats else {},
            "cash_statistics": dict(cash_stats) if cash_stats else {},
            "generated_at": datetime.utcnow().isoformat()
        }
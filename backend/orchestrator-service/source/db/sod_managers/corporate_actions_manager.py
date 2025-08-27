# db/managers/corporate_actions_manager.py
from typing import Dict, List, Any, Optional, Union
from datetime import date, datetime
from decimal import Decimal
import json
from .base_manager import BaseManager

class CorporateActionsManager(BaseManager):
    """Database manager for corporate actions operations"""
    
    # =================================================================
    # CORPORATE ACTIONS CRUD OPERATIONS
    # =================================================================
    
    async def create_corporate_action(self, symbol: str, action_type: str, 
                                    announcement_date: date, ex_date: date,
                                    action_details: Dict[str, Any], record_date: date = None,
                                    payment_date: date = None, effective_date: date = None) -> str:
        """Create a new corporate action"""
        result = await self.execute_returning("""
            INSERT INTO corporate_actions.actions
            (symbol, action_type, announcement_date, ex_date, record_date,
             payment_date, effective_date, action_details, status)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, 'PENDING')
            RETURNING action_id
        """, symbol, action_type, announcement_date, ex_date, record_date,
        payment_date, effective_date, json.dumps(action_details))
        
        return str(result['action_id']) if result else None
    
    async def get_pending_actions(self, processing_date: date) -> List[Dict[str, Any]]:
        """Get all pending corporate actions with ex_date <= processing_date"""
        return await self.fetch_all("""
            SELECT * FROM corporate_actions.actions
            WHERE status = 'PENDING' AND ex_date <= $1
            ORDER BY ex_date, symbol
        """, processing_date)
    
    async def get_corporate_action(self, action_id: str) -> Optional[Dict[str, Any]]:
        """Get corporate action by ID"""
        return await self.fetch_one("""
            SELECT * FROM corporate_actions.actions
            WHERE action_id = $1
        """, action_id)
    
    async def update_action_status(self, action_id: str, status: str, error_message: str = None):
        """Update corporate action status"""
        if error_message:
            await self.execute("""
                UPDATE corporate_actions.actions 
                SET status = $2, 
                    action_details = action_details || jsonb_build_object('error', $3),
                    updated_at = NOW()
                WHERE action_id = $1
            """, action_id, status, error_message)
        else:
            processed_at = datetime.utcnow() if status == 'PROCESSED' else None
            await self.execute("""
                UPDATE corporate_actions.actions 
                SET status = $2, processed_at = $3, updated_at = NOW()
                WHERE action_id = $1
            """, action_id, status, processed_at)
    
    async def get_pending_actions_summary(self) -> Dict[str, Any]:
        """Get summary of pending corporate actions"""
        summary = await self.fetch_all("""
            SELECT 
                action_type,
                COUNT(*) as count,
                MIN(ex_date) as earliest_ex_date,
                MAX(ex_date) as latest_ex_date
            FROM corporate_actions.actions
            WHERE status = 'PENDING'
            GROUP BY action_type
            ORDER BY action_type
        """)
        
        return {
            'by_type': summary,
            'total_pending': sum(row['count'] for row in summary)
        }
    
    # =================================================================
    # POSITION OPERATIONS
    # =================================================================
    
    async def get_positions_for_symbol(self, symbol: str) -> List[Dict[str, Any]]:
        """Get all current positions for a symbol"""
        return await self.fetch_all("""
            SELECT account_id, quantity, avg_cost
            FROM positions.current_positions 
            WHERE symbol = $1 AND quantity != 0
        """, symbol)
    
    async def get_long_positions_for_symbol(self, symbol: str) -> List[Dict[str, Any]]:
        """Get all long positions for a symbol"""
        return await self.fetch_all("""
            SELECT account_id, quantity, avg_cost
            FROM positions.current_positions
            WHERE symbol = $1 AND quantity > 0
        """, symbol)
    
    async def record_position_adjustment(self, action_id: str, account_id: str, symbol: str,
                                       adjustment_date: date, old_quantity: Decimal = None,
                                       new_quantity: Decimal = None, old_price: Decimal = None,
                                       new_price: Decimal = None, cash_adjustment: Decimal = None,
                                       adjustment_reason: str = None) -> str:
        """Record a position adjustment"""
        result = await self.execute_returning("""
            INSERT INTO corporate_actions.position_adjustments
            (action_id, account_id, symbol, adjustment_date, 
             old_quantity, new_quantity, old_price, new_price, 
             cash_adjustment, adjustment_reason)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            RETURNING adjustment_id
        """, action_id, account_id, symbol, adjustment_date,
        float(old_quantity) if old_quantity else None,
        float(new_quantity) if new_quantity else None,
        float(old_price) if old_price else None,
        float(new_price) if new_price else None,
        float(cash_adjustment) if cash_adjustment else None,
        adjustment_reason)
        
        return str(result['adjustment_id']) if result else None
    
    async def record_position_audit(self, account_id: str, symbol: str, adjustment_date: date,
                                  adjustment_type: str, old_quantity: Decimal = None,
                                  new_quantity: Decimal = None, old_avg_cost: Decimal = None,
                                  new_avg_cost: Decimal = None, cash_impact: Decimal = None,
                                  corporate_action_id: str = None, adjustment_reason: str = None) -> str:
        """Record position adjustment for audit"""
        result = await self.execute_returning("""
            INSERT INTO corporate_actions.position_adjustment_audit
            (account_id, symbol, adjustment_date, adjustment_type,
             old_quantity, new_quantity, old_avg_cost, new_avg_cost,
             cash_impact, corporate_action_id, adjustment_reason)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
            RETURNING audit_id
        """, account_id, symbol, adjustment_date, adjustment_type,
        float(old_quantity) if old_quantity else None,
        float(new_quantity) if new_quantity else None,
        float(old_avg_cost) if old_avg_cost else None,
        float(new_avg_cost) if new_avg_cost else None,
        float(cash_impact) if cash_impact else None,
        corporate_action_id, adjustment_reason)
        
        return str(result['audit_id']) if result else None
    
    # =================================================================
    # PRICE OPERATIONS
    # =================================================================
    
    async def get_historical_prices(self, symbol: str, before_date: date) -> List[Dict[str, Any]]:
        """Get historical prices before a specific date"""
        return await self.fetch_all("""
            SELECT price_date, price FROM positions.eod_prices
            WHERE symbol = $1 AND price_date < $2
            ORDER BY price_date DESC
        """, symbol, before_date)
    
    async def update_historical_price(self, symbol: str, price_date: date, new_price: Decimal) -> bool:
        """Update a specific historical price"""
        result = await self.execute("""
            UPDATE positions.eod_prices
            SET price = $1
            WHERE symbol = $2 AND price_date = $3
        """, float(new_price), symbol, price_date)
        
        # Parse result to check if rows were updated
        return result and 'UPDATE 1' in result
    
    async def bulk_update_historical_prices(self, symbol: str, before_date: date, 
                                          adjustment_factor: Decimal) -> int:
        """Bulk update historical prices with adjustment factor"""
        result = await self.execute("""
            UPDATE positions.eod_prices
            SET price = price * $1
            WHERE symbol = $2 AND price_date < $3
        """, float(adjustment_factor), symbol, before_date)
        
        # Extract row count from result
        return int(result.split()[1]) if result and 'UPDATE' in result else 0
    
    async def record_price_adjustment(self, action_id: str, symbol: str, adjustment_date: date,
                                    adjustment_factor: Decimal, dividend_amount: Decimal = None,
                                    adjustment_type: str = None) -> str:
        """Record a price adjustment"""
        result = await self.execute_returning("""
            INSERT INTO corporate_actions.price_adjustments
            (action_id, symbol, adjustment_date, adjustment_factor, 
             dividend_amount, adjustment_type)
            VALUES ($1, $2, $3, $4, $5, $6)
            RETURNING adjustment_id
        """, action_id, symbol, adjustment_date, float(adjustment_factor),
        float(dividend_amount) if dividend_amount else 0, adjustment_type)
        
        return str(result['adjustment_id']) if result else None
    
    async def record_price_adjustment_history(self, symbol: str, adjustment_date: date,
                                            adjustment_type: str, old_price: Decimal = None,
                                            new_price: Decimal = None, adjustment_factor: Decimal = None,
                                            dividend_amount: Decimal = None, split_ratio: Decimal = None,
                                            adjustment_reason: str = None) -> str:
        """Record price adjustment in history table"""
        result = await self.execute_returning("""
            INSERT INTO corporate_actions.price_adjustment_history
            (symbol, adjustment_date, adjustment_type, old_price, new_price,
             adjustment_factor, dividend_amount, split_ratio, adjustment_reason)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            RETURNING adjustment_id
        """, symbol, adjustment_date, adjustment_type,
        float(old_price) if old_price else None,
        float(new_price) if new_price else None,
        float(adjustment_factor) if adjustment_factor else None,
        float(dividend_amount) if dividend_amount else None,
        float(split_ratio) if split_ratio else None,
        adjustment_reason)
        
        return str(result['adjustment_id']) if result else None
    
    # =================================================================
    # ADJUSTMENT QUERIES AND REPORTS
    # =================================================================
    
    async def get_adjustment_summary(self, symbol: str = None, start_date: date = None,
                                   end_date: date = None) -> Dict[str, Any]:
        """Get summary of adjustments applied"""
        where_conditions = []
        params = []
        
        if symbol:
            where_conditions.append(f"symbol = ${len(params) + 1}")
            params.append(symbol)
        
        if start_date:
            where_conditions.append(f"adjustment_date >= ${len(params) + 1}")
            params.append(start_date)
        
        if end_date:
            where_conditions.append(f"adjustment_date <= ${len(params) + 1}")
            params.append(end_date)
        
        where_clause = " AND ".join(where_conditions) if where_conditions else "1=1"
        
        # Price adjustments summary
        price_summary = await self.fetch_all(f"""
            SELECT 
                adjustment_type,
                COUNT(*) as count,
                COUNT(DISTINCT symbol) as unique_symbols
            FROM corporate_actions.price_adjustment_history
            WHERE {where_clause}
            GROUP BY adjustment_type
            ORDER BY count DESC
        """, *params)
        
        # Position adjustments summary
        position_summary = await self.fetch_all(f"""
            SELECT 
                adjustment_type,
                COUNT(*) as count,
                COUNT(DISTINCT account_id) as unique_accounts
            FROM corporate_actions.position_adjustment_audit
            WHERE {where_clause}
            GROUP BY adjustment_type
            ORDER BY count DESC
        """, *params)
        
        return {
            "filter_criteria": {
                "symbol": symbol,
                "start_date": str(start_date) if start_date else None,
                "end_date": str(end_date) if end_date else None
            },
            "price_adjustments": price_summary,
            "position_adjustments": position_summary
        }
    
    async def get_adjustments_for_reversal(self, symbol: str, adjustment_date: date,
                                         adjustment_type: str) -> Dict[str, Any]:
        """Get adjustments that can be reversed"""
        price_adjustments = await self.fetch_all("""
            SELECT * FROM corporate_actions.price_adjustment_history
            WHERE symbol = $1 AND adjustment_date = $2 
              AND adjustment_type = $3 AND status = 'APPLIED'
        """, symbol, adjustment_date, adjustment_type)
        
        position_adjustments = await self.fetch_all("""
            SELECT * FROM corporate_actions.position_adjustment_audit
            WHERE symbol = $1 AND adjustment_date = $2 
              AND adjustment_type = $3 AND status = 'APPLIED'
        """, symbol, adjustment_date, adjustment_type)
        
        return {
            "price_adjustments": price_adjustments,
            "position_adjustments": position_adjustments
        }
    
    async def mark_adjustments_as_reversed(self, adjustment_ids: List[str], table_name: str):
        """Mark adjustments as reversed"""
        if not adjustment_ids:
            return
        
        placeholders = ','.join([f'${i+1}' for i in range(len(adjustment_ids))])
        
        if table_name == "price_adjustment_history":
            column_name = "adjustment_id"
        elif table_name == "position_adjustment_audit":
            column_name = "audit_id"
        else:
            raise ValueError(f"Invalid table name: {table_name}")
        
        query = f"""
            UPDATE corporate_actions.{table_name}
            SET status = 'REVERSED'
            WHERE {column_name} IN ({placeholders})
        """
        
        await self.execute(query, *adjustment_ids)
    
    async def cleanup_old_actions(self, cutoff_date: date) -> int:
        """Clean up old processed corporate actions"""
        result = await self.execute("""
            DELETE FROM corporate_actions.actions
            WHERE ex_date < $1 AND status IN ('PROCESSED', 'CANCELLED')
        """, cutoff_date)
        
        return int(result.split()[1]) if result and 'DELETE' in result else 0
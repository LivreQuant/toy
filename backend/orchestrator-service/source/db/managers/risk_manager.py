# db/managers/risk_manager.py
from typing import Dict, List, Any, Optional
from datetime import date, datetime
from decimal import Decimal
from .base_manager import BaseManager

class RiskManager(BaseManager):
    """Manages all risk model and metrics database operations"""
    
    async def initialize_tables(self):
        """Create risk model tables"""
        await self.create_schema_if_not_exists('risk_model')
        await self.create_schema_if_not_exists('risk_metrics')
        
        # Risk factors table
        await self.execute("""
            CREATE TABLE IF NOT EXISTS risk_model.risk_factors (
                factor_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                factor_date DATE NOT NULL,
                factor_type VARCHAR(50) NOT NULL,
                factor_name VARCHAR(100) NOT NULL,
                factor_value DECIMAL(12,8) NOT NULL,
                factor_volatility DECIMAL(12,8),
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                UNIQUE(factor_date, factor_type, factor_name)
            )
        """)
        
        # Factor exposures table
        await self.execute("""
            CREATE TABLE IF NOT EXISTS risk_model.factor_exposures (
                exposure_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                factor_date DATE NOT NULL,
                symbol VARCHAR(20) NOT NULL,
                factor_name VARCHAR(100) NOT NULL,
                exposure DECIMAL(12,8) NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                UNIQUE(factor_date, symbol, factor_name)
            )
        """)
        
        # Portfolio VaR table
        await self.execute("""
            CREATE TABLE IF NOT EXISTS risk_metrics.portfolio_var (
                var_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                account_id VARCHAR(50) NOT NULL,
                calculation_date DATE NOT NULL,
                confidence_level DECIMAL(5,3) NOT NULL,
                holding_period INTEGER NOT NULL,
                var_amount DECIMAL(20,2) NOT NULL,
                expected_shortfall DECIMAL(20,2),
                portfolio_value DECIMAL(20,2) NOT NULL,
                var_percentage DECIMAL(8,4) NOT NULL,
                method VARCHAR(50) NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                UNIQUE(account_id, calculation_date, confidence_level, holding_period, method)
            )
        """)
        
        # Create indexes
        await self.execute("CREATE INDEX IF NOT EXISTS idx_risk_factors_date ON risk_model.risk_factors(factor_date, factor_type)")
        await self.execute("CREATE INDEX IF NOT EXISTS idx_factor_exposures_symbol ON risk_model.factor_exposures(symbol, factor_date)")
        await self.execute("CREATE INDEX IF NOT EXISTS idx_portfolio_var_account ON risk_metrics.portfolio_var(account_id, calculation_date)")
    
    async def upsert_risk_factors(self, factor_data: List[Dict[str, Any]]) -> int:
        """Insert or update risk factors"""
        if not factor_data:
            return 0
        
        queries = []
        for factor in factor_data:
            query = """
                INSERT INTO risk_model.risk_factors
                (factor_date, factor_type, factor_name, factor_value, factor_volatility)
                VALUES ($1, $2, $3, $4, $5)
                ON CONFLICT (factor_date, factor_type, factor_name)
                DO UPDATE SET
                    factor_value = EXCLUDED.factor_value,
                    factor_volatility = EXCLUDED.factor_volatility
            """
            
            params = (
                factor['factor_date'], factor['factor_type'], factor['factor_name'],
                float(factor['factor_value']), float(factor.get('factor_volatility', 0))
            )
            queries.append((query, params))
        
        await self.execute_transaction(queries)
        return len(queries)
    
    async def get_risk_factors(self, factor_date: date, 
                             factor_type: str = None) -> List[Dict[str, Any]]:
        """Get risk factors for a date"""
        filters = {'factor_date': factor_date}
        if factor_type:
            filters['factor_type'] = factor_type
        
        where_clause, params = self.build_where_clause(filters)
        
        query = f"""
            SELECT * FROM risk_model.risk_factors
            WHERE {where_clause}
            ORDER BY factor_type, factor_name
        """
        
        rows = await self.fetch_all(query, *params)
        decimal_fields = ['factor_value', 'factor_volatility']
        return [self.convert_decimal_fields(row, decimal_fields) for row in rows]
    
    async def upsert_factor_exposures(self, exposure_data: List[Dict[str, Any]]) -> int:
        """Insert or update factor exposures"""
        if not exposure_data:
            return 0
        
        queries = []
        for exposure in exposure_data:
            query = """
                INSERT INTO risk_model.factor_exposures
                (factor_date, symbol, factor_name, exposure)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (factor_date, symbol, factor_name)
                DO UPDATE SET exposure = EXCLUDED.exposure
            """
            
            params = (
                exposure['factor_date'], exposure['symbol'], 
                exposure['factor_name'], float(exposure['exposure'])
            )
            queries.append((query, params))
        
        await self.execute_transaction(queries)
        return len(queries)
    
    async def calculate_portfolio_var(self, account_id: str, calculation_date: date,
                                    confidence_level: Decimal = Decimal('0.95'),
                                    holding_period: int = 1) -> Dict[str, Any]:
        """Calculate and store portfolio VaR"""
        # Get portfolio positions
        positions_query = """
            SELECT symbol, quantity, market_value, last_price
            FROM positions.current_positions
            WHERE account_id = $1 AND position_date = $2 AND quantity != 0
        """
        positions = await self.fetch_all(positions_query, account_id, calculation_date)
        
        if not positions:
            return {"error": "No positions found"}
        
        portfolio_value = sum(Decimal(str(p['market_value'])) for p in positions)
        
        # Simplified VaR calculation (in practice, would use full covariance matrix)
        # Assume 2% daily volatility for demonstration
        daily_volatility = Decimal('0.02')
        
        # Scale by holding period
        scaled_volatility = daily_volatility * Decimal(str(holding_period ** 0.5))
        
        # Calculate VaR based on confidence level
        elif confidence_level == Decimal('0.99'):
            z_score = Decimal('2.326')  # 99% confidence
        else:
            z_score = Decimal('1.96')   # Default 97.5% confidence
        
        var_amount = portfolio_value * scaled_volatility * z_score
        var_percentage = (var_amount / portfolio_value * 100) if portfolio_value > 0 else Decimal('0')
        
        # Expected shortfall (simplified as 1.3x VaR)
        expected_shortfall = var_amount * Decimal('1.3')
        
        # Store VaR calculation
        var_record = {
            'account_id': account_id,
            'calculation_date': calculation_date,
            'confidence_level': confidence_level,
            'holding_period': holding_period,
            'var_amount': var_amount,
            'expected_shortfall': expected_shortfall,
            'portfolio_value': portfolio_value,
            'var_percentage': var_percentage,
            'method': 'PARAMETRIC'
        }
        
        await self.upsert_portfolio_var([var_record])
        
        return {
            'account_id': account_id,
            'calculation_date': str(calculation_date),
            'var_amount': float(var_amount),
            'var_percentage': float(var_percentage),
            'expected_shortfall': float(expected_shortfall),
            'portfolio_value': float(portfolio_value),
            'confidence_level': float(confidence_level)
        }
    
    async def upsert_portfolio_var(self, var_records: List[Dict[str, Any]]) -> int:
        """Insert or update portfolio VaR records"""
        if not var_records:
            return 0
        
        queries = []
        for record in var_records:
            query = """
                INSERT INTO risk_metrics.portfolio_var
                (account_id, calculation_date, confidence_level, holding_period,
                    var_amount, expected_shortfall, portfolio_value, var_percentage, method)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                ON CONFLICT (account_id, calculation_date, confidence_level, holding_period, method)
                DO UPDATE SET
                    var_amount = EXCLUDED.var_amount,
                    expected_shortfall = EXCLUDED.expected_shortfall,
                    portfolio_value = EXCLUDED.portfolio_value,
                    var_percentage = EXCLUDED.var_percentage
            """
            
            params = (
                record['account_id'], record['calculation_date'],
                float(record['confidence_level']), record['holding_period'],
                float(record['var_amount']), float(record['expected_shortfall']),
                float(record['portfolio_value']), float(record['var_percentage']),
                record['method']
            )
            queries.append((query, params))
        
        await self.execute_transaction(queries)
        return len(queries)
    
    async def get_portfolio_var(self, account_id: str, calculation_date: date = None,
                                start_date: date = None, end_date: date = None) -> List[Dict[str, Any]]:
        """Get portfolio VaR records"""
        filters = {'account_id': account_id}
        if calculation_date:
            filters['calculation_date'] = calculation_date
        
        where_clause, params = self.build_where_clause(filters)
        
        if start_date:
            where_clause += f" AND calculation_date >= ${len(params) + 1}"
            params.append(start_date)
        
        if end_date:
            where_clause += f" AND calculation_date <= ${len(params) + 1}"
            params.append(end_date)
        
        query = f"""
            SELECT * FROM risk_metrics.portfolio_var
            WHERE {where_clause}
            ORDER BY calculation_date DESC, confidence_level
        """
        
        rows = await self.fetch_all(query, *params)
        decimal_fields = [
            'confidence_level', 'var_amount', 'expected_shortfall', 
            'portfolio_value', 'var_percentage'
        ]
        return [self.convert_decimal_fields(row, decimal_fields) for row in rows]
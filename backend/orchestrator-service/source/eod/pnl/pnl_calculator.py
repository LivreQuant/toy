# source/eod/pnl/pnl_calculator.py
import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import date, datetime, timedelta
from decimal import Decimal
from enum import Enum
import asyncio

logger = logging.getLogger(__name__)

class PnLType(Enum):
    REALIZED = "realized"
    UNREALIZED = "unrealized"
    TOTAL = "total"

class AttributionType(Enum):
    SECURITY_SELECTION = "security_selection"
    ASSET_ALLOCATION = "asset_allocation"
    TIMING = "timing"
    CURRENCY = "currency"
    INTERACTION = "interaction"

class PnLCalculator:
    """Calculates portfolio P&L and performance attribution"""
    
    def __init__(self, db_manager):
        self.db_manager = db_manager
        
    async def initialize(self):
        """Initialize P&L calculator"""
        await self._create_pnl_tables()
        logger.info("📊 P&L Calculator initialized")
    
    async def _create_pnl_tables(self):
        """Create P&L calculation tables"""
        async with self.db_manager.pool.acquire() as conn:
            await conn.execute("""
                CREATE SCHEMA IF NOT EXISTS pnl
            """)
            
            # Daily P&L table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS pnl.daily_pnl (
                    pnl_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    account_id VARCHAR(50) NOT NULL,
                    symbol VARCHAR(20),
                    pnl_date DATE NOT NULL,
                    realized_pnl DECIMAL(20,2) DEFAULT 0,
                    unrealized_pnl DECIMAL(20,2) DEFAULT 0,
                    total_pnl DECIMAL(20,2) DEFAULT 0,
                    market_value_start DECIMAL(20,2) DEFAULT 0,
                    market_value_end DECIMAL(20,2) DEFAULT 0,
                    net_flows DECIMAL(20,2) DEFAULT 0,
                    currency VARCHAR(3) DEFAULT 'USD',
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    UNIQUE(account_id, symbol, pnl_date)
                )
            """)
            
            # Performance attribution table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS pnl.performance_attribution (
                    attribution_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    account_id VARCHAR(50) NOT NULL,
                    attribution_date DATE NOT NULL,
                    attribution_type VARCHAR(50) NOT NULL,
                    attribution_value DECIMAL(20,2) NOT NULL,
                    attribution_pct DECIMAL(8,4) NOT NULL,
                    benchmark_return DECIMAL(8,4),
                    active_return DECIMAL(8,4),
                    information_ratio DECIMAL(8,4),
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                )
            """)
            
            # Portfolio performance table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS pnl.portfolio_performance (
                    performance_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    account_id VARCHAR(50) NOT NULL,
                    performance_date DATE NOT NULL,
                    total_return DECIMAL(8,4) NOT NULL,
                    benchmark_return DECIMAL(8,4),
                    active_return DECIMAL(8,4),
                    sharpe_ratio DECIMAL(8,4),
                    information_ratio DECIMAL(8,4),
                    max_drawdown DECIMAL(8,4),
                    volatility DECIMAL(8,4),
                    beta DECIMAL(8,4),
                    alpha DECIMAL(8,4),
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    UNIQUE(account_id, performance_date)
                )
            """)
            
            # Risk-adjusted returns
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS pnl.risk_adjusted_returns (
                    return_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    account_id VARCHAR(50) NOT NULL,
                    calculation_date DATE NOT NULL,
                    period_days INTEGER NOT NULL,
                    total_return DECIMAL(8,4) NOT NULL,
                    volatility DECIMAL(8,4) NOT NULL,
                    sharpe_ratio DECIMAL(8,4),
                    sortino_ratio DECIMAL(8,4),
                    calmar_ratio DECIMAL(8,4),
                    var_95 DECIMAL(20,2),
                    cvar_95 DECIMAL(20,2),
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                )
            """)
            
            # Create indices
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_daily_pnl_account_date 
                ON pnl.daily_pnl (account_id, pnl_date)
            """)
            
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_performance_attribution_date 
                ON pnl.performance_attribution (attribution_date, account_id)
            """)
    
    async def calculate_daily_pnl(self, calculation_date: date) -> Dict[str, Any]:
        """Calculate daily P&L for all accounts and positions"""
        logger.info(f"📊 Calculating daily P&L for {calculation_date}")
        
        try:
            results = {
                "accounts_processed": 0,
                "positions_processed": 0,
                "total_realized_pnl": Decimal('0'),
                "total_unrealized_pnl": Decimal('0'),
                "total_pnl": Decimal('0'),
                "pnl_by_account": {},
                "top_contributors": [],
                "top_detractors": []
            }
            
            # Step 1: Calculate realized P&L from trades
            realized_results = await self._calculate_realized_pnl(calculation_date)
            results["total_realized_pnl"] = realized_results["total_realized_pnl"]
            
            # Step 2: Calculate unrealized P&L from position markings
            unrealized_results = await self._calculate_unrealized_pnl(calculation_date)
            results["total_unrealized_pnl"] = unrealized_results["total_unrealized_pnl"]
            results["positions_processed"] = unrealized_results["positions_processed"]
            
            # Step 3: Combine and store daily P&L
            combined_results = await self._combine_and_store_pnl(
                calculation_date, realized_results["pnl_by_account"], 
                unrealized_results["pnl_by_account"]
            )
            results.update(combined_results)
            
            # Step 4: Calculate performance attribution
            attribution_results = await self._calculate_performance_attribution(calculation_date)
            results["attribution_calculated"] = attribution_results["attribution_entries"]
            
            # Convert Decimals to floats for JSON serialization
            results["total_realized_pnl"] = float(results["total_realized_pnl"])
            results["total_unrealized_pnl"] = float(results["total_unrealized_pnl"])
            results["total_pnl"] = float(results["total_pnl"])
            
            logger.info(f"✅ Daily P&L calculation complete: {results}")
            return results
            
        except Exception as e:
            logger.error(f"❌ Failed to calculate daily P&L: {e}", exc_info=True)
            raise
    
    async def _calculate_realized_pnl(self, calculation_date: date) -> Dict[str, Any]:
        """Calculate realized P&L from settled trades"""
        logger.info("💰 Calculating realized P&L")
        
        total_realized_pnl = Decimal('0')
        pnl_by_account = {}
        
        async with self.db_manager.pool.acquire() as conn:
            # Get all settled trades for the date
            trades = await conn.fetch("""
                SELECT 
                    account_id, 
                    symbol, 
                    side,
                    quantity,
                    price,
                    trade_value,
                    commission,
                    fees
                FROM settlement.trades
                WHERE trade_date = $1 
                  AND settlement_status = 'SETTLED'
                  AND side = 'SELL'  -- Only sells generate realized P&L
            """, calculation_date)
            
            for trade in trades:
                account_id = trade['account_id']
                symbol = trade['symbol']
                quantity = Decimal(str(trade['quantity']))
                sell_price = Decimal(str(trade['price']))
                commission = Decimal(str(trade['commission']))
                fees = Decimal(str(trade['fees']))
                
                # Get average cost basis (simplified - would use FIFO/LIFO in practice)
                avg_cost = await self._get_average_cost(account_id, symbol, calculation_date)
                
                if avg_cost:
                    # Calculate realized P&L
                    gross_proceeds = quantity * sell_price
                    cost_basis = quantity * avg_cost
                    realized_pnl = gross_proceeds - cost_basis - commission - fees
                    
                    total_realized_pnl += realized_pnl
                    
                    # Track by account
                    if account_id not in pnl_by_account:
                        pnl_by_account[account_id] = {}
                    
                    if symbol not in pnl_by_account[account_id]:
                        pnl_by_account[account_id][symbol] = {
                            'realized_pnl': Decimal('0'),
                            'unrealized_pnl': Decimal('0')
                        }
                    
                    pnl_by_account[account_id][symbol]['realized_pnl'] += realized_pnl
        
        return {
            "total_realized_pnl": total_realized_pnl,
            "pnl_by_account": pnl_by_account
        }
    
    async def _calculate_unrealized_pnl(self, calculation_date: date) -> Dict[str, Any]:
        """Calculate unrealized P&L from position markings"""
        logger.info("📈 Calculating unrealized P&L")
        
        total_unrealized_pnl = Decimal('0')
        pnl_by_account = {}
        positions_processed = 0
        
        async with self.db_manager.pool.acquire() as conn:
            # Get all positions with current markings
            positions = await conn.fetch("""
                SELECT 
                    account_id,
                    symbol,
                    quantity,
                    avg_cost,
                    market_value,
                    unrealized_pnl
                FROM positions.current_positions
                WHERE position_date = $1 AND quantity != 0
            """, calculation_date)
            
            for position in positions:
                positions_processed += 1
                account_id = position['account_id']
                symbol = position['symbol']
                unrealized_pnl = Decimal(str(position['unrealized_pnl'] or 0))
                
                total_unrealized_pnl += unrealized_pnl
                
                # Track by account
                if account_id not in pnl_by_account:
                    pnl_by_account[account_id] = {}
                
                if symbol not in pnl_by_account[account_id]:
                    pnl_by_account[account_id][symbol] = {
                        'realized_pnl': Decimal('0'),
                        'unrealized_pnl': Decimal('0')
                    }
                
                pnl_by_account[account_id][symbol]['unrealized_pnl'] = unrealized_pnl
        
        return {
            "total_unrealized_pnl": total_unrealized_pnl,
            "pnl_by_account": pnl_by_account,
            "positions_processed": positions_processed
        }
    
    # Continuing pnl_calculator.py

   async def _get_average_cost(self, account_id: str, symbol: str, as_of_date: date) -> Optional[Decimal]:
       """Get average cost basis for a position"""
       async with self.db_manager.pool.acquire() as conn:
           result = await conn.fetchrow("""
               SELECT avg_cost FROM positions.current_positions
               WHERE account_id = $1 AND symbol = $2 AND position_date <= $3
               ORDER BY position_date DESC
               LIMIT 1
           """, account_id, symbol, as_of_date)
           
           return Decimal(str(result['avg_cost'])) if result else None
   
   async def _combine_and_store_pnl(self, calculation_date: date, 
                                  realized_pnl: Dict[str, Dict[str, Dict[str, Decimal]]], 
                                  unrealized_pnl: Dict[str, Dict[str, Dict[str, Decimal]]]) -> Dict[str, Any]:
       """Combine realized and unrealized P&L and store in database"""
       logger.info("🔄 Combining and storing P&L data")
       
       accounts_processed = 0
       total_pnl = Decimal('0')
       pnl_by_account = {}
       top_contributors = []
       top_detractors = []
       
       # Get all unique account/symbol combinations
       all_accounts = set(realized_pnl.keys()) | set(unrealized_pnl.keys())
       
       async with self.db_manager.pool.acquire() as conn:
           # Clear existing data for the date
           await conn.execute("""
               DELETE FROM pnl.daily_pnl WHERE pnl_date = $1
           """, calculation_date)
           
           for account_id in all_accounts:
               accounts_processed += 1
               account_realized = realized_pnl.get(account_id, {})
               account_unrealized = unrealized_pnl.get(account_id, {})
               
               # Get all symbols for this account
               all_symbols = set(account_realized.keys()) | set(account_unrealized.keys())
               
               account_total_pnl = Decimal('0')
               position_pnl = {}
               
               for symbol in all_symbols:
                   realized = account_realized.get(symbol, {}).get('realized_pnl', Decimal('0'))
                   unrealized = account_unrealized.get(symbol, {}).get('unrealized_pnl', Decimal('0'))
                   position_total = realized + unrealized
                   
                   account_total_pnl += position_total
                   position_pnl[symbol] = {
                       'realized_pnl': float(realized),
                       'unrealized_pnl': float(unrealized),
                       'total_pnl': float(position_total)
                   }
                   
                   # Store individual position P&L
                   await conn.execute("""
                       INSERT INTO pnl.daily_pnl
                       (account_id, symbol, pnl_date, realized_pnl, unrealized_pnl, total_pnl)
                       VALUES ($1, $2, $3, $4, $5, $6)
                   """, account_id, symbol, calculation_date, 
                   float(realized), float(unrealized), float(position_total))
                   
                   # Track top contributors/detractors
                   if position_total > 0:
                       top_contributors.append({
                           'account_id': account_id,
                           'symbol': symbol,
                           'pnl': float(position_total)
                       })
                   elif position_total < 0:
                       top_detractors.append({
                           'account_id': account_id,
                           'symbol': symbol,
                           'pnl': float(position_total)
                       })
               
               # Store account-level P&L (symbol = NULL for account total)
               await conn.execute("""
                   INSERT INTO pnl.daily_pnl
                   (account_id, pnl_date, realized_pnl, unrealized_pnl, total_pnl)
                   VALUES ($1, $2, $3, $4, $5)
               """, account_id, calculation_date, 
               float(sum(account_realized.get(s, {}).get('realized_pnl', Decimal('0')) for s in all_symbols)),
               float(sum(account_unrealized.get(s, {}).get('unrealized_pnl', Decimal('0')) for s in all_symbols)),
               float(account_total_pnl))
               
               total_pnl += account_total_pnl
               pnl_by_account[account_id] = {
                   'total_pnl': float(account_total_pnl),
                   'positions': position_pnl
               }
       
       # Sort contributors and detractors
       top_contributors.sort(key=lambda x: x['pnl'], reverse=True)
       top_detractors.sort(key=lambda x: x['pnl'])
       
       return {
           "accounts_processed": accounts_processed,
           "total_pnl": total_pnl,
           "pnl_by_account": pnl_by_account,
           "top_contributors": top_contributors[:10],  # Top 10
           "top_detractors": top_detractors[:10]       # Bottom 10
       }
   
   async def _calculate_performance_attribution(self, calculation_date: date) -> Dict[str, Any]:
       """Calculate performance attribution by various factors"""
       logger.info("🎯 Calculating performance attribution")
       
       attribution_entries = 0
       
       async with self.db_manager.pool.acquire() as conn:
           # Clear existing attribution for the date
           await conn.execute("""
               DELETE FROM pnl.performance_attribution WHERE attribution_date = $1
           """, calculation_date)
           
           # Get all accounts with P&L
           accounts = await conn.fetch("""
               SELECT DISTINCT account_id FROM pnl.daily_pnl 
               WHERE pnl_date = $1 AND symbol IS NULL  -- Account totals only
           """, calculation_date)
           
           for account in accounts:
               account_id = account['account_id']
               
               # Calculate different attribution components
               attributions = await self._calculate_account_attribution(account_id, calculation_date)
               
               for attribution_type, attribution_value in attributions.items():
                   if attribution_value != 0:
                       await conn.execute("""
                           INSERT INTO pnl.performance_attribution
                           (account_id, attribution_date, attribution_type, 
                            attribution_value, attribution_pct)
                           VALUES ($1, $2, $3, $4, $5)
                       """, account_id, calculation_date, attribution_type.value,
                       float(attribution_value), float(attribution_value / 10000))  # Assume $10k base
                       
                       attribution_entries += 1
       
       return {"attribution_entries": attribution_entries}
   
   async def _calculate_account_attribution(self, account_id: str, calculation_date: date) -> Dict[AttributionType, Decimal]:
       """Calculate attribution components for a specific account"""
       # Simplified attribution calculation
       # In practice, this would use factor models and benchmark comparisons
       
       async with self.db_manager.pool.acquire() as conn:
           # Get position-level P&L
           positions = await conn.fetch("""
               SELECT symbol, total_pnl FROM pnl.daily_pnl
               WHERE account_id = $1 AND pnl_date = $2 AND symbol IS NOT NULL
           """, account_id, calculation_date)
           
           total_pnl = sum(Decimal(str(pos['total_pnl'])) for pos in positions)
           
           # Simple attribution breakdown (in practice, use actual factor exposures)
           attributions = {
               AttributionType.SECURITY_SELECTION: total_pnl * Decimal('0.6'),  # 60% from stock picking
               AttributionType.ASSET_ALLOCATION: total_pnl * Decimal('0.2'),    # 20% from allocation
               AttributionType.TIMING: total_pnl * Decimal('0.15'),             # 15% from timing
               AttributionType.CURRENCY: total_pnl * Decimal('0.05'),           # 5% from FX
               AttributionType.INTERACTION: total_pnl * Decimal('0.0')          # 0% interaction
           }
           
           return attributions
   
   async def calculate_risk_adjusted_returns(self, calculation_date: date, 
                                           lookback_periods: List[int] = [30, 60, 252]) -> Dict[str, Any]:
       """Calculate risk-adjusted returns for various periods"""
       logger.info(f"📈 Calculating risk-adjusted returns for {calculation_date}")
       
       results = {
           "accounts_processed": 0,
           "periods_calculated": len(lookback_periods),
           "risk_metrics": {}
       }
       
       async with self.db_manager.pool.acquire() as conn:
           # Get all accounts
           accounts = await conn.fetch("""
               SELECT DISTINCT account_id FROM pnl.daily_pnl 
               WHERE symbol IS NULL AND pnl_date <= $1
           """, calculation_date)
           
           for account in accounts:
               account_id = account['account_id']
               results["accounts_processed"] += 1
               
               account_metrics = {}
               
               for period_days in lookback_periods:
                   start_date = calculation_date - timedelta(days=period_days)
                   
                   # Get historical P&L for the period
                   daily_pnl = await conn.fetch("""
                       SELECT pnl_date, total_pnl 
                       FROM pnl.daily_pnl
                       WHERE account_id = $1 
                         AND symbol IS NULL 
                         AND pnl_date BETWEEN $2 AND $3
                       ORDER BY pnl_date
                   """, account_id, start_date, calculation_date)
                   
                   if len(daily_pnl) >= 10:  # Need minimum history
                       metrics = await self._calculate_risk_metrics(daily_pnl, period_days)
                       
                       # Store in database
                       await conn.execute("""
                           INSERT INTO pnl.risk_adjusted_returns
                           (account_id, calculation_date, period_days, total_return,
                            volatility, sharpe_ratio, sortino_ratio, var_95, cvar_95)
                           VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                           ON CONFLICT (account_id, calculation_date, period_days)
                           DO UPDATE SET
                               total_return = $4, volatility = $5, sharpe_ratio = $6,
                               sortino_ratio = $7, var_95 = $8, cvar_95 = $9
                       """, account_id, calculation_date, period_days,
                       metrics['total_return'], metrics['volatility'], 
                       metrics['sharpe_ratio'], metrics['sortino_ratio'],
                       metrics['var_95'], metrics['cvar_95'])
                       
                       account_metrics[f"{period_days}d"] = metrics
               
               results["risk_metrics"][account_id] = account_metrics
       
       return results
   
   async def _calculate_risk_metrics(self, daily_pnl: List[Dict], period_days: int) -> Dict[str, float]:
       """Calculate risk metrics from daily P&L data"""
       import numpy as np
       
       # Convert to numpy array for calculations
       pnl_values = np.array([float(row['total_pnl']) for row in daily_pnl])
       
       if len(pnl_values) == 0:
           return {
               'total_return': 0.0,
               'volatility': 0.0,
               'sharpe_ratio': 0.0,
               'sortino_ratio': 0.0,
               'var_95': 0.0,
               'cvar_95': 0.0
           }
       
       # Calculate metrics
       total_return = float(np.sum(pnl_values))
       daily_returns = pnl_values / 10000  # Assume $10k base for return calculation
       volatility = float(np.std(daily_returns) * np.sqrt(252))  # Annualized
       
       # Sharpe ratio (assuming 0% risk-free rate)
       mean_return = np.mean(daily_returns)
       sharpe_ratio = float(mean_return / np.std(daily_returns) * np.sqrt(252)) if np.std(daily_returns) > 0 else 0.0
       
       # Sortino ratio (downside deviation)
       downside_returns = daily_returns[daily_returns < 0]
       downside_std = np.std(downside_returns) if len(downside_returns) > 0 else 0.0
       sortino_ratio = float(mean_return / downside_std * np.sqrt(252)) if downside_std > 0 else 0.0
       
       # Value at Risk (95% confidence)
       var_95 = float(np.percentile(pnl_values, 5))
       
       # Conditional Value at Risk (expected shortfall)
       cvar_95 = float(np.mean(pnl_values[pnl_values <= var_95])) if np.any(pnl_values <= var_95) else var_95
       
       return {
           'total_return': total_return,
           'volatility': volatility,
           'sharpe_ratio': sharpe_ratio,
           'sortino_ratio': sortino_ratio,
           'var_95': var_95,
           'cvar_95': cvar_95
       }
   
   async def get_pnl_summary(self, summary_date: date, account_id: str = None) -> Dict[str, Any]:
       """Get P&L summary for a specific date"""
       async with self.db_manager.pool.acquire() as conn:
           where_clause = "WHERE pnl_date = $1"
           params = [summary_date]
           
           if account_id:
               where_clause += " AND account_id = $2"
               params.append(account_id)
           
           # Overall P&L statistics
           stats = await conn.fetchrow(f"""
               SELECT 
                   COUNT(DISTINCT account_id) as accounts,
                   COUNT(*) as total_positions,
                   SUM(realized_pnl) as total_realized_pnl,
                   SUM(unrealized_pnl) as total_unrealized_pnl,
                   SUM(total_pnl) as total_pnl,
                   AVG(total_pnl) as avg_position_pnl
               FROM pnl.daily_pnl
               {where_clause} AND symbol IS NOT NULL
           """, *params)
           
           # Top performing positions
           top_performers = await conn.fetch(f"""
               SELECT account_id, symbol, total_pnl
               FROM pnl.daily_pnl
               {where_clause} AND symbol IS NOT NULL AND total_pnl > 0
               ORDER BY total_pnl DESC
               LIMIT 10
           """, *params)
           
           # Worst performing positions
           worst_performers = await conn.fetch(f"""
               SELECT account_id, symbol, total_pnl
               FROM pnl.daily_pnl
               {where_clause} AND symbol IS NOT NULL AND total_pnl < 0
               ORDER BY total_pnl ASC
               LIMIT 10
           """, *params)
           
           # Performance attribution (if account specified)
           attribution = []
           if account_id:
               attribution = await conn.fetch("""
                   SELECT attribution_type, attribution_value, attribution_pct
                   FROM pnl.performance_attribution
                   WHERE account_id = $1 AND attribution_date = $2
                   ORDER BY ABS(attribution_value) DESC
               """, account_id, summary_date)
           
           return {
               "summary_date": str(summary_date),
               "account_filter": account_id,
               "statistics": dict(stats) if stats else {},
               "top_performers": [dict(row) for row in top_performers],
               "worst_performers": [dict(row) for row in worst_performers],
               "attribution": [dict(row) for row in attribution]
           }
   
   async def get_portfolio_performance_metrics(self, account_id: str, 
                                             start_date: date, end_date: date) -> Dict[str, Any]:
       """Get comprehensive performance metrics for a portfolio over a period"""
       async with self.db_manager.pool.acquire() as conn:
           # Get daily P&L series
           daily_pnl = await conn.fetch("""
               SELECT pnl_date, total_pnl
               FROM pnl.daily_pnl
               WHERE account_id = $1 AND symbol IS NULL
                 AND pnl_date BETWEEN $2 AND $3
               ORDER BY pnl_date
           """, account_id, start_date, end_date)
           
           if not daily_pnl:
               return {"error": "No P&L data found for the specified period"}
           
           # Calculate cumulative performance
           cumulative_pnl = []
           running_total = 0.0
           for row in daily_pnl:
               running_total += float(row['total_pnl'])
               cumulative_pnl.append({
                   'date': str(row['pnl_date']),
                   'daily_pnl': float(row['total_pnl']),
                   'cumulative_pnl': running_total
               })
           
           # Get risk-adjusted metrics
           period_days = (end_date - start_date).days
           risk_metrics = await self._calculate_risk_metrics(daily_pnl, period_days)
           
           # Get attribution data
           attribution = await conn.fetch("""
               SELECT 
                   attribution_type,
                   SUM(attribution_value) as total_attribution,
                   AVG(attribution_pct) as avg_attribution_pct
               FROM pnl.performance_attribution
               WHERE account_id = $1 AND attribution_date BETWEEN $2 AND $3
               GROUP BY attribution_type
               ORDER BY total_attribution DESC
           """, account_id, start_date, end_date)
           
           return {
               "account_id": account_id,
               "period": {"start": str(start_date), "end": str(end_date)},
               "summary": {
                   "total_pnl": running_total,
                   "total_days": len(daily_pnl),
                   "avg_daily_pnl": running_total / len(daily_pnl),
                   "best_day": max(row['daily_pnl'] for row in cumulative_pnl),
                   "worst_day": min(row['daily_pnl'] for row in cumulative_pnl)
               },
               "risk_metrics": risk_metrics,
               "attribution": [dict(row) for row in attribution],
               "daily_performance": cumulative_pnl
           }
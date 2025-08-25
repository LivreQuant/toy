# source/eod/pnl/attribution.py
import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import date, datetime, timedelta
from decimal import Decimal
from enum import Enum
import asyncio
import numpy as np

logger = logging.getLogger(__name__)

class AttributionMethod(Enum):
    BRINSON_HOOD_BEEBOWER = "brinson_hood_beebower"
    BRINSON_FACHLER = "brinson_fachler" 
    GEOMETRIC_ATTRIBUTION = "geometric_attribution"
    ARITHMETIC_ATTRIBUTION = "arithmetic_attribution"

class AttributionLevel(Enum):
    SECURITY = "security"
    SECTOR = "sector"
    COUNTRY = "country"
    CURRENCY = "currency"
    TOTAL = "total"

class PerformanceAttributor:
    """Calculates detailed performance attribution analysis"""
    
    def __init__(self, db_manager):
        self.db_manager = db_manager
        
        # Attribution parameters
        self.attribution_method = AttributionMethod.BRINSON_HOOD_BEEBOWER
        self.risk_free_rate = Decimal('0.05')  # 5% annual risk-free rate
        
    async def initialize(self):
        """Initialize performance attributor"""
        await self._create_attribution_tables()
        logger.info("🎯 Performance Attributor initialized")
    
    async def _create_attribution_tables(self):
        """Create attribution analysis tables"""
        async with self.db_manager.pool.acquire() as conn:
            await conn.execute("""
                CREATE SCHEMA IF NOT EXISTS attribution
            """)
            
            # Detailed attribution results
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS attribution.attribution_analysis (
                    analysis_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    account_id VARCHAR(50) NOT NULL,
                    analysis_date DATE NOT NULL,
                    attribution_level VARCHAR(20) NOT NULL,
                    attribution_category VARCHAR(100),
                    portfolio_weight DECIMAL(8,6) NOT NULL,
                    benchmark_weight DECIMAL(8,6) NOT NULL,
                    portfolio_return DECIMAL(12,8) NOT NULL,
                    benchmark_return DECIMAL(12,8) NOT NULL,
                    allocation_effect DECIMAL(12,8) NOT NULL,
                    selection_effect DECIMAL(12,8) NOT NULL,
                    interaction_effect DECIMAL(12,8) NOT NULL,
                    total_effect DECIMAL(12,8) NOT NULL,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                )
            """)
            
            # Risk attribution
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS attribution.risk_attribution (
                    risk_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    account_id VARCHAR(50) NOT NULL,
                    analysis_date DATE NOT NULL,
                    factor_name VARCHAR(100) NOT NULL,
                    factor_exposure DECIMAL(12,8) NOT NULL,
                    factor_return DECIMAL(12,8) NOT NULL,
                    contribution_to_return DECIMAL(12,8) NOT NULL,
                    contribution_to_risk DECIMAL(12,8) NOT NULL,
                    marginal_contribution DECIMAL(12,8) NOT NULL,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                )
            """)
            
            # Style attribution
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS attribution.style_attribution (
                    style_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    account_id VARCHAR(50) NOT NULL,
                    analysis_date DATE NOT NULL,
                    style_factor VARCHAR(50) NOT NULL,
                    portfolio_exposure DECIMAL(8,6) NOT NULL,
                    benchmark_exposure DECIMAL(8,6) NOT NULL,
                    factor_return DECIMAL(12,8) NOT NULL,
                    attribution_value DECIMAL(12,8) NOT NULL,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                )
            """)
            
            # Transaction cost attribution
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS attribution.transaction_attribution (
                    transaction_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    account_id VARCHAR(50) NOT NULL,
                    analysis_date DATE NOT NULL,
                    symbol VARCHAR(20) NOT NULL,
                    transaction_type VARCHAR(20) NOT NULL,
                    shares_traded DECIMAL(20,8) NOT NULL,
                    execution_price DECIMAL(20,8) NOT NULL,
                    benchmark_price DECIMAL(20,8) NOT NULL,
                    implementation_shortfall DECIMAL(12,8) NOT NULL,
                    market_impact DECIMAL(12,8) NOT NULL,
                    timing_cost DECIMAL(12,8) NOT NULL,
                    total_transaction_cost DECIMAL(12,8) NOT NULL,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                )
            """)
    
    async def calculate_performance_attribution(self, account_id: str, 
                                              attribution_date: date,
                                              benchmark_id: str = None) -> Dict[str, Any]:
        """Calculate comprehensive performance attribution"""
        logger.info(f"🎯 Calculating performance attribution for {account_id} on {attribution_date}")
        
        try:
            results = {
                "account_id": account_id,
                "attribution_date": str(attribution_date),
                "benchmark_id": benchmark_id or "SP500",
                "attribution_levels": [],
                "risk_attribution": {},
                "style_attribution": {},
                "transaction_attribution": {}
            }
            
            # Step 1: Calculate sector attribution
            sector_attribution = await self._calculate_sector_attribution(
                account_id, attribution_date, benchmark_id
            )
            results["attribution_levels"].append({
                "level": "sector",
                "attribution": sector_attribution
            })
            
            # Step 2: Calculate security selection attribution
            security_attribution = await self._calculate_security_attribution(
                account_id, attribution_date, benchmark_id
            )
            results["attribution_levels"].append({
                "level": "security",
                "attribution": security_attribution
            })
            
            # Step 3: Calculate factor-based risk attribution
            risk_attribution = await self._calculate_risk_attribution(
                account_id, attribution_date
            )
            results["risk_attribution"] = risk_attribution
            
            # Step 4: Calculate style attribution
            style_attribution = await self._calculate_style_attribution(
                account_id, attribution_date, benchmark_id
            )
            results["style_attribution"] = style_attribution
            
            # Step 5: Calculate transaction cost attribution
            transaction_attribution = await self._calculate_transaction_attribution(
                account_id, attribution_date
            )
            results["transaction_attribution"] = transaction_attribution
            
            # Step 6: Store all attribution results
            await self._store_attribution_results(results, attribution_date)
            
            logger.info(f"✅ Performance attribution complete for {account_id}")
            return results
            
        except Exception as e:
            logger.error(f"❌ Failed to calculate performance attribution: {e}", exc_info=True)
            raise
    
    async def _calculate_sector_attribution(self, account_id: str, attribution_date: date,
                                          benchmark_id: str) -> Dict[str, Any]:
        """Calculate sector-level attribution using Brinson model"""
        logger.info("🏭 Calculating sector attribution")
        
        # Get portfolio sector weights and returns
        portfolio_sectors = await self._get_portfolio_sector_data(account_id, attribution_date)
        
        # Get benchmark sector weights and returns (simulated)
        benchmark_sectors = await self._get_benchmark_sector_data(benchmark_id, attribution_date)
        
        sector_attributions = []
        total_allocation_effect = Decimal('0')
        total_selection_effect = Decimal('0')
        total_interaction_effect = Decimal('0')
        
        # Get all sectors
        all_sectors = set(portfolio_sectors.keys()) | set(benchmark_sectors.keys())
        
        for sector in all_sectors:
            portfolio_data = portfolio_sectors.get(sector, {'weight': Decimal('0'), 'return': Decimal('0')})
            benchmark_data = benchmark_sectors.get(sector, {'weight': Decimal('0'), 'return': Decimal('0')})
            
            wp = portfolio_data['weight']
            wb = benchmark_data['weight']
            rp = portfolio_data['return']
            rb = benchmark_data['return']
            
            # Calculate benchmark total return for allocation effect
            benchmark_total_return = self._calculate_benchmark_total_return(benchmark_sectors)
            
            # Brinson-Hood-Beebower attribution
            allocation_effect = (wp - wb) * rb
            selection_effect = wb * (rp - rb)
            interaction_effect = (wp - wb) * (rp - rb)
            total_effect = allocation_effect + selection_effect + interaction_effect
            
            sector_attribution = {
                'sector': sector,
                'portfolio_weight': float(wp),
                'benchmark_weight': float(wb),
                'portfolio_return': float(rp),
                'benchmark_return': float(rb),
                'allocation_effect': float(allocation_effect),
                'selection_effect': float(selection_effect),
                'interaction_effect': float(interaction_effect),
                'total_effect': float(total_effect)
            }
            
            sector_attributions.append(sector_attribution)
            
            total_allocation_effect += allocation_effect
            total_selection_effect += selection_effect
            total_interaction_effect += interaction_effect
        
        return {
            'sector_details': sector_attributions,
            'summary': {
                'total_allocation_effect': float(total_allocation_effect),
                'total_selection_effect': float(total_selection_effect),
                'total_interaction_effect': float(total_interaction_effect),
                'total_attribution': float(total_allocation_effect + total_selection_effect + total_interaction_effect)
            }
        }
    
    async def _calculate_security_attribution(self, account_id: str, attribution_date: date,
                                            benchmark_id: str) -> Dict[str, Any]:
        """Calculate security-level attribution"""
        logger.info("📈 Calculating security attribution")
        
        async with self.db_manager.pool.acquire() as conn:
            # Get portfolio positions and returns
            portfolio_positions = await conn.fetch("""
                SELECT 
                    p.symbol,
                    p.market_value,
                    p.unrealized_pnl,
                    s.sector,
                    (p.market_value / SUM(p.market_value) OVER()) * 100 as weight,
                    CASE WHEN p.market_value > 0 
                         THEN p.unrealized_pnl / p.market_value 
                         ELSE 0 
                    END as return
                FROM positions.current_positions p
                LEFT JOIN reference_data.securities s ON p.symbol = s.symbol
                WHERE p.account_id = $1 AND p.position_date = $2 AND p.quantity != 0
            """, account_id, attribution_date)
            
            security_attributions = []
            total_security_selection = Decimal('0')
            
            for position in portfolio_positions:
                symbol = position['symbol']
                portfolio_weight = Decimal(str(position['weight'])) / 100  # Convert to decimal
                portfolio_return = Decimal(str(position['return'] or 0))
                
                # Get benchmark weight and return for this security (simulated)
                benchmark_weight, benchmark_return = await self._get_benchmark_security_data(
                    symbol, benchmark_id, attribution_date
                )
                
                # Security selection effect
                selection_effect = benchmark_weight * (portfolio_return - benchmark_return)
                
                security_attribution = {
                    'symbol': symbol,
                    'sector': position['sector'],
                    'portfolio_weight': float(portfolio_weight),
                    'benchmark_weight': float(benchmark_weight),
                    'portfolio_return': float(portfolio_return),
                    'benchmark_return': float(benchmark_return),
                    'selection_effect': float(selection_effect)
                }
                
                security_attributions.append(security_attribution)
                total_security_selection += selection_effect
            
            # Sort by absolute contribution
            security_attributions.sort(key=lambda x: abs(x['selection_effect']), reverse=True)
            
            return {
                'security_details': security_attributions[:20],  # Top 20 contributors
                'total_security_selection': float(total_security_selection),
                'top_contributors': security_attributions[:5],
                'top_detractors': sorted(security_attributions, key=lambda x: x['selection_effect'])[:5]
            }
    
    async def _calculate_risk_attribution(self, account_id: str, attribution_date: date) -> Dict[str, Any]:
        """Calculate risk factor attribution"""
        logger.info("⚡ Calculating risk factor attribution")
        
        async with self.db_manager.pool.acquire() as conn:
            # Get factor exposures for portfolio
            factor_exposures = await conn.fetch("""
                SELECT 
                    fe.factor_name,
                    AVG(fe.exposure * (cp.market_value / SUM(cp.market_value) OVER())) as portfolio_exposure
                FROM risk_model.factor_exposures fe
                JOIN positions.current_positions cp ON fe.symbol = cp.symbol
                WHERE fe.factor_date = $1 AND cp.account_id = $2 AND cp.position_date = $1
                GROUP BY fe.factor_name
            """, attribution_date, account_id)
            
            # Get factor returns
            factor_returns = await conn.fetch("""
                SELECT factor_name, factor_value as factor_return
                FROM risk_model.risk_factors
                WHERE factor_date = $1
            """, attribution_date)
            
            factor_return_dict = {f['factor_name']: Decimal(str(f['factor_return'])) 
                                for f in factor_returns}
            
            risk_attributions = []
            total_factor_contribution = Decimal('0')
            
            for exposure in factor_exposures:
                factor_name = exposure['factor_name']
                portfolio_exposure = Decimal(str(exposure['portfolio_exposure'] or 0))
                factor_return = factor_return_dict.get(factor_name, Decimal('0'))
                
                # Contribution to return = exposure * factor return
                contribution_to_return = portfolio_exposure * factor_return
                
                # Contribution to risk (simplified)
                contribution_to_risk = abs(portfolio_exposure) * abs(factor_return)
                
                # Marginal contribution (simplified)
                marginal_contribution = contribution_to_return * Decimal('1.1')  # 10% uplift
                
                risk_attribution = {
                    'factor_name': factor_name,
                    'factor_exposure': float(portfolio_exposure),
                    'factor_return': float(factor_return),
                    'contribution_to_return': float(contribution_to_return),
                    'contribution_to_risk': float(contribution_to_risk),
                    'marginal_contribution': float(marginal_contribution)
                }
                
                risk_attributions.append(risk_attribution)
                total_factor_contribution += contribution_to_return
            
            # Sort by absolute contribution
            risk_attributions.sort(key=lambda x: abs(x['contribution_to_return']), reverse=True)
            
            return {
                'factor_details': risk_attributions,
                'total_factor_contribution': float(total_factor_contribution),
                'top_risk_factors': risk_attributions[:10]
            }
    
    async def _calculate_style_attribution(self, account_id: str, attribution_date: date,
                                         benchmark_id: str) -> Dict[str, Any]:
        """Calculate style factor attribution"""
        logger.info("✨ Calculating style attribution")
        
        style_factors = ['VALUE', 'GROWTH', 'QUALITY', 'MOMENTUM', 'SIZE']
        style_attributions = []
        
        async with self.db_manager.pool.acquire() as conn:
            for style_factor in style_factors:
                # Get portfolio exposure to style factor
                portfolio_exposure = await conn.fetchrow("""
                    SELECT AVG(fe.exposure * (cp.market_value / SUM(cp.market_value) OVER())) as avg_exposure
                    FROM risk_model.factor_exposures fe
                    JOIN positions.current_positions cp ON fe.symbol = cp.symbol
                    WHERE fe.factor_date = $1 
                      AND cp.account_id = $2 
                      AND cp.position_date = $1
                      AND fe.factor_name = $3
                """, attribution_date, account_id, style_factor)
                
                # Simulate benchmark exposure (neutral = 0)
                benchmark_exposure = Decimal('0')
                
                # Get factor return
                factor_return = await conn.fetchrow("""
                    SELECT factor_value FROM risk_model.risk_factors
                    WHERE factor_date = $1 AND factor_name = $2
                """, attribution_date, style_factor)
                
                portfolio_exp = Decimal(str(portfolio_exposure['avg_exposure'] or 0))
                factor_ret = Decimal(str(factor_return['factor_value'] or 0)) if factor_return else Decimal('0')
                
                # Style attribution = (portfolio exposure - benchmark exposure) * factor return
                attribution_value = (portfolio_exp - benchmark_exposure) * factor_ret
                
                style_attribution = {
                    'style_factor': style_factor,
                    'portfolio_exposure': float(portfolio_exp),
                    'benchmark_exposure': float(benchmark_exposure),
                    'factor_return': float(factor_ret),
                    'attribution_value': float(attribution_value)
                }
                
                style_attributions.append(style_attribution)
        
        # Sort by absolute attribution
        style_attributions.sort(key=lambda x: abs(x['attribution_value']), reverse=True)
        
        total_style_attribution = sum(s['attribution_value'] for s in style_attributions)
        
        return {
            'style_details': style_attributions,
            'total_style_attribution': total_style_attribution
        }
    
    async def _calculate_transaction_attribution(self, account_id: str, attribution_date: date) -> Dict[str, Any]:
        """Calculate transaction cost attribution"""
        logger.info("💰 Calculating transaction cost attribution")
        
        async with self.db_manager.pool.acquire() as conn:
            # Get trades executed on the attribution date
            trades = await conn.fetch("""
                SELECT 
                    symbol,
                    side,
                    quantity,
                    price,
                    trade_value,
                    commission,
                    fees,
                    execution_time
                FROM settlement.trades
                WHERE account_id = $1 AND trade_date = $2
                ORDER BY execution_time
            """, account_id, attribution_date)
            
            transaction_attributions = []
            total_transaction_cost = Decimal('0')
            total_market_impact = Decimal('0')
            total_timing_cost = Decimal('0')
            
            for trade in trades:
                symbol = trade['symbol']
                side = trade['side']
                quantity = Decimal(str(trade['quantity']))
                execution_price = Decimal(str(trade['price']))
                commission = Decimal(str(trade['commission']))
                fees = Decimal(str(trade['fees']))
                
                # Get benchmark price (e.g., VWAP or opening price)
                benchmark_price = await self._get_benchmark_execution_price(symbol, attribution_date)
                
                # Calculate transaction costs
                price_impact = execution_price - benchmark_price if side == 'BUY' else benchmark_price - execution_price
                market_impact = price_impact * quantity
                
                # Implementation shortfall
                implementation_shortfall = market_impact + commission + fees
                
                # Timing cost (simplified)
                timing_cost = market_impact * Decimal('0.1')  # 10% of market impact
                
                transaction_attribution = {
                    'symbol': symbol,
                    'transaction_type': side,
                    'shares_traded': float(quantity),
                    'execution_price': float(execution_price),
                    'benchmark_price': float(benchmark_price),
                    'implementation_shortfall': float(implementation_shortfall),
                    'market_impact': float(market_impact),
                    'timing_cost': float(timing_cost),
                    'total_transaction_cost': float(commission + fees + abs(market_impact))
                }
                
                transaction_attributions.append(transaction_attribution)
                
                total_transaction_cost += commission + fees + abs(market_impact)
                total_market_impact += abs(market_impact)
                total_timing_cost += abs(timing_cost)
        
        return {
            'transaction_details': transaction_attributions,
            'summary': {
                'total_transaction_cost': float(total_transaction_cost),
                'total_market_impact': float(total_market_impact),
                'total_timing_cost': float(total_timing_cost),
                'trade_count': len(transaction_attributions)
            }
        }
    
    async def _get_portfolio_sector_data(self, account_id: str, attribution_date: date) -> Dict[str, Dict[str, Decimal]]:
        """Get portfolio sector weights and returns"""
        async with self.db_manager.pool.acquire() as conn:
            # Continuing attribution.py

           sector_data = await conn.fetch("""
               SELECT 
                   COALESCE(s.sector, 'UNKNOWN') as sector,
                   SUM(p.market_value) as sector_value,
                   SUM(p.unrealized_pnl) as sector_pnl,
                   SUM(p.market_value) / SUM(SUM(p.market_value)) OVER() as weight,
                   CASE WHEN SUM(p.market_value) > 0 
                        THEN SUM(p.unrealized_pnl) / SUM(p.market_value) 
                        ELSE 0 
                   END as sector_return
               FROM positions.current_positions p
               LEFT JOIN reference_data.securities s ON p.symbol = s.symbol
               WHERE p.account_id = $1 AND p.position_date = $2 AND p.quantity != 0
               GROUP BY s.sector
           """, account_id, attribution_date)
           
           return {
               row['sector']: {
                   'weight': Decimal(str(row['weight'])),
                   'return': Decimal(str(row['sector_return']))
               }
               for row in sector_data
           }
   
   async def _get_benchmark_sector_data(self, benchmark_id: str, attribution_date: date) -> Dict[str, Dict[str, Decimal]]:
       """Get benchmark sector weights and returns (simulated)"""
       # In practice, this would come from benchmark provider data
       # For demo, we'll simulate S&P 500 sector weights and returns
       
       import random
       random.seed(int(attribution_date.strftime("%Y%m%d")))
       
       # Approximate S&P 500 sector weights
       sectors = {
           'TECHNOLOGY': Decimal('0.28'),
           'HEALTHCARE': Decimal('0.13'),
           'FINANCIALS': Decimal('0.11'),
           'COMMUNICATION_SERVICES': Decimal('0.10'),
           'CONSUMER_DISCRETIONARY': Decimal('0.10'),
           'INDUSTRIALS': Decimal('0.08'),
           'CONSUMER_STAPLES': Decimal('0.06'),
           'ENERGY': Decimal('0.04'),
           'UTILITIES': Decimal('0.03'),
           'REAL_ESTATE': Decimal('0.02'),
           'MATERIALS': Decimal('0.03'),
           'UNKNOWN': Decimal('0.02')
       }
       
       benchmark_data = {}
       for sector, weight in sectors.items():
           # Simulate sector return
           sector_return = Decimal(str(random.normalvariate(0.001, 0.02)))  # Daily return
           benchmark_data[sector] = {
               'weight': weight,
               'return': sector_return
           }
       
       return benchmark_data
   
   def _calculate_benchmark_total_return(self, benchmark_sectors: Dict[str, Dict[str, Decimal]]) -> Decimal:
       """Calculate benchmark total return"""
       total_return = Decimal('0')
       for sector_data in benchmark_sectors.values():
           total_return += sector_data['weight'] * sector_data['return']
       return total_return
   
   async def _get_benchmark_security_data(self, symbol: str, benchmark_id: str, 
                                        attribution_date: date) -> Tuple[Decimal, Decimal]:
       """Get benchmark weight and return for a security"""
       # Simulate benchmark data
       import random
       random.seed(hash(symbol + str(attribution_date)) % 1000)
       
       # Most securities have small or zero benchmark weight
       if random.random() < 0.7:  # 70% chance of zero weight
           benchmark_weight = Decimal('0')
           benchmark_return = Decimal('0')
       else:
           benchmark_weight = Decimal(str(random.uniform(0.0001, 0.05)))  # 0.01% to 5%
           benchmark_return = Decimal(str(random.normalvariate(0.001, 0.025)))  # Daily return
       
       return benchmark_weight, benchmark_return
   
   async def _get_benchmark_execution_price(self, symbol: str, trade_date: date) -> Decimal:
       """Get benchmark execution price (e.g., VWAP)"""
       # Simulate benchmark price (in practice, would get from market data)
       async with self.db_manager.pool.acquire() as conn:
           price = await conn.fetchrow("""
               SELECT price FROM positions.eod_prices
               WHERE symbol = $1 AND price_date = $2
           """, symbol, trade_date)
           
           if price:
               base_price = Decimal(str(price['price']))
               # Add small random variance to simulate VWAP vs close price difference
               import random
               variance = Decimal(str(random.uniform(-0.002, 0.002)))  # +/- 0.2%
               return base_price * (1 + variance)
           
           return Decimal('100')  # Default price
   
   async def _store_attribution_results(self, results: Dict[str, Any], attribution_date: date):
       """Store attribution results in database"""
       async with self.db_manager.pool.acquire() as conn:
           account_id = results['account_id']
           
           # Clear existing results for this date and account
           await conn.execute("""
               DELETE FROM attribution.attribution_analysis 
               WHERE account_id = $1 AND analysis_date = $2
           """, account_id, attribution_date)
           
           await conn.execute("""
               DELETE FROM attribution.risk_attribution 
               WHERE account_id = $1 AND analysis_date = $2
           """, account_id, attribution_date)
           
           await conn.execute("""
               DELETE FROM attribution.style_attribution 
               WHERE account_id = $1 AND analysis_date = $2
           """, account_id, attribution_date)
           
           await conn.execute("""
               DELETE FROM attribution.transaction_attribution 
               WHERE account_id = $1 AND analysis_date = $2
           """, account_id, attribution_date)
           
           # Store sector attribution
           for level_data in results['attribution_levels']:
               if level_data['level'] == 'sector':
                   for sector in level_data['attribution']['sector_details']:
                       await conn.execute("""
                           INSERT INTO attribution.attribution_analysis
                           (account_id, analysis_date, attribution_level, attribution_category,
                            portfolio_weight, benchmark_weight, portfolio_return, benchmark_return,
                            allocation_effect, selection_effect, interaction_effect, total_effect)
                           VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
                       """, account_id, attribution_date, 'SECTOR', sector['sector'],
                       sector['portfolio_weight'], sector['benchmark_weight'],
                       sector['portfolio_return'], sector['benchmark_return'],
                       sector['allocation_effect'], sector['selection_effect'],
                       sector['interaction_effect'], sector['total_effect'])
           
           # Store risk attribution
           for factor in results['risk_attribution']['factor_details']:
               await conn.execute("""
                   INSERT INTO attribution.risk_attribution
                   (account_id, analysis_date, factor_name, factor_exposure, factor_return,
                    contribution_to_return, contribution_to_risk, marginal_contribution)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
               """, account_id, attribution_date, factor['factor_name'],
               factor['factor_exposure'], factor['factor_return'],
               factor['contribution_to_return'], factor['contribution_to_risk'],
               factor['marginal_contribution'])
           
           # Store style attribution
           for style in results['style_attribution']['style_details']:
               await conn.execute("""
                   INSERT INTO attribution.style_attribution
                   (account_id, analysis_date, style_factor, portfolio_exposure,
                    benchmark_exposure, factor_return, attribution_value)
                   VALUES ($1, $2, $3, $4, $5, $6, $7)
               """, account_id, attribution_date, style['style_factor'],
               style['portfolio_exposure'], style['benchmark_exposure'],
               style['factor_return'], style['attribution_value'])
           
           # Store transaction attribution
           for transaction in results['transaction_attribution']['transaction_details']:
               await conn.execute("""
                   INSERT INTO attribution.transaction_attribution
                   (account_id, analysis_date, symbol, transaction_type, shares_traded,
                    execution_price, benchmark_price, implementation_shortfall,
                    market_impact, timing_cost, total_transaction_cost)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
               """, account_id, attribution_date, transaction['symbol'],
               transaction['transaction_type'], transaction['shares_traded'],
               transaction['execution_price'], transaction['benchmark_price'],
               transaction['implementation_shortfall'], transaction['market_impact'],
               transaction['timing_cost'], transaction['total_transaction_cost'])
   
   async def get_attribution_summary(self, account_id: str, attribution_date: date) -> Dict[str, Any]:
       """Get attribution analysis summary"""
       async with self.db_manager.pool.acquire() as conn:
           # Sector attribution summary
           sector_summary = await conn.fetch("""
               SELECT 
                   attribution_category as sector,
                   portfolio_weight,
                   benchmark_weight,
                   portfolio_return,
                   benchmark_return,
                   allocation_effect,
                   selection_effect,
                   total_effect
               FROM attribution.attribution_analysis
               WHERE account_id = $1 AND analysis_date = $2 AND attribution_level = 'SECTOR'
               ORDER BY ABS(total_effect) DESC
           """, account_id, attribution_date)
           
           # Top risk factors
           top_risk_factors = await conn.fetch("""
               SELECT 
                   factor_name,
                   factor_exposure,
                   contribution_to_return,
                   contribution_to_risk
               FROM attribution.risk_attribution
               WHERE account_id = $1 AND analysis_date = $2
               ORDER BY ABS(contribution_to_return) DESC
               LIMIT 10
           """, account_id, attribution_date)
           
           # Style attribution
           style_attribution = await conn.fetch("""
               SELECT 
                   style_factor,
                   portfolio_exposure,
                   benchmark_exposure,
                   attribution_value
               FROM attribution.style_attribution
               WHERE account_id = $1 AND analysis_date = $2
               ORDER BY ABS(attribution_value) DESC
           """, account_id, attribution_date)
           
           # Transaction cost summary
           transaction_summary = await conn.fetchrow("""
               SELECT 
                   COUNT(*) as total_trades,
                   SUM(total_transaction_cost) as total_cost,
                   AVG(total_transaction_cost) as avg_cost_per_trade,
                   SUM(market_impact) as total_market_impact
               FROM attribution.transaction_attribution
               WHERE account_id = $1 AND analysis_date = $2
           """, account_id, attribution_date)
           
           return {
               "account_id": account_id,
               "attribution_date": str(attribution_date),
               "sector_attribution": [dict(row) for row in sector_summary],
               "top_risk_factors": [dict(row) for row in top_risk_factors],
               "style_attribution": [dict(row) for row in style_attribution],
               "transaction_summary": dict(transaction_summary) if transaction_summary else {}
           }
   
   async def calculate_multi_period_attribution(self, account_id: str, start_date: date, 
                                              end_date: date) -> Dict[str, Any]:
       """Calculate attribution over multiple periods"""
       logger.info(f"📊 Calculating multi-period attribution from {start_date} to {end_date}")
       
       current_date = start_date
       daily_attributions = []
       
       while current_date <= end_date:
           try:
               daily_attribution = await self.calculate_performance_attribution(
                   account_id, current_date
               )
               daily_attributions.append(daily_attribution)
           except Exception as e:
               logger.warning(f"Failed to calculate attribution for {current_date}: {e}")
           
           current_date += timedelta(days=1)
           
           # Skip weekends (simple check)
           if current_date.weekday() >= 5:
               current_date += timedelta(days=2 - current_date.weekday() + 5)
       
       # Aggregate results
       aggregated_results = await self._aggregate_attribution_results(daily_attributions)
       
       return {
           "account_id": account_id,
           "start_date": str(start_date),
           "end_date": str(end_date),
           "daily_attributions": len(daily_attributions),
           "aggregated_attribution": aggregated_results
       }
   
   async def _aggregate_attribution_results(self, daily_attributions: List[Dict]) -> Dict[str, Any]:
       """Aggregate daily attribution results into period totals"""
       if not daily_attributions:
           return {}
       
       # Aggregate sector attribution
       sector_totals = {}
       risk_factor_totals = {}
       style_totals = {}
       
       for daily_attr in daily_attributions:
           # Aggregate sector attribution
           for level_data in daily_attr.get('attribution_levels', []):
               if level_data['level'] == 'sector':
                   for sector in level_data['attribution']['sector_details']:
                       sector_name = sector['sector']
                       if sector_name not in sector_totals:
                           sector_totals[sector_name] = {
                               'total_allocation_effect': 0,
                               'total_selection_effect': 0,
                               'total_effect': 0,
                               'days': 0
                           }
                       
                       sector_totals[sector_name]['total_allocation_effect'] += sector['allocation_effect']
                       sector_totals[sector_name]['total_selection_effect'] += sector['selection_effect']
                       sector_totals[sector_name]['total_effect'] += sector['total_effect']
                       sector_totals[sector_name]['days'] += 1
           
           # Aggregate risk factor attribution
           for factor in daily_attr.get('risk_attribution', {}).get('factor_details', []):
               factor_name = factor['factor_name']
               if factor_name not in risk_factor_totals:
                   risk_factor_totals[factor_name] = {
                       'total_contribution': 0,
                       'days': 0
                   }
               
               risk_factor_totals[factor_name]['total_contribution'] += factor['contribution_to_return']
               risk_factor_totals[factor_name]['days'] += 1
           
           # Aggregate style attribution
           for style in daily_attr.get('style_attribution', {}).get('style_details', []):
               style_factor = style['style_factor']
               if style_factor not in style_totals:
                   style_totals[style_factor] = {
                       'total_attribution': 0,
                       'days': 0
                   }
               
               style_totals[style_factor]['total_attribution'] += style['attribution_value']
               style_totals[style_factor]['days'] += 1
       
       return {
           'sector_attribution_totals': sector_totals,
           'risk_factor_totals': risk_factor_totals,
           'style_attribution_totals': style_totals,
           'total_periods': len(daily_attributions)
       }
# source/eod/risk_metrics/risk_reporter.py
import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import date, datetime, timedelta
from decimal import Decimal
import asyncio
import numpy as np

logger = logging.getLogger(__name__)

class RiskReporter:
    """Calculates and reports portfolio risk metrics"""
    
    def __init__(self, db_manager):
        self.db_manager = db_manager
        
        # Risk calculation parameters
        self.confidence_levels = [0.95, 0.99]
        self.var_horizons = [1, 10, 22]  # 1 day, 10 day, 1 month
        self.lookback_window = 252  # 1 year of data
        
    async def initialize(self):
        """Initialize risk reporter"""
        await self._create_risk_tables()
        logger.info("⚡ Risk Reporter initialized")
    
    async def _create_risk_tables(self):
        """Create risk reporting tables"""
        async with self.db_manager.pool.acquire() as conn:
            await conn.execute("""
                CREATE SCHEMA IF NOT EXISTS risk_metrics
            """)
            
            # Portfolio VaR table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS risk_metrics.portfolio_var (
                    var_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    account_id VARCHAR(50) NOT NULL,
                    calculation_date DATE NOT NULL,
                    horizon_days INTEGER NOT NULL,
                    confidence_level DECIMAL(5,4) NOT NULL,
                    var_amount DECIMAL(20,2) NOT NULL,
                    cvar_amount DECIMAL(20,2) NOT NULL,
                    portfolio_value DECIMAL(20,2) NOT NULL,
                    var_percentage DECIMAL(8,4) NOT NULL,
                    calculation_method VARCHAR(50) NOT NULL,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    UNIQUE(account_id, calculation_date, horizon_days, confidence_level)
                )
            """)
            
            # Component VaR (individual position contributions)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS risk_metrics.component_var (
                    component_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    account_id VARCHAR(50) NOT NULL,
                    symbol VARCHAR(20) NOT NULL,
                    calculation_date DATE NOT NULL,
                    horizon_days INTEGER NOT NULL,
                    confidence_level DECIMAL(5,4) NOT NULL,
                    component_var DECIMAL(20,2) NOT NULL,
                    marginal_var DECIMAL(20,2) NOT NULL,
                    position_weight DECIMAL(8,6) NOT NULL,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                )
            """)
            
            # Stress test results
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS risk_metrics.stress_tests (
                    stress_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    account_id VARCHAR(50) NOT NULL,
                    test_date DATE NOT NULL,
                    stress_scenario VARCHAR(100) NOT NULL,
                    scenario_description TEXT,
                    portfolio_loss DECIMAL(20,2) NOT NULL,
                    loss_percentage DECIMAL(8,4) NOT NULL,
                    portfolio_value DECIMAL(20,2) NOT NULL,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                )
            """)
            
            # Risk exposure by factor
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS risk_metrics.risk_exposures (
                    exposure_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    account_id VARCHAR(50) NOT NULL,
                    calculation_date DATE NOT NULL,
                    exposure_type VARCHAR(50) NOT NULL,
                    exposure_category VARCHAR(100) NOT NULL,
                    exposure_value DECIMAL(20,2) NOT NULL,
                    exposure_percentage DECIMAL(8,4) NOT NULL,
                    portfolio_value DECIMAL(20,2) NOT NULL,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                )
            """)
            
            # Risk limits and breaches
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS risk_metrics.risk_limits (
                    limit_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    account_id VARCHAR(50) NOT NULL,
                    limit_type VARCHAR(50) NOT NULL,
                    limit_name VARCHAR(100) NOT NULL,
                    limit_value DECIMAL(20,2) NOT NULL,
                    current_value DECIMAL(20,2) NOT NULL,
                    utilization_pct DECIMAL(8,4) NOT NULL,
                    is_breached BOOLEAN DEFAULT FALSE,
                    breach_amount DECIMAL(20,2),
                    last_updated TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                )
            """)
    
    async def calculate_portfolio_risk(self, calculation_date: date) -> Dict[str, Any]:
        """Calculate comprehensive portfolio risk metrics"""
        logger.info(f"⚡ Calculating portfolio risk metrics for {calculation_date}")
        
        try:
            results = {
                "calculation_date": str(calculation_date),
                "portfolios_processed": 0,
                "var_calculations": 0,
                "stress_tests_run": 0,
                "risk_exposures_calculated": 0,
                "limit_breaches": 0,
                "risk_summary": {}
            }
            
            # Get all portfolios (accounts)
            portfolios = await self._get_active_portfolios(calculation_date)
            
            for portfolio in portfolios:
                account_id = portfolio['account_id']
                results["portfolios_processed"] += 1
                
                logger.info(f"Calculating risk for portfolio {account_id}")
                
                # Step 1: Calculate VaR
                var_results = await self._calculate_portfolio_var(account_id, calculation_date)
                results["var_calculations"] += var_results["calculations_performed"]
                
                # Step 2: Run stress tests
                stress_results = await self._run_stress_tests(account_id, calculation_date)
                results["stress_tests_run"] += stress_results["scenarios_tested"]
                
                # Step 3: Calculate risk exposures
                exposure_results = await self._calculate_risk_exposures(account_id, calculation_date)
                results["risk_exposures_calculated"] += exposure_results["exposures_calculated"]
                
                # Step 4: Check risk limits
                limit_results = await self._check_risk_limits(account_id, calculation_date)
                results["limit_breaches"] += limit_results["breaches_found"]
                
                # Compile portfolio summary
                results["risk_summary"][account_id] = {
                    "var_1d_95": var_results.get("var_1d_95", 0),
                    "portfolio_value": var_results.get("portfolio_value", 0),
                    "worst_stress_loss": stress_results.get("worst_case_loss", 0),
                    "limit_breaches": limit_results["breaches_found"]
                }
            
            logger.info(f"✅ Portfolio risk calculation complete: {results}")
            return results
            
        except Exception as e:
            logger.error(f"❌ Failed to calculate portfolio risk: {e}", exc_info=True)
            raise
    
    async def _get_active_portfolios(self, calculation_date: date) -> List[Dict[str, Any]]:
        """Get all portfolios that have positions"""
        async with self.db_manager.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT DISTINCT account_id,
                       COUNT(*) as position_count,
                       SUM(market_value) as total_value
                FROM positions.current_positions
                WHERE position_date = $1 AND quantity != 0
                GROUP BY account_id
                HAVING SUM(market_value) > 0
                ORDER BY total_value DESC
            """, calculation_date)
            
            return [dict(row) for row in rows]
    
    async def _calculate_portfolio_var(self, account_id: str, calculation_date: date) -> Dict[str, Any]:
        """Calculate Value at Risk for a portfolio"""
        logger.info(f"📊 Calculating VaR for portfolio {account_id}")
        
        results = {
            "calculations_performed": 0,
            "portfolio_value": 0,
            "var_1d_95": 0
        }
        
        async with self.db_manager.pool.acquire() as conn:
            # Clear existing VaR calculations for this date
            await conn.execute("""
                DELETE FROM risk_metrics.portfolio_var 
                WHERE account_id = $1 AND calculation_date = $2
            """, account_id, calculation_date)
            
            # Get portfolio positions
            positions = await conn.fetch("""
                SELECT symbol, quantity, market_value, avg_cost
                FROM positions.current_positions
                WHERE account_id = $1 AND position_date = $2 AND quantity != 0
            """, account_id, calculation_date)
            
            if not positions:
                return results
            
            portfolio_value = sum(float(pos['market_value'] or 0) for pos in positions)
            results["portfolio_value"] = portfolio_value
            
            # Get historical price data for VaR calculation
            historical_data = await self._get_historical_portfolio_data(account_id, calculation_date, positions)
            
            for confidence_level in self.confidence_levels:
                for horizon_days in self.var_horizons:
                    # Calculate VaR using different methods
                    var_parametric = await self._calculate_parametric_var(
                        historical_data, portfolio_value, confidence_level, horizon_days
                    )
                    
                    var_historical = await self._calculate_historical_var(
                        historical_data, portfolio_value, confidence_level, horizon_days
                    )
                    
                    # Use historical simulation as primary method
                    var_amount = var_historical
                    cvar_amount = await self._calculate_cvar(historical_data, confidence_level, horizon_days)
                    
                    var_percentage = (var_amount / portfolio_value * 100) if portfolio_value > 0 else 0
                    
                    # Store VaR calculation
                    await conn.execute("""
                        INSERT INTO risk_metrics.portfolio_var
                        (account_id, calculation_date, horizon_days, confidence_level,
                         var_amount, cvar_amount, portfolio_value, var_percentage, calculation_method)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                    """, account_id, calculation_date, horizon_days, confidence_level,
                    var_amount, cvar_amount, portfolio_value, var_percentage, 'HISTORICAL_SIMULATION')
                    
                    results["calculations_performed"] += 1
                    
                    # Store 1-day 95% VaR for summary
                    if horizon_days == 1 and confidence_level == 0.95:
                        results["var_1d_95"] = var_amount
            
            # Calculate component VaR
            await self._calculate_component_var(account_id, calculation_date, positions, historical_data)
        
        return results
    
    async def _get_historical_portfolio_data(self, account_id: str, calculation_date: date, 
                                           positions: List[Dict[str, Any]]) -> np.ndarray:
        """Get historical portfolio returns for VaR calculation"""
        # Simulate historical portfolio returns
        # In practice, this would use actual historical price data
        
        symbols = [pos['symbol'] for pos in positions]
        weights = []
        total_value = sum(float(pos['market_value'] or 0) for pos in positions)
        
        for pos in positions:
            weight = float(pos['market_value'] or 0) / total_value if total_value > 0 else 0
            weights.append(weight)
        
        # Generate synthetic historical returns (for demo)
        np.random.seed(hash(account_id) % 1000)  # Deterministic for testing
        n_days = self.lookback_window
        n_assets = len(symbols)
        
        # Create correlation matrix
        correlation_matrix = np.random.uniform(0.1, 0.7, (n_assets, n_assets))
        np.fill_diagonal(correlation_matrix, 1.0)
        correlation_matrix = (correlation_matrix + correlation_matrix.T) / 2  # Make symmetric
        
        # Continuing risk_reporter.py

       # Generate correlated returns
       volatilities = np.random.uniform(0.15, 0.35, n_assets)  # 15-35% annual vol
       daily_vols = volatilities / np.sqrt(252)  # Convert to daily
       
       # Generate uncorrelated returns
       uncorrelated_returns = np.random.multivariate_normal(
           mean=np.zeros(n_assets),
           cov=np.eye(n_assets),
           size=n_days
       )
       
       # Apply correlation and volatility
       chol = np.linalg.cholesky(correlation_matrix)
       correlated_returns = uncorrelated_returns @ chol.T
       
       # Scale by volatilities
       for i in range(n_assets):
           correlated_returns[:, i] *= daily_vols[i]
       
       # Calculate portfolio returns
       portfolio_returns = np.dot(correlated_returns, weights)
       
       return portfolio_returns
   
   async def _calculate_parametric_var(self, returns: np.ndarray, portfolio_value: float,
                                     confidence_level: float, horizon_days: int) -> float:
       """Calculate VaR using parametric method (normal distribution assumption)"""
       from scipy import stats
       
       daily_vol = np.std(returns)
       horizon_vol = daily_vol * np.sqrt(horizon_days)
       
       # Z-score for confidence level
       z_score = stats.norm.ppf(1 - confidence_level)
       
       # VaR as positive number (loss)
       var_return = -z_score * horizon_vol
       var_amount = portfolio_value * var_return
       
       return max(0, var_amount)
   
   async def _calculate_historical_var(self, returns: np.ndarray, portfolio_value: float,
                                     confidence_level: float, horizon_days: int) -> float:
       """Calculate VaR using historical simulation"""
       if len(returns) < horizon_days:
           return 0.0
       
       # Calculate overlapping horizon returns
       horizon_returns = []
       for i in range(len(returns) - horizon_days + 1):
           horizon_return = np.sum(returns[i:i + horizon_days])
           horizon_returns.append(horizon_return)
       
       horizon_returns = np.array(horizon_returns)
       
       # Calculate VaR as percentile
       var_percentile = (1 - confidence_level) * 100
       var_return = np.percentile(horizon_returns, var_percentile)
       
       # Convert to dollar amount (negative return = loss)
       var_amount = portfolio_value * abs(min(0, var_return))
       
       return var_amount
   
   async def _calculate_cvar(self, returns: np.ndarray, confidence_level: float, horizon_days: int) -> float:
       """Calculate Conditional VaR (Expected Shortfall)"""
       if len(returns) < horizon_days:
           return 0.0
       
       # Calculate overlapping horizon returns
       horizon_returns = []
       for i in range(len(returns) - horizon_days + 1):
           horizon_return = np.sum(returns[i:i + horizon_days])
           horizon_returns.append(horizon_return)
       
       horizon_returns = np.array(horizon_returns)
       
       # Calculate VaR threshold
       var_percentile = (1 - confidence_level) * 100
       var_threshold = np.percentile(horizon_returns, var_percentile)
       
       # CVaR is the mean of returns worse than VaR
       tail_returns = horizon_returns[horizon_returns <= var_threshold]
       cvar_return = np.mean(tail_returns) if len(tail_returns) > 0 else var_threshold
       
       return abs(min(0, cvar_return))
   
   async def _calculate_component_var(self, account_id: str, calculation_date: date,
                                    positions: List[Dict[str, Any]], 
                                    portfolio_returns: np.ndarray):
       """Calculate component VaR (individual position contributions)"""
       logger.info("🔍 Calculating component VaR")
       
       async with self.db_manager.pool.acquire() as conn:
           # Clear existing component VaR
           await conn.execute("""
               DELETE FROM risk_metrics.component_var 
               WHERE account_id = $1 AND calculation_date = $2
           """, account_id, calculation_date)
           
           total_value = sum(float(pos['market_value'] or 0) for pos in positions)
           
           for i, position in enumerate(positions):
               symbol = position['symbol']
               position_value = float(position['market_value'] or 0)
               weight = position_value / total_value if total_value > 0 else 0
               
               # Simulate individual asset returns (for demo)
               np.random.seed(hash(symbol) % 1000)
               asset_returns = np.random.normal(0, 0.02, len(portfolio_returns))  # 2% daily vol
               
               # Calculate marginal VaR (simplified)
               correlation_with_portfolio = np.corrcoef(asset_returns, portfolio_returns)[0, 1]
               portfolio_vol = np.std(portfolio_returns)
               asset_vol = np.std(asset_returns)
               
               marginal_var = correlation_with_portfolio * asset_vol / portfolio_vol if portfolio_vol > 0 else 0
               component_var = weight * marginal_var * total_value
               
               # Store component VaR for 1-day 95% confidence
               await conn.execute("""
                   INSERT INTO risk_metrics.component_var
                   (account_id, symbol, calculation_date, horizon_days, confidence_level,
                    component_var, marginal_var, position_weight)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
               """, account_id, symbol, calculation_date, 1, 0.95,
               component_var, marginal_var * total_value, weight)
   
   async def _run_stress_tests(self, account_id: str, calculation_date: date) -> Dict[str, Any]:
       """Run stress tests on portfolio"""
       logger.info(f"🧪 Running stress tests for portfolio {account_id}")
       
       results = {
           "scenarios_tested": 0,
           "worst_case_loss": 0
       }
       
       async with self.db_manager.pool.acquire() as conn:
           # Clear existing stress test results
           await conn.execute("""
               DELETE FROM risk_metrics.stress_tests 
               WHERE account_id = $1 AND test_date = $2
           """, account_id, calculation_date)
           
           # Get portfolio positions
           positions = await conn.fetch("""
               SELECT symbol, quantity, market_value, avg_cost
               FROM positions.current_positions
               WHERE account_id = $1 AND position_date = $2 AND quantity != 0
           """, account_id, calculation_date)
           
           if not positions:
               return results
           
           portfolio_value = sum(float(pos['market_value'] or 0) for pos in positions)
           
           # Define stress scenarios
           stress_scenarios = [
               {
                   "name": "MARKET_CRASH",
                   "description": "Black Monday scenario: -22% market drop",
                   "market_shock": -0.22,
                   "vol_shock": 2.0
               },
               {
                   "name": "INTEREST_RATE_SHOCK",
                   "description": "200bp interest rate increase",
                   "market_shock": -0.08,
                   "vol_shock": 1.5
               },
               {
                   "name": "CREDIT_CRISIS",
                   "description": "Credit spread widening, liquidity crisis",
                   "market_shock": -0.15,
                   "vol_shock": 2.5
               },
               {
                   "name": "CURRENCY_CRISIS",
                   "description": "Major currency devaluation",
                   "market_shock": -0.10,
                   "vol_shock": 1.8
               },
               {
                   "name": "TECH_BUBBLE_BURST",
                   "description": "Technology sector crash",
                   "market_shock": -0.12,
                   "vol_shock": 2.2
               }
           ]
           
           for scenario in stress_scenarios:
               # Calculate portfolio loss under stress
               portfolio_loss = await self._calculate_stress_loss(
                   positions, scenario["market_shock"], scenario["vol_shock"]
               )
               
               loss_percentage = (portfolio_loss / portfolio_value * 100) if portfolio_value > 0 else 0
               
               # Store stress test result
               await conn.execute("""
                   INSERT INTO risk_metrics.stress_tests
                   (account_id, test_date, stress_scenario, scenario_description,
                    portfolio_loss, loss_percentage, portfolio_value)
                   VALUES ($1, $2, $3, $4, $5, $6, $7)
               """, account_id, calculation_date, scenario["name"], 
               scenario["description"], portfolio_loss, loss_percentage, portfolio_value)
               
               results["scenarios_tested"] += 1
               results["worst_case_loss"] = max(results["worst_case_loss"], portfolio_loss)
       
       return results
   
   async def _calculate_stress_loss(self, positions: List[Dict[str, Any]], 
                                  market_shock: float, vol_shock: float) -> float:
       """Calculate portfolio loss under stress scenario"""
       total_loss = 0.0
       
       for position in positions:
           position_value = float(position['market_value'] or 0)
           
           # Apply market shock with some randomness
           import random
           random.seed(hash(position['symbol']) % 1000)
           
           # Different sectors react differently to stress
           sector_multiplier = random.uniform(0.8, 1.5)  # Some sectors more/less sensitive
           position_shock = market_shock * sector_multiplier
           
           # Add volatility component
           vol_component = random.gauss(0, 0.05) * vol_shock  # Additional volatility
           
           total_shock = position_shock + vol_component
           position_loss = position_value * abs(min(0, total_shock))
           total_loss += position_loss
       
       return total_loss
   
   async def _calculate_risk_exposures(self, account_id: str, calculation_date: date) -> Dict[str, Any]:
       """Calculate risk exposures by various factors"""
       logger.info(f"📊 Calculating risk exposures for portfolio {account_id}")
       
       results = {
           "exposures_calculated": 0
       }
       
       async with self.db_manager.pool.acquire() as conn:
           # Clear existing exposures
           await conn.execute("""
               DELETE FROM risk_metrics.risk_exposures 
               WHERE account_id = $1 AND calculation_date = $2
           """, account_id, calculation_date)
           
           # Get portfolio positions with security details
           positions = await conn.fetch("""
               SELECT 
                   cp.symbol,
                   cp.market_value,
                   s.sector,
                   s.exchange,
                   s.country,
                   s.currency
               FROM positions.current_positions cp
               LEFT JOIN reference_data.securities s ON cp.symbol = s.symbol
               WHERE cp.account_id = $1 AND cp.position_date = $2 AND cp.quantity != 0
           """, account_id, calculation_date)
           
           if not positions:
               return results
           
           portfolio_value = sum(float(pos['market_value'] or 0) for pos in positions)
           
           # Calculate sector exposures
           sector_exposures = {}
           for position in positions:
               sector = position['sector'] or 'UNKNOWN'
               value = float(position['market_value'] or 0)
               sector_exposures[sector] = sector_exposures.get(sector, 0) + value
           
           for sector, exposure_value in sector_exposures.items():
               exposure_pct = (exposure_value / portfolio_value * 100) if portfolio_value > 0 else 0
               
               await conn.execute("""
                   INSERT INTO risk_metrics.risk_exposures
                   (account_id, calculation_date, exposure_type, exposure_category,
                    exposure_value, exposure_percentage, portfolio_value)
                   VALUES ($1, $2, $3, $4, $5, $6, $7)
               """, account_id, calculation_date, 'SECTOR', sector,
               exposure_value, exposure_pct, portfolio_value)
               
               results["exposures_calculated"] += 1
           
           # Calculate country exposures
           country_exposures = {}
           for position in positions:
               country = position['country'] or 'UNKNOWN'
               value = float(position['market_value'] or 0)
               country_exposures[country] = country_exposures.get(country, 0) + value
           
           for country, exposure_value in country_exposures.items():
               exposure_pct = (exposure_value / portfolio_value * 100) if portfolio_value > 0 else 0
               
               await conn.execute("""
                   INSERT INTO risk_metrics.risk_exposures
                   (account_id, calculation_date, exposure_type, exposure_category,
                    exposure_value, exposure_percentage, portfolio_value)
                   VALUES ($1, $2, $3, $4, $5, $6, $7)
               """, account_id, calculation_date, 'COUNTRY', country,
               exposure_value, exposure_pct, portfolio_value)
               
               results["exposures_calculated"] += 1
           
           # Calculate currency exposures
           currency_exposures = {}
           for position in positions:
               currency = position['currency'] or 'USD'
               value = float(position['market_value'] or 0)
               currency_exposures[currency] = currency_exposures.get(currency, 0) + value
           
           for currency, exposure_value in currency_exposures.items():
               exposure_pct = (exposure_value / portfolio_value * 100) if portfolio_value > 0 else 0
               
               await conn.execute("""
                   INSERT INTO risk_metrics.risk_exposures
                   (account_id, calculation_date, exposure_type, exposure_category,
                    exposure_value, exposure_percentage, portfolio_value)
                   VALUES ($1, $2, $3, $4, $5, $6, $7)
               """, account_id, calculation_date, 'CURRENCY', currency,
               exposure_value, exposure_pct, portfolio_value)
               
               results["exposures_calculated"] += 1
       
       return results
   
   async def _check_risk_limits(self, account_id: str, calculation_date: date) -> Dict[str, Any]:
       """Check portfolio against risk limits"""
       logger.info(f"🚨 Checking risk limits for portfolio {account_id}")
       
       results = {
           "breaches_found": 0,
           "limits_checked": 0
       }
       
       async with self.db_manager.pool.acquire() as conn:
           # Define risk limits (in practice, these would be configured per account)
           risk_limits = [
               {
                   "limit_type": "VAR",
                   "limit_name": "1-Day 95% VaR Limit",
                   "limit_value": 50000.0,  # $50k daily VaR limit
                   "query": """
                       SELECT var_amount FROM risk_metrics.portfolio_var
                       WHERE account_id = $1 AND calculation_date = $2 
                         AND horizon_days = 1 AND confidence_level = 0.95
                   """
               },
               {
                   "limit_type": "CONCENTRATION",
                   "limit_name": "Single Position Limit",
                   "limit_value": 10.0,  # 10% max position size
                   "query": """
                       SELECT MAX(market_value / SUM(market_value) OVER() * 100) as max_position_pct
                       FROM positions.current_positions
                       WHERE account_id = $1 AND position_date = $2 AND quantity != 0
                   """
               },
               {
                   "limit_type": "SECTOR",
                   "limit_name": "Single Sector Limit",
                   "limit_value": 25.0,  # 25% max sector exposure
                   "query": """
                       SELECT MAX(exposure_percentage) as max_sector_exposure
                       FROM risk_metrics.risk_exposures
                       WHERE account_id = $1 AND calculation_date = $2 AND exposure_type = 'SECTOR'
                   """
               }
           ]
           
           # Clear existing limits
           await conn.execute("""
               DELETE FROM risk_metrics.risk_limits WHERE account_id = $1
           """, account_id)
           
           for limit in risk_limits:
               results["limits_checked"] += 1
               
               # Get current value
               result = await conn.fetchrow(limit["query"], account_id, calculation_date)
               current_value = 0.0
               
               if result:
                   # Get first non-None value from result
                   for value in result.values():
                       if value is not None:
                           current_value = float(value)
                           break
               
               # Check for breach
               is_breached = current_value > limit["limit_value"]
               breach_amount = max(0, current_value - limit["limit_value"]) if is_breached else 0
               utilization_pct = (current_value / limit["limit_value"] * 100) if limit["limit_value"] > 0 else 0
               
               if is_breached:
                   results["breaches_found"] += 1
                   logger.warning(f"🚨 Risk limit breach: {limit['limit_name']} - {current_value:.2f} > {limit['limit_value']:.2f}")
               
               # Store limit check result
               await conn.execute("""
                   INSERT INTO risk_metrics.risk_limits
                   (account_id, limit_type, limit_name, limit_value, current_value,
                    utilization_pct, is_breached, breach_amount)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
               """, account_id, limit["limit_type"], limit["limit_name"], 
               limit["limit_value"], current_value, utilization_pct, is_breached, breach_amount)
       
       return results
   
   async def get_risk_summary(self, account_id: str, summary_date: date) -> Dict[str, Any]:
       """Get comprehensive risk summary for a portfolio"""
       async with self.db_manager.pool.acquire() as conn:
           # VaR summary
           var_data = await conn.fetch("""
               SELECT horizon_days, confidence_level, var_amount, var_percentage
               FROM risk_metrics.portfolio_var
               WHERE account_id = $1 AND calculation_date = $2
               ORDER BY horizon_days, confidence_level
           """, account_id, summary_date)
           
           # Stress test results
           stress_data = await conn.fetch("""
               SELECT stress_scenario, portfolio_loss, loss_percentage
               FROM risk_metrics.stress_tests
               WHERE account_id = $1 AND test_date = $2
               ORDER BY portfolio_loss DESC
           """, account_id, summary_date)
           
           # Risk exposures
           exposure_data = await conn.fetch("""
               SELECT exposure_type, exposure_category, exposure_percentage
               FROM risk_metrics.risk_exposures
               WHERE account_id = $1 AND calculation_date = $2
                 AND exposure_percentage >= 1.0  -- Only significant exposures
               ORDER BY exposure_type, exposure_percentage DESC
           """, account_id, summary_date)
           
           # Risk limit breaches
           breach_data = await conn.fetch("""
               SELECT limit_name, current_value, limit_value, utilization_pct, breach_amount
               FROM risk_metrics.risk_limits
               WHERE account_id = $1 AND is_breached = TRUE
               ORDER BY breach_amount DESC
           """, account_id, summary_date)
           
           # Top risk contributors (component VaR)
           component_data = await conn.fetch("""
               SELECT symbol, component_var, marginal_var, position_weight
               FROM risk_metrics.component_var
               WHERE account_id = $1 AND calculation_date = $2
                 AND horizon_days = 1 AND confidence_level = 0.95
               ORDER BY ABS(component_var) DESC
               LIMIT 10
           """, account_id, summary_date)
           
           return {
               "account_id": account_id,
               "summary_date": str(summary_date),
               "var_metrics": [dict(row) for row in var_data],
               "stress_tests": [dict(row) for row in stress_data],
               "risk_exposures": [dict(row) for row in exposure_data],
               "limit_breaches": [dict(row) for row in breach_data],
               "top_risk_contributors": [dict(row) for row in component_data]
           }
   
   async def generate_risk_report(self, account_id: str, report_date: date) -> str:
       """Generate a formatted risk report"""
       risk_data = await self.get_risk_summary(account_id, report_date)
       
       report_lines = [
           f"RISK REPORT - {account_id}",
           f"Date: {report_date}",
           "=" * 50,
           "",
           "VALUE AT RISK SUMMARY:",
       ]
       
       for var_metric in risk_data["var_metrics"]:
           horizon = var_metric["horizon_days"]
           confidence = int(var_metric["confidence_level"] * 100)
           var_amount = var_metric["var_amount"]
           var_pct = var_metric["var_percentage"]
           
           report_lines.append(f"  {horizon}d {confidence}% VaR: ${var_amount:,.0f} ({var_pct:.2f}%)")
       
       report_lines.extend([
           "",
           "STRESS TEST RESULTS:",
       ])
       
       for stress in risk_data["stress_tests"][:3]:  # Top 3 worst scenarios
           scenario = stress["stress_scenario"].replace("_", " ").title()
           loss = stress["portfolio_loss"]
           loss_pct = stress["loss_percentage"]
           
           report_lines.append(f"  {scenario}: ${loss:,.0f} loss ({loss_pct:.2f}%)")
       
       if risk_data["limit_breaches"]:
           report_lines.extend([
               "",
               "RISK LIMIT BREACHES:",
           ])
           
           for breach in risk_data["limit_breaches"]:
               limit_name = breach["limit_name"]
               current = breach["current_value"]
               limit_val = breach["limit_value"]
               breach_amount = breach["breach_amount"]
               
               report_lines.append(f"  ⚠️ {limit_name}: {current:.2f} > {limit_val:.2f} (breach: {breach_amount:.2f})")
       
       return "\n".join(report_lines)
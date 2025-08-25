# source/sod/risk_model/risk_calculator.py
import logging
import numpy as np
from typing import Dict, List, Any, Tuple
from datetime import date, datetime, timedelta
import asyncio

logger = logging.getLogger(__name__)

class RiskCalculator:
    """Calculates risk factors and models for the trading universe"""
    
    def __init__(self, db_manager):
        self.db_manager = db_manager
        
        # Risk model parameters
        self.lookback_days = 252  # 1 year
        self.min_history_days = 60
        self.factor_decay = 0.95  # Exponential decay factor
        
    async def initialize(self):
        """Initialize risk calculator"""
        await self._create_risk_tables()
        logger.info("⚡ Risk Calculator initialized")
    
    async def _create_risk_tables(self):
        """Create risk model tables"""
        async with self.db_manager.pool.acquire() as conn:
            await conn.execute("""
                CREATE SCHEMA IF NOT EXISTS risk_model
            """)
            
            # Risk factors table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS risk_model.risk_factors (
                    factor_date DATE NOT NULL,
                    factor_type VARCHAR(50) NOT NULL,
                    factor_name VARCHAR(100) NOT NULL,
                    factor_value DECIMAL(12,6),
                    factor_volatility DECIMAL(12,6),
                    factor_description TEXT,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    PRIMARY KEY (factor_date, factor_type, factor_name)
                )
            """)
            
            # Asset factor exposures
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS risk_model.factor_exposures (
                    factor_date DATE NOT NULL,
                    symbol VARCHAR(20) NOT NULL,
                    factor_name VARCHAR(100) NOT NULL,
                    exposure DECIMAL(12,6) NOT NULL,
                    t_stat DECIMAL(8,4),
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    PRIMARY KEY (factor_date, symbol, factor_name)
                )
            """)
            
            # Factor correlation matrix
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS risk_model.factor_correlations (
                    factor_date DATE NOT NULL,
                    factor1 VARCHAR(100) NOT NULL,
                    factor2 VARCHAR(100) NOT NULL,
                    correlation DECIMAL(8,6) NOT NULL,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    PRIMARY KEY (factor_date, factor1, factor2)
                )
            """)
            
            # Asset specific risk
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS risk_model.specific_risk (
                    factor_date DATE NOT NULL,
                    symbol VARCHAR(20) NOT NULL,
                    specific_vol DECIMAL(12,6) NOT NULL,
                    residual_vol DECIMAL(12,6),
                    r_squared DECIMAL(8,6),
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    PRIMARY KEY (factor_date, symbol)
                )
            """)
    
    async def calculate_risk_model(self, model_date: date) -> Dict[str, Any]:
        """Calculate complete risk model for the given date"""
        logger.info(f"⚡ Calculating risk model for {model_date}")
        
        try:
            results = {}
            
            # Step 1: Calculate style factors
            style_factors = await self._calculate_style_factors(model_date)
            results['style_factors'] = len(style_factors)
            
            # Step 2: Calculate industry factors  
            industry_factors = await self._calculate_industry_factors(model_date)
            results['industry_factors'] = len(industry_factors)
            
            # Step 3: Calculate macro factors
            macro_factors = await self._calculate_macro_factors(model_date)
            results['macro_factors'] = len(macro_factors)
            
            # Step 4: Calculate factor exposures for all assets
            exposures = await self._calculate_factor_exposures(model_date)
            results['asset_exposures'] = len(exposures)
            
            # Step 5: Calculate factor correlation matrix
            correlations = await self._calculate_factor_correlations(model_date)
            results['correlation_matrix'] = correlations['matrix_size']
            
            # Step 6: Calculate asset-specific risk
            specific_risks = await self._calculate_specific_risk(model_date)
            results['specific_risks'] = len(specific_risks)
            
            logger.info(f"✅ Risk model calculated: {results}")
            
            return results
            
        except Exception as e:
            logger.error(f"❌ Failed to calculate risk model: {e}", exc_info=True)
            raise
    
    async def _calculate_style_factors(self, model_date: date) -> List[Dict[str, Any]]:
        """Calculate style factors (Value, Growth, Quality, etc.)"""
        logger.info("📊 Calculating style factors")
        
        # Get universe for the date
        async with self.db_manager.pool.acquire() as conn:
            universe = await conn.fetch("""
                SELECT symbol, market_cap FROM universe.trading_universe
                WHERE universe_date = $1 AND is_tradeable = TRUE
            """, model_date)
            
            if not universe:
                logger.warning("No universe found for date")
                return []
            
            # Calculate style factors
            style_factors = []
            
            # Value factors
            value_factor = await self._calculate_value_factor(model_date, universe)
            style_factors.append(value_factor)
            
            # Growth factors  
            growth_factor = await self._calculate_growth_factor(model_date, universe)
            style_factors.append(growth_factor)
            
            # Quality factors
            quality_factor = await self._calculate_quality_factor(model_date, universe)
            style_factors.append(quality_factor)
            
            # Momentum factors
            momentum_factor = await self._calculate_momentum_factor(model_date, universe)
            style_factors.append(momentum_factor)
            
            # Size factors
            size_factor = await self._calculate_size_factor(model_date, universe)
            style_factors.append(size_factor)
            
            # Save to database
            await self._save_risk_factors(model_date, 'STYLE', style_factors)
            
            return style_factors
    
    # Continuing risk_calculator.py

   async def _calculate_value_factor(self, model_date: date, universe: List) -> Dict[str, Any]:
       """Calculate value factor (simplified)"""
       # This is a simplified implementation
       # Real implementation would use P/E, P/B, EV/EBITDA, etc.
       
       # Simulate value scores
       np.random.seed(42)  # For reproducible fake data
       value_scores = np.random.normal(0, 1, len(universe))
       
       # Cross-sectional standardization
       value_scores = (value_scores - np.mean(value_scores)) / np.std(value_scores)
       
       # Calculate factor return (market cap weighted)
       market_caps = np.array([float(u['market_cap'] or 0) for u in universe])
       total_market_cap = np.sum(market_caps)
       
       if total_market_cap > 0:
           weights = market_caps / total_market_cap
           factor_return = np.sum(weights * value_scores)
       else:
           factor_return = 0.0
       
       return {
           'factor_name': 'VALUE',
           'factor_value': float(factor_return),
           'factor_volatility': float(np.std(value_scores)),
           'factor_description': 'Value factor based on fundamental metrics'
       }
   
   async def _calculate_growth_factor(self, model_date: date, universe: List) -> Dict[str, Any]:
       """Calculate growth factor"""
       np.random.seed(43)
       growth_scores = np.random.normal(0, 1.2, len(universe))
       growth_scores = (growth_scores - np.mean(growth_scores)) / np.std(growth_scores)
       
       market_caps = np.array([float(u['market_cap'] or 0) for u in universe])
       total_market_cap = np.sum(market_caps)
       
       if total_market_cap > 0:
           weights = market_caps / total_market_cap
           factor_return = np.sum(weights * growth_scores)
       else:
           factor_return = 0.0
       
       return {
           'factor_name': 'GROWTH',
           'factor_value': float(factor_return),
           'factor_volatility': float(np.std(growth_scores)),
           'factor_description': 'Growth factor based on earnings and sales growth'
       }
   
   async def _calculate_quality_factor(self, model_date: date, universe: List) -> Dict[str, Any]:
       """Calculate quality factor"""
       np.random.seed(44)
       quality_scores = np.random.normal(0, 0.8, len(universe))
       quality_scores = (quality_scores - np.mean(quality_scores)) / np.std(quality_scores)
       
       market_caps = np.array([float(u['market_cap'] or 0) for u in universe])
       total_market_cap = np.sum(market_caps)
       
       if total_market_cap > 0:
           weights = market_caps / total_market_cap
           factor_return = np.sum(weights * quality_scores)
       else:
           factor_return = 0.0
       
       return {
           'factor_name': 'QUALITY',
           'factor_value': float(factor_return),
           'factor_volatility': float(np.std(quality_scores)),
           'factor_description': 'Quality factor based on profitability and financial health'
       }
   
   async def _calculate_momentum_factor(self, model_date: date, universe: List) -> Dict[str, Any]:
       """Calculate momentum factor"""
       np.random.seed(45)
       momentum_scores = np.random.normal(0, 1.5, len(universe))
       momentum_scores = (momentum_scores - np.mean(momentum_scores)) / np.std(momentum_scores)
       
       market_caps = np.array([float(u['market_cap'] or 0) for u in universe])
       total_market_cap = np.sum(market_caps)
       
       if total_market_cap > 0:
           weights = market_caps / total_market_cap
           factor_return = np.sum(weights * momentum_scores)
       else:
           factor_return = 0.0
       
       return {
           'factor_name': 'MOMENTUM',
           'factor_value': float(factor_return),
           'factor_volatility': float(np.std(momentum_scores)),
           'factor_description': 'Momentum factor based on price and earnings momentum'
       }
   
   async def _calculate_size_factor(self, model_date: date, universe: List) -> Dict[str, Any]:
       """Calculate size factor"""
       # Size factor based on market cap
       market_caps = np.array([float(u['market_cap'] or 1) for u in universe])
       log_market_caps = np.log(market_caps)
       
       # Standardize
       size_scores = (log_market_caps - np.mean(log_market_caps)) / np.std(log_market_caps)
       
       total_market_cap = np.sum(market_caps)
       weights = market_caps / total_market_cap
       factor_return = np.sum(weights * size_scores)
       
       return {
           'factor_name': 'SIZE',
           'factor_value': float(factor_return),
           'factor_volatility': float(np.std(size_scores)),
           'factor_description': 'Size factor based on market capitalization'
       }
   
   async def _calculate_industry_factors(self, model_date: date) -> List[Dict[str, Any]]:
       """Calculate industry factors"""
       logger.info("🏭 Calculating industry factors")
       
       async with self.db_manager.pool.acquire() as conn:
           # Get industry breakdown
           industries = await conn.fetch("""
               SELECT sector, COUNT(*) as count, SUM(market_cap) as total_market_cap
               FROM universe.trading_universe
               WHERE universe_date = $1 AND is_tradeable = TRUE AND sector IS NOT NULL
               GROUP BY sector
               ORDER BY total_market_cap DESC
           """, model_date)
           
           industry_factors = []
           
           for industry in industries:
               sector = industry['sector']
               
               # Simulate industry factor return
               np.random.seed(hash(sector) % 1000)  # Deterministic but varied by sector
               factor_return = np.random.normal(0, 0.02)  # 2% daily vol
               factor_vol = 0.02
               
               industry_factors.append({
                   'factor_name': f'INDUSTRY_{sector}',
                   'factor_value': float(factor_return),
                   'factor_volatility': float(factor_vol),
                   'factor_description': f'Industry factor for {sector} sector'
               })
           
           # Save to database
           await self._save_risk_factors(model_date, 'INDUSTRY', industry_factors)
           
           return industry_factors
   
   async def _calculate_macro_factors(self, model_date: date) -> List[Dict[str, Any]]:
       """Calculate macro-economic factors"""
       logger.info("🌍 Calculating macro factors")
       
       # Simulate macro factors
       macro_factors = []
       
       # Interest rate factor
       np.random.seed(100)
       interest_rate_factor = {
           'factor_name': 'INTEREST_RATE',
           'factor_value': float(np.random.normal(0, 0.005)),  # 0.5% daily vol
           'factor_volatility': 0.005,
           'factor_description': 'Interest rate sensitivity factor'
       }
       macro_factors.append(interest_rate_factor)
       
       # Currency factor
       np.random.seed(101)
       currency_factor = {
           'factor_name': 'USD_STRENGTH',
           'factor_value': float(np.random.normal(0, 0.008)),  # 0.8% daily vol
           'factor_volatility': 0.008,
           'factor_description': 'USD strength factor'
       }
       macro_factors.append(currency_factor)
       
       # Oil price factor
       np.random.seed(102)
       oil_factor = {
           'factor_name': 'OIL_PRICE',
           'factor_value': float(np.random.normal(0, 0.03)),  # 3% daily vol
           'factor_volatility': 0.03,
           'factor_description': 'Oil price sensitivity factor'
       }
       macro_factors.append(oil_factor)
       
       # VIX/Volatility factor
       np.random.seed(103)
       volatility_factor = {
           'factor_name': 'MARKET_VOLATILITY',
           'factor_value': float(np.random.normal(0, 0.05)),  # 5% daily vol
           'factor_volatility': 0.05,
           'factor_description': 'Market volatility factor'
       }
       macro_factors.append(volatility_factor)
       
       # Save to database
       await self._save_risk_factors(model_date, 'MACRO', macro_factors)
       
       return macro_factors
   
   async def _calculate_factor_exposures(self, model_date: date) -> List[Dict[str, Any]]:
       """Calculate factor exposures for all assets"""
       logger.info("🎯 Calculating factor exposures")
       
       async with self.db_manager.pool.acquire() as conn:
           # Get universe
           universe = await conn.fetch("""
               SELECT symbol FROM universe.trading_universe
               WHERE universe_date = $1 AND is_tradeable = TRUE
           """, model_date)
           
           # Get all factors for this date
           factors = await conn.fetch("""
               SELECT factor_name FROM risk_model.risk_factors
               WHERE factor_date = $1
           """, model_date)
           
           exposures = []
           
           for asset in universe:
               symbol = asset['symbol']
               
               for factor in factors:
                   factor_name = factor['factor_name']
                   
                   # Simulate exposure (in practice, this would be calculated via regression)
                   np.random.seed(hash(symbol + factor_name) % 10000)
                   
                   if 'INDUSTRY_' in factor_name:
                       # Industry exposures are 0 or 1
                       exposure = 1.0 if np.random.random() > 0.9 else 0.0
                   else:
                       # Style and macro exposures are continuous
                       exposure = np.random.normal(0, 0.5)
                   
                   exposures.append({
                       'symbol': symbol,
                       'factor_name': factor_name,
                       'exposure': float(exposure),
                       't_stat': float(np.random.normal(0, 2)) if exposure != 0 else 0.0
                   })
           
           # Save to database
           await self._save_factor_exposures(model_date, exposures)
           
           return exposures
   
   async def _calculate_factor_correlations(self, model_date: date) -> Dict[str, Any]:
       """Calculate factor correlation matrix"""
       logger.info("🔢 Calculating factor correlation matrix")
       
       async with self.db_manager.pool.acquire() as conn:
           factors = await conn.fetch("""
               SELECT factor_name FROM risk_model.risk_factors
               WHERE factor_date = $1
               ORDER BY factor_name
           """, model_date)
           
           factor_names = [f['factor_name'] for f in factors]
           n_factors = len(factor_names)
           
           # Generate a positive semi-definite correlation matrix
           np.random.seed(200)
           random_matrix = np.random.randn(n_factors, n_factors)
           correlation_matrix = np.corrcoef(random_matrix)
           
           # Ensure diagonal is 1.0
           np.fill_diagonal(correlation_matrix, 1.0)
           
           # Save correlations to database
           correlations = []
           for i, factor1 in enumerate(factor_names):
               for j, factor2 in enumerate(factor_names):
                   if i <= j:  # Only store upper triangle + diagonal
                       correlations.append({
                           'factor1': factor1,
                           'factor2': factor2,
                           'correlation': float(correlation_matrix[i, j])
                       })
           
           await self._save_factor_correlations(model_date, correlations)
           
           return {
               'matrix_size': f"{n_factors}x{n_factors}",
               'correlations_stored': len(correlations),
               'condition_number': float(np.linalg.cond(correlation_matrix))
           }
   
   async def _calculate_specific_risk(self, model_date: date) -> List[Dict[str, Any]]:
       """Calculate asset-specific risk"""
       logger.info("🎲 Calculating asset-specific risk")
       
       async with self.db_manager.pool.acquire() as conn:
           universe = await conn.fetch("""
               SELECT symbol, market_cap FROM universe.trading_universe
               WHERE universe_date = $1 AND is_tradeable = TRUE
           """, model_date)
           
           specific_risks = []
           
           for asset in universe:
               symbol = asset['symbol']
               market_cap = float(asset['market_cap'] or 1000000)
               
               # Specific risk inversely related to market cap (smaller stocks are riskier)
               base_vol = 0.25  # 25% annual vol
               size_adjustment = max(0.1, np.log(1000000000 / market_cap) * 0.05)  # Scale by size
               
               np.random.seed(hash(symbol) % 10000)
               specific_vol = base_vol * (1 + size_adjustment) * np.random.uniform(0.8, 1.2)
               
               # Simulate R-squared from factor model
               r_squared = np.random.uniform(0.3, 0.8)
               residual_vol = specific_vol * np.sqrt(1 - r_squared)
               
               specific_risks.append({
                   'symbol': symbol,
                   'specific_vol': float(specific_vol),
                   'residual_vol': float(residual_vol),
                   'r_squared': float(r_squared)
               })
           
           await self._save_specific_risk(model_date, specific_risks)
           
           return specific_risks
   
   async def _save_risk_factors(self, factor_date: date, factor_type: str, factors: List[Dict[str, Any]]):
       """Save risk factors to database"""
       async with self.db_manager.pool.acquire() as conn:
           # Delete existing factors for this date and type
           await conn.execute("""
               DELETE FROM risk_model.risk_factors 
               WHERE factor_date = $1 AND factor_type = $2
           """, factor_date, factor_type)
           
           # Insert new factors
           if factors:
               values = []
               for factor in factors:
                   values.append((
                       factor_date,
                       factor_type,
                       factor['factor_name'],
                       factor['factor_value'],
                       factor['factor_volatility'],
                       factor.get('factor_description')
                   ))
               
               await conn.executemany("""
                   INSERT INTO risk_model.risk_factors
                   (factor_date, factor_type, factor_name, factor_value, factor_volatility, factor_description)
                   VALUES ($1, $2, $3, $4, $5, $6)
               """, values)
   
   async def _save_factor_exposures(self, factor_date: date, exposures: List[Dict[str, Any]]):
       """Save factor exposures to database"""
       async with self.db_manager.pool.acquire() as conn:
           # Delete existing exposures for this date
           await conn.execute("""
               DELETE FROM risk_model.factor_exposures WHERE factor_date = $1
           """, factor_date)
           
           # Insert new exposures in batches
           batch_size = 1000
           for i in range(0, len(exposures), batch_size):
               batch = exposures[i:i + batch_size]
               values = []
               
               for exposure in batch:
                   values.append((
                       factor_date,
                       exposure['symbol'],
                       exposure['factor_name'],
                       exposure['exposure'],
                       exposure.get('t_stat')
                   ))
               
               await conn.executemany("""
                   INSERT INTO risk_model.factor_exposures
                   (factor_date, symbol, factor_name, exposure, t_stat)
                   VALUES ($1, $2, $3, $4, $5)
               """, values)
   
   async def _save_factor_correlations(self, factor_date: date, correlations: List[Dict[str, Any]]):
       """Save factor correlations to database"""
       async with self.db_manager.pool.acquire() as conn:
           # Delete existing correlations for this date
           await conn.execute("""
               DELETE FROM risk_model.factor_correlations WHERE factor_date = $1
           """, factor_date)
           
           # Insert new correlations
           if correlations:
               values = []
               for corr in correlations:
                   values.append((
                       factor_date,
                       corr['factor1'],
                       corr['factor2'],
                       corr['correlation']
                   ))
               
               await conn.executemany("""
                   INSERT INTO risk_model.factor_correlations
                   (factor_date, factor1, factor2, correlation)
                   VALUES ($1, $2, $3, $4)
               """, values)
   
   async def _save_specific_risk(self, factor_date: date, specific_risks: List[Dict[str, Any]]):
       """Save specific risks to database"""
       async with self.db_manager.pool.acquire() as conn:
           # Delete existing specific risks for this date
           await conn.execute("""
               DELETE FROM risk_model.specific_risk WHERE factor_date = $1
           """, factor_date)
           
           # Insert new specific risks
           if specific_risks:
               values = []
               for risk in specific_risks:
                   values.append((
                       factor_date,
                       risk['symbol'],
                       risk['specific_vol'],
                       risk['residual_vol'],
                       risk['r_squared']
                   ))
               
               await conn.executemany("""
                   INSERT INTO risk_model.specific_risk
                   (factor_date, symbol, specific_vol, residual_vol, r_squared)
                   VALUES ($1, $2, $3, $4, $5)
               """, values)
   
   async def get_asset_risk_profile(self, symbol: str, factor_date: date) -> Dict[str, Any]:
       """Get complete risk profile for an asset"""
       async with self.db_manager.pool.acquire() as conn:
           # Get factor exposures
           exposures = await conn.fetch("""
               SELECT factor_name, exposure, t_stat 
               FROM risk_model.factor_exposures
               WHERE symbol = $1 AND factor_date = $2
               ORDER BY ABS(exposure) DESC
           """, symbol, factor_date)
           
           # Get specific risk
           specific_risk = await conn.fetchrow("""
               SELECT specific_vol, residual_vol, r_squared
               FROM risk_model.specific_risk
               WHERE symbol = $1 AND factor_date = $2
           """, symbol, factor_date)
           
           return {
               'symbol': symbol,
               'factor_date': str(factor_date),
               'factor_exposures': [dict(exp) for exp in exposures],
               'specific_risk': dict(specific_risk) if specific_risk else None
           }
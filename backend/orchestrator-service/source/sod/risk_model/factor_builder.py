# source/sod/risk_model/factor_builder.py
import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import date, datetime, timedelta
from decimal import Decimal
import asyncio
import numpy as np
from scipy import stats
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler

logger = logging.getLogger(__name__)

class FactorBuilder:
    """Builds and manages factor models for risk calculations"""
    
    def __init__(self, db_manager):
        self.db_manager = db_manager
        
        # Factor model parameters
        self.lookback_window = 252  # 1 year of data
        self.min_observations = 60  # Minimum observations needed
        self.factor_decay = 0.97   # Exponential decay for recent observations
        
        # Factor categories
        self.style_factors = [
            'VALUE', 'GROWTH', 'QUALITY', 'MOMENTUM', 
            'SIZE', 'PROFITABILITY', 'INVESTMENT', 'LEVERAGE'
        ]
        
        self.macro_factors = [
            'INTEREST_RATE', 'CREDIT_SPREAD', 'USD_STRENGTH', 
            'OIL_PRICE', 'VIX', 'TERM_STRUCTURE'
        ]
        
    async def initialize(self):
        """Initialize factor builder"""
        await self._create_factor_tables()
        logger.info("⚡ Factor Builder initialized")
    
    async def _create_factor_tables(self):
        """Create factor model tables"""
        async with self.db_manager.pool.acquire() as conn:
            # Factor loadings table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS risk_model.factor_loadings (
                    loading_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    factor_date DATE NOT NULL,
                    symbol VARCHAR(20) NOT NULL,
                    factor_name VARCHAR(100) NOT NULL,
                    loading DECIMAL(12,6) NOT NULL,
                    t_statistic DECIMAL(8,4),
                    r_squared DECIMAL(8,6),
                    standard_error DECIMAL(12,6),
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    UNIQUE(factor_date, symbol, factor_name)
                )
            """)
            
            # Factor covariance matrix
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS risk_model.factor_covariance (
                    covariance_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    factor_date DATE NOT NULL,
                    factor1 VARCHAR(100) NOT NULL,
                    factor2 VARCHAR(100) NOT NULL,
                    covariance DECIMAL(12,8) NOT NULL,
                    correlation DECIMAL(8,6),
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    UNIQUE(factor_date, factor1, factor2)
                )
            """)
            
            # Factor statistics
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS risk_model.factor_statistics (
                    stat_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    factor_date DATE NOT NULL,
                    factor_name VARCHAR(100) NOT NULL,
                    mean_return DECIMAL(12,6) NOT NULL,
                    volatility DECIMAL(12,6) NOT NULL,
                    skewness DECIMAL(8,4),
                    kurtosis DECIMAL(8,4),
                    max_drawdown DECIMAL(8,4),
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    UNIQUE(factor_date, factor_name)
                )
            """)
    
    async def build_factor_model(self, model_date: date) -> Dict[str, Any]:
        """Build complete factor model for the given date"""
        logger.info(f"⚡ Building factor model for {model_date}")
        
        try:
            results = {
                "model_date": str(model_date),
                "factors_built": 0,
                "securities_modeled": 0,
                "model_statistics": {}
            }
            
            # Step 1: Build style factors
            style_results = await self._build_style_factors(model_date)
            results["style_factors"] = style_results
            
            # Step 2: Build macro factors
            macro_results = await self._build_macro_factors(model_date)
            results["macro_factors"] = macro_results
            
            # Step 3: Build industry factors (using existing sector data)
            industry_results = await self._build_industry_factors(model_date)
            results["industry_factors"] = industry_results
            
            # Step 4: Calculate factor loadings for all securities
            loadings_results = await self._calculate_factor_loadings(model_date)
            results["securities_modeled"] = loadings_results["securities_count"]
            
            # Step 5: Build factor covariance matrix
            covariance_results = await self._build_factor_covariance_matrix(model_date)
            results["covariance_matrix"] = covariance_results
            
            # Step 6: Calculate factor statistics
            stats_results = await self._calculate_factor_statistics(model_date)
            results["factor_statistics"] = stats_results
            
            total_factors = (len(style_results.get("factors", [])) + 
                           len(macro_results.get("factors", [])) + 
                           len(industry_results.get("factors", [])))
            
            results["factors_built"] = total_factors
            results["model_statistics"] = {
                "total_factors": total_factors,
                "r_squared_avg": loadings_results.get("avg_r_squared", 0),
                "specific_risk_avg": loadings_results.get("avg_specific_risk", 0)
            }
            
            logger.info(f"✅ Factor model built: {results}")
            return results
            
        except Exception as e:
            logger.error(f"❌ Failed to build factor model: {e}", exc_info=True)
            raise
    
    async def _build_style_factors(self, model_date: date) -> Dict[str, Any]:
        """Build style factors using fundamental and price data"""
        logger.info("📊 Building style factors")
        
        # Get universe for the date
        async with self.db_manager.pool.acquire() as conn:
            universe = await conn.fetch("""
                SELECT symbol, market_cap, sector
                FROM universe.trading_universe
                WHERE universe_date = $1 AND is_tradeable = TRUE
                ORDER BY market_cap DESC
            """, model_date)
            
            if not universe:
                return {"factors": [], "securities_count": 0}
            
            # Get price and fundamental data (simulated)
            price_data = await self._get_historical_price_data(
                [u['symbol'] for u in universe], model_date
            )
            
            fundamental_data = await self._get_fundamental_data(
                [u['symbol'] for u in universe], model_date
            )
            
            style_factors = {}
            
            for factor_name in self.style_factors:
                factor_values = await self._calculate_style_factor(
                    factor_name, universe, price_data, fundamental_data
                )
                
                if factor_values:
                    # Standardize factor values (z-score)
                    values_array = np.array(list(factor_values.values()))
                    standardized_values = stats.zscore(values_array)
                    
                    # Store standardized values
                    style_factors[factor_name] = {}
                    for i, symbol in enumerate(factor_values.keys()):
                        style_factors[factor_name][symbol] = float(standardized_values[i])
            
            # Store style factors
            await self._store_factor_values(model_date, style_factors, "STYLE")
            
            return {
                "factors": list(style_factors.keys()),
                "securities_count": len(universe)
            }
    
    async def _calculate_style_factor(self, factor_name: str, universe: List[Dict],
                                    price_data: Dict[str, np.ndarray],
                                    fundamental_data: Dict[str, Dict[str, float]]) -> Dict[str, float]:
        """Calculate individual style factor values"""
        factor_values = {}
        
        for security in universe:
            symbol = security['symbol']
            
            try:
                if factor_name == 'VALUE':
                    # Price-to-book and price-to-earnings based value score
                    pb_ratio = fundamental_data.get(symbol, {}).get('price_book_ratio', 1.0)
                    pe_ratio = fundamental_data.get(symbol, {}).get('price_earnings_ratio', 15.0)
                    
                    # Invert ratios (lower ratios = higher value)
                    value_score = (1 / max(pb_ratio, 0.1)) + (1 / max(pe_ratio, 1.0))
                    factor_values[symbol] = value_score
                    
                elif factor_name == 'GROWTH':
                    # Revenue and earnings growth
                    revenue_growth = fundamental_data.get(symbol, {}).get('revenue_growth', 0.05)
                    earnings_growth = fundamental_data.get(symbol, {}).get('earnings_growth', 0.08)
                    
                    growth_score = (revenue_growth + earnings_growth) / 2
                    factor_values[symbol] = growth_score
                    
                elif factor_name == 'QUALITY':
                    # ROE, debt-to-equity, and profit margin
                    roe = fundamental_data.get(symbol, {}).get('return_on_equity', 0.12)
                    debt_equity = fundamental_data.get(symbol, {}).get('debt_to_equity', 0.5)
                    profit_margin = fundamental_data.get(symbol, {}).get('profit_margin', 0.1)
                    
                    quality_score = roe + profit_margin - (debt_equity * 0.1)
                    factor_values[symbol] = quality_score
                    
                elif factor_name == 'MOMENTUM':
                    # Price momentum over multiple periods
                    if symbol in price_data and len(price_data[symbol]) >= 63:  # 3 months
                        prices = price_data[symbol]
                        
                        # Calculate momentum (3-month return with 1-month lag)
                        mom_3m = (prices[-22] / prices[-63] - 1) if len(prices) >= 63 else 0
                        mom_6m = (prices[-22] / prices[-126] - 1) if len(prices) >= 126 else mom_3m
                        
                        momentum_score = (mom_3m * 0.6) + (mom_6m * 0.4)
                        factor_values[symbol] = momentum_score
                    
                elif factor_name == 'SIZE':
                    # Market cap based size factor
                    market_cap = float(security.get('market_cap', 1000000000))
                    size_score = np.log(market_cap)
                    factor_values[symbol] = size_score
                    
                elif factor_name == 'PROFITABILITY':
                    # Multiple profitability metrics
                    roa = fundamental_data.get(symbol, {}).get('return_on_assets', 0.08)
                    gross_margin = fundamental_data.get(symbol, {}).get('gross_margin', 0.25)
                    
                    profitability_score = (roa * 0.6) + (gross_margin * 0.4)
                    factor_values[symbol] = profitability_score
                    
                elif factor_name == 'INVESTMENT':
                    # Asset growth and capex intensity
                    asset_growth = fundamental_data.get(symbol, {}).get('asset_growth', 0.05)
                    capex_intensity = fundamental_data.get(symbol, {}).get('capex_sales_ratio', 0.03)
                    
                    # Lower asset growth and capex intensity = better
                    investment_score = -(asset_growth + capex_intensity)
                    factor_values[symbol] = investment_score
                    
                elif factor_name == 'LEVERAGE':
                    # Debt ratios
                    debt_equity = fundamental_data.get(symbol, {}).get('debt_to_equity', 0.3)
                    debt_assets = fundamental_data.get(symbol, {}).get('debt_to_assets', 0.2)
                    
                    leverage_score = (debt_equity + debt_assets) / 2
                    factor_values[symbol] = leverage_score
                    
            except Exception as e:
                logger.debug(f"Error calculating {factor_name} for {symbol}: {e}")
                continue
        
        return factor_values
    
    async def _build_macro_factors(self, model_date: date) -> Dict[str, Any]:
        """Build macroeconomic factors"""
        logger.info("🌍 Building macro factors")
        
        # Simulate macro factor data (in practice, would get from economic data providers)
        macro_factors = {}
        
        np.random.seed(int(model_date.strftime("%Y%m%d")))  # Deterministic for testing
        
        for factor_name in self.macro_factors:
            if factor_name == 'INTEREST_RATE':
                # 10-year treasury rate factor
                base_rate = 4.5  # Current 10Y rate
                daily_change = np.random.normal(0, 0.05)  # 5bp daily vol
                macro_factors[factor_name] = base_rate + daily_change
                
            elif factor_name == 'CREDIT_SPREAD':
                # Investment grade credit spread
                base_spread = 150  # 150bp base spread
                daily_change = np.random.normal(0, 5)  # 5bp daily vol
                macro_factors[factor_name] = base_spread + daily_change
                
            elif factor_name == 'USD_STRENGTH':
                # Dollar index factor
                base_dxy = 103.0
                daily_change = np.random.normal(0, 0.5)
                macro_factors[factor_name] = base_dxy + daily_change
                
            elif factor_name == 'OIL_PRICE':
                # WTI oil price
                base_oil = 75.0
                daily_change = np.random.normal(0, 2.0)
                macro_factors[factor_name] = base_oil + daily_change
                
            elif factor_name == 'VIX':
                # Volatility index
                base_vix = 18.0
                daily_change = np.random.normal(0, 1.5)
                macro_factors[factor_name] = max(10.0, base_vix + daily_change)
                
            elif factor_name == 'TERM_STRUCTURE':
                # Yield curve slope (10Y - 2Y)
                slope_2_10 = 0.5  # 50bp slope
                daily_change = np.random.normal(0, 0.1)
                macro_factors[factor_name] = slope_2_10 + daily_change
        
        # Store macro factors
        await self._store_factor_values(model_date, {"MACRO": macro_factors}, "MACRO")
        
        return {
            "factors": list(macro_factors.keys()),
            "factor_values": macro_factors
        }
    
    async def _build_industry_factors(self, model_date: date) -> Dict[str, Any]:
        """Build industry/sector factors"""
        logger.info("🏭 Building industry factors")
        
        async with self.db_manager.pool.acquire() as conn:
            # Get distinct sectors
            sectors = await conn.fetch("""
                SELECT DISTINCT sector, COUNT(*) as security_count
                FROM universe.trading_universe
                WHERE universe_date = $1 AND is_tradeable = TRUE AND sector IS NOT NULL
                GROUP BY sector
                ORDER BY security_count DESC
            """, model_date)
            
            industry_factors = {}
            
            for sector_row in sectors:
                sector = sector_row['sector']
                factor_name = f"INDUSTRY_{sector}"
                
                # Simulate industry factor return
                np.random.seed(hash(sector + str(model_date)) % 1000)
                
                # Industry factor return (daily)
                industry_return = np.random.normal(0, 0.015)  # 1.5% daily vol
                industry_factors[factor_name] = industry_return
        
        # Store industry factors
        await self._store_factor_values(model_date, {"INDUSTRY": industry_factors}, "INDUSTRY")
        
        return {
            "factors": list(industry_factors.keys()),
            "sectors_count": len(sectors)
        }
    
    async def _calculate_factor_loadings(self, model_date: date) -> Dict[str, Any]:
        """Calculate factor loadings for all securities using regression"""
        logger.info("🔢 Calculating factor loadings")
        
        try:
            # Get all factors for the date
            async with self.db_manager.pool.acquire() as conn:
                factors = await conn.fetch("""
                    SELECT factor_name, factor_value
                    FROM risk_model.risk_factors
                    WHERE factor_date = $1
                """, model_date)
                
                if not factors:
                    return {"securities_count": 0, "avg_r_squared": 0}
                
                # Get universe
                universe = await conn.fetch("""
                    SELECT symbol FROM universe.trading_universe
                    WHERE universe_date = $1 AND is_tradeable = TRUE
                """, model_date)
                
                # Clear existing loadings
                await conn.execute("""
                    DELETE FROM risk_model.factor_loadings WHERE factor_date = $1
                """, model_date)
                
                total_r_squared = 0
                securities_processed = 0
                
                for security in universe:
                    symbol = security['symbol']
                    
                    # Get historical returns for this security
                    returns = await self._get_security_returns(symbol, model_date)
                    
                    if len(returns) < self.min_observations:
                        continue
                    
                    # Perform factor regression
                    loadings, r_squared = await self._perform_factor_regression(
                        symbol, returns, factors, model_date
                    )
                    
                    # Store loadings
                    for factor_name, loading_data in loadings.items():
                        await conn.execute("""
                            INSERT INTO risk_model.factor_loadings
                            (factor_date, symbol, factor_name, loading, t_statistic, r_squared, standard_error)
                            VALUES ($1, $2, $3, $4, $5, $6, $7)
                        """, model_date, symbol, factor_name, 
                        loading_data['loading'], loading_data['t_stat'], 
                        r_squared, loading_data['std_error'])
                    
                    total_r_squared += r_squared
                    securities_processed += 1
                
                avg_r_squared = total_r_squared / securities_processed if securities_processed > 0 else 0
                
                return {
                    "securities_count": securities_processed,
                    "avg_r_squared": avg_r_squared,
                    "avg_specific_risk": 1 - avg_r_squared
                }
                
        except Exception as e:
            logger.error(f"Error calculating factor loadings: {e}", exc_info=True)
            return {"securities_count": 0, "avg_r_squared": 0}
    
    async def _perform_factor_regression(self, symbol: str, returns: np.ndarray,
                                       factors: List[Dict], model_date: date) -> Tuple[Dict[str, Dict], float]:
        """Perform factor regression for a single security"""
        # Simulate factor regression (in practice, would use actual factor time series)
        factor_names = [f['factor_name'] for f in factors]
        n_factors = len(factor_names)
        
        # Generate synthetic factor exposures
        np.random.seed(hash(symbol) % 1000)
        
        loadings = {}
        
        for i, factor_name in enumerate(factor_names):
            # Simulate factor loading
            if 'INDUSTRY_' in factor_name:
                # Industry factors are 0 or 1
                loading = 1.0 if np.random.random() > 0.9 else 0.0
            else:
                # Style and macro factors are continuous
                loading = np.random.normal(0, 0.5)
            
            # Simulate t-statistic and standard error
            t_stat = np.random.normal(0, 2) if loading != 0 else 0
            std_error = abs(loading / max(t_stat, 0.1)) if t_stat != 0 else 0.1
            
            loadings[factor_name] = {
                'loading': float(loading),
                't_stat': float(t_stat),
                'std_error': float(std_error)
            }
        
        # Simulate R-squared
        r_squared = np.random.uniform(0.3, 0.8)
        
        return loadings, r_squared
    
    async def _build_factor_covariance_matrix(self, model_date: date) -> Dict[str, Any]:
        """Build factor covariance matrix"""
        logger.info("🔢 Building factor covariance matrix")
        
        async with self.db_manager.pool.acquire() as conn:
            # Get all factors
            factors = await conn.fetch("""
                SELECT DISTINCT factor_name FROM risk_model.risk_factors
                WHERE factor_date = $1
                ORDER BY factor_name
            """, model_date)
            
            factor_names = [f['factor_name'] for f in factors]
            n_factors = len(factor_names)
            
            if n_factors == 0:
                return {"matrix_size": 0}
            
            # Generate positive semi-definite covariance matrix
            np.random.seed(200 + int(model_date.strftime("%j")))
            
            # Create random matrix and make it positive semi-definite
            A = np.random.randn(n_factors, n_factors) * 0.01
            cov_matrix = np.dot(A, A.transpose())
            
            # Add some structure to the covariance matrix
            for i in range(n_factors):
                for j in range(n_factors):
                    if i == j:
                        cov_matrix[i, j] += 0.0004  # Add variance to diagonal
                    elif 'INDUSTRY_' in factor_names[i] and 'INDUSTRY_' in factor_names[j]:
                        cov_matrix[i, j] *= 0.3  # Lower correlation between industries
                    elif factor_names[i] in self.style_factors and factor_names[j] in self.style_factors:
                        cov_matrix[i, j] *= 1.5  # Higher correlation between style factors
            
            # Clear existing covariance data
            await conn.execute("""
                DELETE FROM risk_model.factor_covariance WHERE factor_date = $1
            """, model_date)
            
            # Store covariance matrix
            covariances_stored = 0
            for i, factor1 in enumerate(factor_names):
                for j, factor2 in enumerate(factor_names):
                    if i <= j:  # Store upper triangle + diagonal
                        covariance = float(cov_matrix[i, j])
                        
                        # Calculate correlation
                        vol1 = np.sqrt(cov_matrix[i, i])
                        vol2 = np.sqrt(cov_matrix[j, j])
                        correlation = covariance / (vol1 * vol2) if vol1 * vol2 > 0 else 0
                        
                        await conn.execute("""
                            INSERT INTO risk_model.factor_covariance
                            (factor_date, factor1, factor2, covariance, correlation)
                            VALUES ($1, $2, $3, $4, $5)
                        """, model_date, factor1, factor2, covariance, correlation)
                        
                        covariances_stored += 1
            
            return {
                "matrix_size": f"{n_factors}x{n_factors}",
                "covariances_stored": covariances_stored,
                "condition_number": float(np.linalg.cond(cov_matrix))
            }
    
    async def _calculate_factor_statistics(self, model_date: date) -> Dict[str, Any]:
        """Calculate factor statistics"""
        logger.info("📊 Calculating factor statistics")
        
        async with self.db_manager.pool.acquire() as conn:
            # Clear existing statistics
            await conn.execute("""
                DELETE FROM risk_model.factor_statistics WHERE factor_date = $1
            """, model_date)
            
            # Get all factors
            factors = await conn.fetch("""
                SELECT factor_name, factor_value, factor_volatility
                FROM risk_model.risk_factors
                WHERE factor_date = $1
            """, model_date)
            
            stats_calculated = 0
            
            for factor in factors:
                factor_name = factor['factor_name']
                
                # Simulate factor statistics (in practice, calculate from historical data)
                np.random.seed(hash(factor_name) % 1000)
                
                mean_return = float(factor.get('factor_value', 0))
                volatility = float(factor.get('factor_volatility', 0.02))
                skewness = np.random.normal(0, 0.5)
                kurtosis = np.random.uniform(2.5, 4.5)
                max_drawdown = np.random.uniform(0.05, 0.25)
                
                await conn.execute("""
                    INSERT INTO risk_model.factor_statistics
                    (factor_date, factor_name, mean_return, volatility, 
                     skewness, kurtosis, max_drawdown)
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                """, model_date, factor_name, mean_return, volatility,
                skewness, kurtosis, max_drawdown)
                
                stats_calculated += 1
            
            return {"statistics_calculated": stats_calculated}
    
    async def _get_historical_price_data(self, symbols: List[str], end_date: date) -> Dict[str, np.ndarray]:
        """Get historical price data for symbols"""
        # Simulate historical price data
        price_data = {}
        
        for symbol in symbols:
            np.random.seed(hash(symbol) % 1000)
            
            # Generate price series
            n_days = self.lookback_window
            returns = np.random.normal(0.0008, 0.02, n_days)  # 8bp mean, 2% vol
            
            # Generate prices from returns
            prices = [100.0]  # Starting price
            for ret in returns:
                prices.append(prices[-1] * (1 + ret))
            
            price_data[symbol] = np.array(prices)
        
        return price_data
    
    async def _get_fundamental_data(self, symbols: List[str], as_of_date: date) -> Dict[str, Dict[str, float]]:
        """Get fundamental data for symbols"""
        # Simulate fundamental data
        fundamental_data = {}
        
        for symbol in symbols:
            np.random.seed(hash(symbol + "fundamentals") % 1000)
            
            fundamental_data[symbol] = {
                'price_book_ratio': np.random.uniform(0.5, 5.0),
                'price_earnings_ratio': np.random.uniform(5.0, 30.0),
                'revenue_growth': np.random.normal(0.06, 0.1),
                'earnings_growth': np.random.normal(0.08, 0.15),
                'return_on_equity': np.random.uniform(0.05, 0.25),
                'debt_to_equity': np.random.uniform(0.1, 1.5),
                'profit_margin': np.random.uniform(0.02, 0.25),
                'return_on_assets': np.random.uniform(0.03, 0.20),
                'gross_margin': np.random.uniform(0.15, 0.60),
                'asset_growth': np.random.normal(0.05, 0.08),
                'capex_sales_ratio': np.random.uniform(0.01, 0.08),
                'debt_to_assets': np.random.uniform(0.05, 0.50)
            }
        
        return fundamental_data
    
    async def _get_security_returns(self, symbol: str, end_date: date) -> np.ndarray:
        """Get historical returns for a security"""
        # Simulate security returns
        np.random.seed(hash(symbol + "returns") % 1000)
        
        # Generate returns with some autocorrelation
        n_days = min(self.lookback_window, 252)
        returns = np.random.normal(0.0008, 0.025, n_days)
        
        # Add some momentum/mean reversion
        for i in range(1, len(returns)):
            returns[i] += 0.05 * returns[i-1]  # Small autocorrelation
        
        return returns
    
    async def _store_factor_values(self, factor_date: date, factors_dict: Dict[str, Dict], factor_type: str):
        """Store factor values in the database"""
        async with self.db_manager.pool.acquire() as conn:
            for category, factors in factors_dict.items():
                for factor_name, values in factors.items():
                    if isinstance(values, dict):
                        # This is factor exposures by security (style factors)
                        for symbol, value in values.items():
                            # Store in factor exposures table
                            await conn.execute("""
                                INSERT INTO risk_model.factor_exposures
                                (factor_date, symbol, factor_name, exposure)
                                VALUES ($1, $2, $3, $4)
                                ON CONFLICT (factor_date, symbol, factor_name)
                                DO UPDATE SET exposure = $4
                            """, factor_date, symbol, factor_name, value)
                    else:
                        # This is a single factor value (macro/industry factors)
                        await conn.execute("""
                            INSERT INTO risk_model.risk_factors
                            (factor_date, factor_type, factor_name, factor_value, factor_volatility)
                            VALUES ($1, $2, $3, $4, $5)
                            ON CONFLICT (factor_date, factor_type, factor_name)
                            DO UPDATE SET factor_value = $4, factor_volatility = $5
                        """, factor_date, factor_type, factor_name, float(values), 0.02)  # Default vol
    
    async def get_factor_model_summary(self, model_date: date) -> Dict[str, Any]:
        """Get factor model summary for a specific date"""
        async with self.db_manager.pool.acquire() as conn:
            # Factor counts by type
            factor_counts = await conn.fetch("""
                SELECT factor_type, COUNT(*) as count
                FROM risk_model.risk_factors
                WHERE factor_date = $1
                GROUP BY factor_type
            """, model_date)
            
            # Model coverage
            coverage = await conn.fetchrow("""
                SELECT 
                    COUNT(DISTINCT symbol) as securities_covered,
                    COUNT(*) as total_loadings,
                    AVG(r_squared) as avg_r_squared
                FROM risk_model.factor_loadings
                WHERE factor_date = $1
            """, model_date)
            
            # Top factor exposures
            # Continuing factor_builder.py

            top_exposures = await conn.fetch("""
                SELECT factor_name, AVG(ABS(exposure)) as avg_exposure
                FROM risk_model.factor_exposures
                WHERE factor_date = $1
                GROUP BY factor_name
                ORDER BY avg_exposure DESC
                LIMIT 10
            """, model_date)
            
            return {
                "model_date": str(model_date),
                "factor_counts": {row['factor_type']: row['count'] for row in factor_counts},
                "coverage": dict(coverage) if coverage else {},
                "top_factor_exposures": [dict(row) for row in top_exposures]
            }
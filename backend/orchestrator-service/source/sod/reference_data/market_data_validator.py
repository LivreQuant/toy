# source/sod/reference_data/market_data_validator.py
import logging
from typing import Dict, List, Any, Tuple, Optional
from datetime import date, datetime, timedelta
from decimal import Decimal
import asyncio
import statistics

logger = logging.getLogger(__name__)

class MarketDataValidator:
    """Validates market data feeds and identifies anomalies"""
    
    def __init__(self, db_manager):
        self.db_manager = db_manager
        
        # Validation thresholds
        self.max_daily_return = 0.50  # 50% max daily return
        self.min_price = 0.01  # Minimum valid price
        self.max_price = 100000.0  # Maximum valid price
        self.max_spread_pct = 10.0  # 10% max bid-ask spread
        
    async def initialize(self):
        """Initialize market data validator"""
        await self._create_validation_tables()
        logger.info("📈 Market Data Validator initialized")
    
    async def _create_validation_tables(self):
        """Create validation tables"""
        async with self.db_manager.pool.acquire() as conn:
            await conn.execute("""
                CREATE SCHEMA IF NOT EXISTS market_data
            """)
            
            # Market data validation log
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS market_data.validation_log (
                    validation_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    validation_date DATE NOT NULL,
                    symbol VARCHAR(20) NOT NULL,
                    data_source VARCHAR(50),
                    validation_type VARCHAR(50) NOT NULL,
                    status VARCHAR(20) NOT NULL,
                    issue_description TEXT,
                    old_value DECIMAL(20,8),
                    new_value DECIMAL(20,8),
                    confidence_score DECIMAL(5,2),
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                )
            """)
            
            # Price outliers table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS market_data.price_outliers (
                    outlier_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    detection_date DATE NOT NULL,
                    symbol VARCHAR(20) NOT NULL,
                    price_type VARCHAR(20) NOT NULL,
                    outlier_price DECIMAL(20,8) NOT NULL,
                    expected_range_min DECIMAL(20,8),
                    expected_range_max DECIMAL(20,8),
                    z_score DECIMAL(8,4),
                    action_taken VARCHAR(50),
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                )
            """)
            
            # Data feed status
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS market_data.feed_status (
                    feed_name VARCHAR(100) PRIMARY KEY,
                    last_update_time TIMESTAMP WITH TIME ZONE,
                    status VARCHAR(20) DEFAULT 'ACTIVE',
                    records_received INTEGER DEFAULT 0,
                    records_processed INTEGER DEFAULT 0,
                    error_count INTEGER DEFAULT 0,
                    last_error TEXT,
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                )
            """)
    
    async def validate_market_data(self, validation_date: date) -> Dict[str, Any]:
        """Validate market data for the given date"""
        logger.info(f"📈 Validating market data for {validation_date}")
        
        try:
            results = {
                "total_securities_checked": 0,
                "price_outliers_detected": 0,
                "invalid_prices_found": 0,
                "wide_spreads_detected": 0,
                "missing_data_found": 0,
                "data_feeds_checked": 0,
                "overall_quality_score": 0.0
            }
            
            # Step 1: Validate individual security prices
            price_validation = await self._validate_security_prices(validation_date)
            results.update(price_validation)
            
            # Step 2: Check for price outliers
            outlier_results = await self._detect_price_outliers(validation_date)
            results["price_outliers_detected"] = outlier_results["outliers_found"]
            
            # Step 3: Validate bid-ask spreads
            spread_results = await self._validate_bid_ask_spreads(validation_date)
            results["wide_spreads_detected"] = spread_results["wide_spreads"]
            
            # Step 4: Check data completeness
            completeness_results = await self._check_data_completeness(validation_date)
            results["missing_data_found"] = completeness_results["missing_count"]
            
            # Step 5: Validate data feeds
            feed_results = await self._validate_data_feeds(validation_date)
            results["data_feeds_checked"] = feed_results["feeds_checked"]
            
            # Calculate overall quality score
            results["overall_quality_score"] = await self._calculate_quality_score(results)
            
            logger.info(f"✅ Market data validation complete: Quality Score {results['overall_quality_score']:.2f}%")
            return results
            
        except Exception as e:
            logger.error(f"❌ Failed to validate market data: {e}", exc_info=True)
            raise
    
    async def _validate_security_prices(self, validation_date: date) -> Dict[str, Any]:
        """Validate individual security prices"""
        logger.info("💰 Validating security prices")
        
        invalid_count = 0
        total_count = 0
        
        async with self.db_manager.pool.acquire() as conn:
            # Get all active securities with prices
            securities = await conn.fetch("""
                SELECT symbol, last_price, bid_price, ask_price, price_date
                FROM reference_data.securities
                WHERE is_active = TRUE
                ORDER BY symbol
            """)
            
            for security in securities:
                total_count += 1
                symbol = security['symbol']
                last_price = security['last_price']
                bid_price = security['bid_price']
                ask_price = security['ask_price']
                price_date = security['price_date']
                
                issues = []
                
                # Check for invalid last price
                if not last_price or last_price <= 0:
                    issues.append("invalid_last_price")
                elif last_price < self.min_price or last_price > self.max_price:
                    issues.append("price_out_of_range")
                
                # Check bid-ask consistency
                if bid_price and ask_price and last_price:
                    if bid_price >= ask_price:
                        issues.append("inverted_bid_ask")
                    if last_price < bid_price * 0.95 or last_price > ask_price * 1.05:
                        issues.append("price_outside_bid_ask")
                
                # Check for stale prices
                if price_date and price_date < validation_date - timedelta(days=1):
                    issues.append("stale_price")
                
                if issues:
                    invalid_count += 1
                    
                    # Log validation issues
                    for issue in issues:
                        await self._log_validation_issue(
                            validation_date, symbol, "PRICE_VALIDATION",
                            issue, last_price, None
                        )
            
            return {
                "total_securities_checked": total_count,
                "invalid_prices_found": invalid_count
            }
    
    async def _detect_price_outliers(self, validation_date: date) -> Dict[str, Any]:
        """Detect price outliers using statistical methods"""
        logger.info("🔍 Detecting price outliers")
        
        outliers_found = 0
        
        async with self.db_manager.pool.acquire() as conn:
            # Get securities with historical price data (simulated)
            securities = await conn.fetch("""
                SELECT symbol, last_price, market_cap
                FROM reference_data.securities
                WHERE is_active = TRUE AND last_price > 0
                ORDER BY symbol
            """)
            
            for security in securities:
                symbol = security['symbol']
                current_price = float(security['last_price'])
                
                # Simulate historical prices for outlier detection
                # In practice, you'd query actual historical price data
                historical_prices = await self._get_simulated_historical_prices(symbol, validation_date)
                
                if len(historical_prices) >= 20:  # Need sufficient history
                    # Calculate z-score
                    mean_price = statistics.mean(historical_prices)
                    std_price = statistics.stdev(historical_prices)
                    
                    if std_price > 0:
                        z_score = (current_price - mean_price) / std_price
                        
                        # Flag as outlier if |z-score| > 3
                        if abs(z_score) > 3:
                            outliers_found += 1
                            
                            # Calculate expected range
                            expected_min = mean_price - 2 * std_price
                            expected_max = mean_price + 2 * std_price
                            
                            # Record outlier
                            await conn.execute("""
                                INSERT INTO market_data.price_outliers
                                (detection_date, symbol, price_type, outlier_price, 
                                 expected_range_min, expected_range_max, z_score, action_taken)
                                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                            """, 
                            validation_date, symbol, 'LAST_PRICE', current_price,
                            expected_min, expected_max, z_score, 'FLAGGED_FOR_REVIEW')
                            
                            logger.warning(f"🚨 Price outlier detected: {symbol} = ${current_price:.2f} (z-score: {z_score:.2f})")
        
        return {"outliers_found": outliers_found}
    
    async def _get_simulated_historical_prices(self, symbol: str, current_date: date, days: int = 30) -> List[float]:
        """Simulate historical prices for demonstration"""
        import random
        import math
        
        # Get current price as starting point
        async with self.db_manager.pool.acquire() as conn:
            result = await conn.fetchrow("""
                SELECT last_price FROM reference_data.securities WHERE symbol = $1
            """, symbol)
            
            if not result or not result['last_price']:
                return []
            
            current_price = float(result['last_price'])
        
        # Generate realistic price series with some volatility
        random.seed(hash(symbol) % 10000)  # Deterministic for testing
        prices = []
        price = current_price
        
        # Work backwards from current date
        for i in range(days):
            # Random walk with slight mean reversion
            daily_return = random.gauss(0, 0.02)  # 2% daily volatility
            if abs(price - current_price) / current_price > 0.1:  # Mean reversion
                daily_return *= -0.5
            
            price *= (1 + daily_return)
            price = max(0.01, price)  # Ensure positive prices
            prices.append(price)
        
        # Occasionally inject an outlier for testing
        if random.random() < 0.05:  # 5% chance
            outlier_idx = random.randint(0, len(prices) - 1)
            outlier_multiplier = random.choice([0.5, 1.5, 2.0])  # 50% drop or 50-100% spike
            prices[outlier_idx] *= outlier_multiplier
        
        return prices
    
    async def _validate_bid_ask_spreads(self, validation_date: date) -> Dict[str, Any]:
        """Validate bid-ask spreads"""
        logger.info("📊 Validating bid-ask spreads")
        
        wide_spreads = 0
        
        async with self.db_manager.pool.acquire() as conn:
            securities = await conn.fetch("""
                SELECT symbol, bid_price, ask_price, last_price
                FROM reference_data.securities
                WHERE is_active = TRUE 
                  AND bid_price IS NOT NULL 
                  AND ask_price IS NOT NULL
                  AND bid_price > 0 AND ask_price > 0
            """)
            
            for security in securities:
                symbol = security['symbol']
                bid = float(security['bid_price'])
                ask = float(security['ask_price'])
                last = float(security['last_price']) if security['last_price'] else (bid + ask) / 2
                
                if ask > bid:  # Valid spread
                    spread_pct = ((ask - bid) / last) * 100
                    
                    if spread_pct > self.max_spread_pct:
                        wide_spreads += 1
                        
                        await self._log_validation_issue(
                            validation_date, symbol, "SPREAD_VALIDATION",
                            f"Wide spread: {spread_pct:.2f}%", spread_pct, None
                        )
        
        return {"wide_spreads": wide_spreads}
    
    async def _check_data_completeness(self, validation_date: date) -> Dict[str, Any]:
        """Check for missing data"""
        logger.info("📋 Checking data completeness")
        
        async with self.db_manager.pool.acquire() as conn:
            # Count securities missing key data points
            missing_data = await conn.fetchrow("""
                SELECT 
                    COUNT(CASE WHEN last_price IS NULL THEN 1 END) as missing_price,
                    COUNT(CASE WHEN bid_price IS NULL THEN 1 END) as missing_bid,
                    COUNT(CASE WHEN ask_price IS NULL THEN 1 END) as missing_ask,
                    COUNT(CASE WHEN market_cap IS NULL THEN 1 END) as missing_market_cap,
                    COUNT(CASE WHEN sector IS NULL THEN 1 END) as missing_sector
                FROM reference_data.securities
                WHERE is_active = TRUE
            """)
            
            total_missing = sum(missing_data[key] for key in missing_data.keys())
            
            return {
                "missing_count": total_missing,
                "missing_breakdown": dict(missing_data)
            }
    
    async def _validate_data_feeds(self, validation_date: date) -> Dict[str, Any]:
        """Validate data feed status"""
        logger.info("📡 Validating data feeds")
        
        # Simulate data feed validation
        feeds = ['BLOOMBERG_EQUITY', 'REFINITIV_PRICING', 'ICE_REFERENCE', 'NASDAQ_FEED']
        feeds_checked = 0
        
        async with self.db_manager.pool.acquire() as conn:
            for feed_name in feeds:
                feeds_checked += 1
                
                # Simulate feed status (in practice, check actual feed health)
                import random
                random.seed(hash(feed_name) % 1000)
                
                status = random.choice(['ACTIVE'] * 9 + ['DELAYED'])  # 90% active
                records_received = random.randint(50000, 100000)
                records_processed = int(records_received * random.uniform(0.95, 1.0))
                error_count = records_received - records_processed
                
                # Update feed status
                await conn.execute("""
                    INSERT INTO market_data.feed_status
                    (feed_name, last_update_time, status, records_received, 
                     records_processed, error_count, updated_at)
                    VALUES ($1, $2, $3, $4, $5, $6, NOW())
                    ON CONFLICT (feed_name) 
                    DO UPDATE SET
                        last_update_time = $2,
                        status = $3,
                        records_received = $4,
                        records_processed = $5,
                        error_count = $6,
                        updated_at = NOW()
                """, feed_name, datetime.utcnow(), status, 
                records_received, records_processed, error_count)
                
                if status != 'ACTIVE':
                    logger.warning(f"⚠️ Data feed issue: {feed_name} status is {status}")
        
        return {"feeds_checked": feeds_checked}
    
    async def _calculate_quality_score(self, validation_results: Dict[str, Any]) -> float:
        """Calculate overall data quality score"""
        total_securities = validation_results.get("total_securities_checked", 1)
        
        # Weight different types of issues
        issue_weights = {
            "invalid_prices_found": 3.0,      # High impact
            "price_outliers_detected": 2.0,   # Medium-high impact
            "wide_spreads_detected": 1.0,     # Medium impact
            "missing_data_found": 0.5         # Lower impact
        }
        
        total_weighted_issues = 0
        for issue_type, weight in issue_weights.items():
            issue_count = validation_results.get(issue_type, 0)
            total_weighted_issues += issue_count * weight
        
        # Calculate score (0-100)
        quality_score = max(0, 100 * (1 - total_weighted_issues / (total_securities * 10)))
        
        return round(quality_score, 2)
    
    async def _log_validation_issue(self, validation_date: date, symbol: str, 
                                  validation_type: str, issue_description: str,
                                  old_value: float = None, new_value: float = None):
        """Log a validation issue"""
        async with self.db_manager.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO market_data.validation_log
                (validation_date, symbol, validation_type, status, issue_description, 
                 old_value, new_value, confidence_score)
                VALUES ($1, $2, $3, 'FAILED', $4, $5, $6, $7)
            """, validation_date, symbol, validation_type, issue_description,
            old_value, new_value, 85.0)  # Default confidence
    
    async def get_validation_summary(self, validation_date: date) -> Dict[str, Any]:
        """Get validation summary for a specific date"""
        async with self.db_manager.pool.acquire() as conn:
            # Get validation issues by type
            issues_by_type = await conn.fetch("""
                SELECT validation_type, status, COUNT(*) as count
                FROM market_data.validation_log
                WHERE validation_date = $1
                GROUP BY validation_type, status
                ORDER BY validation_type, status
            """)
            
            # Get recent outliers
            recent_outliers = await conn.fetch("""
                SELECT symbol, price_type, outlier_price, z_score
                FROM market_data.price_outliers
                WHERE detection_date = $1
                ORDER BY ABS(z_score) DESC
                LIMIT 10
            """)
            
            # Get feed status
            feed_status = await conn.fetch("""
                SELECT feed_name, status, error_count, last_update_time
                FROM market_data.feed_status
                ORDER BY feed_name
            """)
            
            return {
                "validation_date": str(validation_date),
                "issues_by_type": [dict(row) for row in issues_by_type],
                "top_outliers": [dict(row) for row in recent_outliers],
                "feed_status": [dict(row) for row in feed_status]
            }
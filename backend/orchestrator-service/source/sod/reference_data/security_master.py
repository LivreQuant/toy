# source/sod/reference_data/security_master.py
import logging
from typing import Dict, List, Any, Optional, Set
from datetime import date, datetime
import asyncio
from decimal import Decimal

logger = logging.getLogger(__name__)

class SecurityMasterManager:
    """Manages security reference data and master database"""
    
    def __init__(self, db_manager):
        self.db_manager = db_manager
        
    async def initialize(self):
        """Initialize security master manager"""
        await self._create_security_tables()
        logger.info("📊 Security Master Manager initialized")
    
    async def _create_security_tables(self):
        """Create security master tables"""
        async with self.db_manager.pool.acquire() as conn:
            await conn.execute("""
                CREATE SCHEMA IF NOT EXISTS reference_data
            """)
            
            # Main securities table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS reference_data.securities (
                    security_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    symbol VARCHAR(20) NOT NULL,
                    cusip VARCHAR(9),
                    isin VARCHAR(12),
                    sedol VARCHAR(7),
                    security_name VARCHAR(200) NOT NULL,
                    security_type VARCHAR(50) NOT NULL,
                    sector VARCHAR(50),
                    industry VARCHAR(100),
                    exchange VARCHAR(20),
                    country VARCHAR(3),
                    currency VARCHAR(3) DEFAULT 'USD',
                    market_cap BIGINT,
                    shares_outstanding BIGINT,
                    avg_volume_30d BIGINT,
                    bid_price DECIMAL(20,8),
                    ask_price DECIMAL(20,8),
                    last_price DECIMAL(20,8),
                    price_date DATE,
                    is_active BOOLEAN DEFAULT TRUE,
                    listing_date DATE,
                    delisting_date DATE,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    UNIQUE(symbol, exchange)
                )
            """)
            
            # Indices for fast lookups
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_securities_symbol 
                ON reference_data.securities (symbol)
            """)
            
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_securities_cusip 
                ON reference_data.securities (cusip) WHERE cusip IS NOT NULL
            """)
            
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_securities_isin 
                ON reference_data.securities (isin) WHERE isin IS NOT NULL
            """)
            
            # Security attributes table (for flexible metadata)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS reference_data.security_attributes (
                    security_id UUID REFERENCES reference_data.securities(security_id),
                    attribute_name VARCHAR(100) NOT NULL,
                    attribute_value TEXT,
                    effective_date DATE NOT NULL,
                    expiry_date DATE,
                    data_source VARCHAR(50),
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    PRIMARY KEY (security_id, attribute_name, effective_date)
                )
            """)
            
            # Data quality tracking
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS reference_data.data_quality_log (
                    log_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    check_date DATE NOT NULL,
                    check_type VARCHAR(50) NOT NULL,
                    total_records INTEGER,
                    passed_records INTEGER,
                    failed_records INTEGER,
                    quality_score DECIMAL(5,2),
                    issues JSONB,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                )
            """)
    
    async def update_security_master(self, update_date: date) -> Dict[str, Any]:
        """Update security master data from various sources"""
        logger.info(f"📊 Updating security master for {update_date}")
        
        try:
            results = {
                "securities_processed": 0,
                "securities_added": 0,
                "securities_updated": 0,
                "securities_deactivated": 0,
                "data_quality_issues": 0
            }
            
            # Step 1: Load data from external sources (simulated)
            external_data = await self._fetch_external_security_data(update_date)
            logger.info(f"Fetched {len(external_data)} securities from external sources")
            
            # Step 2: Process each security
            for security_data in external_data:
                try:
                    action_taken = await self._process_security_record(security_data, update_date)
                    results["securities_processed"] += 1
                    
                    if action_taken == "ADDED":
                        results["securities_added"] += 1
                    elif action_taken == "UPDATED":
                        results["securities_updated"] += 1
                    elif action_taken == "DEACTIVATED":
                        results["securities_deactivated"] += 1
                        
                except Exception as e:
                    logger.error(f"Error processing security {security_data.get('symbol', 'UNKNOWN')}: {e}")
                    results["data_quality_issues"] += 1
            
            # Step 3: Run data quality checks
            quality_results = await self._run_data_quality_checks(update_date)
            results.update(quality_results)
            
            # Step 4: Update derived fields
            await self._update_derived_fields(update_date)
            
            logger.info(f"✅ Security master update complete: {results}")
            return results
            
        except Exception as e:
            logger.error(f"❌ Failed to update security master: {e}", exc_info=True)
            raise
    
    async def _fetch_external_security_data(self, update_date: date) -> List[Dict[str, Any]]:
        """Simulate fetching data from external vendors"""
        # In practice, this would connect to Bloomberg, Refinitiv, etc.
        # For now, we'll generate sample data
        
        import random
        import string
        
        sample_data = []
        sectors = ['TECH', 'FINANCIALS', 'HEALTHCARE', 'ENERGY', 'CONSUMER', 'INDUSTRIALS', 'MATERIALS', 'UTILITIES', 'REITS', 'TELECOM']
        exchanges = ['NYSE', 'NASDAQ', 'AMEX']
        
        # Generate sample securities
        for i in range(2500):  # Simulate 2500 securities
            symbol = ''.join(random.choices(string.ascii_uppercase, k=random.randint(2, 5)))
            
            # Make some realistic symbols
            if i < 100:
                common_symbols = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA', 'META', 'NFLX', 'NVDA', 'CRM', 'ORCL',
                                'IBM', 'INTC', 'CSCO', 'ADBE', 'PYPL', 'UBER', 'LYFT', 'SPOT', 'SQ', 'ZM']
                if i < len(common_symbols):
                    symbol = common_symbols[i]
            
            market_cap = random.randint(100_000_000, 2_000_000_000_000)  # $100M to $2T
            shares_outstanding = random.randint(10_000_000, 10_000_000_000)
            last_price = market_cap / shares_outstanding
            
            security_data = {
                'symbol': symbol,
                'cusip': ''.join(random.choices(string.ascii_uppercase + string.digits, k=9)),
                'isin': 'US' + ''.join(random.choices(string.ascii_uppercase + string.digits, k=10)),
                'security_name': f"{symbol} Corporation",
                'security_type': 'COMMON_STOCK',
                'sector': random.choice(sectors),
                'industry': f"{random.choice(['Software', 'Hardware', 'Services', 'Manufacturing', 'Retail'])}",
                'exchange': random.choice(exchanges),
                'country': 'USA',
                'currency': 'USD',
                'market_cap': market_cap,
                'shares_outstanding': shares_outstanding,
                'avg_volume_30d': random.randint(100_000, 50_000_000),
                'last_price': round(last_price, 2),
                'bid_price': round(last_price * 0.999, 2),
                'ask_price': round(last_price * 1.001, 2),
                'is_active': random.choice([True] * 95 + [False] * 5),  # 95% active
                'listing_date': update_date,
                'data_source': random.choice(['BLOOMBERG', 'REFINITIV', 'FACTSET'])
            }
            
            sample_data.append(security_data)
        
        # Simulate some data quality issues
        for _ in range(50):  # 50 records with issues
            idx = random.randint(0, len(sample_data) - 1)
            issue_type = random.choice(['missing_cusip', 'invalid_price', 'missing_sector'])
            
            if issue_type == 'missing_cusip':
                sample_data[idx]['cusip'] = None
            elif issue_type == 'invalid_price':
                sample_data[idx]['last_price'] = -1  # Invalid price
            elif issue_type == 'missing_sector':
                sample_data[idx]['sector'] = None
        
        return sample_data
    
    async def _process_security_record(self, security_data: Dict[str, Any], update_date: date) -> str:
        """Process a single security record"""
        async with self.db_manager.pool.acquire() as conn:
            symbol = security_data['symbol']
            exchange = security_data.get('exchange', 'UNKNOWN')
            
            # Check if security already exists
            existing = await conn.fetchrow("""
                SELECT security_id, updated_at FROM reference_data.securities
                WHERE symbol = $1 AND exchange = $2
            """, symbol, exchange)
            
            if existing:
                # Update existing security
                await conn.execute("""
                    UPDATE reference_data.securities 
                    SET security_name = $3,
                        security_type = $4,
                        sector = $5,
                        industry = $6,
                        country = $7,
                        currency = $8,
                        market_cap = $9,
                        shares_outstanding = $10,
                        avg_volume_30d = $11,
                        bid_price = $12,
                        ask_price = $13,
                        last_price = $14,
                        price_date = $15,
                        is_active = $16,
                        updated_at = NOW()
                    WHERE symbol = $1 AND exchange = $2
                """, 
                symbol, exchange,
                security_data.get('security_name'),
                security_data.get('security_type'),
                security_data.get('sector'),
                security_data.get('industry'),
                security_data.get('country'),
                security_data.get('currency'),
                security_data.get('market_cap'),
                security_data.get('shares_outstanding'),
                security_data.get('avg_volume_30d'),
                security_data.get('bid_price'),
                security_data.get('ask_price'),
                security_data.get('last_price'),
                update_date,
                security_data.get('is_active', True)
                )
                
                return "UPDATED"
            else:
                # Insert new security
                await conn.execute("""
                    INSERT INTO reference_data.securities
                    (symbol, cusip, isin, security_name, security_type, sector, industry,
                     exchange, country, currency, market_cap, shares_outstanding, avg_volume_30d,
                     bid_price, ask_price, last_price, price_date, is_active, listing_date)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19)
                """,
                symbol,
                security_data.get('cusip'),
                security_data.get('isin'),
                security_data.get('security_name'),
                security_data.get('security_type'),
                security_data.get('sector'),
                security_data.get('industry'),
                exchange,
                security_data.get('country'),
                security_data.get('currency'),
                security_data.get('market_cap'),
                security_data.get('shares_outstanding'),
                security_data.get('avg_volume_30d'),
                security_data.get('bid_price'),
                security_data.get('ask_price'),
                security_data.get('last_price'),
                update_date,
                security_data.get('is_active', True),
                security_data.get('listing_date', update_date)
                )
                
                return "ADDED"
    
    async def _run_data_quality_checks(self, check_date: date) -> Dict[str, Any]:
        """Run data quality checks on security master"""
        logger.info("🔍 Running data quality checks")
        
        async with self.db_manager.pool.acquire() as conn:
            quality_issues = []
            
            # Check 1: Missing CUSIPs
            missing_cusips = await conn.fetchrow("""
                SELECT COUNT(*) as count FROM reference_data.securities
                WHERE cusip IS NULL AND is_active = TRUE
            """)
            if missing_cusips['count'] > 0:
                quality_issues.append({
                    'issue_type': 'missing_cusip',
                    'count': missing_cusips['count'],
                    'severity': 'MEDIUM'
                })
            
            # Continuing reference_data/security_master.py

           # Check 2: Invalid prices
           invalid_prices = await conn.fetchrow("""
               SELECT COUNT(*) as count FROM reference_data.securities
               WHERE (last_price IS NULL OR last_price <= 0) AND is_active = TRUE
           """)
           if invalid_prices['count'] > 0:
               quality_issues.append({
                   'issue_type': 'invalid_price',
                   'count': invalid_prices['count'],
                   'severity': 'HIGH'
               })
           
           # Check 3: Missing sectors
           missing_sectors = await conn.fetchrow("""
               SELECT COUNT(*) as count FROM reference_data.securities
               WHERE sector IS NULL AND is_active = TRUE
           """)
           if missing_sectors['count'] > 0:
               quality_issues.append({
                   'issue_type': 'missing_sector',
                   'count': missing_sectors['count'],
                   'severity': 'LOW'
               })
           
           # Check 4: Duplicate symbols (same exchange)
           duplicate_symbols = await conn.fetch("""
               SELECT symbol, exchange, COUNT(*) as count
               FROM reference_data.securities
               WHERE is_active = TRUE
               GROUP BY symbol, exchange
               HAVING COUNT(*) > 1
           """)
           if duplicate_symbols:
               quality_issues.append({
                   'issue_type': 'duplicate_symbols',
                   'count': len(duplicate_symbols),
                   'severity': 'HIGH',
                   'details': [dict(row) for row in duplicate_symbols]
               })
           
           # Check 5: Stale prices (older than 5 days)
           from datetime import timedelta
           stale_cutoff = check_date - timedelta(days=5)
           stale_prices = await conn.fetchrow("""
               SELECT COUNT(*) as count FROM reference_data.securities
               WHERE (price_date IS NULL OR price_date < $1) AND is_active = TRUE
           """, stale_cutoff)
           if stale_prices['count'] > 0:
               quality_issues.append({
                   'issue_type': 'stale_prices',
                   'count': stale_prices['count'],
                   'severity': 'MEDIUM'
               })
           
           # Calculate overall quality score
           total_securities = await conn.fetchrow("""
               SELECT COUNT(*) as count FROM reference_data.securities WHERE is_active = TRUE
           """)
           
           total_issues = sum(issue['count'] for issue in quality_issues)
           quality_score = max(0, (1 - total_issues / max(total_securities['count'], 1)) * 100)
           
           # Log quality results
           await conn.execute("""
               INSERT INTO reference_data.data_quality_log
               (check_date, check_type, total_records, passed_records, failed_records, quality_score, issues)
               VALUES ($1, $2, $3, $4, $5, $6, $7)
           """, 
           check_date, 'SECURITY_MASTER_CHECK',
           total_securities['count'],
           total_securities['count'] - total_issues,
           total_issues,
           quality_score,
           quality_issues
           )
           
           logger.info(f"📊 Data quality score: {quality_score:.2f}% ({total_issues} issues found)")
           
           return {
               'quality_score': quality_score,
               'total_issues': total_issues,
               'quality_issues': quality_issues
           }
   
   async def _update_derived_fields(self, update_date: date):
       """Update calculated/derived fields"""
       logger.info("🔄 Updating derived fields")
       
       async with self.db_manager.pool.acquire() as conn:
           # Update market cap based on price and shares outstanding
           await conn.execute("""
               UPDATE reference_data.securities
               SET market_cap = CASE 
                   WHEN last_price > 0 AND shares_outstanding > 0 
                   THEN last_price * shares_outstanding
                   ELSE market_cap
               END
               WHERE is_active = TRUE
           """)
           
           # Calculate average volume over different periods (if we had historical data)
           # This is simplified - in practice you'd calculate from actual trade data
           await conn.execute("""
               UPDATE reference_data.securities
               SET avg_volume_30d = CASE 
                   WHEN avg_volume_30d IS NULL OR avg_volume_30d = 0
                   THEN GREATEST(100000, market_cap / 100000)  -- Rough estimate
                   ELSE avg_volume_30d
               END
               WHERE is_active = TRUE
           """)
   
   async def get_security_by_symbol(self, symbol: str, exchange: str = None) -> Dict[str, Any]:
       """Get security information by symbol"""
       async with self.db_manager.pool.acquire() as conn:
           if exchange:
               result = await conn.fetchrow("""
                   SELECT * FROM reference_data.securities
                   WHERE symbol = $1 AND exchange = $2 AND is_active = TRUE
               """, symbol, exchange)
           else:
               result = await conn.fetchrow("""
                   SELECT * FROM reference_data.securities
                   WHERE symbol = $1 AND is_active = TRUE
                   ORDER BY market_cap DESC NULLS LAST
                   LIMIT 1
               """, symbol)
           
           return dict(result) if result else None
   
   async def get_securities_by_sector(self, sector: str, limit: int = None) -> List[Dict[str, Any]]:
       """Get securities by sector"""
       async with self.db_manager.pool.acquire() as conn:
           query = """
               SELECT * FROM reference_data.securities
               WHERE sector = $1 AND is_active = TRUE
               ORDER BY market_cap DESC NULLS LAST
           """
           
           if limit:
               query += f" LIMIT {limit}"
           
           rows = await conn.fetch(query, sector)
           return [dict(row) for row in rows]
   
   async def get_market_statistics(self) -> Dict[str, Any]:
       """Get market-wide statistics"""
       async with self.db_manager.pool.acquire() as conn:
           # Overall statistics
           overall_stats = await conn.fetchrow("""
               SELECT 
                   COUNT(*) as total_securities,
                   COUNT(CASE WHEN is_active THEN 1 END) as active_securities,
                   SUM(CASE WHEN is_active THEN market_cap ELSE 0 END) as total_market_cap,
                   AVG(CASE WHEN is_active AND last_price > 0 THEN last_price END) as avg_price,
                   SUM(CASE WHEN is_active THEN avg_volume_30d ELSE 0 END) as total_volume
               FROM reference_data.securities
           """)
           
           # By sector breakdown
           sector_stats = await conn.fetch("""
               SELECT 
                   sector,
                   COUNT(*) as count,
                   SUM(market_cap) as sector_market_cap,
                   AVG(last_price) as avg_price
               FROM reference_data.securities
               WHERE is_active = TRUE AND sector IS NOT NULL
               GROUP BY sector
               ORDER BY sector_market_cap DESC NULLS LAST
           """)
           
           # By exchange breakdown
           exchange_stats = await conn.fetch("""
               SELECT 
                   exchange,
                   COUNT(*) as count,
                   SUM(market_cap) as exchange_market_cap
               FROM reference_data.securities
               WHERE is_active = TRUE
               GROUP BY exchange
               ORDER BY exchange_market_cap DESC NULLS LAST
           """)
           
           return {
               'overall': dict(overall_stats),
               'by_sector': [dict(row) for row in sector_stats],
               'by_exchange': [dict(row) for row in exchange_stats]
           }
   
   async def validate_security_identifiers(self, identifiers: List[str], 
                                         identifier_type: str = 'symbol') -> Dict[str, Any]:
       """Validate a list of security identifiers"""
       valid_identifiers = []
       invalid_identifiers = []
       
       async with self.db_manager.pool.acquire() as conn:
           for identifier in identifiers:
               if identifier_type == 'symbol':
                   result = await conn.fetchrow("""
                       SELECT symbol FROM reference_data.securities
                       WHERE symbol = $1 AND is_active = TRUE
                       LIMIT 1
                   """, identifier)
               elif identifier_type == 'cusip':
                   result = await conn.fetchrow("""
                       SELECT symbol FROM reference_data.securities
                       WHERE cusip = $1 AND is_active = TRUE
                       LIMIT 1
                   """, identifier)
               elif identifier_type == 'isin':
                   result = await conn.fetchrow("""
                       SELECT symbol FROM reference_data.securities
                       WHERE isin = $1 AND is_active = TRUE
                       LIMIT 1
                   """, identifier)
               else:
                   result = None
               
               if result:
                   valid_identifiers.append(identifier)
               else:
                   invalid_identifiers.append(identifier)
       
       return {
           'total_checked': len(identifiers),
           'valid_count': len(valid_identifiers),
           'invalid_count': len(invalid_identifiers),
           'valid_identifiers': valid_identifiers,
           'invalid_identifiers': invalid_identifiers,
           'validation_rate': len(valid_identifiers) / len(identifiers) * 100 if identifiers else 0
       }
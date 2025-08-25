# source/sod/universe/universe_builder.py
import logging
from typing import Dict, List, Any, Set
from datetime import datetime, date
import asyncio

logger = logging.getLogger(__name__)

class UniverseBuilder:
    """Builds and manages the trading universe"""
    
    def __init__(self, db_manager):
        self.db_manager = db_manager
        
        # Universe criteria (configurable)
        self.min_market_cap = 100_000_000  # $100M
        self.min_avg_volume = 100_000      # 100K shares daily
        self.max_spread_bps = 50          # 50 basis points
        self.excluded_sectors = {'REIT', 'UTIL'}  # Example exclusions
        
    async def initialize(self):
        """Initialize universe builder"""
        await self._create_universe_tables()
        logger.info("🌐 Universe Builder initialized")
    
    async def _create_universe_tables(self):
        """Create universe-related tables"""
        async with self.db_manager.pool.acquire() as conn:
            await conn.execute("""
                CREATE SCHEMA IF NOT EXISTS universe
            """)
            
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS universe.trading_universe (
                    universe_date DATE NOT NULL,
                    symbol VARCHAR(20) NOT NULL,
                    security_id VARCHAR(50) NOT NULL,
                    security_name VARCHAR(200),
                    sector VARCHAR(50),
                    market_cap BIGINT,
                    avg_volume_30d BIGINT,
                    avg_spread_bps DECIMAL(8,2),
                    is_tradeable BOOLEAN DEFAULT TRUE,
                    inclusion_reason TEXT,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    PRIMARY KEY (universe_date, symbol)
                )
            """)
            
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS universe.universe_stats (
                    universe_date DATE PRIMARY KEY,
                    total_securities INTEGER,
                    tradeable_securities INTEGER,
                    total_market_cap BIGINT,
                    sectors_included INTEGER,
                    criteria_applied JSONB,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                )
            """)
    
    async def build_daily_universe(self, target_date: date) -> Dict[str, Any]:
        """Build trading universe for the target date"""
        logger.info(f"🌐 Building trading universe for {target_date}")
        
        try:
            # Step 1: Get all eligible securities
            eligible_securities = await self._get_eligible_securities(target_date)
            logger.info(f"📊 Found {len(eligible_securities)} eligible securities")
            
            # Step 2: Apply filters
            filtered_securities = await self._apply_universe_filters(eligible_securities)
            logger.info(f"✅ {len(filtered_securities)} securities passed filters")
            
            # Step 3: Save universe to database
            await self._save_universe(target_date, filtered_securities)
            
            # Step 4: Generate universe statistics
            stats = await self._generate_universe_stats(target_date, filtered_securities)
            await self._save_universe_stats(target_date, stats)
            
            logger.info(f"🎉 Universe built successfully: {stats['tradeable_securities']} securities")
            
            return {
                "total_securities": len(eligible_securities),
                "tradeable_securities": len(filtered_securities),
                "universe_stats": stats
            }
            
        except Exception as e:
            logger.error(f"❌ Failed to build universe: {e}", exc_info=True)
            raise
    
    async def _get_eligible_securities(self, target_date: date) -> List[Dict[str, Any]]:
        """Get all potentially eligible securities"""
        async with self.db_manager.pool.acquire() as conn:
            # This would query your actual security master table
            rows = await conn.fetch("""
                SELECT 
                    symbol,
                    security_id,
                    security_name,
                    sector,
                    market_cap,
                    avg_volume_30d,
                    CASE 
                        WHEN bid_price > 0 AND ask_price > 0 
                        THEN ((ask_price - bid_price) / ((ask_price + bid_price) / 2)) * 10000
                        ELSE 999
                    END as spread_bps,
                    is_active,
                    listing_date,
                    delisting_date
                FROM reference_data.securities
                WHERE is_active = TRUE
                  AND (delisting_date IS NULL OR delisting_date > $1)
                  AND listing_date <= $1
                ORDER BY market_cap DESC NULLS LAST
            """, target_date)
            
            return [dict(row) for row in rows]
    
    async def _apply_universe_filters(self, securities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Apply universe selection criteria"""
        filtered = []
        
        for security in securities:
            reasons = []
            include = True
            
            # Market cap filter
            if not security.get('market_cap') or security['market_cap'] < self.min_market_cap:
                include = False
                reasons.append(f"market_cap_below_{self.min_market_cap}")
            
            # Volume filter
            if not security.get('avg_volume_30d') or security['avg_volume_30d'] < self.min_avg_volume:
                include = False
                reasons.append(f"volume_below_{self.min_avg_volume}")
            
            # Spread filter
            if security.get('spread_bps', 999) > self.max_spread_bps:
                include = False
                reasons.append(f"spread_above_{self.max_spread_bps}_bps")
            
            # Sector exclusions
            if security.get('sector') in self.excluded_sectors:
                include = False
                reasons.append(f"excluded_sector_{security.get('sector')}")
            
            if include:
                security['inclusion_reason'] = "passed_all_filters"
                filtered.append(security)
            else:
                logger.debug(f"Excluded {security['symbol']}: {', '.join(reasons)}")
        
        return filtered
    
    async def _save_universe(self, universe_date: date, securities: List[Dict[str, Any]]):
        """Save universe to database"""
        async with self.db_manager.pool.acquire() as conn:
            # Delete existing universe for this date
            await conn.execute("""
                DELETE FROM universe.trading_universe WHERE universe_date = $1
            """, universe_date)
            
            # Insert new universe
            if securities:
                values = []
                for sec in securities:
                    values.append((
                        universe_date,
                        sec['symbol'],
                        sec['security_id'],
                        sec.get('security_name'),
                        sec.get('sector'),
                        sec.get('market_cap'),
                        sec.get('avg_volume_30d'),
                        sec.get('spread_bps'),
                        True,  # is_tradeable
                        sec.get('inclusion_reason')
                    ))
                
                await conn.executemany("""
                    INSERT INTO universe.trading_universe 
                    (universe_date, symbol, security_id, security_name, sector, 
                     market_cap, avg_volume_30d, avg_spread_bps, is_tradeable, inclusion_reason)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                """, values)
    
    async def _generate_universe_stats(self, universe_date: date, securities: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate universe statistics"""
        if not securities:
            return {
                "total_securities": 0,
                "tradeable_securities": 0,
                "total_market_cap": 0,
                "sectors_included": 0,
                "avg_market_cap": 0,
                "avg_volume": 0,
                "criteria_applied": {
                    "min_market_cap": self.min_market_cap,
                    "min_avg_volume": self.min_avg_volume,
                    "max_spread_bps": self.max_spread_bps,
                    "excluded_sectors": list(self.excluded_sectors)
                }
            }
        
        sectors = set(sec.get('sector') for sec in securities if sec.get('sector'))
        total_market_cap = sum(sec.get('market_cap', 0) for sec in securities)
        total_volume = sum(sec.get('avg_volume_30d', 0) for sec in securities)
        
        return {
            "total_securities": len(securities),
            "tradeable_securities": len([s for s in securities if s.get('is_tradeable', True)]),
            "total_market_cap": total_market_cap,
            "sectors_included": len(sectors),
            "avg_market_cap": total_market_cap // len(securities) if securities else 0,
            "avg_volume": total_volume // len(securities) if securities else 0,
            "sector_breakdown": dict(Counter(sec.get('sector') for sec in securities)),
            "criteria_applied": {
                "min_market_cap": self.min_market_cap,
                "min_avg_volume": self.min_avg_volume,
                "max_spread_bps": self.max_spread_bps,
                "excluded_sectors": list(self.excluded_sectors)
            }
        }
    
    async def _save_universe_stats(self, universe_date: date, stats: Dict[str, Any]):
        """Save universe statistics"""
        async with self.db_manager.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO universe.universe_stats 
                (universe_date, total_securities, tradeable_securities, total_market_cap,
                 sectors_included, criteria_applied)
                VALUES ($1, $2, $3, $4, $5, $6)
                ON CONFLICT (universe_date) 
                DO UPDATE SET
                    total_securities = $2,
                    tradeable_securities = $3,
                    total_market_cap = $4,
                    sectors_included = $5,
                    criteria_applied = $6,
                    created_at = NOW()
            """, 
            universe_date, 
            stats['total_securities'],
            stats['tradeable_securities'], 
            stats['total_market_cap'],
            stats['sectors_included'],
            json.dumps(stats['criteria_applied'])
            )
    
    async def get_universe_for_date(self, universe_date: date) -> List[Dict[str, Any]]:
        """Get trading universe for a specific date"""
        async with self.db_manager.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT * FROM universe.trading_universe 
                WHERE universe_date = $1 AND is_tradeable = TRUE
                ORDER BY market_cap DESC
            """, universe_date)
            
            return [dict(row) for row in rows]
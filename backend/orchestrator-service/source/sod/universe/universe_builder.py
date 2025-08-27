# source/sod/universe/universe_builder.py
import logging
from typing import Dict, List, Any, Set
from datetime import datetime, date
from collections import Counter

logger = logging.getLogger(__name__)

class UniverseBuilder:
    """Builds and manages the trading universe - NO DATABASE ACCESS"""
    
    def __init__(self, db_manager):
        self.db_manager = db_manager
        
        # Universe criteria (configurable)
        self.min_market_cap = 100_000_000  # $100M
        self.min_avg_volume = 100_000      # 100K shares daily
        self.max_spread_bps = 50          # 50 basis points
        self.excluded_sectors = {'REIT', 'UTIL'}  # Example exclusions
        
    async def initialize(self):
        """Initialize universe builder"""
        # Initialize tables through database manager ONLY
        if hasattr(self.db_manager, 'universe'):
            await self.db_manager.universe.initialize_tables()
        
        logger.info("🌐 Universe Builder initialized")
    
    async def build_universe(self, target_date: date = None) -> Dict[str, Any]:
        """Build trading universe for the target date"""
        if target_date is None:
            target_date = date.today()
            
        logger.info(f"🌐 Building trading universe for {target_date}")
        
        try:
            # Step 1: Get eligible securities through database manager ONLY
            eligible_securities = await self.db_manager.universe.get_eligible_securities(target_date)
            logger.info(f"📊 Found {len(eligible_securities)} eligible securities")
            
            # Step 2: Apply filters (pure business logic)
            filtered_securities = await self._apply_universe_filters(eligible_securities)
            logger.info(f"✅ {len(filtered_securities)} securities passed filters")
            
            # Step 3: Save universe through database manager ONLY
            await self.db_manager.universe.save_universe_data(target_date, filtered_securities)
            
            # Step 4: Generate statistics (pure business logic)
            stats = self._generate_universe_stats(filtered_securities)
            
            # Step 5: Save statistics through database manager ONLY
            await self.db_manager.universe.save_universe_stats(target_date, stats)
            
            logger.info(f"🎉 Universe built successfully: {stats['tradeable_securities']} securities")
            
            return {
                "universe_date": target_date.isoformat(),
                "total_securities": len(eligible_securities),
                "tradeable_securities": len(filtered_securities),
                "universe_stats": stats
            }
            
        except Exception as e:
            logger.error(f"❌ Failed to build universe: {e}", exc_info=True)
            raise
    
    async def _apply_universe_filters(self, eligible_securities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Apply universe filters - pure business logic"""
        filtered_securities = []
        
        for security in eligible_securities:
            # Apply market cap filter
            market_cap = security.get('market_cap', 0)
            if market_cap and market_cap < self.min_market_cap:
                security['exclusion_reason'] = f"Market cap ${market_cap:,} below minimum ${self.min_market_cap:,}"
                security['is_tradeable'] = False
                continue
            
            # Apply volume filter
            avg_volume = security.get('avg_volume_30d', 0)
            if avg_volume and avg_volume < self.min_avg_volume:
                security['exclusion_reason'] = f"Volume {avg_volume:,} below minimum {self.min_avg_volume:,}"
                security['is_tradeable'] = False
                continue
            
            # Apply spread filter
            spread_bps = security.get('spread_bps', 0)
            if spread_bps and spread_bps > self.max_spread_bps:
                security['exclusion_reason'] = f"Spread {spread_bps:.1f}bps above maximum {self.max_spread_bps}bps"
                security['is_tradeable'] = False
                continue
            
            # Apply sector filter
            sector = security.get('sector')
            if sector and sector in self.excluded_sectors:
                security['exclusion_reason'] = f"Sector {sector} excluded"
                security['is_tradeable'] = False
                continue
            
            # Security passed all filters
            security['is_tradeable'] = True
            security['inclusion_reason'] = "Passed all universe filters"
            filtered_securities.append(security)
        
        return filtered_securities
    
    def _generate_universe_stats(self, securities: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate universe statistics - pure business logic"""
        if not securities:
            return {
                "total_securities": 0,
                "tradeable_securities": 0,
                "total_market_cap": 0,
                "sectors_included": 0,
                "avg_market_cap": 0,
                "avg_volume": 0,
                "sector_breakdown": {},
                "criteria_applied": self._get_criteria_dict()
            }
        
        sectors = set(sec.get('sector') for sec in securities if sec.get('sector'))
        total_market_cap = sum(sec.get('market_cap', 0) for sec in securities)
        total_volume = sum(sec.get('avg_volume_30d', 0) for sec in securities)
        
        # Count tradeable securities
        tradeable_securities = len([s for s in securities if s.get('is_tradeable', True)])
        
        # Sector breakdown
        sector_counts = Counter(sec.get('sector') for sec in securities if sec.get('sector'))
        
        return {
            "total_securities": len(securities),
            "tradeable_securities": tradeable_securities,
            "total_market_cap": total_market_cap,
            "sectors_included": len(sectors),
            "avg_market_cap": total_market_cap // len(securities) if securities else 0,
            "avg_volume": total_volume // len(securities) if securities else 0,
            "sector_breakdown": dict(sector_counts),
            "criteria_applied": self._get_criteria_dict()
        }
    
    def _get_criteria_dict(self) -> Dict[str, Any]:
        """Get criteria dictionary for logging"""
        return {
            "min_market_cap": self.min_market_cap,
            "min_avg_volume": self.min_avg_volume,
            "max_spread_bps": self.max_spread_bps,
            "excluded_sectors": list(self.excluded_sectors)
        }
    
    # =================================================================
    # UTILITY METHODS - ALL THROUGH DATABASE MANAGER
    # =================================================================
    
    async def get_universe_for_date(self, universe_date: date) -> List[Dict[str, Any]]:
        """Get universe through database manager ONLY"""
        return await self.db_manager.universe.get_universe_for_date(universe_date)
    
    async def get_universe_stats(self, universe_date: date) -> Optional[Dict[str, Any]]:
        """Get stats through database manager ONLY"""
        return await self.db_manager.universe.get_universe_stats(universe_date)
    
    async def get_sectors_breakdown(self, universe_date: date) -> List[Dict[str, Any]]:
        """Get sector breakdown through database manager ONLY"""
        return await self.db_manager.universe.get_sectors_for_date(universe_date)
    
    def update_criteria(self, min_market_cap: int = None, min_avg_volume: int = None,
                       max_spread_bps: float = None, excluded_sectors: Set[str] = None):
        """Update universe criteria"""
        if min_market_cap is not None:
            self.min_market_cap = min_market_cap
        if min_avg_volume is not None:
            self.min_avg_volume = min_avg_volume
        if max_spread_bps is not None:
            self.max_spread_bps = max_spread_bps
        if excluded_sectors is not None:
            self.excluded_sectors = excluded_sectors
        
        logger.info(f"🔧 Universe criteria updated: {self._get_criteria_dict()}")
    
    async def get_universe_history(self, symbol: str, days_back: int = 30) -> List[Dict[str, Any]]:
        """Get universe history through database manager ONLY"""
        end_date = date.today()
        start_date = end_date - timedelta(days=days_back)
        
        return await self.db_manager.universe.get_universe_history(symbol, start_date, end_date)
    
    async def validate_universe(self, universe_date: date) -> Dict[str, Any]:
        """Validate universe data"""
        try:
            universe_data = await self.db_manager.universe.get_universe_for_date(universe_date)
            stats = await self.db_manager.universe.get_universe_stats(universe_date)
            
            validation = {
                "universe_date": universe_date.isoformat(),
                "validation_status": "PASSED",
                "issues": []
            }
            
            # Validate data consistency
            if stats:
                actual_count = len(universe_data)
                expected_count = stats['total_securities']
                
                if actual_count != expected_count:
                    validation["issues"].append({
                        "type": "COUNT_MISMATCH",
                        "actual": actual_count,
                        "expected": expected_count
                    })
                    validation["validation_status"] = "FAILED"
            
            # Validate business rules
            for security in universe_data:
                if security.get('is_tradeable'):
                    market_cap = security.get('market_cap', 0)
                    if market_cap and market_cap < self.min_market_cap:
                        validation["issues"].append({
                            "type": "CRITERIA_VIOLATION",
                            "symbol": security['symbol'],
                            "issue": f"Market cap ${market_cap:,} below minimum"
                        })
                        validation["validation_status"] = "FAILED"
            
            return validation
            
        except Exception as e:
            return {
                "universe_date": universe_date.isoformat(),
                "validation_status": "ERROR",
                "error": str(e)
            }
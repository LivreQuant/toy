# source/sod/universe/symbology_manager.py
import logging
from typing import Dict, List, Any
from datetime import date

logger = logging.getLogger(__name__)

class SymbologyManager:
    """Manages symbol mappings and cross-references - NO DATABASE ACCESS"""
    
    def __init__(self, db_manager):
        self.db_manager = db_manager
        
        # Primary exchanges for conflict resolution
        self.primary_exchanges = {
            'NYSE', 'NASDAQ', 'NYSE_ARCA', 'NYSE_AMERICAN'
        }
        
    async def initialize(self):
        """Initialize symbology manager"""
        # Initialize tables through database manager ONLY
        if hasattr(self.db_manager, 'universe'):
            await self.db_manager.universe.initialize_tables()
        
        logger.info("🔤 Symbology Manager initialized")
    
    async def update_symbol_mappings(self, mapping_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Update symbol mappings from various data sources"""
        logger.info(f"🔤 Updating symbol mappings for {len(mapping_data)} symbols")
        
        try:
            conflicts_detected = []
            mappings_updated = 0
            mappings_added = 0
            
            for mapping in mapping_data:
                primary_symbol = mapping['primary_symbol']
                symbol_type = mapping['symbol_type']  # CUSIP, ISIN, SEDOL, etc.
                symbol_value = mapping['symbol_value']
                data_vendor = mapping.get('data_vendor', 'INTERNAL')
                effective_date = mapping.get('effective_date', date.today())
                
                # Add mapping through database manager ONLY
                result = await self.db_manager.universe.add_symbol_mapping(
                    primary_symbol, symbol_type, symbol_value, data_vendor, effective_date
                )
                
                if result['conflict']:
                    if result['conflict']:
                    conflicts_detected.append({
                        'symbol_value': symbol_value,
                        'symbol_type': symbol_type,
                        'existing_symbol': result['existing_symbol'],
                        'new_symbol': result['new_symbol']
                    })
                elif result['success']:
                    if result['inserted']:
                        mappings_added += 1
                    else:
                        mappings_updated += 1
            
            logger.info(f"✅ Symbol mappings updated: {mappings_added} added, {mappings_updated} updated, {len(conflicts_detected)} conflicts")
            
            return {
                "mappings_added": mappings_added,
                "mappings_updated": mappings_updated,
                "conflicts_detected": len(conflicts_detected),
                "conflicts": conflicts_detected
            }
            
        except Exception as e:
            logger.error(f"❌ Failed to update symbol mappings: {e}", exc_info=True)
            raise
    
    async def resolve_symbol_conflicts(self) -> Dict[str, Any]:
        """Resolve pending symbol conflicts using business rules"""
        logger.info("🔧 Resolving symbol mapping conflicts")
        
        try:
            # Get conflicts through database manager ONLY
            conflicts = await self.db_manager.universe.get_pending_conflicts()
            
            resolved_count = 0
            for conflict in conflicts:
                resolution = await self._resolve_conflict_logic(
                    conflict['symbol_value'], 
                    conflict['symbol_type'],
                    conflict['conflicting_symbols']
                )
                
                if resolution['resolved_symbol']:
                    # Resolve through database manager ONLY
                    await self.db_manager.universe.resolve_conflict(
                        conflict['conflict_id'],
                        resolution['resolved_symbol'],
                        resolution['resolution_reason']
                    )
                    resolved_count += 1
            
            logger.info(f"✅ Resolved {resolved_count}/{len(conflicts)} conflicts")
            
            return {
                "total_conflicts": len(conflicts),
                "resolved_conflicts": resolved_count,
                "pending_conflicts": len(conflicts) - resolved_count
            }
            
        except Exception as e:
            logger.error(f"❌ Failed to resolve conflicts: {e}", exc_info=True)
            raise
    
    async def _resolve_conflict_logic(self, symbol_value: str, symbol_type: str,
                                    conflicting_symbols: List[str]) -> Dict[str, Any]:
        """Apply business rules to resolve conflicts - pure business logic"""
        
        # Rule 1: Prefer symbols from primary exchanges
        for symbol in conflicting_symbols:
            # Get securities by exchange through database manager ONLY
            securities = await self.db_manager.universe.get_securities_by_exchange('NYSE')
            exchange_symbols = {sec['symbol'] for sec in securities}
            
            if symbol in exchange_symbols:
                return {
                    'resolved_symbol': symbol,
                    'resolution_reason': 'Primary exchange: NYSE'
                }
            
            # Check other primary exchanges
            for exchange in self.primary_exchanges:
                securities = await self.db_manager.universe.get_securities_by_exchange(exchange)
                exchange_symbols = {sec['symbol'] for sec in securities}
                
                if symbol in exchange_symbols:
                    return {
                        'resolved_symbol': symbol,
                        'resolution_reason': f'Primary exchange: {exchange}'
                    }
        
        # Rule 2: Prefer the first symbol alphabetically (fallback)
        resolved_symbol = min(conflicting_symbols)
        
        return {
            'resolved_symbol': resolved_symbol,
            'resolution_reason': 'Alphabetical fallback'
        }
    
    async def get_symbol_mapping(self, symbol_value: str, symbol_type: str) -> str:
        """Get primary symbol through database manager ONLY"""
        return await self.db_manager.universe.get_symbol_mapping(symbol_value, symbol_type)
    
    async def get_all_mappings_for_symbol(self, primary_symbol: str) -> List[Dict[str, Any]]:
        """Get all mappings through database manager ONLY"""
        return await self.db_manager.universe.get_all_mappings_for_symbol(primary_symbol)
    
    async def validate_mappings(self, symbol_list: List[str] = None) -> Dict[str, Any]:
        """Validate symbol mappings"""
        logger.info("🔍 Validating symbol mappings")
        
        validation_results = {
            "validation_status": "PASSED",
            "issues": [],
            "statistics": {
                "symbols_checked": 0,
                "mappings_found": 0,
                "missing_mappings": 0,
                "duplicate_mappings": 0
            }
        }
        
        try:
            symbols_to_check = symbol_list or []
            
            # If no specific symbols provided, get recent universe
            if not symbols_to_check:
                recent_universe = await self.db_manager.universe.get_universe_for_date(date.today())
                symbols_to_check = [u['symbol'] for u in recent_universe[:100]]  # Sample 100 symbols
            
            validation_results["statistics"]["symbols_checked"] = len(symbols_to_check)
            
            for symbol in symbols_to_check:
                # Get mappings through database manager ONLY
                mappings = await self.get_all_mappings_for_symbol(symbol)
                
                if mappings:
                    validation_results["statistics"]["mappings_found"] += 1
                    
                    # Check for required mapping types
                    mapping_types = {m['symbol_type'] for m in mappings}
                    required_types = {'CUSIP', 'ISIN'}
                    
                    missing_types = required_types - mapping_types
                    if missing_types:
                        validation_results["issues"].append({
                            "type": "MISSING_REQUIRED_MAPPINGS",
                            "symbol": symbol,
                            "missing_types": list(missing_types)
                        })
                        validation_results["validation_status"] = "FAILED"
                        
                else:
                    validation_results["statistics"]["missing_mappings"] += 1
                    validation_results["issues"].append({
                        "type": "NO_MAPPINGS_FOUND",
                        "symbol": symbol
                    })
                    validation_results["validation_status"] = "FAILED"
            
            logger.info(f"✅ Mapping validation completed: {validation_results['validation_status']}")
            return validation_results
            
        except Exception as e:
            logger.error(f"❌ Mapping validation failed: {e}", exc_info=True)
            validation_results["validation_status"] = "ERROR"
            validation_results["issues"].append({
                "type": "VALIDATION_ERROR",
                "details": str(e)
            })
            return validation_results
    
    async def cross_reference_symbol(self, input_symbol: str, input_type: str,
                                    target_type: str) -> Optional[str]:
        """Cross-reference symbol from one type to another"""
        try:
            # Step 1: Get primary symbol from input
            primary_symbol = await self.get_symbol_mapping(input_symbol, input_type)
            
            if not primary_symbol:
                logger.warning(f"No primary symbol found for {input_symbol} ({input_type})")
                return None
            
            # Step 2: Get target mapping from primary symbol
            mappings = await self.get_all_mappings_for_symbol(primary_symbol)
            
            for mapping in mappings:
                if mapping['symbol_type'] == target_type:
                    return mapping['symbol_value']
            
            logger.warning(f"No {target_type} mapping found for {primary_symbol}")
            return None
            
        except Exception as e:
            logger.error(f"❌ Cross-reference failed for {input_symbol}: {e}")
            return None
    
    async def bulk_cross_reference(self, symbol_mappings: List[Dict[str, str]]) -> List[Dict[str, Any]]:
        """Bulk cross-reference symbols"""
        results = []
        
        for mapping in symbol_mappings:
            input_symbol = mapping['input_symbol']
            input_type = mapping['input_type']
            target_type = mapping['target_type']
            
            result = {
                "input_symbol": input_symbol,
                "input_type": input_type,
                "target_type": target_type,
                "target_symbol": None,
                "success": False,
                "error": None
            }
            
            try:
                target_symbol = await self.cross_reference_symbol(
                    input_symbol, input_type, target_type
                )
                
                if target_symbol:
                    result["target_symbol"] = target_symbol
                    result["success"] = True
                else:
                    result["error"] = "No mapping found"
                    
            except Exception as e:
                result["error"] = str(e)
            
            results.append(result)
        
        successful = len([r for r in results if r['success']])
        logger.info(f"✅ Bulk cross-reference completed: {successful}/{len(results)} successful")
        
        return results
    
    async def get_mapping_statistics(self) -> Dict[str, Any]:
        """Get mapping statistics through database manager ONLY"""
        try:
            # This would need specific methods in the database manager
            # For now, return basic stats structure
            stats = {
                "total_mappings": 0,
                "mapping_types": {},
                "data_vendors": {},
                "conflicts_pending": 0,
                "conflicts_resolved": 0,
                "last_updated": date.today().isoformat()
            }
            
            # Get conflicts through database manager ONLY
            pending_conflicts = await self.db_manager.universe.get_pending_conflicts()
            stats["conflicts_pending"] = len(pending_conflicts)
            
            return stats
            
        except Exception as e:
            logger.error(f"❌ Failed to get mapping statistics: {e}")
            return {}
    
    def normalize_symbol(self, symbol: str, symbol_type: str) -> str:
        """Normalize symbol format based on type - pure business logic"""
        symbol = symbol.strip().upper()
        
        if symbol_type == 'CUSIP':
            # CUSIP should be 9 characters
            if len(symbol) == 8:
                # Add check digit if missing
                symbol += self._calculate_cusip_check_digit(symbol)
            return symbol[:9]
            
        elif symbol_type == 'ISIN':
            # ISIN should be 12 characters
            return symbol[:12]
            
        elif symbol_type == 'SEDOL':
            # SEDOL should be 7 characters
            return symbol[:7]
            
        elif symbol_type == 'TICKER':
            # Remove any exchange suffixes
            if '.' in symbol:
                symbol = symbol.split('.')[0]
            return symbol
            
        return symbol
    
    def _calculate_cusip_check_digit(self, cusip: str) -> str:
        """Calculate CUSIP check digit - pure business logic"""
        if len(cusip) != 8:
            return '0'
        
        total = 0
        for i, char in enumerate(cusip):
            if char.isdigit():
                value = int(char)
            elif char.isalpha():
                value = ord(char) - ord('A') + 10
            else:
                value = 0
            
            if i % 2 == 1:  # Odd positions (1-indexed)
                value *= 2
            
            total += value
        
        check_digit = (10 - (total % 10)) % 10
        return str(check_digit)
    
    async def export_mappings(self, symbol_type: str = None, 
                            data_vendor: str = None) -> List[Dict[str, Any]]:
        """Export symbol mappings - through database manager ONLY"""
        logger.info(f"📤 Exporting symbol mappings (type: {symbol_type}, vendor: {data_vendor})")
        
        try:
            # This would need a specific export method in the database manager
            # For now, we'll use the general get_all_mappings approach
            all_mappings = []
            
            # Get a sample of symbols to export mappings for
            recent_universe = await self.db_manager.universe.get_universe_for_date(date.today())
            
            for security in recent_universe[:100]:  # Sample 100
                symbol_mappings = await self.get_all_mappings_for_symbol(security['symbol'])
                
                for mapping in symbol_mappings:
                    # Apply filters
                    if symbol_type and mapping['symbol_type'] != symbol_type:
                        continue
                    if data_vendor and mapping.get('data_vendor') != data_vendor:
                        continue
                    
                    all_mappings.append({
                        'primary_symbol': security['symbol'],
                        'symbol_type': mapping['symbol_type'],
                        'symbol_value': mapping['symbol_value'],
                        'data_vendor': mapping.get('data_vendor'),
                        'effective_date': mapping['effective_date']
                    })
            
            logger.info(f"✅ Exported {len(all_mappings)} symbol mappings")
            return all_mappings
            
        except Exception as e:
            logger.error(f"❌ Failed to export mappings: {e}")
            raise


    # =============================================================================
    # UTILITY FUNCTIONS FOR SYMBOLOGY
    # =============================================================================

    def validate_symbol_format(symbol: str, symbol_type: str) -> bool:
    """Validate symbol format - pure business logic"""
    if not symbol or not symbol.strip():
        return False
    
    symbol = symbol.strip().upper()
    
    if symbol_type == 'CUSIP':
        return len(symbol) == 9 and symbol[:8].isalnum()
    elif symbol_type == 'ISIN':
        return len(symbol) == 12 and symbol[:2].isalpha() and symbol[2:].isalnum()
    elif symbol_type == 'SEDOL':
        return len(symbol) == 7 and symbol[:6].isalnum()
    elif symbol_type == 'TICKER':
        return len(symbol) <= 10 and symbol.replace('.', '').isalnum()
    
    return True  # Default to valid for unknown types

    def parse_bloomberg_symbol(bb_symbol: str) -> Dict[str, str]:
    """Parse Bloomberg symbol format - pure business logic"""
    parts = bb_symbol.split(' ')
    
    if len(parts) >= 2:
        ticker = parts[0]
        exchange = parts[1]
        
        return {
            'ticker': ticker,
            'exchange': exchange,
            'full_symbol': bb_symbol
        }
    
    return {
        'ticker': bb_symbol,
        'exchange': None,
        'full_symbol': bb_symbol
    }

    def generate_symbol_key(symbol: str, symbol_type: str, data_vendor: str = None) -> str:
    """Generate unique key for symbol mapping - pure business logic"""
    components = [symbol_type, symbol]
    
    if data_vendor:
        components.append(data_vendor)
    
    return '|'.join(components).upper()
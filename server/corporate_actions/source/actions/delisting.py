import os
import glob
import pandas as pd
import json
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from decimal import Decimal
import logging
from collections import defaultdict
from source.config import config
from source.actions.utils import ConfidenceCalculator, FieldConfidence
from source.actions.symbol_mapper import SymbolMapper

logger = logging.getLogger(__name__)


@dataclass
class SymbolMappingInfo:
    """Information about symbol mapping."""
    master_symbol: str
    source_mappings: Dict[str, str]  # source -> original symbol
    unmapped_sources: List[str]
    mapping_confidence: float


@dataclass
class UnifiedDelisting:
    """Unified delisting representation with master symbol mapping."""

    # Core identifiers
    master_symbol: str  # The unified master symbol (company being delisted)
    source: str
    symbol_mapping: Optional[SymbolMappingInfo] = None

    # Dates
    delisting_date: Optional[str] = None

    # Company information
    delisted_symbol: Optional[str] = None
    company_name: Optional[str] = None

    # Delisting details
    delisting_type: Optional[str] = None  # worthless, regulatory, voluntary, general
    delisting_reason: Optional[str] = None

    # Confidence tracking
    field_confidences: Dict[str, FieldConfidence] = field(default_factory=dict)
    overall_confidence: float = 1.0
    source_agreement_score: float = 1.0
    data_completeness: float = 1.0

    # Raw data
    raw_data: Dict[str, Any] = field(default_factory=dict)
    source_list: List[str] = field(default_factory=list)


@dataclass
class DelistingMatchResult:
    """Result of matching delistings across sources."""
    master_symbol: str
    merged_delisting: UnifiedDelisting
    match_quality: float  # 0.0 to 1.0
    match_details: Dict[str, Any]


class EnhancedDelistingProcessor:
    """Enhanced processor for delistings with symbol mapping and debug reporting."""

    FIELD_MAPPINGS = {
        'alpaca': {
            'symbol': 'symbol',
            'delisting_date': 'process_date',
            'delisted_symbol': 'symbol',
            'delisting_type': lambda x: 'worthless'
        },
        'sharadar_delisted': {
            'symbol': 'ticker',
            'delisting_date': 'date',
            'delisted_symbol': 'ticker',
            'company_name': 'name',
            'delisting_type': lambda x: 'general'
        },
        'sharadar_regulatory': {
            'symbol': 'ticker',
            'delisting_date': 'date',
            'delisted_symbol': 'ticker',
            'company_name': 'name',
            'delisting_type': lambda x: 'regulatory'
        },
        'sharadar_voluntary': {
            'symbol': 'ticker',
            'delisting_date': 'date',
            'delisted_symbol': 'ticker',
            'company_name': 'name',
            'delisting_type': lambda x: 'voluntary'
        }
    }

    SOURCE_RELIABILITY = {
        'alpaca': 7,
        'sharadar_delisted': 9,
        'sharadar_regulatory': 9,
        'sharadar_voluntary': 9
    }

    def __init__(self, master_csv_path: str):
        self.confidence_calculator = ConfidenceCalculator()
        self.symbol_mapper = SymbolMapper(master_csv_path)
        self.debug_results = []

    def process_all_sources(self, source_data_dict: Dict[str, List[Dict[str, Any]]]) -> List[DelistingMatchResult]:
        """Process delistings from all sources and match by master symbol."""

        # Process each source separately
        processed_by_source = {}
        for source, data in source_data_dict.items():
            processed_by_source[source] = self.process_source_data(source, data)

        # Group by master symbol (company being delisted)
        symbol_groups = self._group_by_master_symbol(processed_by_source)

        # Merge and analyze matches
        match_results = []
        for master_symbol, delistings_by_source in symbol_groups.items():
            try:
                match_result = self._create_match_result(master_symbol, delistings_by_source)
                match_results.append(match_result)
                self.debug_results.append(self._create_debug_entry(match_result))
            except Exception as e:
                logger.error(f"Error processing delistings for {master_symbol}: {e}")
                continue

        # Sort debug results by match quality (worst first)
        self.debug_results.sort(key=lambda x: x['match_quality'])

        return match_results

    def process_source_data(self, source: str, data: List[Dict[str, Any]]) -> List[UnifiedDelisting]:
        """Process delisting data from a specific source with symbol mapping."""
        
        if source not in self.FIELD_MAPPINGS:
            raise ValueError(f"Unknown source: {source}")

        delistings = []
        mapping = self.FIELD_MAPPINGS[source]

        for record in data:
            try:
                # Map to unified format first
                delisting = self._map_record_to_unified(source, record, mapping)

                # Map to master symbol (delisted company)
                source_symbol = delisting.master_symbol
                master_symbol = self.symbol_mapper.map_to_master_symbol(
                    source.replace('_delisted', '').replace('_regulatory', '').replace('_voluntary', ''),
                    source_symbol
                )

                if master_symbol:
                    delisting.master_symbol = master_symbol
                    delisting.symbol_mapping = SymbolMappingInfo(
                        master_symbol=master_symbol,
                        source_mappings={source: source_symbol},
                        unmapped_sources=[],
                        mapping_confidence=1.0
                    )
                else:
                    delisting.master_symbol = source_symbol
                    delisting.symbol_mapping = SymbolMappingInfo(
                        master_symbol=source_symbol,
                        source_mappings={},
                        unmapped_sources=[source],
                        mapping_confidence=0.0
                    )

                delisting.data_completeness = self._calculate_completeness_score(delisting)
                delistings.append(delisting)

            except Exception as e:
                logger.error(f"Error processing {source} record: {e}, record: {record}")
                continue

        return delistings

    def _map_record_to_unified(self, source: str, record: Dict[str, Any],
                               mapping: Dict[str, str]) -> UnifiedDelisting:
        """Map a single record from source format to unified format."""
        unified_data = {
            'master_symbol': '',
            'source': source,
            'raw_data': record.copy()
        }

        for unified_field, source_field in mapping.items():
            if callable(source_field):
                unified_data[unified_field] = source_field(record)
            elif source_field in record and record[source_field] is not None:
                value = record[source_field]

                if unified_field == 'symbol':
                    unified_data['master_symbol'] = str(value)
                else:
                    unified_data[unified_field] = str(value) if value is not None else None

        return UnifiedDelisting(**unified_data)

    def _calculate_completeness_score(self, delisting: UnifiedDelisting) -> float:
        """Calculate data completeness score."""
        required_fields = ['master_symbol', 'delisting_date', 'delisted_symbol']
        optional_fields = ['company_name', 'delisting_type', 'delisting_reason']
        
        required_score = sum(1 for field in required_fields if getattr(delisting, field))
        optional_score = sum(1 for field in optional_fields if getattr(delisting, field))
        
        return (required_score / len(required_fields)) * 0.7 + (optional_score / len(optional_fields)) * 0.3

    def _group_by_master_symbol(self, processed_by_source: Dict[str, List[UnifiedDelisting]]) -> Dict[str, Dict[str, List[UnifiedDelisting]]]:
        """Group delistings by master symbol."""
        symbol_groups = defaultdict(lambda: defaultdict(list))
        
        for source, delistings in processed_by_source.items():
            for delisting in delistings:
                symbol_groups[delisting.master_symbol][source].append(delisting)
        
        return dict(symbol_groups)

    def _create_match_result(self, master_symbol: str, 
                           delistings_by_source: Dict[str, List[UnifiedDelisting]]) -> DelistingMatchResult:
        """Create a match result by merging delistings from multiple sources."""
        
        # Flatten all delistings
        all_delistings = []
        for source_delistings in delistings_by_source.values():
            all_delistings.extend(source_delistings)
        
        # Create merged delisting
        merged_delisting = self._merge_delistings(master_symbol, all_delistings)
        
        # Calculate match quality
        match_quality = self._calculate_match_quality(delistings_by_source)
        
        # Create match details
        match_details = {
            'source_count': len(delistings_by_source),
            'total_records': len(all_delistings),
            'sources': list(delistings_by_source.keys())
        }
        
        return DelistingMatchResult(
            master_symbol=master_symbol,
            merged_delisting=merged_delisting,
            match_quality=match_quality,
            match_details=match_details
        )

    def _merge_delistings(self, master_symbol: str, delistings: List[UnifiedDelisting]) -> UnifiedDelisting:
        """Merge multiple delisting records into a single unified record."""
        
        if not delistings:
            raise ValueError("Cannot merge empty delistings list")
        
        # Group field values by source
        field_values = defaultdict(dict)
        all_sources = []
        
        for delisting in delistings:
            all_sources.append(delisting.source)
            for field_name in ['delisting_date', 'delisted_symbol', 'company_name', 
                              'delisting_type', 'delisting_reason']:
                value = getattr(delisting, field_name)
                if value is not None:
                    field_values[field_name][delisting.source] = value
        
        # Use confidence calculator to merge fields
        merged_fields = {}
        field_confidences = {}
        
        for field_name, values_by_source in field_values.items():
            field_confidence = self.confidence_calculator.calculate_field_confidence(field_name, values_by_source)
            merged_fields[field_name] = field_confidence.value
            field_confidences[field_name] = field_confidence
        
        # Calculate overall confidence metrics
        confidences = [fc.confidence for fc in field_confidences.values()]
        overall_confidence = sum(confidences) / len(confidences) if confidences else 0.0
        
        # Calculate source agreement
        source_agreement_scores = [fc.source_agreement for fc in field_confidences.values()]
        source_agreement_score = sum(source_agreement_scores) / len(source_agreement_scores) if source_agreement_scores else 0.0
        
        # Create symbol mapping info
        source_mappings = {}
        unmapped_sources = []
        
        for delisting in delistings:
            if delisting.symbol_mapping:
                source_mappings.update(delisting.symbol_mapping.source_mappings)
                unmapped_sources.extend(delisting.symbol_mapping.unmapped_sources)
        
        symbol_mapping = SymbolMappingInfo(
            master_symbol=master_symbol,
            source_mappings=source_mappings,
            unmapped_sources=list(set(unmapped_sources)),
            mapping_confidence=1.0 - (len(set(unmapped_sources)) / len(set(all_sources))) if all_sources else 0.0
        )
        
        # Create unified delisting
        merged_delisting = UnifiedDelisting(
            master_symbol=master_symbol,
            source='merged',
            symbol_mapping=symbol_mapping,
            delisting_date=merged_fields.get('delisting_date'),
            delisted_symbol=merged_fields.get('delisted_symbol'),
            company_name=merged_fields.get('company_name'),
            delisting_type=merged_fields.get('delisting_type'),
            delisting_reason=merged_fields.get('delisting_reason'),
            field_confidences=field_confidences,
            overall_confidence=overall_confidence,
            source_agreement_score=source_agreement_score,
            data_completeness=sum(delisting.data_completeness for delisting in delistings) / len(delistings),
            source_list=list(set(all_sources))
        )
        
        return merged_delisting

    def _calculate_match_quality(self, delistings_by_source: Dict[str, List[UnifiedDelisting]]) -> float:
        """Calculate match quality based on source agreement and data completeness."""
        
        if not delistings_by_source:
            return 0.0
        
        # Base quality on number of sources
        source_count = len(delistings_by_source)
        source_quality = min(source_count / 3, 1.0)  # Optimal at 3+ sources
        
        # Average data completeness across all records
        all_delistings = []
        for source_delistings in delistings_by_source.values():
            all_delistings.extend(source_delistings)
        
        if not all_delistings:
            return 0.0
        
        avg_completeness = sum(d.data_completeness for d in all_delistings) / len(all_delistings)
        
        # Check date agreement
        dates = set()
        for source_delistings in delistings_by_source.values():
            for delisting in source_delistings:
                if delisting.delisting_date:
                    dates.add(delisting.delisting_date)
        
        date_agreement = 1.0 if len(dates) <= 1 else 0.8
        
        return (source_quality * 0.4) + (avg_completeness * 0.4) + (date_agreement * 0.2)

    def _create_debug_entry(self, match_result: DelistingMatchResult) -> Dict[str, Any]:
        """Create debug entry for a match result."""
        
        delisting = match_result.merged_delisting
        
        return {
            'master_symbol': match_result.master_symbol,
            'match_quality': match_result.match_quality,
            'source_count': len(delisting.source_list),
            'sources': delisting.source_list,
            'overall_confidence': delisting.overall_confidence,
            'data_completeness': delisting.data_completeness,
            'source_agreement_score': delisting.source_agreement_score,
            'delisting_date': delisting.delisting_date,
            'delisting_type': delisting.delisting_type,
            'mapping_confidence': delisting.symbol_mapping.mapping_confidence if delisting.symbol_mapping else 0.0,
            'unmapped_sources': delisting.symbol_mapping.unmapped_sources if delisting.symbol_mapping else [],
            'match_details': match_result.match_details
        }

    def export_unified_delistings(self, results, data_dir=None, filename=None):
        """Export unified delistings to CSV format"""
        if data_dir is None:
            data_dir = config.data_dir
            
        if filename is None:
            filename = config.get_unified_filename(config.unified_delistings_file)

        os.makedirs(data_dir, exist_ok=True)
        csv_file_path = os.path.join(data_dir, filename)

        csv_data = []
        for result in results:
            delisting = result.merged_delisting

            csv_row = {
                'master_symbol': delisting.master_symbol,
                'source': delisting.source,
                'delisting_date': delisting.delisting_date,
                'delisted_symbol': delisting.delisted_symbol,
                'company_name': delisting.company_name,
                'delisting_type': delisting.delisting_type,
                'delisting_reason': delisting.delisting_reason,
                'overall_confidence': delisting.overall_confidence,
                'source_agreement_score': delisting.source_agreement_score,
                'data_completeness': delisting.data_completeness,
                'match_quality': result.match_quality,
                'source_count': len(delisting.source_list),
                'sources': ', '.join(delisting.source_list),
                'mapping_confidence': delisting.symbol_mapping.mapping_confidence if delisting.symbol_mapping else 0.0,
                'unmapped_sources': ', '.join(
                    delisting.symbol_mapping.unmapped_sources) if delisting.symbol_mapping and delisting.symbol_mapping.unmapped_sources else ''
            }
            csv_data.append(csv_row)

        pd.DataFrame(csv_data).to_csv(csv_file_path, index=False)
        print(f"CSV summary exported to {csv_file_path}")
        return csv_file_path

    def export_debug_report(self, debug_dir=None):
        """Export detailed debug report."""
        if debug_dir is None:
            debug_dir = config.debug_dir

        os.makedirs(debug_dir, exist_ok=True)
        debug_file = os.path.join(debug_dir, f"delisting_debug_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")

        with open(debug_file, 'w') as f:
            json.dump(self.debug_results, f, indent=2, default=str)

        print(f"Debug report exported to {debug_file}")
        return debug_file


if __name__ == "__main__":
    # Ensure directories exist
    config.ensure_directories()
    
    # Use configuration paths
    data_dir = config.data_dir
    debug_dir = config.debug_dir

    # Find master files using configured path
    master_files = glob.glob(os.path.join(config.master_files_dir, '*.csv'))
    if not master_files:
        raise FileNotFoundError(f"No master CSV files found in {config.master_files_dir}")

    master_file = max(master_files)
    print(f"Using master file: {master_file}")

    processor = EnhancedDelistingProcessor(master_file)

    source_data = {
        'alpaca': [{'symbol': 'XYZ', 'process_date': '2025-08-15'}],
        'sharadar_delisted': [{'ticker': 'XYZ', 'date': '2025-08-15', 'name': 'XYZ Corporation'}]
    }

    results = processor.process_all_sources(source_data)
    processor.export_debug_report(debug_dir)
    processor.export_unified_delistings(results, data_dir)

    print(f"Processed {len(results)} delisting matches")
    for result in results:
        print(f"{result.master_symbol}: Quality {result.match_quality:.2%}, "
              f"Confidence {result.merged_delisting.overall_confidence:.2%}")
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from decimal import Decimal
import logging
import os
from collections import defaultdict
import glob
from source.actions.utils import ConfidenceCalculator, FieldConfidence
from source.actions.symbol_mapper import SymbolMapper
import json
import pandas as pd
from datetime import datetime

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
        important_fields = [
            delisting.master_symbol, delisting.delisting_date, delisting.delisted_symbol, delisting.delisting_type
        ]
        filled_fields = sum(1 for field in important_fields if field is not None)
        return filled_fields / len(important_fields)

    def _group_by_master_symbol(self, processed_by_source: Dict[str, List[UnifiedDelisting]]) -> Dict[
        str, Dict[str, List[UnifiedDelisting]]]:
        """Group delistings by master symbol (delisted company) across sources."""
        symbol_groups = {}

        for source, delistings in processed_by_source.items():
            for delisting in delistings:
                master_symbol = delisting.master_symbol
                if master_symbol not in symbol_groups:
                    symbol_groups[master_symbol] = {}
                if source not in symbol_groups[master_symbol]:
                    symbol_groups[master_symbol][source] = []
                symbol_groups[master_symbol][source].append(delisting)

        return symbol_groups

    def _create_match_result(self, master_symbol: str,
                             delistings_by_source: Dict[str, List[UnifiedDelisting]]) -> DelistingMatchResult:
        """Create a match result for delistings with the same master symbol."""

        representative_delistings = []
        for source, delistings in delistings_by_source.items():
            if delistings:
                representative_delistings.append(delistings[0])

        merged = self.merge_delistings_with_confidence([representative_delistings])
        match_quality = self._calculate_match_quality(delistings_by_source, merged)

        match_details = {
            'sources_matched': list(delistings_by_source.keys()),
            'total_delistings': sum(len(delistings) for delistings in delistings_by_source.values()),
            'date_agreement': merged.field_confidences.get('delisting_date',
                                                           FieldConfidence(None, 0, 0, 0, [])).agreement_ratio,
            'type_agreement': merged.field_confidences.get('delisting_type',
                                                           FieldConfidence(None, 0, 0, 0, [])).agreement_ratio,
            'symbol_agreement': merged.field_confidences.get('delisted_symbol',
                                                             FieldConfidence(None, 0, 0, 0, [])).agreement_ratio,
        }

        return DelistingMatchResult(
            master_symbol=master_symbol,
            merged_delisting=merged,
            match_quality=match_quality,
            match_details=match_details
        )

    def _calculate_match_quality(self, delistings_by_source: Dict[str, List[UnifiedDelisting]],
                                 merged: UnifiedDelisting) -> float:
        """Calculate overall match quality for debugging."""
        source_count = len(delistings_by_source)
        source_score = min(1.0, source_count / 4.0)  # Max quality with 4+ sources
        confidence_score = merged.overall_confidence
        agreement_score = merged.source_agreement_score
        mapping_score = merged.symbol_mapping.mapping_confidence if merged.symbol_mapping else 0.0

        quality = (
                source_score * 0.2 +
                confidence_score * 0.4 +
                agreement_score * 0.3 +
                mapping_score * 0.1
        )
        return quality

    def _create_debug_entry(self, match_result: DelistingMatchResult) -> Dict[str, Any]:
        """Create a debug entry for a match result."""
        merged = match_result.merged_delisting

        return {
            'master_symbol': match_result.master_symbol,
            'match_quality': match_result.match_quality,
            'sources': match_result.match_details['sources_matched'],
            'source_count': len(match_result.match_details['sources_matched']),
            'overall_confidence': merged.overall_confidence,
            'source_agreement': merged.source_agreement_score,
            'data_completeness': merged.data_completeness,
            'delisting_date': merged.delisting_date,
            'delisted_symbol': merged.delisted_symbol,
            'delisting_type': merged.delisting_type,
            'company_name': merged.company_name,
            'field_agreements': {
                'delisting_date': merged.field_confidences.get('delisting_date',
                                                               FieldConfidence(None, 0, 0, 0, [])).agreement_ratio,
                'delisting_type': merged.field_confidences.get('delisting_type',
                                                               FieldConfidence(None, 0, 0, 0, [])).agreement_ratio,
                'delisted_symbol': merged.field_confidences.get('delisted_symbol',
                                                                FieldConfidence(None, 0, 0, 0, [])).agreement_ratio,
            },
            'disagreements': {
                field: conf.disagreement_details
                for field, conf in merged.field_confidences.items()
                if conf.disagreement_details
            },
            'symbol_mapping_info': {
                'mapping_confidence': merged.symbol_mapping.mapping_confidence if merged.symbol_mapping else 0,
                'source_mappings': merged.symbol_mapping.source_mappings if merged.symbol_mapping else {},
                'unmapped_sources': merged.symbol_mapping.unmapped_sources if merged.symbol_mapping else []
            },
            'raw_data_summary': {
                source: {
                    'symbol': data.get('symbol') or data.get('ticker'),
                    'delisting_date': data.get('process_date') or data.get('date'),
                    'company_name': data.get('name')
                }
                for source, data in merged.raw_data.items()
            }
        }

    def merge_delistings_with_confidence(self, delisting_groups: List[List[UnifiedDelisting]]) -> UnifiedDelisting:
        """Merge delistings with confidence analysis."""
        if not delisting_groups or not any(delisting_groups):
            raise ValueError("No delistings to merge")

        all_delistings = [delisting for group in delisting_groups for delisting in group if delisting]

        if not all_delistings:
            raise ValueError("No valid delistings to merge")

        field_values = defaultdict(dict)
        source_reliabilities = {}

        for delisting in all_delistings:
            source_reliabilities[delisting.source] = self.SOURCE_RELIABILITY.get(delisting.source, 5) / 10.0

            fields_to_analyze = {
                'delisting_date': delisting.delisting_date,
                'delisted_symbol': delisting.delisted_symbol,
                'company_name': delisting.company_name,
                'delisting_type': delisting.delisting_type,
                'delisting_reason': delisting.delisting_reason
            }

            for field_name, value in fields_to_analyze.items():
                if value is not None:
                    field_values[field_name][delisting.source] = value

        field_confidences = {}
        for field_name, values_by_source in field_values.items():
            field_confidences[field_name] = self.confidence_calculator.calculate_field_confidence(
                field_name, values_by_source, source_reliabilities
            )

        merged = UnifiedDelisting(
            master_symbol=all_delistings[0].master_symbol,
            source='+'.join(sorted(set(delisting.source for delisting in all_delistings))),
            source_list=[delisting.source for delisting in all_delistings],
            raw_data={delisting.source: delisting.raw_data for delisting in all_delistings},
            symbol_mapping=all_delistings[0].symbol_mapping
        )

        for field_name, confidence in field_confidences.items():
            setattr(merged, field_name, confidence.value)

        merged.field_confidences = field_confidences

        field_weights = {
            'delisting_date': 0.3,
            'delisted_symbol': 0.25,
            'delisting_type': 0.25,
            'company_name': 0.15,
            'delisting_reason': 0.05
        }

        merged.overall_confidence = self.confidence_calculator.calculate_overall_confidence(
            field_confidences, field_weights
        )
        merged.source_agreement_score = self.confidence_calculator.calculate_source_agreement_score(
            field_confidences
        )
        merged.data_completeness = self._calculate_completeness_score(merged)

        return merged

    def export_debug_report(self, debug_dir: str, filename: str = None):
        """Export debug results to debug directory."""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d")
            filename = f'delistings_debug_report_{timestamp}.json'

        os.makedirs(debug_dir, exist_ok=True)

        debug_file_path = os.path.join(debug_dir, filename)
        with open(debug_file_path, 'w') as f:
            json.dump(self.debug_results, f, indent=2)

        summary_filename = filename.replace('.json', '_summary.csv')
        summary_file_path = os.path.join(debug_dir, summary_filename)

        summary_data = []
        for result in self.debug_results:
            summary_data.append({
                'master_symbol': result['master_symbol'],
                'match_quality': result['match_quality'],
                'source_count': result['source_count'],
                'overall_confidence': result['overall_confidence'],
                'source_agreement': result['source_agreement'],
                'date_agreement': result['field_agreements']['delisting_date'],
                'type_agreement': result['field_agreements']['delisting_type'],
                'symbol_agreement': result['field_agreements']['delisted_symbol'],
                'sources': ', '.join(result['sources']),
                'delisted_symbol': result['delisted_symbol'],
                'delisting_type': result['delisting_type'],
                'has_disagreements': len(result['disagreements']) > 0,
                'mapping_confidence': result['symbol_mapping_info']['mapping_confidence']
            })

        pd.DataFrame(summary_data).to_csv(summary_file_path, index=False)
        print(f"Debug report exported to {debug_file_path}")
        print(f"Summary CSV exported to {summary_file_path}")

    def export_unified_delistings(self, results: List[DelistingMatchResult], data_dir: str, filename: str = None):
        """Export unified delisting results to data directory."""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d")
            filename = f'unified_delistings_{timestamp}.csv'

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


if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.join(base_dir, '../..')

    data_dir = os.path.join(parent_dir, "data")
    debug_dir = os.path.join(parent_dir, "debug")
    example_dir = os.path.join(parent_dir, "example")

    master_files = glob.glob(os.path.join(example_dir, 'master/*.csv'))
    if not master_files:
        raise FileNotFoundError("No master CSV files found in example/master/ directory")

    master_file = max(master_files)
    print(f"Using master file: {master_file}")

    processor = EnhancedDelistingProcessor(master_file)

    source_data = {
        'alpaca': [{'symbol': 'ENRN', 'process_date': '2025-08-15'}],
        'sharadar_delisted': [{'ticker': 'ENRN', 'date': '2025-08-15', 'name': 'Enron Corporation'}],
        'sharadar_regulatory': [{'ticker': 'ENRN', 'date': '2025-08-15', 'name': 'Enron Corporation'}]
    }

    results = processor.process_all_sources(source_data)
    processor.export_debug_report(debug_dir)
    processor.export_unified_delistings(results, data_dir)

    print(f"Processed {len(results)} delisting matches")
    for result in results:
        print(f"{result.master_symbol}: Quality {result.match_quality:.2%}, "
              f"Confidence {result.merged_delisting.overall_confidence:.2%}")
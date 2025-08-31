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
class UnifiedSpinoff:
    """Unified spinoff representation with master symbol mapping."""

    # Core identifiers
    master_symbol: str  # The unified master symbol (parent company doing the spinoff)
    source: str
    symbol_mapping: Optional[SymbolMappingInfo] = None

    # Dates
    ex_date: Optional[str] = None
    record_date: Optional[str] = None
    payable_date: Optional[str] = None

    # Source company information (parent doing the spinoff)
    source_symbol: Optional[str] = None
    source_cusip: Optional[str] = None
    source_rate: Optional[Decimal] = None

    # New company information (spun-off entity)
    new_symbol: Optional[str] = None
    new_cusip: Optional[str] = None
    new_rate: Optional[Decimal] = None

    # Confidence tracking
    field_confidences: Dict[str, FieldConfidence] = field(default_factory=dict)
    overall_confidence: float = 1.0
    source_agreement_score: float = 1.0
    data_completeness: float = 1.0

    # Raw data
    raw_data: Dict[str, Any] = field(default_factory=dict)
    source_list: List[str] = field(default_factory=list)


@dataclass
class SpinoffMatchResult:
    """Result of matching spinoffs across sources."""
    master_symbol: str
    merged_spinoff: UnifiedSpinoff
    match_quality: float  # 0.0 to 1.0
    match_details: Dict[str, Any]


class EnhancedSpinoffProcessor:
    """Enhanced processor for spinoffs with symbol mapping and debug reporting."""

    FIELD_MAPPINGS = {
        'alpaca': {
            'symbol': 'source_symbol',
            'source_cusip': 'source_cusip',
            'source_rate': 'source_rate',

            'new_symbol': 'new_symbol',
            'new_cusip': 'new_cusip',
            'new_rate': 'new_rate',

            'ex_date': 'ex_date',
            'record_date': 'record_date',
            'payable_date': 'payable_date'
        },
        'sharadar_spinoff': {
            'symbol': 'ticker',

            'new_symbol': 'contraticker',

            'ex_date': 'date',
            'new_rate': 'value'
        },
        'sharadar_spinoff_dividend': {
            'symbol': 'ticker',
            'new_symbol': 'contraticker',

            'ex_date': 'date',

            'new_rate': 'value'
        }
    }

    SOURCE_RELIABILITY = {
        'alpaca': 9,
        'sharadar_spinoff': 7,
        'sharadar_spinoff_dividend': 7
    }

    def __init__(self, master_csv_path: str):
        self.confidence_calculator = ConfidenceCalculator()
        self.symbol_mapper = SymbolMapper(master_csv_path)
        self.debug_results = []

    def process_all_sources(self, source_data_dict: Dict[str, List[Dict[str, Any]]]) -> List[SpinoffMatchResult]:
        """Process spinoffs from all sources and match by master symbol."""

        # Process each source separately
        processed_by_source = {}
        for source, data in source_data_dict.items():
            processed_by_source[source] = self.process_source_data(source, data)

        # Group by master symbol (parent company doing the spinoff)
        symbol_groups = self._group_by_master_symbol(processed_by_source)

        # Merge and analyze matches
        match_results = []
        for master_symbol, spinoffs_by_source in symbol_groups.items():
            try:
                match_result = self._create_match_result(master_symbol, spinoffs_by_source)
                match_results.append(match_result)
                self.debug_results.append(self._create_debug_entry(match_result))
            except Exception as e:
                logger.error(f"Error processing spinoffs for {master_symbol}: {e}")
                continue

        # Sort debug results by match quality (worst first)
        self.debug_results.sort(key=lambda x: x['match_quality'])

        return match_results

    def process_source_data(self, source: str, data: List[Dict[str, Any]]) -> List[UnifiedSpinoff]:
        """Process spinoff data from a specific source with symbol mapping."""
        if source not in self.FIELD_MAPPINGS:
            raise ValueError(f"Unknown source: {source}")

        spinoffs = []
        mapping = self.FIELD_MAPPINGS[source]

        for record in data:
            try:
                # Map to unified format first
                spinoff = self._map_record_to_unified(source, record, mapping)

                # Map to master symbol (parent company)
                source_symbol = spinoff.master_symbol
                master_symbol = self.symbol_mapper.map_to_master_symbol(
                    source.replace('_spinoff', '').replace('_dividend', ''),
                    source_symbol
                )

                if master_symbol:
                    spinoff.master_symbol = master_symbol
                    spinoff.symbol_mapping = SymbolMappingInfo(
                        master_symbol=master_symbol,
                        source_mappings={source: source_symbol},
                        unmapped_sources=[],
                        mapping_confidence=1.0
                    )
                else:
                    spinoff.master_symbol = source_symbol
                    spinoff.symbol_mapping = SymbolMappingInfo(
                        master_symbol=source_symbol,
                        source_mappings={},
                        unmapped_sources=[source],
                        mapping_confidence=0.0
                    )

                spinoff.data_completeness = self._calculate_completeness_score(spinoff)
                spinoffs.append(spinoff)

            except Exception as e:
                logger.error(f"Error processing {source} record: {e}, record: {record}")
                continue

        return spinoffs

    def _map_record_to_unified(self, source: str, record: Dict[str, Any],
                               mapping: Dict[str, str]) -> UnifiedSpinoff:
        """Map a single record from source format to unified format."""
        unified_data = {
            'master_symbol': '',
            'source': source,
            'raw_data': record.copy()
        }

        for unified_field, source_field in mapping.items():
            if source_field in record and record[source_field] is not None:
                value = record[source_field]

                if unified_field == 'symbol':
                    unified_data['master_symbol'] = str(value)
                elif unified_field in ['source_rate', 'new_rate']:
                    unified_data[unified_field] = self._normalize_decimal_value(value)
                else:
                    unified_data[unified_field] = str(value) if value is not None else None

        return UnifiedSpinoff(**unified_data)

    def _normalize_decimal_value(self, value: Any) -> Optional[Decimal]:
        """Normalize numeric values to Decimal for precision."""
        if value is None:
            return None
        try:
            return Decimal(str(value))
        except Exception as e:
            logger.warning(f"Could not convert value to Decimal: {value}, error: {e}")
            return None

    def _calculate_completeness_score(self, spinoff: UnifiedSpinoff) -> float:
        """Calculate data completeness score."""
        important_fields = [
            spinoff.master_symbol, spinoff.ex_date, spinoff.source_symbol, spinoff.new_symbol
        ]
        filled_fields = sum(1 for field in important_fields if field is not None)
        return filled_fields / len(important_fields)

    def _group_by_master_symbol(self, processed_by_source: Dict[str, List[UnifiedSpinoff]]) -> Dict[
        str, Dict[str, List[UnifiedSpinoff]]]:
        """Group spinoffs by master symbol (parent company) across sources."""
        symbol_groups = {}

        for source, spinoffs in processed_by_source.items():
            for spinoff in spinoffs:
                master_symbol = spinoff.master_symbol
                if master_symbol not in symbol_groups:
                    symbol_groups[master_symbol] = {}
                if source not in symbol_groups[master_symbol]:
                    symbol_groups[master_symbol][source] = []
                symbol_groups[master_symbol][source].append(spinoff)

        return symbol_groups

    def _create_match_result(self, master_symbol: str,
                             spinoffs_by_source: Dict[str, List[UnifiedSpinoff]]) -> SpinoffMatchResult:
        """Create a match result for spinoffs with the same master symbol."""

        representative_spinoffs = []
        for source, spinoffs in spinoffs_by_source.items():
            if spinoffs:
                representative_spinoffs.append(spinoffs[0])

        merged = self.merge_spinoffs_with_confidence([representative_spinoffs])
        match_quality = self._calculate_match_quality(spinoffs_by_source, merged)

        match_details = {
            'sources_matched': list(spinoffs_by_source.keys()),
            'total_spinoffs': sum(len(spinoffs) for spinoffs in spinoffs_by_source.values()),
            'date_agreement': merged.field_confidences.get('ex_date',
                                                           FieldConfidence(None, 0, 0, 0, [])).agreement_ratio,
            'new_symbol_agreement': merged.field_confidences.get('new_symbol',
                                                                 FieldConfidence(None, 0, 0, 0, [])).agreement_ratio,
            'rate_agreement': merged.field_confidences.get('new_rate',
                                                           FieldConfidence(None, 0, 0, 0, [])).agreement_ratio,
        }

        return SpinoffMatchResult(
            master_symbol=master_symbol,
            merged_spinoff=merged,
            match_quality=match_quality,
            match_details=match_details
        )

    def _calculate_match_quality(self, spinoffs_by_source: Dict[str, List[UnifiedSpinoff]],
                                 merged: UnifiedSpinoff) -> float:
        """Calculate overall match quality for debugging."""
        source_count = len(spinoffs_by_source)
        source_score = min(1.0, source_count / 3.0)  # Max quality with 3+ sources
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

    def _create_debug_entry(self, match_result: SpinoffMatchResult) -> Dict[str, Any]:
        """Create a debug entry for a match result."""
        merged = match_result.merged_spinoff

        return {
            'master_symbol': match_result.master_symbol,
            'match_quality': match_result.match_quality,
            'sources': match_result.match_details['sources_matched'],
            'source_count': len(match_result.match_details['sources_matched']),
            'overall_confidence': merged.overall_confidence,
            'source_agreement': merged.source_agreement_score,
            'data_completeness': merged.data_completeness,
            'ex_date': merged.ex_date,
            'source_symbol': merged.source_symbol,
            'new_symbol': merged.new_symbol,
            'source_rate': str(merged.source_rate) if merged.source_rate else None,
            'new_rate': str(merged.new_rate) if merged.new_rate else None,
            'field_agreements': {
                'ex_date': merged.field_confidences.get('ex_date', FieldConfidence(None, 0, 0, 0, [])).agreement_ratio,
                'new_symbol': merged.field_confidences.get('new_symbol',
                                                           FieldConfidence(None, 0, 0, 0, [])).agreement_ratio,
                'new_rate': merged.field_confidences.get('new_rate',
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
                    'source_symbol': data.get('source_symbol') or data.get('ticker'),
                    'new_symbol': data.get('new_symbol') or data.get('spinoffticker'),
                    'ex_date': data.get('ex_date') or data.get('date'),
                    'source_rate': data.get('source_rate'),
                    'new_rate': data.get('new_rate') or data.get('value')
                }
                for source, data in merged.raw_data.items()
            }
        }

    def merge_spinoffs_with_confidence(self, spinoff_groups: List[List[UnifiedSpinoff]]) -> UnifiedSpinoff:
        """Merge spinoffs with confidence analysis."""
        if not spinoff_groups or not any(spinoff_groups):
            raise ValueError("No spinoffs to merge")

        all_spinoffs = [spinoff for group in spinoff_groups for spinoff in group if spinoff]

        if not all_spinoffs:
            raise ValueError("No valid spinoffs to merge")

        field_values = defaultdict(dict)
        source_reliabilities = {}

        for spinoff in all_spinoffs:
            source_reliabilities[spinoff.source] = self.SOURCE_RELIABILITY.get(spinoff.source, 5) / 10.0

            fields_to_analyze = {
                'ex_date': spinoff.ex_date,
                'record_date': spinoff.record_date,
                'payable_date': spinoff.payable_date,
                'source_symbol': spinoff.source_symbol,
                'source_cusip': spinoff.source_cusip,
                'source_rate': spinoff.source_rate,
                'new_symbol': spinoff.new_symbol,
                'new_cusip': spinoff.new_cusip,
                'new_rate': spinoff.new_rate
            }

            for field_name, value in fields_to_analyze.items():
                if value is not None:
                    field_values[field_name][spinoff.source] = value

        field_confidences = {}
        for field_name, values_by_source in field_values.items():
            if field_name in ['source_rate', 'new_rate']:
                field_confidences[field_name] = self.confidence_calculator.calculate_field_confidence(
                    field_name.replace('_rate', '_amount'),
                    values_by_source, source_reliabilities
                )
            else:
                field_confidences[field_name] = self.confidence_calculator.calculate_field_confidence(
                    field_name, values_by_source, source_reliabilities
                )

        merged = UnifiedSpinoff(
            master_symbol=all_spinoffs[0].master_symbol,
            source='+'.join(sorted(set(spinoff.source for spinoff in all_spinoffs))),
            source_list=[spinoff.source for spinoff in all_spinoffs],
            raw_data={spinoff.source: spinoff.raw_data for spinoff in all_spinoffs},
            symbol_mapping=all_spinoffs[0].symbol_mapping
        )

        for field_name, confidence in field_confidences.items():
            setattr(merged, field_name, confidence.value)

        merged.field_confidences = field_confidences

        field_weights = {
            'new_symbol': 0.3,
            'ex_date': 0.25,
            'new_rate': 0.2,
            'source_symbol': 0.15,
            'source_rate': 0.1
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
            filename = f'spinoffs_debug_report_{timestamp}.json'

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
                'date_agreement': result['field_agreements']['ex_date'],
                'new_symbol_agreement': result['field_agreements']['new_symbol'],
                'rate_agreement': result['field_agreements']['new_rate'],
                'sources': ', '.join(result['sources']),
                'source_symbol': result['source_symbol'],
                'new_symbol': result['new_symbol'],
                'has_disagreements': len(result['disagreements']) > 0,
                'mapping_confidence': result['symbol_mapping_info']['mapping_confidence']
            })

        pd.DataFrame(summary_data).to_csv(summary_file_path, index=False)
        print(f"Debug report exported to {debug_file_path}")
        print(f"Summary CSV exported to {summary_file_path}")

    def export_unified_spinoffs(self, results: List[SpinoffMatchResult], data_dir: str, filename: str = None):
        """Export unified spinoff results to data directory."""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d")
            filename = f'unified_spinoffs_{timestamp}.csv'

        os.makedirs(data_dir, exist_ok=True)
        csv_file_path = os.path.join(data_dir, filename)

        csv_data = []
        for result in results:
            spinoff = result.merged_spinoff

            csv_row = {
                'master_symbol': spinoff.master_symbol,
                'source': spinoff.source,
                'ex_date': spinoff.ex_date,
                'record_date': spinoff.record_date,
                'payable_date': spinoff.payable_date,
                'source_symbol': spinoff.source_symbol,
                'source_cusip': spinoff.source_cusip,
                'source_rate': str(spinoff.source_rate) if spinoff.source_rate else None,
                'new_symbol': spinoff.new_symbol,
                'new_cusip': spinoff.new_cusip,
                'new_rate': str(spinoff.new_rate) if spinoff.new_rate else None,
                'overall_confidence': spinoff.overall_confidence,
                'source_agreement_score': spinoff.source_agreement_score,
                'data_completeness': spinoff.data_completeness,
                'match_quality': result.match_quality,
                'source_count': len(spinoff.source_list),
                'sources': ', '.join(spinoff.source_list),
                'mapping_confidence': spinoff.symbol_mapping.mapping_confidence if spinoff.symbol_mapping else 0.0,
                'unmapped_sources': ', '.join(
                    spinoff.symbol_mapping.unmapped_sources) if spinoff.symbol_mapping and spinoff.symbol_mapping.unmapped_sources else ''
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

    processor = EnhancedSpinoffProcessor(master_file)

    source_data = {
        'alpaca': [{'source_symbol': 'IBM', 'new_symbol': 'KYN', 'ex_date': '2025-08-15', 'new_rate': '1.0'}],
        'sharadar_spinoff': [{'ticker': 'IBM', 'spinoffticker': 'KYN', 'date': '2025-08-15', 'value': '25.50'}],
        'sharadar_spinoff_dividend': [{'ticker': 'IBM', 'date': '2025-08-15', 'value': '25.50'}]
    }

    results = processor.process_all_sources(source_data)
    processor.export_debug_report(debug_dir)
    processor.export_unified_spinoffs(results, data_dir)

    print(f"Processed {len(results)} spinoff matches")
    for result in results:
        print(f"{result.master_symbol}: Quality {result.match_quality:.2%}, "
              f"Confidence {result.merged_spinoff.overall_confidence:.2%}")
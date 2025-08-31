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
class UnifiedIPO:
    """Unified IPO representation with master symbol mapping."""

    # Core identifiers
    master_symbol: str  # The unified master symbol (company going public)
    source: str
    symbol_mapping: Optional[SymbolMappingInfo] = None

    # Dates
    listing_date: Optional[str] = None

    # Company information
    ipo_symbol: Optional[str] = None
    company_name: Optional[str] = None

    # IPO details
    listing_exchange: Optional[str] = None

    # Confidence tracking
    field_confidences: Dict[str, FieldConfidence] = field(default_factory=dict)
    overall_confidence: float = 1.0
    source_agreement_score: float = 1.0
    data_completeness: float = 1.0

    # Raw data
    raw_data: Dict[str, Any] = field(default_factory=dict)
    source_list: List[str] = field(default_factory=list)


@dataclass
class IPOMatchResult:
    """Result of matching IPOs across sources."""
    master_symbol: str
    merged_ipo: UnifiedIPO
    match_quality: float  # 0.0 to 1.0
    match_details: Dict[str, Any]


class EnhancedIPOProcessor:
    """Enhanced processor for IPOs with symbol mapping and debug reporting."""

    FIELD_MAPPINGS = {
        'sharadar': {
            'symbol': 'ticker',
            'listing_date': 'date',
            'ipo_symbol': 'ticker',
            'company_name': 'name',
            'listing_exchange': 'exchange'
        }
    }

    SOURCE_RELIABILITY = {
        'sharadar': 8
    }

    def __init__(self, master_csv_path: str):
        self.confidence_calculator = ConfidenceCalculator()
        self.symbol_mapper = SymbolMapper(master_csv_path)
        self.debug_results = []

    def process_all_sources(self, source_data_dict: Dict[str, List[Dict[str, Any]]]) -> List[IPOMatchResult]:
        """Process IPOs from all sources and match by master symbol."""

        # Process each source separately
        processed_by_source = {}
        for source, data in source_data_dict.items():
            processed_by_source[source] = self.process_source_data(source, data)

        # Group by master symbol (company going public)
        symbol_groups = self._group_by_master_symbol(processed_by_source)

        # Merge and analyze matches
        match_results = []
        for master_symbol, ipos_by_source in symbol_groups.items():
            try:
                match_result = self._create_match_result(master_symbol, ipos_by_source)
                match_results.append(match_result)
                self.debug_results.append(self._create_debug_entry(match_result))
            except Exception as e:
                logger.error(f"Error processing IPOs for {master_symbol}: {e}")
                continue

        # Sort debug results by match quality (worst first)
        self.debug_results.sort(key=lambda x: x['match_quality'])

        return match_results

    def process_source_data(self, source: str, data: List[Dict[str, Any]]) -> List[UnifiedIPO]:
        """Process IPO data from a specific source with symbol mapping."""
        if source not in self.FIELD_MAPPINGS:
            raise ValueError(f"Unknown source: {source}")

        ipos = []
        mapping = self.FIELD_MAPPINGS[source]

        for record in data:
            try:
                # Map to unified format first
                ipo = self._map_record_to_unified(source, record, mapping)

                # Map to master symbol (IPO company)
                source_symbol = ipo.master_symbol
                master_symbol = self.symbol_mapper.map_to_master_symbol(source, source_symbol)

                if master_symbol:
                    ipo.master_symbol = master_symbol
                    ipo.symbol_mapping = SymbolMappingInfo(
                        master_symbol=master_symbol,
                        source_mappings={source: source_symbol},
                        unmapped_sources=[],
                        mapping_confidence=1.0
                    )
                else:
                    ipo.master_symbol = source_symbol
                    ipo.symbol_mapping = SymbolMappingInfo(
                        master_symbol=source_symbol,
                        source_mappings={},
                        unmapped_sources=[source],
                        mapping_confidence=0.0
                    )

                ipo.data_completeness = self._calculate_completeness_score(ipo)
                ipos.append(ipo)

            except Exception as e:
                logger.error(f"Error processing {source} record: {e}, record: {record}")
                continue

        return ipos

    def _map_record_to_unified(self, source: str, record: Dict[str, Any],
                               mapping: Dict[str, str]) -> UnifiedIPO:
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
                else:
                    unified_data[unified_field] = str(value) if value is not None else None

        return UnifiedIPO(**unified_data)

    def _calculate_completeness_score(self, ipo: UnifiedIPO) -> float:
        """Calculate data completeness score."""
        important_fields = [
            ipo.master_symbol, ipo.listing_date, ipo.ipo_symbol, ipo.company_name
        ]
        filled_fields = sum(1 for field in important_fields if field is not None)
        return filled_fields / len(important_fields)

    def _group_by_master_symbol(self, processed_by_source: Dict[str, List[UnifiedIPO]]) -> Dict[
        str, Dict[str, List[UnifiedIPO]]]:
        """Group IPOs by master symbol (IPO company) across sources."""
        symbol_groups = {}

        for source, ipos in processed_by_source.items():
            for ipo in ipos:
                master_symbol = ipo.master_symbol
                if master_symbol not in symbol_groups:
                    symbol_groups[master_symbol] = {}
                if source not in symbol_groups[master_symbol]:
                    symbol_groups[master_symbol][source] = []
                symbol_groups[master_symbol][source].append(ipo)

        return symbol_groups

    def _create_match_result(self, master_symbol: str,
                             ipos_by_source: Dict[str, List[UnifiedIPO]]) -> IPOMatchResult:
        """Create a match result for IPOs with the same master symbol."""

        representative_ipos = []
        for source, ipos in ipos_by_source.items():
            if ipos:
                representative_ipos.append(ipos[0])

        merged = self.merge_ipos_with_confidence([representative_ipos])
        match_quality = self._calculate_match_quality(ipos_by_source, merged)

        match_details = {
            'sources_matched': list(ipos_by_source.keys()),
            'total_ipos': sum(len(ipos) for ipos in ipos_by_source.values()),
            'date_agreement': merged.field_confidences.get('listing_date',
                                                           FieldConfidence(None, 0, 0, 0, [])).agreement_ratio,
            'symbol_agreement': merged.field_confidences.get('ipo_symbol',
                                                             FieldConfidence(None, 0, 0, 0, [])).agreement_ratio,
            'name_agreement': merged.field_confidences.get('company_name',
                                                           FieldConfidence(None, 0, 0, 0, [])).agreement_ratio,
        }

        return IPOMatchResult(
            master_symbol=master_symbol,
            merged_ipo=merged,
            match_quality=match_quality,
            match_details=match_details
        )

    def _calculate_match_quality(self, ipos_by_source: Dict[str, List[UnifiedIPO]],
                                 merged: UnifiedIPO) -> float:
        """Calculate overall match quality for debugging."""
        source_count = len(ipos_by_source)
        source_score = min(1.0, source_count / 1.0)  # Only one source available
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

    def _create_debug_entry(self, match_result: IPOMatchResult) -> Dict[str, Any]:
        """Create a debug entry for a match result."""
        merged = match_result.merged_ipo

        return {
            'master_symbol': match_result.master_symbol,
            'match_quality': match_result.match_quality,
            'sources': match_result.match_details['sources_matched'],
            'source_count': len(match_result.match_details['sources_matched']),
            'overall_confidence': merged.overall_confidence,
            'source_agreement': merged.source_agreement_score,
            'data_completeness': merged.data_completeness,
            'listing_date': merged.listing_date,
            'ipo_symbol': merged.ipo_symbol,
            'company_name': merged.company_name,
            'listing_exchange': merged.listing_exchange,
            'field_agreements': {
                'listing_date': merged.field_confidences.get('listing_date',
                                                             FieldConfidence(None, 0, 0, 0, [])).agreement_ratio,
                'ipo_symbol': merged.field_confidences.get('ipo_symbol',
                                                           FieldConfidence(None, 0, 0, 0, [])).agreement_ratio,
                'company_name': merged.field_confidences.get('company_name',
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
                    'symbol': data.get('ticker'),
                    'listing_date': data.get('date'),
                    'company_name': data.get('name'),
                    'exchange': data.get('exchange')
                }
                for source, data in merged.raw_data.items()
            }
        }

    def merge_ipos_with_confidence(self, ipo_groups: List[List[UnifiedIPO]]) -> UnifiedIPO:
        """Merge IPOs with confidence analysis."""
        if not ipo_groups or not any(ipo_groups):
            raise ValueError("No IPOs to merge")

        all_ipos = [ipo for group in ipo_groups for ipo in group if ipo]

        if not all_ipos:
            raise ValueError("No valid IPOs to merge")

        field_values = defaultdict(dict)
        source_reliabilities = {}

        for ipo in all_ipos:
            source_reliabilities[ipo.source] = self.SOURCE_RELIABILITY.get(ipo.source, 5) / 10.0

            fields_to_analyze = {
                'listing_date': ipo.listing_date,
                'ipo_symbol': ipo.ipo_symbol,
                'company_name': ipo.company_name,
                'listing_exchange': ipo.listing_exchange
            }

            for field_name, value in fields_to_analyze.items():
                if value is not None:
                    field_values[field_name][ipo.source] = value

        field_confidences = {}
        for field_name, values_by_source in field_values.items():
            field_confidences[field_name] = self.confidence_calculator.calculate_field_confidence(
                field_name, values_by_source, source_reliabilities
            )

        merged = UnifiedIPO(
            master_symbol=all_ipos[0].master_symbol,
            source='+'.join(sorted(set(ipo.source for ipo in all_ipos))),
            source_list=[ipo.source for ipo in all_ipos],
            raw_data={ipo.source: ipo.raw_data for ipo in all_ipos},
            symbol_mapping=all_ipos[0].symbol_mapping
        )

        for field_name, confidence in field_confidences.items():
            setattr(merged, field_name, confidence.value)

        merged.field_confidences = field_confidences

        field_weights = {
            'ipo_symbol': 0.3,
            'listing_date': 0.3,
            'company_name': 0.25,
            'listing_exchange': 0.15
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
            filename = f'ipos_debug_report_{timestamp}.json'

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
                'date_agreement': result['field_agreements']['listing_date'],
                'symbol_agreement': result['field_agreements']['ipo_symbol'],
                'name_agreement': result['field_agreements']['company_name'],
                'sources': ', '.join(result['sources']),
                'ipo_symbol': result['ipo_symbol'],
                'company_name': result['company_name'],
                'listing_exchange': result['listing_exchange'],
                'has_disagreements': len(result['disagreements']) > 0,
                'mapping_confidence': result['symbol_mapping_info']['mapping_confidence']
            })

        pd.DataFrame(summary_data).to_csv(summary_file_path, index=False)
        print(f"Debug report exported to {debug_file_path}")
        print(f"Summary CSV exported to {summary_file_path}")

    def export_unified_ipos(self, results: List[IPOMatchResult], data_dir: str, filename: str = None):
        """Export unified IPO results to data directory."""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d")
            filename = f'unified_ipos_{timestamp}.csv'

        os.makedirs(data_dir, exist_ok=True)
        csv_file_path = os.path.join(data_dir, filename)

        csv_data = []
        for result in results:
            ipo = result.merged_ipo

            csv_row = {
                'master_symbol': ipo.master_symbol,
                'source': ipo.source,
                'listing_date': ipo.listing_date,
                'ipo_symbol': ipo.ipo_symbol,
                'company_name': ipo.company_name,
                'listing_exchange': ipo.listing_exchange,
                'overall_confidence': ipo.overall_confidence,
                'source_agreement_score': ipo.source_agreement_score,
                'data_completeness': ipo.data_completeness,
                'match_quality': result.match_quality,
                'source_count': len(ipo.source_list),
                'sources': ', '.join(ipo.source_list),
                'mapping_confidence': ipo.symbol_mapping.mapping_confidence if ipo.symbol_mapping else 0.0,
                'unmapped_sources': ', '.join(
                    ipo.symbol_mapping.unmapped_sources) if ipo.symbol_mapping and ipo.symbol_mapping.unmapped_sources else ''
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

    processor = EnhancedIPOProcessor(master_file)

    source_data = {
        'sharadar': [{'ticker': 'UBER', 'date': '2019-05-10', 'name': 'Uber Technologies Inc', 'exchange': 'NYSE'}]
    }

    results = processor.process_all_sources(source_data)
    processor.export_debug_report(debug_dir)
    processor.export_unified_ipos(results, data_dir)

    print(f"Processed {len(results)} IPO matches")
    for result in results:
        print(f"{result.master_symbol}: Quality {result.match_quality:.2%}, "
              f"Confidence {result.merged_ipo.overall_confidence:.2%}")
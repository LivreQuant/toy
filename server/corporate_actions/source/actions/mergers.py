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
from source.config import config

logger = logging.getLogger(__name__)


@dataclass
class SymbolMappingInfo:
    """Information about symbol mapping."""
    master_symbol: str
    source_mappings: Dict[str, str]  # source -> original symbol
    unmapped_sources: List[str]
    mapping_confidence: float


@dataclass
class UnifiedMerger:
    """Unified merger representation with master symbol mapping."""

    # Core identifiers
    master_symbol: str  # The unified master symbol (target company being acquired)
    source: str
    symbol_mapping: Optional[SymbolMappingInfo] = None

    # Dates
    ex_date: Optional[str] = None
    payable_date: Optional[str] = None

    # Companies involved
    acquiree_symbol: Optional[str] = None  # Company being acquired
    acquirer_symbol: Optional[str] = None  # Company doing the acquiring

    # CUSIP/CIK information
    acquiree_cusip: Optional[str] = None
    acquirer_cusip: Optional[str] = None
    acquiree_cik: Optional[str] = None
    acquirer_cik: Optional[str] = None

    # Deal terms
    acquiree_rate: Optional[Decimal] = None  # Rate for acquiree shares
    acquirer_rate: Optional[Decimal] = None  # Rate for acquirer shares
    cash_rate: Optional[Decimal] = None  # Cash component per share
    deal_type: Optional[str] = None  # stock, mixed

    # Additional info
    link: Optional[str] = None

    # Confidence tracking
    field_confidences: Dict[str, FieldConfidence] = field(default_factory=dict)
    overall_confidence: float = 1.0
    source_agreement_score: float = 1.0
    data_completeness: float = 1.0

    # Raw data
    raw_data: Dict[str, Any] = field(default_factory=dict)
    source_list: List[str] = field(default_factory=list)


@dataclass
class MergerMatchResult:
    """Result of matching mergers across sources."""
    master_symbol: str
    merged_merger: UnifiedMerger
    match_quality: float  # 0.0 to 1.0
    match_details: Dict[str, Any]


class EnhancedMergerProcessor:
    """Enhanced processor for mergers with symbol mapping and debug reporting."""

    FIELD_MAPPINGS = {
        'alpaca_stock': {
            'symbol': 'acquiree_symbol',
            'acquiree_cusip': 'acquiree_cusip',
            'acquiree_rate': 'acquiree_rate',

            'acquirer_symbol': 'acquirer_symbol',
            'acquirer_cusip': 'acquirer_cusip',
            'acquirer_rate': 'acquirer_rate',

            'cash_rate': 'cash_rate',

            'ex_date': 'effective_date',
            'payable_date': 'payable_date',

            'deal_type': lambda x: 'stock'
        },
        'alpaca_stock_and_cash': {
            'symbol': 'acquiree_symbol',
            'acquiree_cusip': 'acquiree_cusip',
            'acquiree_rate': 'acquiree_rate',

            'acquirer_symbol': 'acquirer_symbol',
            'acquirer_cusip': 'acquirer_cusip',
            'acquirer_rate': 'acquirer_rate',

            'cash_rate': 'cash_rate',

            'ex_date': 'effective_date',
            'payable_date': 'payable_date',

            'deal_type': lambda x: 'mixed'
        },
        'fmp': {
            'symbol': 'targetedSymbol',
            'acquiree_cik': 'targetedCik',

            'acquirer_symbol': 'targetedSymbol',
            'acquirer_cik': 'cik',

            'ex_date': 'transactionDate',
            'payable_date': 'acceptedDate',

            'link': 'link'
        },
        'sharadar': {
            'symbol': 'ticker',

            'acquirer_symbol': 'contraticker',

            'ex_date': 'date',

            'cash_rate': 'value'
        }
    }

    SOURCE_RELIABILITY = {
        'alpaca_stock': 9,
        'alpaca_stock_and_cash': 9,
        'fmp': 8,
        'sharadar': 7
    }

    def __init__(self, master_csv_path: str):
        self.confidence_calculator = ConfidenceCalculator()
        self.symbol_mapper = SymbolMapper(master_csv_path)
        self.debug_results = []

    def process_all_sources(self, source_data_dict: Dict[str, List[Dict[str, Any]]]) -> List[MergerMatchResult]:
        """Process mergers from all sources and match by master symbol."""

        # Process each source separately
        processed_by_source = {}
        for source, data in source_data_dict.items():
            processed_by_source[source] = self.process_source_data(source, data)

        # Group by master symbol (target company being acquired)
        symbol_groups = self._group_by_master_symbol(processed_by_source)

        # Merge and analyze matches
        match_results = []
        for master_symbol, mergers_by_source in symbol_groups.items():
            try:
                match_result = self._create_match_result(master_symbol, mergers_by_source)
                match_results.append(match_result)
                self.debug_results.append(self._create_debug_entry(match_result))
            except Exception as e:
                logger.error(f"Error processing mergers for {master_symbol}: {e}")
                continue

        # Sort debug results by match quality (worst first)
        self.debug_results.sort(key=lambda x: x['match_quality'])

        return match_results

    def process_source_data(self, source: str, data: List[Dict[str, Any]]) -> List[UnifiedMerger]:
        """Process merger data from a specific source with symbol mapping."""
        if source not in self.FIELD_MAPPINGS:
            raise ValueError(f"Unknown source: {source}")

        mergers = []
        mapping = self.FIELD_MAPPINGS[source]

        for record in data:
            try:
                # Map to unified format first
                merger = self._map_record_to_unified(source, record, mapping)

                # Map to master symbol (target company)
                source_symbol = merger.master_symbol
                master_symbol = self.symbol_mapper.map_to_master_symbol(
                    source.replace('_stock', '').replace('_and_cash', ''),
                    source_symbol
                )

                if master_symbol:
                    merger.master_symbol = master_symbol
                    merger.symbol_mapping = SymbolMappingInfo(
                        master_symbol=master_symbol,
                        source_mappings={source: source_symbol},
                        unmapped_sources=[],
                        mapping_confidence=1.0
                    )
                else:
                    merger.master_symbol = source_symbol
                    merger.symbol_mapping = SymbolMappingInfo(
                        master_symbol=source_symbol,
                        source_mappings={},
                        unmapped_sources=[source],
                        mapping_confidence=0.0
                    )

                merger.data_completeness = self._calculate_completeness_score(merger)
                mergers.append(merger)

            except Exception as e:
                logger.error(f"Error processing {source} record: {e}, record: {record}")
                continue

        return mergers

    def _map_record_to_unified(self, source: str, record: Dict[str, Any],
                               mapping: Dict[str, str]) -> UnifiedMerger:
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
                elif unified_field in ['acquiree_rate', 'acquirer_rate', 'cash_rate']:
                    unified_data[unified_field] = self._normalize_decimal_value(value)
                else:
                    unified_data[unified_field] = str(value) if value is not None else None

        return UnifiedMerger(**unified_data)

    def _normalize_decimal_value(self, value: Any) -> Optional[Decimal]:
        """Normalize numeric values to Decimal for precision."""
        if value is None:
            return None
        try:
            return Decimal(str(value))
        except Exception as e:
            logger.warning(f"Could not convert value to Decimal: {value}, error: {e}")
            return None

    def _calculate_completeness_score(self, merger: UnifiedMerger) -> float:
        """Calculate data completeness score."""
        important_fields = [
            merger.master_symbol, merger.ex_date, merger.acquiree_symbol, merger.acquirer_symbol
        ]
        filled_fields = sum(1 for field in important_fields if field is not None)
        return filled_fields / len(important_fields)

    def _group_by_master_symbol(self, processed_by_source: Dict[str, List[UnifiedMerger]]) -> Dict[
        str, Dict[str, List[UnifiedMerger]]]:
        """Group mergers by master symbol (target company) across sources."""
        symbol_groups = {}

        for source, mergers in processed_by_source.items():
            for merger in mergers:
                master_symbol = merger.master_symbol
                if master_symbol not in symbol_groups:
                    symbol_groups[master_symbol] = {}
                if source not in symbol_groups[master_symbol]:
                    symbol_groups[master_symbol][source] = []
                symbol_groups[master_symbol][source].append(merger)

        return symbol_groups

    def _create_match_result(self, master_symbol: str,
                             mergers_by_source: Dict[str, List[UnifiedMerger]]) -> MergerMatchResult:
        """Create a match result for mergers with the same master symbol."""

        representative_mergers = []
        for source, mergers in mergers_by_source.items():
            if mergers:
                representative_mergers.append(mergers[0])

        merged = self.merge_mergers_with_confidence([representative_mergers])
        match_quality = self._calculate_match_quality(mergers_by_source, merged)

        match_details = {
            'sources_matched': list(mergers_by_source.keys()),
            'total_mergers': sum(len(mergers) for mergers in mergers_by_source.values()),
            'date_agreement': merged.field_confidences.get('ex_date',
                                                           FieldConfidence(None, 0, 0, 0, [])).agreement_ratio,
            'acquirer_agreement': merged.field_confidences.get('acquirer_symbol',
                                                               FieldConfidence(None, 0, 0, 0, [])).agreement_ratio,
            'deal_type_agreement': merged.field_confidences.get('deal_type',
                                                                FieldConfidence(None, 0, 0, 0, [])).agreement_ratio,
        }

        return MergerMatchResult(
            master_symbol=master_symbol,
            merged_merger=merged,
            match_quality=match_quality,
            match_details=match_details
        )

    def _calculate_match_quality(self, mergers_by_source: Dict[str, List[UnifiedMerger]],
                                 merged: UnifiedMerger) -> float:
        """Calculate overall match quality for debugging."""
        source_count = len(mergers_by_source)
        source_score = min(1.0, source_count / 4.0)
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

    def _create_debug_entry(self, match_result: MergerMatchResult) -> Dict[str, Any]:
        """Create a debug entry for a match result."""
        merged = match_result.merged_merger

        return {
            'master_symbol': match_result.master_symbol,
            'match_quality': match_result.match_quality,
            'sources': match_result.match_details['sources_matched'],
            'source_count': len(match_result.match_details['sources_matched']),
            'overall_confidence': merged.overall_confidence,
            'source_agreement': merged.source_agreement_score,
            'data_completeness': merged.data_completeness,
            'ex_date': merged.ex_date,
            'acquiree_symbol': merged.acquiree_symbol,
            'acquirer_symbol': merged.acquirer_symbol,
            'deal_type': merged.deal_type,
            'cash_rate': str(merged.cash_rate) if merged.cash_rate else None,
            'acquirer_rate': str(merged.acquirer_rate) if merged.acquirer_rate else None,
            'field_agreements': {
                'ex_date': merged.field_confidences.get('ex_date', FieldConfidence(None, 0, 0, 0, [])).agreement_ratio,
                'acquirer_symbol': merged.field_confidences.get('acquirer_symbol',
                                                                FieldConfidence(None, 0, 0, 0, [])).agreement_ratio,
                'deal_type': merged.field_confidences.get('deal_type',
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
                    'acquiree_symbol': data.get('acquiree_symbol') or data.get('targetedSymbol') or data.get('ticker'),
                    'acquirer_symbol': data.get('acquirer_symbol') or data.get('acquirerticker'),
                    'ex_date': data.get('effective_date') or data.get('transactionDate') or data.get('date'),
                    'cash_rate': data.get('cash_rate') or data.get('value'),
                    'acquirer_rate': data.get('acquirer_rate')
                }
                for source, data in merged.raw_data.items()
            }
        }

    def merge_mergers_with_confidence(self, merger_groups: List[List[UnifiedMerger]]) -> UnifiedMerger:
        """Merge mergers with confidence analysis."""
        if not merger_groups or not any(merger_groups):
            raise ValueError("No mergers to merge")

        all_mergers = [merger for group in merger_groups for merger in group if merger]

        if not all_mergers:
            raise ValueError("No valid mergers to merge")

        field_values = defaultdict(dict)
        source_reliabilities = {}

        for merger in all_mergers:
            source_reliabilities[merger.source] = self.SOURCE_RELIABILITY.get(merger.source, 5) / 10.0

            fields_to_analyze = {
                'ex_date': merger.ex_date,
                'payable_date': merger.payable_date,
                'acquiree_symbol': merger.acquiree_symbol,
                'acquirer_symbol': merger.acquirer_symbol,
                'acquiree_cusip': merger.acquiree_cusip,
                'acquirer_cusip': merger.acquirer_cusip,
                'acquiree_cik': merger.acquiree_cik,
                'acquirer_cik': merger.acquirer_cik,
                'acquiree_rate': merger.acquiree_rate,
                'acquirer_rate': merger.acquirer_rate,
                'cash_rate': merger.cash_rate,
                'deal_type': merger.deal_type,
                'link': merger.link
            }

            for field_name, value in fields_to_analyze.items():
                if value is not None:
                    field_values[field_name][merger.source] = value

        field_confidences = {}
        for field_name, values_by_source in field_values.items():
            if field_name in ['acquiree_rate', 'acquirer_rate', 'cash_rate']:
                field_confidences[field_name] = self.confidence_calculator.calculate_field_confidence(
                    field_name.replace('_rate', '_amount'),
                    values_by_source, source_reliabilities
                )
            else:
                field_confidences[field_name] = self.confidence_calculator.calculate_field_confidence(
                    field_name, values_by_source, source_reliabilities
                )

        merged = UnifiedMerger(
            master_symbol=all_mergers[0].master_symbol,
            source='+'.join(sorted(set(merger.source for merger in all_mergers))),
            source_list=[merger.source for merger in all_mergers],
            raw_data={merger.source: merger.raw_data for merger in all_mergers},
            symbol_mapping=all_mergers[0].symbol_mapping
        )

        for field_name, confidence in field_confidences.items():
            setattr(merged, field_name, confidence.value)

        merged.field_confidences = field_confidences

        field_weights = {
            'acquirer_symbol': 0.3,
            'ex_date': 0.25,
            'deal_type': 0.2,
            'cash_rate': 0.1,
            'acquirer_rate': 0.1,
            'acquiree_symbol': 0.05
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
            filename = f'mergers_debug_report_{timestamp}.json'

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
                'acquirer_agreement': result['field_agreements']['acquirer_symbol'],
                'deal_type_agreement': result['field_agreements']['deal_type'],
                'sources': ', '.join(result['sources']),
                'acquiree_symbol': result['acquiree_symbol'],
                'acquirer_symbol': result['acquirer_symbol'],
                'deal_type': result['deal_type'],
                'has_disagreements': len(result['disagreements']) > 0,
                'mapping_confidence': result['symbol_mapping_info']['mapping_confidence']
            })

        pd.DataFrame(summary_data).to_csv(summary_file_path, index=False)
        print(f"Debug report exported to {debug_file_path}")
        print(f"Summary CSV exported to {summary_file_path}")
        
    def export_unified_mergers(self, results, data_dir=None, filename=None):
        """Export unified mergers to CSV format"""
        if data_dir is None:
            data_dir = config.data_dir
            
        if filename is None:
            filename = config.get_unified_filename(config.unified_mergers_file)

        os.makedirs(data_dir, exist_ok=True)
        csv_file_path = os.path.join(data_dir, filename)

        csv_data = []
        for result in results:
            merger = result.merged_merger

            csv_row = {
                'master_symbol': merger.master_symbol,
                'source': merger.source,
                'ex_date': merger.ex_date,
                'payable_date': merger.payable_date,
                'acquiree_symbol': merger.acquiree_symbol,
                'acquirer_symbol': merger.acquirer_symbol,
                'acquiree_cusip': merger.acquiree_cusip,
                'acquirer_cusip': merger.acquirer_cusip,
                'acquiree_cik': merger.acquiree_cik,
                'acquirer_cik': merger.acquirer_cik,
                'acquiree_rate': str(merger.acquiree_rate) if merger.acquiree_rate else None,
                'acquirer_rate': str(merger.acquirer_rate) if merger.acquirer_rate else None,
                'cash_rate': str(merger.cash_rate) if merger.cash_rate else None,
                'deal_type': merger.deal_type,
                'link': merger.link,
                'overall_confidence': merger.overall_confidence,
                'source_agreement_score': merger.source_agreement_score,
                'data_completeness': merger.data_completeness,
                'match_quality': result.match_quality,
                'source_count': len(merger.source_list),
                'sources': ', '.join(merger.source_list),
                'mapping_confidence': merger.symbol_mapping.mapping_confidence if merger.symbol_mapping else 0.0,
                'unmapped_sources': ', '.join(
                    merger.symbol_mapping.unmapped_sources) if merger.symbol_mapping and merger.symbol_mapping.unmapped_sources else ''
            }
            csv_data.append(csv_row)

        pd.DataFrame(csv_data).to_csv(csv_file_path, index=False)
        print(f"CSV summary exported to {csv_file_path}")
        return csv_file_path


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

    processor = EnhancedMergerProcessor(master_file)

    source_data = {
        'alpaca': [{'acquiree_symbol': 'ABC', 'acquirer_symbol': 'XYZ', 'ex_date': '2025-08-15'}]
    }

    results = processor.process_all_sources(source_data)
    processor.export_debug_report(debug_dir)
    processor.export_unified_mergers(results, data_dir)

    print(f"Processed {len(results)} merger matches")
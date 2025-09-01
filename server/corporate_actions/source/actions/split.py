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
class UnifiedStockSplit:
    """Unified stock split representation with master symbol mapping."""

    # Core identifiers
    master_symbol: str  # The unified master symbol
    source: str
    symbol_mapping: Optional[SymbolMappingInfo] = None

    # Dates
    ex_date: Optional[str] = None
    record_date: Optional[str] = None
    payable_date: Optional[str] = None

    # Split ratios - using Decimal for precision
    split_ratio: Optional[Decimal] = None  # Calculated ratio (new/old)
    old_rate: Optional[Decimal] = None  # Original shares
    new_rate: Optional[Decimal] = None  # New shares

    # Split type - True for reverse splits, False for forward splits
    is_reverse: Optional[bool] = None

    # CUSIP changes (for Alpaca)
    old_cusip: Optional[str] = None
    new_cusip: Optional[str] = None

    # Confidence tracking
    field_confidences: Dict[str, FieldConfidence] = field(default_factory=dict)
    overall_confidence: float = 1.0
    source_agreement_score: float = 1.0
    data_completeness: float = 1.0

    # Raw data
    raw_data: Dict[str, Any] = field(default_factory=dict)
    source_list: List[str] = field(default_factory=list)


@dataclass
class SplitMatchResult:
    """Result of matching splits across sources."""
    master_symbol: str
    merged_split: UnifiedStockSplit
    match_quality: float  # 0.0 to 1.0
    match_details: Dict[str, Any]


class EnhancedStockSplitProcessor:
    """Enhanced processor for stock splits with symbol mapping and debug reporting."""

    FIELD_MAPPINGS = {
        'alpaca_forward': {
            'symbol': 'symbol',
            'ex_date': 'ex_date',
            'payable_date': 'payable_date',
            'record_date': 'record_date',
            'old_rate': 'old_rate',
            'new_rate': 'new_rate',
            'new_cusip': 'cusip',
            'is_reverse': lambda x: False
        },
        'alpaca_reverse': {
            'symbol': 'symbol',
            'ex_date': 'ex_date',
            'payable_date': 'payable_date',
            'record_date': 'record_date',
            'old_rate': 'old_rate',
            'new_rate': 'new_rate',
            'old_cusip': 'old_cusip',
            'new_cusip': 'new_cusip',
            'is_reverse': lambda x: True
        },
        'fmp': {
            'symbol': 'symbol',
            'ex_date': 'date',
            'old_rate': 'denominator',
            'new_rate': 'numerator'
        },
        'poly': {
            'symbol': 'ticker',
            'ex_date': 'execution_date',
            'old_rate': 'split_from',
            'new_rate': 'split_to'
        },
        'sharadar': {
            'symbol': 'ticker',
            'ex_date': 'date',
            'old_rate': lambda x: Decimal('1'),
            'new_rate': 'value'
        }
    }

    SOURCE_RELIABILITY = {
        'alpaca_forward': 9,
        'alpaca_reverse': 9,
        'poly': 8,
        'fmp': 7,
        'sharadar': 6
    }

    def __init__(self, master_csv_path: str):
        self.confidence_calculator = ConfidenceCalculator()
        self.symbol_mapper = SymbolMapper(master_csv_path)
        self.debug_results = []

    def process_all_sources(self, source_data_dict: Dict[str, List[Dict[str, Any]]]) -> List[SplitMatchResult]:
        """Process splits from all sources and match by master symbol."""

        # Process each source separately
        processed_by_source = {}
        for source, data in source_data_dict.items():
            processed_by_source[source] = self.process_source_data(source, data)

        # Group by master symbol
        symbol_groups = self._group_by_master_symbol(processed_by_source)

        # Merge and analyze matches
        match_results = []
        for master_symbol, splits_by_source in symbol_groups.items():
            try:
                match_result = self._create_match_result(master_symbol, splits_by_source)
                match_results.append(match_result)
                self.debug_results.append(self._create_debug_entry(match_result))
            except Exception as e:
                logger.error(f"Error processing splits for {master_symbol}: {e}")
                continue

        # Sort debug results by match quality (worst first)
        self.debug_results.sort(key=lambda x: x['match_quality'])

        return match_results

    def process_source_data(self, source: str, data: List[Dict[str, Any]]) -> List[UnifiedStockSplit]:
        """Process split data from a specific source with symbol mapping."""
        if source not in self.FIELD_MAPPINGS:
            raise ValueError(f"Unknown source: {source}")

        splits = []
        mapping = self.FIELD_MAPPINGS[source]

        for record in data:
            try:
                # Map to unified format first
                split = self._map_record_to_unified(source, record, mapping)

                # Map to master symbol
                source_symbol = split.master_symbol
                master_symbol = self.symbol_mapper.map_to_master_symbol(
                    source.replace('_forward', '').replace('_reverse', ''),
                    source_symbol
                )

                if master_symbol:
                    split.master_symbol = master_symbol
                    split.symbol_mapping = SymbolMappingInfo(
                        master_symbol=master_symbol,
                        source_mappings={source: source_symbol},
                        unmapped_sources=[],
                        mapping_confidence=1.0
                    )
                else:
                    split.master_symbol = source_symbol
                    split.symbol_mapping = SymbolMappingInfo(
                        master_symbol=source_symbol,
                        source_mappings={},
                        unmapped_sources=[source],
                        mapping_confidence=0.0
                    )

                split.data_completeness = self._calculate_completeness_score(split)
                splits.append(split)

            except Exception as e:
                logger.error(f"Error processing {source} record: {e}, record: {record}")
                continue

        return splits

    def _map_record_to_unified(self, source: str, record: Dict[str, Any],
                               mapping: Dict[str, str]) -> UnifiedStockSplit:
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
                elif unified_field in ['split_ratio', 'old_rate', 'new_rate']:
                    unified_data[unified_field] = self._normalize_decimal_value(value)
                else:
                    unified_data[unified_field] = value

        # Calculate split ratio if not provided
        if 'split_ratio' not in unified_data or unified_data['split_ratio'] is None:
            unified_data['split_ratio'] = self._calculate_split_ratio(unified_data)

        # Determine if reverse split based on rates if not already set
        if 'is_reverse' not in unified_data or unified_data['is_reverse'] is None:
            if unified_data.get('old_rate') and unified_data.get('new_rate'):
                unified_data['is_reverse'] = unified_data['new_rate'] < unified_data['old_rate']
            elif unified_data.get('split_ratio'):
                unified_data['is_reverse'] = float(unified_data['split_ratio']) < 1.0

        return UnifiedStockSplit(**unified_data)

    def _calculate_split_ratio(self, unified_data: Dict[str, Any]) -> Optional[Decimal]:
        """Calculate split ratio from available data."""
        if unified_data.get('new_rate') and unified_data.get('old_rate'):
            try:
                return unified_data['new_rate'] / unified_data['old_rate']
            except (TypeError, ZeroDivisionError):
                pass
        return None

    def _normalize_decimal_value(self, value: Any) -> Optional[Decimal]:
        """Normalize numeric values to Decimal for precision."""
        if value is None:
            return None
        try:
            return Decimal(str(value))
        except Exception as e:
            logger.warning(f"Could not convert value to Decimal: {value}, error: {e}")
            return None

    def _calculate_completeness_score(self, split: UnifiedStockSplit) -> float:
        """Calculate data completeness score."""
        important_fields = [
            split.master_symbol, split.ex_date, split.split_ratio
        ]
        filled_fields = sum(1 for field in important_fields if field is not None)
        return filled_fields / len(important_fields)

    def _group_by_master_symbol(self, processed_by_source: Dict[str, List[UnifiedStockSplit]]) -> Dict[
        str, Dict[str, List[UnifiedStockSplit]]]:
        """Group splits by master symbol across sources."""
        symbol_groups = {}

        for source, splits in processed_by_source.items():
            for split in splits:
                master_symbol = split.master_symbol
                if master_symbol not in symbol_groups:
                    symbol_groups[master_symbol] = {}
                if source not in symbol_groups[master_symbol]:
                    symbol_groups[master_symbol][source] = []
                symbol_groups[master_symbol][source].append(split)

        return symbol_groups

    def _create_match_result(self, master_symbol: str,
                             splits_by_source: Dict[str, List[UnifiedStockSplit]]) -> SplitMatchResult:
        """Create a match result for splits with the same master symbol."""

        representative_splits = []
        for source, splits in splits_by_source.items():
            if splits:
                representative_splits.append(splits[0])

        merged = self.merge_splits_with_confidence([representative_splits])
        match_quality = self._calculate_match_quality(splits_by_source, merged)

        match_details = {
            'sources_matched': list(splits_by_source.keys()),
            'total_splits': sum(len(splits) for splits in splits_by_source.values()),
            'date_agreement': merged.field_confidences.get('ex_date',
                                                           FieldConfidence(None, 0, 0, 0, [])).agreement_ratio,
            'ratio_agreement': merged.field_confidences.get('split_ratio',
                                                            FieldConfidence(None, 0, 0, 0, [])).agreement_ratio,
        }

        return SplitMatchResult(
            master_symbol=master_symbol,
            merged_split=merged,
            match_quality=match_quality,
            match_details=match_details
        )

    def _calculate_match_quality(self, splits_by_source: Dict[str, List[UnifiedStockSplit]],
                                 merged: UnifiedStockSplit) -> float:
        """Calculate overall match quality for debugging."""
        source_count = len(splits_by_source)
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

    def _create_debug_entry(self, match_result: SplitMatchResult) -> Dict[str, Any]:
        """Create a debug entry for a match result."""
        merged = match_result.merged_split

        return {
            'master_symbol': match_result.master_symbol,
            'match_quality': match_result.match_quality,
            'sources': match_result.match_details['sources_matched'],
            'source_count': len(match_result.match_details['sources_matched']),
            'overall_confidence': merged.overall_confidence,
            'source_agreement': merged.source_agreement_score,
            'data_completeness': merged.data_completeness,
            'ex_date': merged.ex_date,
            'split_ratio': str(merged.split_ratio) if merged.split_ratio else None,
            'is_reverse': merged.is_reverse,
            'field_agreements': {
                'ex_date': merged.field_confidences.get('ex_date', FieldConfidence(None, 0, 0, 0, [])).agreement_ratio,
                'split_ratio': merged.field_confidences.get('split_ratio',
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
                    'old_rate': data.get('old_rate') or data.get('split_from') or data.get('denominator'),
                    'new_rate': data.get('new_rate') or data.get('split_to') or data.get('numerator') or data.get(
                        'value'),
                    'date': data.get('ex_date') or data.get('date') or data.get('execution_date')
                }
                for source, data in merged.raw_data.items()
            }
        }

    def merge_splits_with_confidence(self, split_groups: List[List[UnifiedStockSplit]]) -> UnifiedStockSplit:
        """Merge splits with confidence analysis."""
        if not split_groups or not any(split_groups):
            raise ValueError("No splits to merge")

        all_splits = [split for group in split_groups for split in group if split]

        if not all_splits:
            raise ValueError("No valid splits to merge")

        field_values = defaultdict(dict)
        source_reliabilities = {}

        for split in all_splits:
            source_reliabilities[split.source] = self.SOURCE_RELIABILITY.get(split.source, 5) / 10.0

            fields_to_analyze = {
                'ex_date': split.ex_date,
                'record_date': split.record_date,
                'payable_date': split.payable_date,
                'split_ratio': split.split_ratio,
                'old_rate': split.old_rate,
                'new_rate': split.new_rate,
                'is_reverse': split.is_reverse,
                'old_cusip': split.old_cusip,
                'new_cusip': split.new_cusip
            }

            for field_name, value in fields_to_analyze.items():
                if value is not None:
                    field_values[field_name][split.source] = value

        field_confidences = {}
        for field_name, values_by_source in field_values.items():
            if field_name.endswith('_ratio') or field_name.endswith('_rate'):
                field_confidences[field_name] = self.confidence_calculator.calculate_field_confidence(
                    field_name.replace('_ratio', '_amount').replace('_rate', '_amount'),
                    values_by_source, source_reliabilities
                )
            else:
                field_confidences[field_name] = self.confidence_calculator.calculate_field_confidence(
                    field_name, values_by_source, source_reliabilities
                )

        merged = UnifiedStockSplit(
            master_symbol=all_splits[0].master_symbol,
            source='+'.join(sorted(set(split.source for split in all_splits))),
            source_list=[split.source for split in all_splits],
            raw_data={split.source: split.raw_data for split in all_splits},
            symbol_mapping=all_splits[0].symbol_mapping
        )

        for field_name, confidence in field_confidences.items():
            setattr(merged, field_name, confidence.value)

        merged.field_confidences = field_confidences

        field_weights = {
            'split_ratio': 0.5,
            'ex_date': 0.3,
            'is_reverse': 0.1,
            'record_date': 0.1
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
            filename = f'stock_splits_debug_report_{timestamp}.json'

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
                'ex_date_agreement': result['field_agreements']['ex_date'],
                'ratio_agreement': result['field_agreements']['split_ratio'],
                'sources': ', '.join(result['sources']),
                'is_reverse': result['is_reverse'],
                'has_disagreements': len(result['disagreements']) > 0,
                'mapping_confidence': result['symbol_mapping_info']['mapping_confidence']
            })

        pd.DataFrame(summary_data).to_csv(summary_file_path, index=False)
        print(f"Debug report exported to {debug_file_path}")
        print(f"Summary CSV exported to {summary_file_path}")

        
    def export_unified_stock_splits(self, results, data_dir=None, filename=None):
        """Export unified stock splits to CSV format"""
        if data_dir is None:
            data_dir = config.data_dir
            
        if filename is None:
            filename = config.get_unified_filename(config.unified_stock_splits_file)

        os.makedirs(data_dir, exist_ok=True)
        csv_file_path = os.path.join(data_dir, filename)

        csv_data = []
        for result in results:
            split = result.merged_split

            csv_row = {
                'master_symbol': split.master_symbol,
                'source': split.source,
                'ex_date': split.ex_date,
                'record_date': split.record_date,
                'payable_date': split.payable_date,
                'split_ratio': str(split.split_ratio) if split.split_ratio else None,
                'old_rate': str(split.old_rate) if split.old_rate else None,
                'new_rate': str(split.new_rate) if split.new_rate else None,
                'is_reverse': split.is_reverse,
                'old_cusip': split.old_cusip,
                'new_cusip': split.new_cusip,
                'overall_confidence': split.overall_confidence,
                'source_agreement_score': split.source_agreement_score,
                'data_completeness': split.data_completeness,
                'match_quality': result.match_quality,
                'source_count': len(split.source_list),
                'sources': ', '.join(split.source_list),
                'mapping_confidence': split.symbol_mapping.mapping_confidence if split.symbol_mapping else 0.0,
                'unmapped_sources': ', '.join(
                    split.symbol_mapping.unmapped_sources) if split.symbol_mapping and split.symbol_mapping.unmapped_sources else ''
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

    processor = EnhancedStockSplitProcessor(master_file)

    source_data = {
        'alpaca': [{'symbol': 'AAPL', 'ex_date': '2025-08-15', 'split_ratio': '2:1'}]
    }

    results = processor.process_all_sources(source_data)
    processor.export_debug_report(debug_dir)
    processor.export_unified_stock_splits(results, data_dir)

    print(f"Processed {len(results)} stock split matches")
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
    execution_date: Optional[str] = None

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
        'alpaca_forward_splits': {
            'symbol': 'symbol',
            'ex_date': 'ex_date',
            'payable_date': 'payable_date',
            'record_date': 'record_date',
            'old_rate': 'old_rate',
            'new_rate': 'new_rate',
            'new_cusip': 'cusip',
            'is_reverse': lambda x: False
        },
        'alpaca_reverse_splits': {
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
            'execution_date': 'execution_date',
            'old_rate': 'split_from',
            'new_rate': 'split_to'
        },
        'sharadar_split': {
            'symbol': 'ticker',
            'ex_date': 'date',
            'old_rate': lambda x: Decimal('1'),
            'new_rate': 'value'
        }
    }

    SOURCE_RELIABILITY = {
        'alpaca_forward_splits': 9,
        'alpaca_reverse_splits': 9,
        'poly': 8,
        'fmp': 7,
        'sharadar_split': 6
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

        if not data:
            return []

        field_mapping = self.FIELD_MAPPINGS.get(source, {})
        unified_splits = []

        for row in data:
            try:
                # Extract basic fields using mapping
                unified_data = {}
                raw_data = dict(row)  # Keep original data

                for unified_field, source_field in field_mapping.items():
                    if callable(source_field):
                        unified_data[unified_field] = source_field(row)
                    else:
                        unified_data[unified_field] = row.get(source_field)

                # Convert numeric fields to proper types and calculate split ratio
                old_rate = unified_data.get('old_rate')
                new_rate = unified_data.get('new_rate')

                if old_rate is not None:
                    try:
                        unified_data['old_rate'] = Decimal(str(old_rate))
                    except (ValueError, TypeError):
                        unified_data['old_rate'] = None

                if new_rate is not None:
                    try:
                        unified_data['new_rate'] = Decimal(str(new_rate))
                    except (ValueError, TypeError):
                        unified_data['new_rate'] = None

                # Calculate split ratio (new_rate / old_rate)
                if unified_data.get('old_rate') and unified_data.get('new_rate'):
                    try:
                        unified_data['split_ratio'] = unified_data['new_rate'] / unified_data['old_rate']
                    except (ZeroDivisionError, TypeError):
                        unified_data['split_ratio'] = None

                # Map symbol to master symbol
                original_symbol = unified_data.get('symbol')
                if not original_symbol:
                    continue

                # Use the correct method name: map_to_master_symbol
                master_symbol = self.symbol_mapper.map_to_master_symbol(source.split('_')[0], original_symbol)

                # Create symbol mapping info
                if master_symbol:
                    symbol_mapping = SymbolMappingInfo(
                        master_symbol=master_symbol,
                        source_mappings={source: original_symbol},
                        unmapped_sources=[],
                        mapping_confidence=1.0
                    )
                else:
                    # If no mapping found, use original symbol as master symbol
                    master_symbol = original_symbol
                    symbol_mapping = SymbolMappingInfo(
                        master_symbol=master_symbol,
                        source_mappings={},
                        unmapped_sources=[source],
                        mapping_confidence=0.0
                    )

                # Create unified split
                split = UnifiedStockSplit(
                    master_symbol=master_symbol,
                    source=source,
                    symbol_mapping=symbol_mapping,
                    ex_date=unified_data.get('ex_date'),
                    record_date=unified_data.get('record_date'),
                    payable_date=unified_data.get('payable_date'),
                    execution_date=unified_data.get('execution_date'),
                    split_ratio=unified_data.get('split_ratio'),
                    old_rate=unified_data.get('old_rate'),
                    new_rate=unified_data.get('new_rate'),
                    is_reverse=unified_data.get('is_reverse'),
                    old_cusip=unified_data.get('old_cusip'),
                    new_cusip=unified_data.get('new_cusip'),
                    raw_data={source: raw_data},
                    source_list=[source]
                )

                # Calculate data completeness
                split.data_completeness = self._calculate_completeness_score(split)
                unified_splits.append(split)

            except Exception as e:
                logger.error(f"Error processing split row from {source}: {e}")
                continue

        return unified_splits

    def _calculate_completeness_score(self, split: UnifiedStockSplit) -> float:
        """Calculate data completeness score."""
        required_fields = ['master_symbol', 'ex_date', 'split_ratio']
        optional_fields = ['old_rate', 'new_rate', 'record_date', 'payable_date', 'is_reverse']

        required_score = sum(1 for field in required_fields if getattr(split, field))
        optional_score = sum(1 for field in optional_fields if getattr(split, field))

        return (required_score / len(required_fields)) * 0.7 + (optional_score / len(optional_fields)) * 0.3

    def _group_by_master_symbol(self, processed_by_source: Dict[str, List[UnifiedStockSplit]]) -> Dict[
        str, Dict[str, List[UnifiedStockSplit]]]:
        """Group splits by master symbol and source."""

        symbol_groups = defaultdict(lambda: defaultdict(list))

        for source, splits in processed_by_source.items():
            for split in splits:
                symbol_groups[split.master_symbol][source].append(split)

        return dict(symbol_groups)

    def _create_match_result(self, master_symbol: str,
                             splits_by_source: Dict[str, List[UnifiedStockSplit]]) -> SplitMatchResult:
        """Create a match result for a master symbol."""

        # Flatten splits from all sources
        all_splits = []
        for source_splits in splits_by_source.values():
            all_splits.extend(source_splits)

        if not all_splits:
            raise ValueError(f"No splits found for {master_symbol}")

        # Group splits that are likely the same (by ex_date and split_ratio)
        split_groups = self._group_similar_splits(all_splits)

        # Merge the largest group (most common split)
        largest_group = max(split_groups, key=len) if split_groups else []

        if not largest_group:
            raise ValueError(f"No valid split groups for {master_symbol}")

        merged_split = self.merge_splits_with_confidence([largest_group])

        # Calculate match quality
        match_quality = self._calculate_match_quality(largest_group, splits_by_source)

        match_details = {
            'sources_matched': list(splits_by_source.keys()),
            'total_splits': len(all_splits),
            'merged_splits': len(largest_group),
            'split_groups': len(split_groups)
        }

        return SplitMatchResult(
            master_symbol=master_symbol,
            merged_split=merged_split,
            match_quality=match_quality,
            match_details=match_details
        )

    def _group_similar_splits(self, splits: List[UnifiedStockSplit]) -> List[List[UnifiedStockSplit]]:
        """Group splits that appear to be the same event."""

        groups = []
        remaining_splits = splits.copy()

        while remaining_splits:
            current = remaining_splits.pop(0)
            current_group = [current]

            # Find similar splits
            to_remove = []
            for i, split in enumerate(remaining_splits):
                if self._are_splits_similar(current, split):
                    current_group.append(split)
                    to_remove.append(i)

            # Remove grouped splits
            for i in reversed(to_remove):
                remaining_splits.pop(i)

            groups.append(current_group)

        return groups

    def _are_splits_similar(self, split1: UnifiedStockSplit, split2: UnifiedStockSplit) -> bool:
        """Check if two splits are likely the same event."""

        # Same ex_date (most important)
        if split1.ex_date and split2.ex_date and split1.ex_date == split2.ex_date:
            # If ratios are present, they should be similar
            if split1.split_ratio and split2.split_ratio:
                ratio_diff = abs(split1.split_ratio - split2.split_ratio)
                if ratio_diff / max(split1.split_ratio, split2.split_ratio) < 0.01:  # 1% tolerance
                    return True
            else:
                return True  # Same date, missing ratios

        return False

    def _calculate_match_quality(self, merged_splits: List[UnifiedStockSplit],
                                 all_splits_by_source: Dict[str, List[UnifiedStockSplit]]) -> float:
        """Calculate the quality of the match."""

        if not merged_splits:
            return 0.0

        # Base quality on source agreement
        sources_in_merge = set(split.source for split in merged_splits)
        total_sources = len(all_splits_by_source)

        source_coverage = len(sources_in_merge) / total_sources if total_sources > 0 else 0

        # Quality score based on coverage and data completeness
        data_completeness = sum(split.data_completeness for split in merged_splits) / len(merged_splits)

        return (source_coverage * 0.7 + data_completeness * 0.3)

    def merge_splits_with_confidence(self, split_groups: List[List[UnifiedStockSplit]]) -> UnifiedStockSplit:
        """Merge splits with confidence analysis."""

        if not split_groups or not any(split_groups):
            raise ValueError("No splits to merge")

        all_splits = [split for group in split_groups for split in group if split]

        if not all_splits:
            raise ValueError("No valid splits to merge")

        # Collect values by field and source
        field_values = defaultdict(dict)
        source_reliabilities = {}

        for split in all_splits:
            source_reliabilities[split.source] = self.SOURCE_RELIABILITY.get(split.source, 5) / 10.0

            fields_to_analyze = {
                'ex_date': split.ex_date,
                'record_date': split.record_date,
                'payable_date': split.payable_date,
                'execution_date': split.execution_date,
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

        # Calculate confidence for each field
        field_confidences = {}
        for field_name, values_by_source in field_values.items():
            field_confidences[field_name] = self.confidence_calculator.calculate_field_confidence(
                field_name, values_by_source, source_reliabilities
            )

        # Build merged split
        merged = UnifiedStockSplit(
            master_symbol=all_splits[0].master_symbol,
            source='+'.join(sorted(set(split.source for split in all_splits))),
            source_list=[split.source for split in all_splits],
            raw_data={split.source: split.raw_data[split.source] for split in all_splits if
                      split.source in split.raw_data},
            symbol_mapping=all_splits[0].symbol_mapping
        )

        # Set field values using confidence analysis - USE .value NOT .final_value
        for field_name, confidence in field_confidences.items():
            setattr(merged, field_name, confidence.value)

        merged.field_confidences = field_confidences

        # Calculate overall scores
        merged.overall_confidence = sum(conf.confidence_score for conf in field_confidences.values()) / len(
            field_confidences) if field_confidences else 0.0
        merged.source_agreement_score = sum(conf.agreement_ratio for conf in field_confidences.values()) / len(
            field_confidences) if field_confidences else 0.0
        merged.data_completeness = len([conf for conf in field_confidences.values() if conf.value is not None]) / len(
            field_confidences) if field_confidences else 0.0

        return merged

    def _create_debug_entry(self, match_result: SplitMatchResult) -> Dict[str, Any]:
        """Create debug entry for a match result."""

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
            'old_rate': str(merged.old_rate) if merged.old_rate else None,
            'new_rate': str(merged.new_rate) if merged.new_rate else None,
            'is_reverse': merged.is_reverse,
            'field_agreements': {
                'ex_date': merged.field_confidences.get('ex_date', FieldConfidence(None, 0, 0, 0, [])).agreement_ratio,
                'split_ratio': merged.field_confidences.get('split_ratio',
                                                            FieldConfidence(None, 0, 0, 0, [])).agreement_ratio,
                'old_rate': merged.field_confidences.get('old_rate',
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
                    'ex_date': data.get('ex_date') or data.get('date') or data.get('execution_date'),
                    'old_rate': data.get('old_rate') or data.get('denominator') or data.get('split_from'),
                    'new_rate': data.get('new_rate') or data.get('numerator') or data.get('split_to') or data.get(
                        'value')
                }
                for source, data in merged.raw_data.items()
            }
        }

    def export_debug_report(self, debug_dir: str):
        """Export debug report to JSON file."""

        debug_file_path = os.path.join(debug_dir, 'split_debug.json')
        summary_file_path = os.path.join(debug_dir, 'split_summary.csv')

        os.makedirs(debug_dir, exist_ok=True)

        # Export detailed debug JSON
        with open(debug_file_path, 'w') as f:
            json.dump(self.debug_results, f, indent=2, default=str)

        # Export summary CSV
        summary_data = []
        for result in self.debug_results:
            summary_data.append({
                'master_symbol': result['master_symbol'],
                'match_quality': result['match_quality'],
                'source_count': result['source_count'],
                'overall_confidence': result['overall_confidence'],
                'ex_date': result['ex_date'],
                'split_ratio': result['split_ratio'],
                'is_reverse': result['is_reverse']
            })

        pd.DataFrame(summary_data).to_csv(summary_file_path, index=False)

        print(f"Debug report exported to {debug_file_path}")
        print(f"Summary CSV exported to {summary_file_path}")

    def export_unified_splits(self, results, filename):
        """Export unified splits to CSV file."""

        if not results:
            print("No split results to export.")
            return None

        os.makedirs(os.path.dirname(filename), exist_ok=True)
        csv_file_path = os.path.join(filename)

        csv_data = []
        for result in results:
            split = result.merged_split

            csv_row = {
                'master_symbol': split.master_symbol,
                'source': split.source,
                'ex_date': split.ex_date,
                'record_date': split.record_date,
                'payable_date': split.payable_date,
                'execution_date': split.execution_date,
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


def extract_split_from_sources(alpaca_data: Dict[str, pd.DataFrame],
                               fmp_data: Dict[str, pd.DataFrame],
                               poly_data: Dict[str, pd.DataFrame],
                               sharadar_data: pd.DataFrame) -> Dict[str, List[Dict[str, Any]]]:
    """Extract split data from all sources and return in standardized format."""

    extracted_data = {}

    # Extract from Alpaca - look for split actions
    alpaca_forward_splits = []
    alpaca_reverse_splits = []
    for action_type, df in alpaca_data.items():
        if 'split' in action_type.lower():
            if not df.empty:
                records = df.to_dict('records')
                if 'reverse' in action_type.lower():
                    alpaca_reverse_splits.extend(records)
                else:
                    alpaca_forward_splits.extend(records)

    extracted_data['alpaca_forward_splits'] = alpaca_forward_splits
    extracted_data['alpaca_reverse_splits'] = alpaca_reverse_splits

    # Extract from FMP
    if 'splits' in fmp_data and not fmp_data['splits'].empty:
        extracted_data['fmp'] = fmp_data['splits'].to_dict('records')
    else:
        extracted_data['fmp'] = []

    # Extract from Polygon
    if 'splits' in poly_data and not poly_data['splits'].empty:
        extracted_data['poly'] = poly_data['splits'].to_dict('records')
    else:
        extracted_data['poly'] = []

    # Extract from Sharadar (filter for split actions)
    if not sharadar_data.empty:
        split_records = sharadar_data[sharadar_data['action'] == 'split']
        extracted_data['sharadar_split'] = split_records.to_dict('records')
    else:
        extracted_data['sharadar_split'] = []

    return extracted_data


def run(alpaca_data: Dict[str, pd.DataFrame],
        fmp_data: Dict[str, pd.DataFrame],
        poly_data: Dict[str, pd.DataFrame],
        sharadar_data: pd.DataFrame):
    """Main function to process splits from all sources."""

    # Ensure directories exist
    config.ensure_directories()

    # Find master files using configured path
    master_files = glob.glob(os.path.join(config.master_files_dir, '*_MASTER_UPDATED.csv'))
    if not master_files:
        raise FileNotFoundError(f"No master CSV files found in {config.master_files_dir}")

    master_file = max(master_files)  # Get the most recent master file
    print(f"Using master file: {master_file}")

    # Extract split data from all sources
    print("Extracting split data from sources...")
    source_data = extract_split_from_sources(alpaca_data, fmp_data, poly_data, sharadar_data)

    # Print extraction summary
    total_records = sum(len(data) for data in source_data.values())
    for source, data in source_data.items():
        print(f"  - {source}: {len(data)} split records extracted")

    if total_records == 0:
        print("No split records found in any source. Skipping split processing.")
        return

    # Initialize processor
    processor = EnhancedStockSplitProcessor(master_file)

    # Process all sources
    print("Processing splits from all sources...")
    results = processor.process_all_sources(source_data)

    # Always export debug report (even if empty)
    processor.export_debug_report(config.debug_dir)

    # Only export CSV if we have results
    if results:
        # Ensure the filename is set properly
        split_filename = config.unified_stock_splits_file or 'unified_stock_splits.csv'
        processor.export_unified_splits(results, os.path.join(config.data_dir, split_filename))

        print(f"Processed {len(results)} split matches")
        for result in results:
            print(f"{result.master_symbol}: Quality {result.match_quality:.2%}, "
                  f"Confidence {result.merged_split.overall_confidence:.2%}")
    else:
        print("No split matches found after processing.")
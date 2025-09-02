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
        'sharadar': {
            'symbol': 'ticker',
            'delisting_date': 'date',
            'delisted_symbol': 'ticker',
            'company_name': 'name',
            'delisting_type': lambda x: 'general'
        }
    }

    SOURCE_RELIABILITY = {
        'alpaca': 7,
        'sharadar': 9
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

        # Group by master symbol
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

        if not data:
            return []

        field_mapping = self.FIELD_MAPPINGS.get(source, {})
        unified_delistings = []

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

                # Map symbol to master symbol
                original_symbol = unified_data.get('symbol')
                if not original_symbol:
                    continue

                # Use the correct method name: map_to_master_symbol
                master_symbol = self.symbol_mapper.map_to_master_symbol(source, original_symbol)

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

                # Create unified delisting
                delisting = UnifiedDelisting(
                    master_symbol=master_symbol,
                    source=source,
                    symbol_mapping=symbol_mapping,
                    delisting_date=unified_data.get('delisting_date'),
                    delisted_symbol=unified_data.get('delisted_symbol'),
                    company_name=unified_data.get('company_name'),
                    delisting_type=unified_data.get('delisting_type'),
                    delisting_reason=unified_data.get('delisting_reason'),
                    raw_data={source: raw_data},
                    source_list=[source]
                )

                # Calculate data completeness
                delisting.data_completeness = self._calculate_completeness_score(delisting)
                unified_delistings.append(delisting)

            except Exception as e:
                logger.error(f"Error processing delisting row from {source}: {e}")
                continue

        return unified_delistings

    def _calculate_completeness_score(self, delisting: UnifiedDelisting) -> float:
        """Calculate data completeness score."""
        required_fields = ['master_symbol', 'delisting_date', 'delisted_symbol']
        optional_fields = ['company_name', 'delisting_type', 'delisting_reason']

        required_score = sum(1 for field in required_fields if getattr(delisting, field))
        optional_score = sum(1 for field in optional_fields if getattr(delisting, field))

        return (required_score / len(required_fields)) * 0.7 + (optional_score / len(optional_fields)) * 0.3

    def _group_by_master_symbol(self, processed_by_source: Dict[str, List[UnifiedDelisting]]) -> Dict[
        str, Dict[str, List[UnifiedDelisting]]]:
        """Group delistings by master symbol and source."""

        symbol_groups = defaultdict(lambda: defaultdict(list))

        for source, delistings in processed_by_source.items():
            for delisting in delistings:
                symbol_groups[delisting.master_symbol][source].append(delisting)

        return dict(symbol_groups)

    def _create_match_result(self, master_symbol: str,
                             delistings_by_source: Dict[str, List[UnifiedDelisting]]) -> DelistingMatchResult:
        """Create a match result for a master symbol."""

        # Flatten delistings from all sources
        all_delistings = []
        for source_delistings in delistings_by_source.values():
            all_delistings.extend(source_delistings)

        if not all_delistings:
            raise ValueError(f"No delistings found for {master_symbol}")

        # Group delistings that are likely the same (by delisting_date)
        delisting_groups = self._group_similar_delistings(all_delistings)

        # Merge the largest group (most common delisting)
        largest_group = max(delisting_groups, key=len) if delisting_groups else []

        if not largest_group:
            raise ValueError(f"No valid delisting groups for {master_symbol}")

        merged_delisting = self.merge_delistings_with_confidence([largest_group])

        # Calculate match quality
        match_quality = self._calculate_match_quality(largest_group, delistings_by_source)

        match_details = {
            'sources_matched': list(delistings_by_source.keys()),
            'total_delistings': len(all_delistings),
            'merged_delistings': len(largest_group),
            'delisting_groups': len(delisting_groups)
        }

        return DelistingMatchResult(
            master_symbol=master_symbol,
            merged_delisting=merged_delisting,
            match_quality=match_quality,
            match_details=match_details
        )

    def _group_similar_delistings(self, delistings: List[UnifiedDelisting]) -> List[List[UnifiedDelisting]]:
        """Group delistings that appear to be the same event."""

        groups = []
        remaining_delistings = delistings.copy()

        while remaining_delistings:
            current = remaining_delistings.pop(0)
            current_group = [current]

            # Find similar delistings
            to_remove = []
            for i, delisting in enumerate(remaining_delistings):
                if self._are_delistings_similar(current, delisting):
                    current_group.append(delisting)
                    to_remove.append(i)

            # Remove grouped delistings
            for i in reversed(to_remove):
                remaining_delistings.pop(i)

            groups.append(current_group)

        return groups

    def _are_delistings_similar(self, del1: UnifiedDelisting, del2: UnifiedDelisting) -> bool:
        """Check if two delistings are likely the same event."""

        # Same delisting_date (most important)
        if del1.delisting_date and del2.delisting_date and del1.delisting_date == del2.delisting_date:
            return True

        # If no dates, consider them similar if from different sources (likely same event)
        if not del1.delisting_date and not del2.delisting_date:
            return del1.source != del2.source

        return False

    def _calculate_match_quality(self, merged_delistings: List[UnifiedDelisting],
                                 all_delistings_by_source: Dict[str, List[UnifiedDelisting]]) -> float:
        """Calculate the quality of the match."""

        if not merged_delistings:
            return 0.0

        # Base quality on source agreement
        sources_in_merge = set(del_.source for del_ in merged_delistings)
        total_sources = len(all_delistings_by_source)

        source_coverage = len(sources_in_merge) / total_sources if total_sources > 0 else 0

        # Quality score based on coverage and data completeness
        data_completeness = sum(del_.data_completeness for del_ in merged_delistings) / len(merged_delistings)

        return (source_coverage * 0.7 + data_completeness * 0.3)

    def merge_delistings_with_confidence(self, delisting_groups: List[List[UnifiedDelisting]]) -> UnifiedDelisting:
        """Merge delistings with confidence analysis."""

        if not delisting_groups or not any(delisting_groups):
            raise ValueError("No delistings to merge")

        all_delistings = [del_ for group in delisting_groups for del_ in group if del_]

        if not all_delistings:
            raise ValueError("No valid delistings to merge")

        # Collect values by field and source
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

        # Calculate confidence for each field
        field_confidences = {}
        for field_name, values_by_source in field_values.items():
            field_confidences[field_name] = self.confidence_calculator.calculate_field_confidence(
                field_name, values_by_source, source_reliabilities
            )

        # Build merged delisting
        merged = UnifiedDelisting(
            master_symbol=all_delistings[0].master_symbol,
            source='+'.join(sorted(set(del_.source for del_ in all_delistings))),
            source_list=[del_.source for del_ in all_delistings],
            raw_data={del_.source: del_.raw_data[del_.source] for del_ in all_delistings if
                      del_.source in del_.raw_data},
            symbol_mapping=all_delistings[0].symbol_mapping
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

    def _create_debug_entry(self, match_result: DelistingMatchResult) -> Dict[str, Any]:
        """Create debug entry for a match result."""

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
            'delisting_type': merged.delisting_type,
            'company_name': merged.company_name,
            'field_agreements': {
                'delisting_date': merged.field_confidences.get('delisting_date',
                                                               FieldConfidence(None, 0, 0, 0, [])).agreement_ratio,
                'delisting_type': merged.field_confidences.get('delisting_type',
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
                    'symbol': data.get('symbol') or data.get('ticker'),
                    'date': data.get('process_date') or data.get('date'),
                    'name': data.get('name')
                }
                for source, data in merged.raw_data.items()
            }
        }

    def export_debug_report(self, debug_dir: str):
        """Export debug report to JSON file."""

        debug_file_path = os.path.join(debug_dir, 'delisting_debug.json')
        summary_file_path = os.path.join(debug_dir, 'delisting_summary.csv')

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
                'delisting_date': result['delisting_date'],
                'delisting_type': result['delisting_type']
            })

        pd.DataFrame(summary_data).to_csv(summary_file_path, index=False)

        print(f"Debug report exported to {debug_file_path}")
        print(f"Summary CSV exported to {summary_file_path}")

    def export_unified_delistings(self, results, filename):
        """Export unified delistings to CSV file."""

        if not results:
            print("No delisting results to export.")
            return None

        os.makedirs(os.path.dirname(filename), exist_ok=True)
        csv_file_path = os.path.join(filename)

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


def extract_delisting_from_sources(alpaca_data: Dict[str, pd.DataFrame],
                                   fmp_data: Dict[str, pd.DataFrame],
                                   poly_data: Dict[str, pd.DataFrame],
                                   sharadar_data: pd.DataFrame) -> Dict[str, List[Dict[str, Any]]]:
    """Extract delisting data from all sources and return in standardized format."""

    extracted_data = {}

    # Extract from Alpaca - look for delisting/worthless actions
    alpaca_delistings = []
    for action_type, df in alpaca_data.items():
        if 'worthless' in action_type.lower() or 'delisting' in action_type.lower():
            if not df.empty:
                alpaca_delistings.extend(df.to_dict('records'))
    extracted_data['alpaca'] = alpaca_delistings

    # Extract from FMP - no delisting data typically
    extracted_data['fmp'] = []

    # Extract from Polygon - no delisting data typically
    extracted_data['poly'] = []

    # Extract from Sharadar (filter for delisting actions)
    if not sharadar_data.empty:
        # Look for various delisting action types
        delisting_actions = ['delisted', 'worthless', 'regulatory', 'voluntary']
        delisting_records = sharadar_data[sharadar_data['action'].isin(delisting_actions)]
        extracted_data['sharadar'] = delisting_records.to_dict('records')
    else:
        extracted_data['sharadar'] = []

    return extracted_data


def run(alpaca_data: Dict[str, pd.DataFrame],
        fmp_data: Dict[str, pd.DataFrame],
        poly_data: Dict[str, pd.DataFrame],
        sharadar_data: pd.DataFrame):
    """Main function to process delistings from all sources."""

    # Ensure directories exist
    config.ensure_directories()

    # Find master files using configured path
    master_files = glob.glob(os.path.join(config.master_files_dir, '*_MASTER_UPDATED.csv'))
    if not master_files:
        raise FileNotFoundError(f"No master CSV files found in {config.master_files_dir}")

    master_file = max(master_files)  # Get the most recent master file
    print(f"Using master file: {master_file}")

    # Extract delisting data from all sources
    print("Extracting delisting data from sources...")
    source_data = extract_delisting_from_sources(alpaca_data, fmp_data, poly_data, sharadar_data)

    # Print extraction summary
    total_records = sum(len(data) for data in source_data.values())
    for source, data in source_data.items():
        print(f"  - {source}: {len(data)} delisting records extracted")

    if total_records == 0:
        print("No delisting records found in any source. Skipping delisting processing.")
        return

    # Initialize processor
    processor = EnhancedDelistingProcessor(master_file)

    # Process all sources
    print("Processing delistings from all sources...")
    results = processor.process_all_sources(source_data)

    # Always export debug report (even if empty)
    processor.export_debug_report(config.debug_dir)

    # Only export CSV if we have results
    if results:
        # Ensure the filename is set properly
        delisting_filename = config.unified_delisting_file or 'unified_delisting.csv'
        processor.export_unified_delistings(results, os.path.join(config.data_dir, delisting_filename))

        print(f"Processed {len(results)} delisting matches")
        for result in results:
            print(f"{result.master_symbol}: Quality {result.match_quality:.2%}, "
                  f"Confidence {result.merged_delisting.overall_confidence:.2%}")
    else:
        print("No delisting matches found after processing.")
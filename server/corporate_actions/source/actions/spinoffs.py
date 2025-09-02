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

    # Parent company information (company doing the spinoff)
    source_symbol: Optional[str] = None
    source_cusip: Optional[str] = None
    source_rate: Optional[Decimal] = None

    # Spun-off company information (new entity)
    new_symbol: Optional[str] = None
    new_cusip: Optional[str] = None
    new_rate: Optional[Decimal] = None
    company_name: Optional[str] = None

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
        'alpaca_spinoffs': {
            'symbol': 'source_symbol',
            'source_symbol': 'source_symbol',
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
            'source_symbol': 'ticker',
            'new_symbol': 'contraticker',
            'company_name': 'contraname',
            'ex_date': 'date',
            'new_rate': 'value'
        }
    }

    SOURCE_RELIABILITY = {
        'alpaca_spinoffs': 9,
        'sharadar_spinoff': 7
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

        # Group by master symbol
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

        if not data:
            return []

        field_mapping = self.FIELD_MAPPINGS.get(source, {})
        unified_spinoffs = []

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

                # Convert numeric fields to proper types
                for rate_field in ['source_rate', 'new_rate']:
                    if unified_data.get(rate_field) is not None:
                        try:
                            unified_data[rate_field] = Decimal(str(unified_data[rate_field]))
                        except (ValueError, TypeError):
                            unified_data[rate_field] = None

                # Map symbol to master symbol (use source_symbol as the parent company)
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

                # Create unified spinoff
                spinoff = UnifiedSpinoff(
                    master_symbol=master_symbol,
                    source=source,
                    symbol_mapping=symbol_mapping,
                    ex_date=unified_data.get('ex_date'),
                    record_date=unified_data.get('record_date'),
                    payable_date=unified_data.get('payable_date'),
                    source_symbol=unified_data.get('source_symbol'),
                    source_cusip=unified_data.get('source_cusip'),
                    source_rate=unified_data.get('source_rate'),
                    new_symbol=unified_data.get('new_symbol'),
                    new_cusip=unified_data.get('new_cusip'),
                    new_rate=unified_data.get('new_rate'),
                    company_name=unified_data.get('company_name'),
                    raw_data={source: raw_data},
                    source_list=[source]
                )

                # Calculate data completeness
                spinoff.data_completeness = self._calculate_completeness_score(spinoff)
                unified_spinoffs.append(spinoff)

            except Exception as e:
                logger.error(f"Error processing spinoff row from {source}: {e}")
                continue

        return unified_spinoffs

    def _calculate_completeness_score(self, spinoff: UnifiedSpinoff) -> float:
        """Calculate data completeness score."""
        required_fields = ['master_symbol', 'ex_date', 'source_symbol', 'new_symbol']
        optional_fields = ['new_rate', 'source_rate', 'company_name', 'record_date', 'payable_date']

        required_score = sum(1 for field in required_fields if getattr(spinoff, field))
        optional_score = sum(1 for field in optional_fields if getattr(spinoff, field))

        return (required_score / len(required_fields)) * 0.7 + (optional_score / len(optional_fields)) * 0.3

    def _group_by_master_symbol(self, processed_by_source: Dict[str, List[UnifiedSpinoff]]) -> Dict[
        str, Dict[str, List[UnifiedSpinoff]]]:
        """Group spinoffs by master symbol and source."""

        symbol_groups = defaultdict(lambda: defaultdict(list))

        for source, spinoffs in processed_by_source.items():
            for spinoff in spinoffs:
                symbol_groups[spinoff.master_symbol][source].append(spinoff)

        return dict(symbol_groups)

    def _create_match_result(self, master_symbol: str,
                             spinoffs_by_source: Dict[str, List[UnifiedSpinoff]]) -> SpinoffMatchResult:
        """Create a match result for a master symbol."""

        # Flatten spinoffs from all sources
        all_spinoffs = []
        for source_spinoffs in spinoffs_by_source.values():
            all_spinoffs.extend(source_spinoffs)

        if not all_spinoffs:
            raise ValueError(f"No spinoffs found for {master_symbol}")

        # Group spinoffs that are likely the same (by ex_date and new_symbol)
        spinoff_groups = self._group_similar_spinoffs(all_spinoffs)

        # Merge the largest group (most common spinoff)
        largest_group = max(spinoff_groups, key=len) if spinoff_groups else []

        if not largest_group:
            raise ValueError(f"No valid spinoff groups for {master_symbol}")

        merged_spinoff = self.merge_spinoffs_with_confidence([largest_group])

        # Calculate match quality
        match_quality = self._calculate_match_quality(largest_group, spinoffs_by_source)

        match_details = {
            'sources_matched': list(spinoffs_by_source.keys()),
            'total_spinoffs': len(all_spinoffs),
            'merged_spinoffs': len(largest_group),
            'spinoff_groups': len(spinoff_groups)
        }

        return SpinoffMatchResult(
            master_symbol=master_symbol,
            merged_spinoff=merged_spinoff,
            match_quality=match_quality,
            match_details=match_details
        )

    def _group_similar_spinoffs(self, spinoffs: List[UnifiedSpinoff]) -> List[List[UnifiedSpinoff]]:
        """Group spinoffs that appear to be the same event."""

        groups = []
        remaining_spinoffs = spinoffs.copy()

        while remaining_spinoffs:
            current = remaining_spinoffs.pop(0)
            current_group = [current]

            # Find similar spinoffs
            to_remove = []
            for i, spinoff in enumerate(remaining_spinoffs):
                if self._are_spinoffs_similar(current, spinoff):
                    current_group.append(spinoff)
                    to_remove.append(i)

            # Remove grouped spinoffs
            for i in reversed(to_remove):
                remaining_spinoffs.pop(i)

            groups.append(current_group)

        return groups

    def _are_spinoffs_similar(self, spinoff1: UnifiedSpinoff, spinoff2: UnifiedSpinoff) -> bool:
        """Check if two spinoffs are likely the same event."""

        # Same ex_date and similar new symbols
        if spinoff1.ex_date and spinoff2.ex_date and spinoff1.ex_date == spinoff2.ex_date:
            if spinoff1.new_symbol and spinoff2.new_symbol and spinoff1.new_symbol == spinoff2.new_symbol:
                return True

        return False

    def _calculate_match_quality(self, merged_spinoffs: List[UnifiedSpinoff],
                                 all_spinoffs_by_source: Dict[str, List[UnifiedSpinoff]]) -> float:
        """Calculate the quality of the match."""

        if not merged_spinoffs:
            return 0.0

        # Base quality on source agreement
        sources_in_merge = set(spinoff.source for spinoff in merged_spinoffs)
        total_sources = len(all_spinoffs_by_source)

        source_coverage = len(sources_in_merge) / total_sources if total_sources > 0 else 0

        # Quality score based on coverage and data completeness
        data_completeness = sum(spinoff.data_completeness for spinoff in merged_spinoffs) / len(merged_spinoffs)

        return (source_coverage * 0.7 + data_completeness * 0.3)

    def merge_spinoffs_with_confidence(self, spinoff_groups: List[List[UnifiedSpinoff]]) -> UnifiedSpinoff:
        """Merge spinoffs with confidence analysis."""

        if not spinoff_groups or not any(spinoff_groups):
            raise ValueError("No spinoffs to merge")

        all_spinoffs = [spinoff for group in spinoff_groups for spinoff in group if spinoff]

        if not all_spinoffs:
            raise ValueError("No valid spinoffs to merge")

        # Collect values by field and source
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
                'new_rate': spinoff.new_rate,
                'company_name': spinoff.company_name
            }

            for field_name, value in fields_to_analyze.items():
                if value is not None:
                    field_values[field_name][spinoff.source] = value

        # Calculate confidence for each field
        field_confidences = {}
        for field_name, values_by_source in field_values.items():
            field_confidences[field_name] = self.confidence_calculator.calculate_field_confidence(
                field_name, values_by_source, source_reliabilities
            )

        # Build merged spinoff
        merged = UnifiedSpinoff(
            master_symbol=all_spinoffs[0].master_symbol,
            source='+'.join(sorted(set(spinoff.source for spinoff in all_spinoffs))),
            source_list=[spinoff.source for spinoff in all_spinoffs],
            raw_data={spinoff.source: spinoff.raw_data[spinoff.source] for spinoff in all_spinoffs if
                      spinoff.source in spinoff.raw_data},
            symbol_mapping=all_spinoffs[0].symbol_mapping
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

    def _create_debug_entry(self, match_result: SpinoffMatchResult) -> Dict[str, Any]:
        """Create debug entry for a match result."""

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
                    'new_symbol': data.get('new_symbol') or data.get('contraticker'),
                    'ex_date': data.get('ex_date') or data.get('date'),
                    'new_rate': data.get('new_rate') or data.get('value')
                }
                for source, data in merged.raw_data.items()
            }
        }

    def export_debug_report(self, debug_dir: str):
        """Export debug report to JSON file."""

        debug_file_path = os.path.join(debug_dir, 'spinoff_debug.json')
        summary_file_path = os.path.join(debug_dir, 'spinoff_summary.csv')

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
                'source_symbol': result['source_symbol'],
                'new_symbol': result['new_symbol']
            })

        pd.DataFrame(summary_data).to_csv(summary_file_path, index=False)

        print(f"Debug report exported to {debug_file_path}")
        print(f"Summary CSV exported to {summary_file_path}")

    def export_unified_spinoffs(self, results, filename):
        """Export unified spinoffs to CSV file."""

        if not results:
            print("No spinoff results to export.")
            return None

        os.makedirs(os.path.dirname(filename), exist_ok=True)
        csv_file_path = os.path.join(filename)

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
                'company_name': spinoff.company_name,
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


def extract_spinoff_from_sources(alpaca_data: Dict[str, pd.DataFrame],
                                 fmp_data: Dict[str, pd.DataFrame],
                                 poly_data: Dict[str, pd.DataFrame],
                                 sharadar_data: pd.DataFrame) -> Dict[str, List[Dict[str, Any]]]:
    """Extract spinoff data from all sources and return in standardized format."""

    extracted_data = {}

    # Extract from Alpaca - look for spinoff actions
    alpaca_spinoffs = []
    for action_type, df in alpaca_data.items():
        if 'spinoff' in action_type.lower():
            if not df.empty:
                alpaca_spinoffs.extend(df.to_dict('records'))
    extracted_data['alpaca_spinoffs'] = alpaca_spinoffs

    # Extract from FMP - no spinoff data typically
    extracted_data['fmp'] = []

    # Extract from Polygon - no spinoff data typically
    extracted_data['poly'] = []

    # Extract from Sharadar (filter for spinoff actions)
    if not sharadar_data.empty:
        spinoff_records = sharadar_data[sharadar_data['action'] == 'spinoff']
        extracted_data['sharadar_spinoff'] = spinoff_records.to_dict('records')
    else:
        extracted_data['sharadar_spinoff'] = []

    return extracted_data


def run(alpaca_data: Dict[str, pd.DataFrame],
        fmp_data: Dict[str, pd.DataFrame],
        poly_data: Dict[str, pd.DataFrame],
        sharadar_data: pd.DataFrame):
    """Main function to process spinoffs from all sources."""

    # Ensure directories exist
    config.ensure_directories()

    # Find master files using configured path
    master_files = glob.glob(os.path.join(config.master_files_dir, '*_MASTER_UPDATED.csv'))
    if not master_files:
        raise FileNotFoundError(f"No master CSV files found in {config.master_files_dir}")

    master_file = max(master_files)  # Get the most recent master file
    print(f"Using master file: {master_file}")

    # Extract spinoff data from all sources
    print("Extracting spinoff data from sources...")
    source_data = extract_spinoff_from_sources(alpaca_data, fmp_data, poly_data, sharadar_data)

    # Print extraction summary
    total_records = sum(len(data) for data in source_data.values())
    for source, data in source_data.items():
        print(f"  - {source}: {len(data)} spinoff records extracted")

    if total_records == 0:
        print("No spinoff records found in any source. Skipping spinoff processing.")
        return

    # Initialize processor
    processor = EnhancedSpinoffProcessor(master_file)

    # Process all sources
    print("Processing spinoffs from all sources...")
    results = processor.process_all_sources(source_data)

    # Always export debug report (even if empty)
    processor.export_debug_report(config.debug_dir)

    # Only export CSV if we have results
    if results:
        # Ensure the filename is set properly
        spinoff_filename = config.unified_spinoffs_file or 'unified_spinoffs.csv'
        processor.export_unified_spinoffs(results, os.path.join(config.data_dir, spinoff_filename))

        print(f"Processed {len(results)} spinoff matches")
        for result in results:
            print(f"{result.master_symbol}: Quality {result.match_quality:.2%}, "
                  f"Confidence {result.merged_spinoff.overall_confidence:.2%}")
    else:
        print("No spinoff matches found after processing.")
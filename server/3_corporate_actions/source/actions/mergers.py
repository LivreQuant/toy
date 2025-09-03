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
class UnifiedMerger:
    """Unified merger representation with master symbol mapping."""

    # Core identifiers
    master_symbol: str  # The unified master symbol (target company being acquired)
    source: str
    symbol_mapping: Optional[SymbolMappingInfo] = None

    # Dates
    ex_date: Optional[str] = None
    payable_date: Optional[str] = None
    transaction_date: Optional[str] = None
    accepted_date: Optional[str] = None

    # Companies involved
    acquiree_symbol: Optional[str] = None  # Company being acquired (target)
    acquirer_symbol: Optional[str] = None  # Company doing the acquiring
    company_name: Optional[str] = None

    # CUSIP/CIK information
    acquiree_cusip: Optional[str] = None
    acquirer_cusip: Optional[str] = None
    acquiree_cik: Optional[str] = None
    acquirer_cik: Optional[str] = None

    # Deal terms
    acquiree_rate: Optional[Decimal] = None  # Rate for acquiree shares
    acquirer_rate: Optional[Decimal] = None  # Rate for acquirer shares
    cash_rate: Optional[Decimal] = None  # Cash component per share
    deal_value: Optional[Decimal] = None  # Total deal value
    deal_type: Optional[str] = None  # stock, mixed, cash

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
            'acquiree_symbol': 'acquiree_symbol',
            'acquirer_symbol': 'acquirer_symbol',
            'acquiree_cusip': 'acquiree_cusip',
            'acquirer_cusip': 'acquirer_cusip',
            'acquiree_rate': 'acquiree_rate',
            'acquirer_rate': 'acquirer_rate',
            'ex_date': 'effective_date',
            'payable_date': 'payable_date',
            'deal_type': lambda x: 'stock'
        },
        'alpaca_stock_and_cash': {
            'symbol': 'acquiree_symbol',
            'acquiree_symbol': 'acquiree_symbol',
            'acquirer_symbol': 'acquirer_symbol',
            'acquiree_cusip': 'acquiree_cusip',
            'acquirer_cusip': 'acquirer_cusip',
            'acquiree_rate': 'acquiree_rate',
            'acquirer_rate': 'acquirer_rate',
            'cash_rate': 'cash_rate',
            'ex_date': 'effective_date',
            'payable_date': 'payable_date',
            'deal_type': lambda x: 'mixed'
        },
        'fmp': {
            'symbol': 'targetedSymbol',
            'acquiree_symbol': 'targetedSymbol',
            'acquirer_symbol': 'symbol',  # Assuming the main symbol is the acquirer
            'acquiree_cik': 'targetedCik',
            'acquirer_cik': 'cik',
            'transaction_date': 'transactionDate',
            'accepted_date': 'acceptedDate',
            'link': 'link',
            'deal_type': lambda x: 'acquisition'
        },
        'sharadar_mergerfrom': {
            'symbol': 'ticker',
            'acquiree_symbol': 'ticker',
            'acquirer_symbol': 'contraticker',
            'company_name': 'contraname',
            'ex_date': 'date',
            'deal_value': 'value',
            'deal_type': lambda x: 'mergerfrom'
        },
        'sharadar_mergerto': {
            'symbol': 'ticker',
            'acquiree_symbol': 'contraticker',  # In mergerto, contraticker is the target
            'acquirer_symbol': 'ticker',
            'company_name': 'contraname',
            'ex_date': 'date',
            'deal_value': 'value',
            'deal_type': lambda x: 'mergerto'
        }
    }

    SOURCE_RELIABILITY = {
        'alpaca_stock': 9,
        'alpaca_stock_and_cash': 9,
        'fmp': 8,
        'sharadar_mergerfrom': 7,
        'sharadar_mergerto': 7
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

        # Group by master symbol
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

        if not data:
            return []

        field_mapping = self.FIELD_MAPPINGS.get(source, {})
        unified_mergers = []

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
                for rate_field in ['acquiree_rate', 'acquirer_rate', 'cash_rate', 'deal_value']:
                    if unified_data.get(rate_field) is not None:
                        try:
                            unified_data[rate_field] = Decimal(str(unified_data[rate_field]))
                        except (ValueError, TypeError):
                            unified_data[rate_field] = None

                # Map symbol to master symbol (use acquiree_symbol as the target being acquired)
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

                # Create unified merger
                merger = UnifiedMerger(
                    master_symbol=master_symbol,
                    source=source,
                    symbol_mapping=symbol_mapping,
                    ex_date=unified_data.get('ex_date'),
                    payable_date=unified_data.get('payable_date'),
                    transaction_date=unified_data.get('transaction_date'),
                    accepted_date=unified_data.get('accepted_date'),
                    acquiree_symbol=unified_data.get('acquiree_symbol'),
                    acquirer_symbol=unified_data.get('acquirer_symbol'),
                    company_name=unified_data.get('company_name'),
                    acquiree_cusip=unified_data.get('acquiree_cusip'),
                    acquirer_cusip=unified_data.get('acquirer_cusip'),
                    acquiree_cik=unified_data.get('acquiree_cik'),
                    acquirer_cik=unified_data.get('acquirer_cik'),
                    acquiree_rate=unified_data.get('acquiree_rate'),
                    acquirer_rate=unified_data.get('acquirer_rate'),
                    cash_rate=unified_data.get('cash_rate'),
                    deal_value=unified_data.get('deal_value'),
                    deal_type=unified_data.get('deal_type'),
                    link=unified_data.get('link'),
                    raw_data={source: raw_data},
                    source_list=[source]
                )

                # Calculate data completeness
                merger.data_completeness = self._calculate_completeness_score(merger)
                unified_mergers.append(merger)

            except Exception as e:
                logger.error(f"Error processing merger row from {source}: {e}")
                continue

        return unified_mergers

    def _calculate_completeness_score(self, merger: UnifiedMerger) -> float:
        """Calculate data completeness score."""
        required_fields = ['master_symbol', 'ex_date', 'acquiree_symbol', 'acquirer_symbol']
        optional_fields = ['deal_type', 'cash_rate', 'deal_value', 'company_name', 'link']

        required_score = sum(1 for field in required_fields if getattr(merger, field))
        optional_score = sum(1 for field in optional_fields if getattr(merger, field))

        return (required_score / len(required_fields)) * 0.7 + (optional_score / len(optional_fields)) * 0.3

    def _group_by_master_symbol(self, processed_by_source: Dict[str, List[UnifiedMerger]]) -> Dict[
        str, Dict[str, List[UnifiedMerger]]]:
        """Group mergers by master symbol and source."""

        symbol_groups = defaultdict(lambda: defaultdict(list))

        for source, mergers in processed_by_source.items():
            for merger in mergers:
                symbol_groups[merger.master_symbol][source].append(merger)

        return dict(symbol_groups)

    def _create_match_result(self, master_symbol: str,
                             mergers_by_source: Dict[str, List[UnifiedMerger]]) -> MergerMatchResult:
        """Create a match result for a master symbol."""

        # Flatten mergers from all sources
        all_mergers = []
        for source_mergers in mergers_by_source.values():
            all_mergers.extend(source_mergers)

        if not all_mergers:
            raise ValueError(f"No mergers found for {master_symbol}")

        # Group mergers that are likely the same (by ex_date and companies involved)
        merger_groups = self._group_similar_mergers(all_mergers)

        # Merge the largest group (most common merger)
        largest_group = max(merger_groups, key=len) if merger_groups else []

        if not largest_group:
            raise ValueError(f"No valid merger groups for {master_symbol}")

        merged_merger = self.merge_mergers_with_confidence([largest_group])

        # Calculate match quality
        match_quality = self._calculate_match_quality(largest_group, mergers_by_source)

        match_details = {
            'sources_matched': list(mergers_by_source.keys()),
            'total_mergers': len(all_mergers),
            'merged_mergers': len(largest_group),
            'merger_groups': len(merger_groups)
        }

        return MergerMatchResult(
            master_symbol=master_symbol,
            merged_merger=merged_merger,
            match_quality=match_quality,
            match_details=match_details
        )

    def _group_similar_mergers(self, mergers: List[UnifiedMerger]) -> List[List[UnifiedMerger]]:
        """Group mergers that appear to be the same event."""

        groups = []
        remaining_mergers = mergers.copy()

        while remaining_mergers:
            current = remaining_mergers.pop(0)
            current_group = [current]

            # Find similar mergers
            to_remove = []
            for i, merger in enumerate(remaining_mergers):
                if self._are_mergers_similar(current, merger):
                    current_group.append(merger)
                    to_remove.append(i)

            # Remove grouped mergers
            for i in reversed(to_remove):
                remaining_mergers.pop(i)

            groups.append(current_group)

        return groups

    def _are_mergers_similar(self, merger1: UnifiedMerger, merger2: UnifiedMerger) -> bool:
        """Check if two mergers are likely the same event."""

        # Same ex_date and similar companies
        if merger1.ex_date and merger2.ex_date and merger1.ex_date == merger2.ex_date:
            # Check if companies match (either direction)
            if ((
                    merger1.acquiree_symbol == merger2.acquiree_symbol and merger1.acquirer_symbol == merger2.acquirer_symbol) or
                    (
                            merger1.acquiree_symbol == merger2.acquirer_symbol and merger1.acquirer_symbol == merger2.acquiree_symbol)):
                return True

        return False

    def _calculate_match_quality(self, merged_mergers: List[UnifiedMerger],
                                 all_mergers_by_source: Dict[str, List[UnifiedMerger]]) -> float:
        """Calculate the quality of the match."""

        if not merged_mergers:
            return 0.0

        # Base quality on source agreement
        sources_in_merge = set(merger.source for merger in merged_mergers)
        total_sources = len(all_mergers_by_source)

        source_coverage = len(sources_in_merge) / total_sources if total_sources > 0 else 0

        # Quality score based on coverage and data completeness
        data_completeness = sum(merger.data_completeness for merger in merged_mergers) / len(merged_mergers)

        return (source_coverage * 0.7 + data_completeness * 0.3)

    def merge_mergers_with_confidence(self, merger_groups: List[List[UnifiedMerger]]) -> UnifiedMerger:
        """Merge mergers with confidence analysis."""

        if not merger_groups or not any(merger_groups):
            raise ValueError("No mergers to merge")

        all_mergers = [merger for group in merger_groups for merger in group if merger]

        if not all_mergers:
            raise ValueError("No valid mergers to merge")

        # Collect values by field and source
        field_values = defaultdict(dict)
        source_reliabilities = {}

        for merger in all_mergers:
            source_reliabilities[merger.source] = self.SOURCE_RELIABILITY.get(merger.source, 5) / 10.0

            fields_to_analyze = {
                'ex_date': merger.ex_date,
                'payable_date': merger.payable_date,
                'transaction_date': merger.transaction_date,
                'accepted_date': merger.accepted_date,
                'acquiree_symbol': merger.acquiree_symbol,
                'acquirer_symbol': merger.acquirer_symbol,
                'company_name': merger.company_name,
                'acquiree_cusip': merger.acquiree_cusip,
                'acquirer_cusip': merger.acquirer_cusip,
                'acquiree_cik': merger.acquiree_cik,
                'acquirer_cik': merger.acquirer_cik,
                'acquiree_rate': merger.acquiree_rate,
                'acquirer_rate': merger.acquirer_rate,
                'cash_rate': merger.cash_rate,
                'deal_value': merger.deal_value,
                'deal_type': merger.deal_type,
                'link': merger.link
            }

            for field_name, value in fields_to_analyze.items():
                if value is not None:
                    field_values[field_name][merger.source] = value

        # Calculate confidence for each field
        field_confidences = {}
        for field_name, values_by_source in field_values.items():
            field_confidences[field_name] = self.confidence_calculator.calculate_field_confidence(
                field_name, values_by_source, source_reliabilities
            )

        # Build merged merger
        merged = UnifiedMerger(
            master_symbol=all_mergers[0].master_symbol,
            source='+'.join(sorted(set(merger.source for merger in all_mergers))),
            source_list=[merger.source for merger in all_mergers],
            raw_data={merger.source: merger.raw_data[merger.source] for merger in all_mergers if
                      merger.source in merger.raw_data},
            symbol_mapping=all_mergers[0].symbol_mapping
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

    def _create_debug_entry(self, match_result: MergerMatchResult) -> Dict[str, Any]:
        """Create debug entry for a match result."""

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
            'field_agreements': {
                'ex_date': merged.field_confidences.get('ex_date', FieldConfidence(None, 0, 0, 0, [])).agreement_ratio,
                'acquiree_symbol': merged.field_confidences.get('acquiree_symbol',
                                                                FieldConfidence(None, 0, 0, 0, [])).agreement_ratio,
                'acquirer_symbol': merged.field_confidences.get('acquirer_symbol',
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
                    'acquiree': data.get('acquiree_symbol') or data.get('targetedSymbol') or data.get('ticker'),
                    'acquirer': data.get('acquirer_symbol') or data.get('symbol') or data.get('contraticker'),
                    'date': data.get('effective_date') or data.get('transactionDate') or data.get('date'),
                    'deal_type': data.get('deal_type')
                }
                for source, data in merged.raw_data.items()
            }
        }

    def export_debug_report(self, debug_dir: str):
        """Export debug report to JSON file."""

        debug_file_path = os.path.join(debug_dir, 'merger_debug.json')
        summary_file_path = os.path.join(debug_dir, 'merger_summary.csv')

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
                'acquiree_symbol': result['acquiree_symbol'],
                'acquirer_symbol': result['acquirer_symbol'],
                'deal_type': result['deal_type']
            })

        pd.DataFrame(summary_data).to_csv(summary_file_path, index=False)

        print(f"Debug report exported to {debug_file_path}")
        print(f"Summary CSV exported to {summary_file_path}")

    def export_unified_mergers(self, results, filename):
        """Export unified mergers to CSV file."""

        if not results:
            print("No merger results to export.")
            return None

        os.makedirs(os.path.dirname(filename), exist_ok=True)
        csv_file_path = os.path.join(filename)

        csv_data = []
        for result in results:
            merger = result.merged_merger

            csv_row = {
                'master_symbol': merger.master_symbol,
                'source': merger.source,
                'ex_date': merger.ex_date,
                'payable_date': merger.payable_date,
                'transaction_date': merger.transaction_date,
                'accepted_date': merger.accepted_date,
                'acquiree_symbol': merger.acquiree_symbol,
                'acquirer_symbol': merger.acquirer_symbol,
                'company_name': merger.company_name,
                'acquiree_cusip': merger.acquiree_cusip,
                'acquirer_cusip': merger.acquirer_cusip,
                'acquiree_cik': merger.acquiree_cik,
                'acquirer_cik': merger.acquirer_cik,
                'acquiree_rate': str(merger.acquiree_rate) if merger.acquiree_rate else None,
                'acquirer_rate': str(merger.acquirer_rate) if merger.acquirer_rate else None,
                'cash_rate': str(merger.cash_rate) if merger.cash_rate else None,
                'deal_value': str(merger.deal_value) if merger.deal_value else None,
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


def extract_merger_from_sources(alpaca_data: Dict[str, pd.DataFrame],
                                fmp_data: Dict[str, pd.DataFrame],
                                poly_data: Dict[str, pd.DataFrame],
                                sharadar_data: pd.DataFrame) -> Dict[str, List[Dict[str, Any]]]:
    """Extract merger data from all sources and return in standardized format."""

    extracted_data = {}

    # Extract from Alpaca - look for merger actions
    alpaca_mergers = []
    for action_type, df in alpaca_data.items():
        if 'merger' in action_type.lower() or 'stock_mergers' in action_type.lower():
            if not df.empty:
                # Determine the merger type based on action_type
                source_key = f"alpaca_{action_type.lower()}"
                records = df.to_dict('records')
                for record in records:
                    record['_source_type'] = source_key
                alpaca_mergers.extend(records)

    # Split Alpaca mergers by type for proper field mapping
    extracted_data['alpaca_stock'] = []
    extracted_data['alpaca_stock_and_cash'] = []
    for merger in alpaca_mergers:
        source_type = merger.get('_source_type', 'alpaca_stock')
        if 'cash' in source_type:
            extracted_data['alpaca_stock_and_cash'].append(merger)
        else:
            extracted_data['alpaca_stock'].append(merger)

    # Extract from FMP
    if 'mergers' in fmp_data and not fmp_data['mergers'].empty:
        extracted_data['fmp'] = fmp_data['mergers'].to_dict('records')
    else:
        extracted_data['fmp'] = []

    # Extract from Polygon - no merger data typically
    extracted_data['poly'] = []

    # Extract from Sharadar (filter for merger actions)
    extracted_data['sharadar_mergerfrom'] = []
    extracted_data['sharadar_mergerto'] = []
    if not sharadar_data.empty:
        mergerfrom_records = sharadar_data[sharadar_data['action'] == 'mergerfrom']
        mergerto_records = sharadar_data[sharadar_data['action'] == 'mergerto']
        extracted_data['sharadar_mergerfrom'] = mergerfrom_records.to_dict('records')
        extracted_data['sharadar_mergerto'] = mergerto_records.to_dict('records')

    return extracted_data


def run(alpaca_data: Dict[str, pd.DataFrame],
        fmp_data: Dict[str, pd.DataFrame],
        poly_data: Dict[str, pd.DataFrame],
        sharadar_data: pd.DataFrame):
    """Main function to process mergers from all sources."""

    # Ensure directories exist
    config.ensure_directories()

    # Find master files using configured path
    master_files = glob.glob(os.path.join(config.master_files_dir, '*_MASTER_UPDATED.csv'))
    if not master_files:
        raise FileNotFoundError(f"No master CSV files found in {config.master_files_dir}")

    master_file = max(master_files)  # Get the most recent master file
    print(f"Using master file: {master_file}")

    # Extract merger data from all sources
    print("Extracting merger data from sources...")
    source_data = extract_merger_from_sources(alpaca_data, fmp_data, poly_data, sharadar_data)

    # Print extraction summary
    total_records = sum(len(data) for data in source_data.values())
    for source, data in source_data.items():
        print(f"  - {source}: {len(data)} merger records extracted")

    if total_records == 0:
        print("No merger records found in any source. Skipping merger processing.")
        return

    # Initialize processor
    processor = EnhancedMergerProcessor(master_file)

    # Process all sources
    print("Processing mergers from all sources...")
    results = processor.process_all_sources(source_data)

    # Always export debug report (even if empty)
    processor.export_debug_report(config.debug_dir)

    # Only export CSV if we have results
    if results:
        # Ensure the filename is set properly
        merger_filename = config.unified_mergers_file or 'unified_mergers.csv'
        processor.export_unified_mergers(results, os.path.join(config.data_dir, merger_filename))

        print(f"Processed {len(results)} merger matches")
        for result in results:
            print(f"{result.master_symbol}: Quality {result.match_quality:.2%}, "
                  f"Confidence {result.merged_merger.overall_confidence:.2%}")
    else:
        print("No merger matches found after processing.")
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
class UnifiedCashDividend:
    """Unified cash dividend representation with master symbol mapping."""

    # Core identifiers
    master_symbol: str  # The unified master symbol
    source: str
    symbol_mapping: Optional[SymbolMappingInfo] = None

    # Dates
    ex_date: Optional[str] = None
    record_date: Optional[str] = None
    payment_date: Optional[str] = None
    declaration_date: Optional[str] = None

    # Amounts
    dividend_amount: Optional[Decimal] = None
    adjusted_dividend: Optional[Decimal] = None
    currency: str = "USD"

    # Additional metadata
    frequency: Optional[int] = None
    is_foreign: Optional[bool] = None
    is_special: Optional[bool] = None

    # Confidence tracking
    field_confidences: Dict[str, FieldConfidence] = field(default_factory=dict)
    overall_confidence: float = 1.0
    source_agreement_score: float = 1.0
    data_completeness: float = 1.0

    # Raw data
    raw_data: Dict[str, Any] = field(default_factory=dict)
    source_list: List[str] = field(default_factory=list)


@dataclass
class DividendMatchResult:
    """Result of matching dividends across sources."""
    master_symbol: str
    merged_dividend: UnifiedCashDividend
    match_quality: float  # 0.0 to 1.0
    match_details: Dict[str, Any]


class EnhancedCashDividendProcessor:
    """Enhanced processor with symbol mapping and debug reporting."""

    FIELD_MAPPINGS = {
        'alpaca': {
            'symbol': 'symbol',
            'ex_date': 'ex_date',
            'record_date': 'record_date',
            'payment_date': 'payable_date',
            'dividend_amount': 'rate',
            'is_foreign': 'foreign',
            'is_special': 'special'
        },
        'fmp': {
            'symbol': 'symbol',
            'ex_date': 'date',
            'record_date': 'recordDate',
            'payment_date': 'paymentDate',
            'declaration_date': 'declarationDate',
            'dividend_amount': 'dividend'
        },
        'poly': {
            'symbol': 'ticker',
            'ex_date': 'ex_dividend_date',
            'record_date': 'record_date',
            'payment_date': 'pay_date',
            'declaration_date': 'declaration_date',
            'dividend_amount': 'cash_amount',
            'currency': 'currency',
            'frequency': 'frequency'
        },
        'sharadar': {
            'symbol': 'ticker',
            'ex_date': 'date',
            'dividend_amount': 'value'
        }
    }

    SOURCE_RELIABILITY = {
        'alpaca': 9,
        'poly': 8,
        'fmp': 7,
        'sharadar': 6
    }

    def __init__(self, master_csv_path: str):
        self.confidence_calculator = ConfidenceCalculator()
        self.symbol_mapper = SymbolMapper(master_csv_path)
        self.debug_results = []

    def process_all_sources(self, source_data_dict: Dict[str, List[Dict[str, Any]]]) -> List[DividendMatchResult]:
        """Process dividends from all sources and match by master symbol."""

        # Process each source separately
        processed_by_source = {}
        for source, data in source_data_dict.items():
            processed_by_source[source] = self.process_source_data(source, data)

        # Group by master symbol
        symbol_groups = self._group_by_master_symbol(processed_by_source)

        # Merge and analyze matches
        match_results = []
        for master_symbol, dividends_by_source in symbol_groups.items():
            try:
                match_result = self._create_match_result(master_symbol, dividends_by_source)
                match_results.append(match_result)
                self.debug_results.append(self._create_debug_entry(match_result))
            except Exception as e:
                logger.error(f"Error processing dividends for {master_symbol}: {e}")
                continue

        # Sort debug results by match quality (worst first)
        self.debug_results.sort(key=lambda x: x['match_quality'])

        return match_results

    def process_source_data(self, source: str, data: List[Dict[str, Any]]) -> List[UnifiedCashDividend]:
        """Process dividend data from a specific source with symbol mapping."""

        if not data:
            return []

        field_mapping = self.FIELD_MAPPINGS.get(source, {})
        unified_dividends = []

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

                # Convert dividend amount to Decimal if present
                if unified_data.get('dividend_amount') is not None:
                    try:
                        unified_data['dividend_amount'] = Decimal(str(unified_data['dividend_amount']))
                    except (ValueError, TypeError):
                        unified_data['dividend_amount'] = None

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

                # Create unified dividend
                dividend = UnifiedCashDividend(
                    master_symbol=master_symbol,
                    source=source,
                    symbol_mapping=symbol_mapping,
                    ex_date=unified_data.get('ex_date'),
                    record_date=unified_data.get('record_date'),
                    payment_date=unified_data.get('payment_date'),
                    declaration_date=unified_data.get('declaration_date'),
                    dividend_amount=unified_data.get('dividend_amount'),
                    currency=unified_data.get('currency', 'USD'),
                    frequency=unified_data.get('frequency'),
                    is_foreign=unified_data.get('is_foreign'),
                    is_special=unified_data.get('is_special'),
                    raw_data={source: raw_data},
                    source_list=[source]
                )

                unified_dividends.append(dividend)

            except Exception as e:
                logger.error(f"Error processing dividend row from {source}: {e}")
                continue

        return unified_dividends

    def _group_by_master_symbol(self, processed_by_source: Dict[str, List[UnifiedCashDividend]]) -> Dict[
        str, Dict[str, List[UnifiedCashDividend]]]:
        """Group dividends by master symbol and source."""

        symbol_groups = defaultdict(lambda: defaultdict(list))

        for source, dividends in processed_by_source.items():
            for dividend in dividends:
                symbol_groups[dividend.master_symbol][source].append(dividend)

        return dict(symbol_groups)

    def _create_match_result(self, master_symbol: str,
                             dividends_by_source: Dict[str, List[UnifiedCashDividend]]) -> DividendMatchResult:
        """Create a match result for a master symbol."""

        # Flatten dividends from all sources
        all_dividends = []
        for source_dividends in dividends_by_source.values():
            all_dividends.extend(source_dividends)

        if not all_dividends:
            raise ValueError(f"No dividends found for {master_symbol}")

        # Group dividends that are likely the same (by ex_date and amount)
        dividend_groups = self._group_similar_dividends(all_dividends)

        # Merge the largest group (most common dividend)
        largest_group = max(dividend_groups, key=len) if dividend_groups else []

        if not largest_group:
            raise ValueError(f"No valid dividend groups for {master_symbol}")

        merged_dividend = self.merge_dividends_with_confidence([largest_group])

        # Calculate match quality
        match_quality = self._calculate_match_quality(largest_group, dividends_by_source)

        match_details = {
            'sources_matched': list(dividends_by_source.keys()),
            'total_dividends': len(all_dividends),
            'merged_dividends': len(largest_group),
            'dividend_groups': len(dividend_groups)
        }

        return DividendMatchResult(
            master_symbol=master_symbol,
            merged_dividend=merged_dividend,
            match_quality=match_quality,
            match_details=match_details
        )

    def _group_similar_dividends(self, dividends: List[UnifiedCashDividend]) -> List[List[UnifiedCashDividend]]:
        """Group dividends that appear to be the same event."""

        groups = []
        remaining_dividends = dividends.copy()

        while remaining_dividends:
            current = remaining_dividends.pop(0)
            current_group = [current]

            # Find similar dividends
            to_remove = []
            for i, dividend in enumerate(remaining_dividends):
                if self._are_dividends_similar(current, dividend):
                    current_group.append(dividend)
                    to_remove.append(i)

            # Remove grouped dividends
            for i in reversed(to_remove):
                remaining_dividends.pop(i)

            groups.append(current_group)

        return groups

    def _are_dividends_similar(self, div1: UnifiedCashDividend, div2: UnifiedCashDividend) -> bool:
        """Check if two dividends are likely the same event."""

        # Same ex_date (most important)
        if div1.ex_date and div2.ex_date and div1.ex_date == div2.ex_date:
            # If amounts are present, they should be similar
            if div1.dividend_amount and div2.dividend_amount:
                amount_diff = abs(div1.dividend_amount - div2.dividend_amount)
                if amount_diff / max(div1.dividend_amount, div2.dividend_amount) < 0.01:  # 1% tolerance
                    return True
            else:
                return True  # Same date, missing amounts

        return False

    def _calculate_match_quality(self, merged_dividends: List[UnifiedCashDividend],
                                 all_dividends_by_source: Dict[str, List[UnifiedCashDividend]]) -> float:
        """Calculate the quality of the match."""

        if not merged_dividends:
            return 0.0

        # Base quality on source agreement
        sources_in_merge = set(div.source for div in merged_dividends)
        total_sources = len(all_dividends_by_source)

        source_coverage = len(sources_in_merge) / total_sources if total_sources > 0 else 0

        # Quality score based on coverage and data completeness
        data_completeness = sum(1 for div in merged_dividends if div.dividend_amount) / len(merged_dividends)

        return (source_coverage * 0.7 + data_completeness * 0.3)

    def merge_dividends_with_confidence(self, dividend_groups: List[List[UnifiedCashDividend]]) -> UnifiedCashDividend:
        """Merge dividends with confidence analysis."""

        if not dividend_groups or not any(dividend_groups):
            raise ValueError("No dividends to merge")

        all_dividends = [div for group in dividend_groups for div in group if div]

        if not all_dividends:
            raise ValueError("No valid dividends to merge")

        # Collect values by field and source
        field_values = defaultdict(dict)
        source_reliabilities = {}

        for dividend in all_dividends:
            source_reliabilities[dividend.source] = self.SOURCE_RELIABILITY.get(dividend.source, 5) / 10.0

            fields_to_analyze = {
                'ex_date': dividend.ex_date,
                'record_date': dividend.record_date,
                'payment_date': dividend.payment_date,
                'declaration_date': dividend.declaration_date,
                'dividend_amount': dividend.dividend_amount,
                'adjusted_dividend': dividend.adjusted_dividend,
                'currency': dividend.currency,
                'frequency': dividend.frequency
            }

            for field_name, value in fields_to_analyze.items():
                if value is not None:
                    field_values[field_name][dividend.source] = value

        # Calculate confidence for each field
        field_confidences = {}
        for field_name, values_by_source in field_values.items():
            field_confidences[field_name] = self.confidence_calculator.calculate_field_confidence(
                field_name, values_by_source, source_reliabilities
            )

        # Build merged dividend
        merged = UnifiedCashDividend(
            master_symbol=all_dividends[0].master_symbol,
            source='+'.join(sorted(set(div.source for div in all_dividends))),
            source_list=[div.source for div in all_dividends],
            raw_data={div.source: div.raw_data[div.source] for div in all_dividends if div.source in div.raw_data},
            symbol_mapping=all_dividends[0].symbol_mapping
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

    def _create_debug_entry(self, match_result: DividendMatchResult) -> Dict[str, Any]:
        """Create debug entry for a match result."""

        merged = match_result.merged_dividend

        return {
            'master_symbol': match_result.master_symbol,
            'match_quality': match_result.match_quality,
            'sources': match_result.match_details['sources_matched'],
            'source_count': len(match_result.match_details['sources_matched']),
            'overall_confidence': merged.overall_confidence,
            'source_agreement': merged.source_agreement_score,
            'data_completeness': merged.data_completeness,
            'ex_date': merged.ex_date,
            'dividend_amount': str(merged.dividend_amount) if merged.dividend_amount else None,
            'currency': merged.currency,
            'field_agreements': {
                'ex_date': merged.field_confidences.get('ex_date', FieldConfidence(None, 0, 0, 0, [])).agreement_ratio,
                'dividend_amount': merged.field_confidences.get('dividend_amount',
                                                                FieldConfidence(None, 0, 0, 0, [])).agreement_ratio,
                'currency': merged.field_confidences.get('currency',
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
                    'amount': data.get('rate') or data.get('dividend') or data.get('cash_amount') or data.get('value'),
                    'date': data.get('ex_date') or data.get('date') or data.get('ex_dividend_date')
                }
                for source, data in merged.raw_data.items()
            }
        }

    def export_debug_report(self, debug_dir: str):
        """Export debug report to JSON file."""

        debug_file_path = os.path.join(debug_dir, 'cash_dividends_debug.json')
        summary_file_path = os.path.join(debug_dir, 'cash_dividends_summary.csv')

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
                'dividend_amount': result['dividend_amount']
            })

        pd.DataFrame(summary_data).to_csv(summary_file_path, index=False)

        print(f"Debug report exported to {debug_file_path}")
        print(f"Summary CSV exported to {summary_file_path}")

    def export_unified_dividends(self, results, filename):
        """Export unified dividends to CSV file."""

        os.makedirs(os.path.dirname(filename), exist_ok=True)
        csv_file_path = os.path.join(filename)

        csv_data = []
        for result in results:
            dividend = result.merged_dividend

            csv_row = {
                'master_symbol': dividend.master_symbol,
                'source': dividend.source,
                'ex_date': dividend.ex_date,
                'record_date': dividend.record_date,
                'payable_date': dividend.payment_date,
                'rate': str(dividend.dividend_amount) if dividend.dividend_amount else None,
                'currency': dividend.currency,
                'overall_confidence': dividend.overall_confidence,
                'source_agreement_score': dividend.source_agreement_score,
                'data_completeness': dividend.data_completeness,
                'match_quality': result.match_quality,
                'source_count': len(dividend.source_list),
                'sources': ', '.join(dividend.source_list),
                'mapping_confidence': dividend.symbol_mapping.mapping_confidence if dividend.symbol_mapping else 0.0,
                'unmapped_sources': ', '.join(
                    dividend.symbol_mapping.unmapped_sources) if dividend.symbol_mapping and dividend.symbol_mapping.unmapped_sources else ''
            }
            csv_data.append(csv_row)

        pd.DataFrame(csv_data).to_csv(csv_file_path, index=False)
        print(f"CSV summary exported to {csv_file_path}")

        return csv_file_path


def extract_cash_dividends_from_sources(alpaca_data: Dict[str, pd.DataFrame],
                                        fmp_data: Dict[str, pd.DataFrame],
                                        poly_data: Dict[str, pd.DataFrame],
                                        sharadar_data: pd.DataFrame) -> Dict[str, List[Dict[str, Any]]]:
    """Extract cash dividend data from all sources and return in standardized format."""

    extracted_data = {}

    # Extract from Alpaca
    if 'cash_dividends' in alpaca_data and not alpaca_data['cash_dividends'].empty:
        extracted_data['alpaca'] = alpaca_data['cash_dividends'].to_dict('records')
    else:
        extracted_data['alpaca'] = []

    # Extract from FMP
    if 'dividends' in fmp_data and not fmp_data['dividends'].empty:
        extracted_data['fmp'] = fmp_data['dividends'].to_dict('records')
    else:
        extracted_data['fmp'] = []

    # Extract from Polygon
    if 'dividends' in poly_data and not poly_data['dividends'].empty:
        extracted_data['poly'] = poly_data['dividends'].to_dict('records')
    else:
        extracted_data['poly'] = []

    # Extract from Sharadar (filter for dividend actions)
    if not sharadar_data.empty:
        dividend_records = sharadar_data[sharadar_data['action'] == 'dividend']
        extracted_data['sharadar'] = dividend_records.to_dict('records')
    else:
        extracted_data['sharadar'] = []

    return extracted_data


def run(alpaca_data: Dict[str, pd.DataFrame],
        fmp_data: Dict[str, pd.DataFrame],
        poly_data: Dict[str, pd.DataFrame],
        sharadar_data: pd.DataFrame):
    """Main function to process cash dividends from all sources."""

    # Ensure directories exist
    config.ensure_directories()

    # Find master files using configured path
    master_files = glob.glob(os.path.join(config.master_files_dir, '*_MASTER_UPDATED.csv'))
    if not master_files:
        raise FileNotFoundError(f"No master CSV files found in {config.master_files_dir}")

    master_file = max(master_files)  # Get the most recent master file
    print(f"Using master file: {master_file}")

    # Extract cash dividend data from all sources
    print("Extracting cash dividend data from sources...")
    source_data = extract_cash_dividends_from_sources(alpaca_data, fmp_data, poly_data, sharadar_data)

    # Print extraction summary
    for source, data in source_data.items():
        print(f"  - {source}: {len(data)} cash dividend records extracted")

    # Initialize processor
    processor = EnhancedCashDividendProcessor(master_file)

    # Process all sources
    print("Processing dividends from all sources...")
    results = processor.process_all_sources(source_data)

    # Export to appropriate directories
    processor.export_debug_report(config.debug_dir)
    processor.export_unified_dividends(results, os.path.join(config.data_dir, config.unified_cash_dividends_file))

    print(f"Processed {len(results)} dividend matches")
    for result in results:
        print(f"{result.master_symbol}: Quality {result.match_quality:.2%}, "
              f"Confidence {result.merged_dividend.overall_confidence:.2%}")
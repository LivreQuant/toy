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
class UnifiedStockDividend:
    """Unified stock dividend representation with master symbol mapping."""

    # Core identifiers
    master_symbol: str  # The unified master symbol (company paying stock dividend)
    source: str
    symbol_mapping: Optional[SymbolMappingInfo] = None

    # Dates
    ex_date: Optional[str] = None
    record_date: Optional[str] = None
    payable_date: Optional[str] = None

    # Company information
    dividend_symbol: Optional[str] = None

    # Dividend details
    dividend_ratio: Optional[Decimal] = None  # Additional shares received per share owned

    # Confidence tracking
    field_confidences: Dict[str, FieldConfidence] = field(default_factory=dict)
    overall_confidence: float = 1.0
    source_agreement_score: float = 1.0
    data_completeness: float = 1.0

    # Raw data
    raw_data: Dict[str, Any] = field(default_factory=dict)
    source_list: List[str] = field(default_factory=list)


@dataclass
class StockDividendMatchResult:
    """Result of matching stock dividends across sources."""
    master_symbol: str
    merged_dividend: UnifiedStockDividend
    match_quality: float  # 0.0 to 1.0
    match_details: Dict[str, Any]


class EnhancedStockDividendProcessor:
    """Enhanced processor for stock dividends with symbol mapping and debug reporting."""

    FIELD_MAPPINGS = {
        'alpaca': {
            'symbol': 'symbol',
            'ex_date': 'ex_date',
            'record_date': 'record_date',
            'payable_date': 'payable_date',
            'dividend_symbol': 'symbol',
            'dividend_ratio': 'rate'
        },
        'sharadar': {
            'symbol': 'ticker',
            'ex_date': 'date',
            'dividend_symbol': 'ticker',
            'dividend_ratio': 'value'
        }
    }

    SOURCE_RELIABILITY = {
        'alpaca': 9,
        'sharadar': 7
    }

    def __init__(self, master_csv_path: str):
        self.confidence_calculator = ConfidenceCalculator()
        self.symbol_mapper = SymbolMapper(master_csv_path)
        self.debug_results = []

    def process_all_sources(self, source_data_dict: Dict[str, List[Dict[str, Any]]]) -> List[StockDividendMatchResult]:
        """Process stock dividends from all sources and match by master symbol."""

        # FILTER OUT EMPTY SOURCES
        filtered_source_data = {source: data for source, data in source_data_dict.items() if data}

        if not filtered_source_data:
            return []

        # Process each source separately
        processed_by_source = {}
        for source, data in filtered_source_data.items():
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
                logger.error(f"Error processing stock dividends for {master_symbol}: {e}")
                continue

        # Sort debug results by match quality (worst first)
        self.debug_results.sort(key=lambda x: x['match_quality'])

        return match_results

    def process_source_data(self, source: str, data: List[Dict[str, Any]]) -> List[UnifiedStockDividend]:
        """Process stock dividend data from a specific source with symbol mapping."""
        if source not in self.FIELD_MAPPINGS:
            raise ValueError(f"Unknown source: {source}")

        dividends = []
        mapping = self.FIELD_MAPPINGS[source]

        for record in data:
            try:
                # Map to unified format first
                dividend = self._map_record_to_unified(source, record, mapping)

                # Map to master symbol
                source_symbol = dividend.master_symbol
                master_symbol = self.symbol_mapper.map_to_master_symbol(source, source_symbol)

                if master_symbol:
                    dividend.master_symbol = master_symbol
                    dividend.symbol_mapping = SymbolMappingInfo(
                        master_symbol=master_symbol,
                        source_mappings={source: source_symbol},
                        unmapped_sources=[],
                        mapping_confidence=1.0
                    )
                else:
                    dividend.master_symbol = source_symbol
                    dividend.symbol_mapping = SymbolMappingInfo(
                        master_symbol=source_symbol,
                        source_mappings={},
                        unmapped_sources=[source],
                        mapping_confidence=0.0
                    )

                dividend.data_completeness = self._calculate_completeness_score(dividend)
                dividends.append(dividend)

            except Exception as e:
                logger.error(f"Error processing {source} record: {e}, record: {record}")
                continue

        return dividends

    def _map_record_to_unified(self, source: str, record: Dict[str, Any],
                               mapping: Dict[str, str]) -> UnifiedStockDividend:
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
                elif unified_field == 'dividend_ratio':
                    unified_data[unified_field] = self._safe_decimal_conversion(value)
                else:
                    unified_data[unified_field] = str(value) if value is not None else None

        return UnifiedStockDividend(**unified_data)

    def _safe_decimal_conversion(self, value):
        """Safely convert value to Decimal."""
        if value is None:
            return None
        try:
            return Decimal(str(value))
        except Exception as e:
            logger.warning(f"Could not convert value to Decimal: {value}, error: {e}")
            return None

    def _calculate_completeness_score(self, dividend: UnifiedStockDividend) -> float:
        """Calculate data completeness score."""
        important_fields = [
            dividend.master_symbol, dividend.ex_date, dividend.dividend_symbol, dividend.dividend_ratio
        ]
        filled_fields = sum(1 for field in important_fields if field is not None)
        return filled_fields / len(important_fields)

    def _group_by_master_symbol(self, processed_by_source: Dict[str, List[UnifiedStockDividend]]) -> Dict[
        str, Dict[str, List[UnifiedStockDividend]]]:
        """Group stock dividends by master symbol (dividend paying company) across sources."""
        symbol_groups = defaultdict(lambda: defaultdict(list))

        for source, stock_dividends in processed_by_source.items():
            for dividend in stock_dividends:
                symbol_groups[dividend.master_symbol][source].append(dividend)

        return dict(symbol_groups)

    def _create_match_result(self, master_symbol: str,
                             dividends_by_source: Dict[str, List[UnifiedStockDividend]]) -> StockDividendMatchResult:
        """Create a match result for stock dividends with the same master symbol."""

        # Flatten stock dividends from all sources
        all_dividends = []
        for source_dividends in dividends_by_source.values():
            all_dividends.extend(source_dividends)

        if not all_dividends:
            raise ValueError(f"No stock dividends found for {master_symbol}")

        # Group dividends that are likely the same (by ex_date and ratio)
        dividend_groups = self._group_similar_dividends(all_dividends)

        # Merge the largest group (most common dividend)
        largest_group = max(dividend_groups, key=len) if dividend_groups else []

        if not largest_group:
            raise ValueError(f"No valid stock dividend groups for {master_symbol}")

        merged_dividend = self.merge_dividends_with_confidence([largest_group])

        # Calculate match quality
        match_quality = self._calculate_match_quality(largest_group, dividends_by_source)

        match_details = {
            'sources_matched': list(dividends_by_source.keys()),
            'total_dividends': len(all_dividends),
            'merged_dividends': len(largest_group),
            'dividend_groups': len(dividend_groups)
        }

        return StockDividendMatchResult(
            master_symbol=master_symbol,
            merged_dividend=merged_dividend,
            match_quality=match_quality,
            match_details=match_details
        )

    def _group_similar_dividends(self, dividends: List[UnifiedStockDividend]) -> List[List[UnifiedStockDividend]]:
        """Group stock dividends that appear to be the same event."""
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

    def _are_dividends_similar(self, div1: UnifiedStockDividend, div2: UnifiedStockDividend) -> bool:
        """Check if two stock dividends are likely the same event."""

        # Same ex_date and similar ratio
        if div1.ex_date and div2.ex_date and div1.ex_date == div2.ex_date:
            # Check if ratios are the same (allowing for slight decimal differences)
            if div1.dividend_ratio and div2.dividend_ratio:
                ratio_diff = abs(div1.dividend_ratio - div2.dividend_ratio)
                if ratio_diff < Decimal('0.001'):  # Allow small differences
                    return True
            elif div1.dividend_ratio == div2.dividend_ratio:  # Both None
                return True

        return False

    def _calculate_match_quality(self, merged_dividends: List[UnifiedStockDividend],
                                 all_dividends_by_source: Dict[str, List[UnifiedStockDividend]]) -> float:
        """Calculate the quality of the match."""

        if not merged_dividends:
            return 0.0

        # Base quality on source agreement
        sources_in_merge = set(dividend.source for dividend in merged_dividends)
        total_sources = len(all_dividends_by_source)

        source_coverage = len(sources_in_merge) / total_sources if total_sources > 0 else 0

        # Quality score based on coverage and data completeness
        data_completeness = sum(dividend.data_completeness for dividend in merged_dividends) / len(merged_dividends)

        return (source_coverage * 0.7 + data_completeness * 0.3)

    def merge_dividends_with_confidence(self,
                                        dividend_groups: List[List[UnifiedStockDividend]]) -> UnifiedStockDividend:
        """Merge stock dividends with confidence analysis."""

        if not dividend_groups or not any(dividend_groups):
            raise ValueError("No stock dividends to merge")

        all_dividends = [dividend for group in dividend_groups for dividend in group if dividend]

        if not all_dividends:
            raise ValueError("No valid stock dividends to merge")

        field_values = defaultdict(dict)
        source_reliabilities = {}

        for dividend in all_dividends:
            source_reliabilities[dividend.source] = self.SOURCE_RELIABILITY.get(dividend.source, 5) / 10.0

            fields_to_analyze = {
                'ex_date': dividend.ex_date,
                'record_date': dividend.record_date,
                'payable_date': dividend.payable_date,
                'dividend_symbol': dividend.dividend_symbol,
                'dividend_ratio': dividend.dividend_ratio
            }

            for field_name, value in fields_to_analyze.items():
                if value is not None:
                    field_values[field_name][dividend.source] = value

        field_confidences = {}
        for field_name, values_by_source in field_values.items():
            if field_name in ['dividend_ratio']:
                field_confidences[field_name] = self.confidence_calculator.calculate_field_confidence(
                    field_name.replace('_ratio', '_amount'),
                    values_by_source, source_reliabilities
                )
            else:
                field_confidences[field_name] = self.confidence_calculator.calculate_field_confidence(
                    field_name, values_by_source, source_reliabilities
                )

        merged = UnifiedStockDividend(
            master_symbol=all_dividends[0].master_symbol,
            source='+'.join(sorted(set(dividend.source for dividend in all_dividends))),
            source_list=[dividend.source for dividend in all_dividends],
            raw_data={dividend.source: dividend.raw_data for dividend in all_dividends},
            symbol_mapping=all_dividends[0].symbol_mapping
        )

        for field_name, confidence in field_confidences.items():
            setattr(merged, field_name, confidence.value)

        merged.field_confidences = field_confidences

        field_weights = {
            'dividend_ratio': 0.4,
            'ex_date': 0.3,
            'dividend_symbol': 0.2,
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

    def _create_debug_entry(self, match_result: StockDividendMatchResult) -> Dict[str, Any]:
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
            'dividend_symbol': merged.dividend_symbol,
            'dividend_ratio': str(merged.dividend_ratio) if merged.dividend_ratio else None,
            'field_agreements': {
                'ex_date': merged.field_confidences.get('ex_date', FieldConfidence(None, 0, 0, 0, [])).agreement_ratio,
                'dividend_symbol': merged.field_confidences.get('dividend_symbol',
                                                                FieldConfidence(None, 0, 0, 0, [])).agreement_ratio,
                'dividend_ratio': merged.field_confidences.get('dividend_ratio',
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
                    'ex_date': data.get('ex_date') or data.get('date'),
                    'dividend_ratio': data.get('rate') or data.get('value')
                }
                for source, data in merged.raw_data.items()
            }
        }

    def export_debug_report(self, debug_dir: str):
        """Export debug report to JSON file."""
        debug_file_path = os.path.join(debug_dir, 'stock_dividend_debug.json')
        summary_file_path = os.path.join(debug_dir, 'stock_dividend_summary.csv')

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
                'dividend_ratio': result['dividend_ratio']
            })

        pd.DataFrame(summary_data).to_csv(summary_file_path, index=False)

        print(f"Debug report exported to {debug_file_path}")
        print(f"Summary CSV exported to {summary_file_path}")

    def export_unified_stock_dividends(self, results, filename):
        """Export unified stock dividends to CSV file."""

        if not results:
            print("No stock dividend results to export.")
            return

        csv_data = []
        for result in results:
            dividend = result.merged_dividend

            csv_row = {
                'master_symbol': dividend.master_symbol,
                'source': dividend.source,
                'ex_date': dividend.ex_date,
                'record_date': dividend.record_date,
                'payable_date': dividend.payable_date,
                'dividend_symbol': dividend.dividend_symbol,
                'dividend_ratio': str(dividend.dividend_ratio) if dividend.dividend_ratio else None,
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

        pd.DataFrame(csv_data).to_csv(filename, index=False)
        print(f"Unified stock dividends exported to {filename}")


def extract_stock_dividend_from_sources(alpaca_data: Dict[str, pd.DataFrame],
                                        fmp_data: Dict[str, pd.DataFrame],
                                        poly_data: Dict[str, pd.DataFrame],
                                        sharadar_data: pd.DataFrame) -> Dict[str, List[Dict[str, Any]]]:
    """Extract stock dividend data from all sources."""
    extracted_data = {}

    # Extract from Alpaca - look for stock dividend actions
    alpaca_stock_dividends = []
    for action_type, df in alpaca_data.items():
        if 'stock_dividend' in action_type.lower():
            if not df.empty:
                alpaca_stock_dividends.extend(df.to_dict('records'))
    extracted_data['alpaca'] = alpaca_stock_dividends

    # Extract from FMP - no stock dividend data typically
    extracted_data['fmp'] = []

    # Extract from Polygon - no stock dividend data typically
    extracted_data['poly'] = []

    # Extract from Sharadar (filter for stock dividend actions)
    if not sharadar_data.empty:
        stock_dividend_records = sharadar_data[sharadar_data['action'] == 'stockdividend']
        extracted_data['sharadar'] = stock_dividend_records.to_dict('records')
    else:
        extracted_data['sharadar'] = []

    return extracted_data


def run(alpaca_data: Dict[str, pd.DataFrame],
        fmp_data: Dict[str, pd.DataFrame],
        poly_data: Dict[str, pd.DataFrame],
        sharadar_data: pd.DataFrame):
    """Main function to process stock dividends from all sources."""

    # Ensure directories exist
    config.ensure_directories()

    # Find master files using configured path
    master_files = glob.glob(os.path.join(config.master_files_dir, '*_MASTER_UPDATED.csv'))
    if not master_files:
        raise FileNotFoundError(f"No master CSV files found in {config.master_files_dir}")

    master_file = max(master_files)  # Get the most recent master file
    print(f"Using master file: {master_file}")

    # Extract stock dividend data from all sources
    print("Extracting stock dividend data from sources...")
    source_data = extract_stock_dividend_from_sources(alpaca_data, fmp_data, poly_data, sharadar_data)

    # Print extraction summary
    total_records = sum(len(data) for data in source_data.values())
    for source, data in source_data.items():
        print(f"  - {source}: {len(data)} stock dividend records extracted")

    if total_records == 0:
        print("No stock dividend records found in any source. Skipping stock dividend processing.")
        return

    # Initialize processor
    processor = EnhancedStockDividendProcessor(master_file)

    # Process all sources
    print("Processing stock dividends from all sources...")
    results = processor.process_all_sources(source_data)

    # Always export debug report (even if empty)
    processor.export_debug_report(config.debug_dir)

    # Only export CSV if we have results
    if results:
        # Ensure the filename is set properly
        stock_dividend_filename = config.unified_stock_dividends_file or 'unified_stock_dividends.csv'
        processor.export_unified_stock_dividends(results, os.path.join(config.data_dir, stock_dividend_filename))

        print(f"Processed {len(results)} stock dividend matches")
        for result in results:
            print(f"{result.master_symbol}: Quality {result.match_quality:.2%}, "
                  f"Confidence {result.merged_dividend.overall_confidence:.2%}")
    else:
        print("No stock dividend matches found after processing.")


if __name__ == "__main__":
    # Test run with sample data
    config.ensure_directories()

    # Find master files using configured path
    master_files = glob.glob(os.path.join(config.master_files_dir, '*.csv'))
    if not master_files:
        raise FileNotFoundError(f"No master CSV files found in {config.master_files_dir}")

    master_file = max(master_files)
    print(f"Using master file: {master_file}")

    processor = EnhancedStockDividendProcessor(master_file)

    # Sample test data
    source_data = {
        'alpaca': [{'symbol': 'AAPL', 'ex_date': '2025-08-15', 'rate': '0.05'}],
        'sharadar': [{'ticker': 'AAPL', 'date': '2025-08-15', 'value': '0.05'}]
    }

    results = processor.process_all_sources(source_data)
    processor.export_debug_report(config.debug_dir)
    if results:
        stock_dividend_filename = config.unified_stock_dividends_file or 'unified_stock_dividends.csv'
        processor.export_unified_stock_dividends(results, os.path.join(config.data_dir, stock_dividend_filename))

    print(f"Processed {len(results)} stock dividend matches")
    for result in results:
        print(f"{result.master_symbol}: Quality {result.match_quality:.2%}, "
              f"Confidence {result.merged_dividend.overall_confidence:.2%}")
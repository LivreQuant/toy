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
        }
    }

    SOURCE_RELIABILITY = {
        'alpaca': 9
    }

    def __init__(self, master_csv_path: str):
        self.confidence_calculator = ConfidenceCalculator()
        self.symbol_mapper = SymbolMapper(master_csv_path)
        self.debug_results = []

    def process_all_sources(self, source_data_dict: Dict[str, List[Dict[str, Any]]]) -> List[StockDividendMatchResult]:
        """Process stock dividends from all sources and match by master symbol."""

        # Process each source separately
        processed_by_source = {}
        for source, data in source_data_dict.items():
            processed_by_source[source] = self.process_source_data(source, data)

        # Group by master symbol (company paying stock dividend)
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

        stock_dividends = []
        mapping = self.FIELD_MAPPINGS[source]

        for record in data:
            try:
                # Map to unified format first
                dividend = self._map_record_to_unified(source, record, mapping)

                # Map to master symbol (dividend paying company)
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
                stock_dividends.append(dividend)

            except Exception as e:
                logger.error(f"Error processing {source} record: {e}, record: {record}")
                continue

        return stock_dividends

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
                elif unified_field in ['dividend_ratio']:
                    unified_data[unified_field] = self._normalize_decimal_value(value)
                else:
                    unified_data[unified_field] = str(value) if value is not None else None

        return UnifiedStockDividend(**unified_data)

    def _normalize_decimal_value(self, value: Any) -> Optional[Decimal]:
        """Normalize numeric values to Decimal for precision."""
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
        symbol_groups = {}

        for source, stock_dividends in processed_by_source.items():
            for dividend in stock_dividends:
                master_symbol = dividend.master_symbol
                if master_symbol not in symbol_groups:
                    symbol_groups[master_symbol] = {}
                if source not in symbol_groups[master_symbol]:
                    symbol_groups[master_symbol][source] = []
                symbol_groups[master_symbol][source].append(dividend)

        return symbol_groups

    def _create_match_result(self, master_symbol: str,
                             dividends_by_source: Dict[str, List[UnifiedStockDividend]]) -> StockDividendMatchResult:
        """Create a match result for stock dividends with the same master symbol."""

        representative_dividends = []
        for source, stock_dividends in dividends_by_source.items():
            if stock_dividends:
                representative_dividends.append(stock_dividends[0])

        merged = self.merge_dividends_with_confidence([representative_dividends])
        match_quality = self._calculate_match_quality(dividends_by_source, merged)

        match_details = {
            'sources_matched': list(dividends_by_source.keys()),
            'total_dividends': sum(len(stock_dividends) for stock_dividends in dividends_by_source.values()),
            'date_agreement': merged.field_confidences.get('ex_date',
                                                           FieldConfidence(None, 0, 0, 0, [])).agreement_ratio,
            'symbol_agreement': merged.field_confidences.get('dividend_symbol',
                                                             FieldConfidence(None, 0, 0, 0, [])).agreement_ratio,
            'ratio_agreement': merged.field_confidences.get('dividend_ratio',
                                                            FieldConfidence(None, 0, 0, 0, [])).agreement_ratio,
        }

        return StockDividendMatchResult(
            master_symbol=master_symbol,
            merged_dividend=merged,
            match_quality=match_quality,
            match_details=match_details
        )

    def _calculate_match_quality(self, dividends_by_source: Dict[str, List[UnifiedStockDividend]],
                                 merged: UnifiedStockDividend) -> float:
        """Calculate overall match quality for debugging."""
        source_count = len(dividends_by_source)
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

    def _create_debug_entry(self, match_result: StockDividendMatchResult) -> Dict[str, Any]:
        """Create a debug entry for a match result."""
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
                    'symbol': data.get('symbol'),
                    'ex_date': data.get('ex_date'),
                    'dividend_ratio': data.get('rate')
                }
                for source, data in merged.raw_data.items()
            }
        }

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

    def export_debug_report(self, debug_dir: str, filename: str = None):
        """Export debug results to debug directory."""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d")
            filename = f'stock_dividends_debug_report_{timestamp}.json'

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
                'symbol_agreement': result['field_agreements']['dividend_symbol'],
                'ratio_agreement': result['field_agreements']['dividend_ratio'],
                'sources': ', '.join(result['sources']),
                'dividend_symbol': result['dividend_symbol'],
                'dividend_ratio': result['dividend_ratio'],
                'has_disagreements': len(result['disagreements']) > 0,
                'mapping_confidence': result['symbol_mapping_info']['mapping_confidence']
            })

        pd.DataFrame(summary_data).to_csv(summary_file_path, index=False)
        print(f"Debug report exported to {debug_file_path}")
        print(f"Summary CSV exported to {summary_file_path}")

    def export_unified_stock_dividends(self, results: List[StockDividendMatchResult], data_dir: str,
                                       filename: str = None):
        """Export unified stock dividend results to data directory."""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d")
            filename = f'unified_stock_dividends_{timestamp}.csv'

        os.makedirs(data_dir, exist_ok=True)
        csv_file_path = os.path.join(data_dir, filename)

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

    processor = EnhancedStockDividendProcessor(master_file)

    source_data = {
        'alpaca': [{'symbol': 'AAPL', 'ex_date': '2025-08-15', 'rate': '0.05'}]
    }

    results = processor.process_all_sources(source_data)
    processor.export_debug_report(debug_dir)
    processor.export_unified_stock_dividends(results, data_dir)

    print(f"Processed {len(results)} stock dividend matches")
    for result in results:
        print(f"{result.master_symbol}: Quality {result.match_quality:.2%}, "
              f"Confidence {result.merged_dividend.overall_confidence:.2%}")
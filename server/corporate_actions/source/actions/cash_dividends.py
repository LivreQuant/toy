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
class UnifiedCashDividend:
    """Unified cash dividend representation with master symbol mapping."""

    # Core identifiers
    master_symbol: str  # The unified master symbol
    source: str
    #source_id: Optional[str] = None
    symbol_mapping: Optional[SymbolMappingInfo] = None

    # Dates
    ex_date: Optional[str] = None
    record_date: Optional[str] = None
    payment_date: Optional[str] = None
    declaration_date: Optional[str] = None
    #process_date: Optional[str] = None

    # Amounts
    dividend_amount: Optional[Decimal] = None
    adjusted_dividend: Optional[Decimal] = None
    currency: str = "USD"

    # Additional metadata
    frequency: Optional[int] = None
    #dividend_type: Optional[str] = None
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
            #'declaration_date': 'process_date',
            'dividend_amount': 'rate',
            #'source_id': 'id',
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
            #'adjusted_dividend': 'adjDividend'
        },
        'poly': {
            'symbol': 'ticker',
            'ex_date': 'ex_dividend_date',
            'record_date': 'record_date',
            'payment_date': 'pay_date',
            'declaration_date': 'declaration_date',
            'dividend_amount': 'cash_amount',
            'currency': 'currency',
            'frequency': 'frequency',
            #'dividend_type': 'dividend_type',
            #'source_id': 'id'
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
        if source not in self.FIELD_MAPPINGS:
            raise ValueError(f"Unknown source: {source}")

        dividends = []
        mapping = self.FIELD_MAPPINGS[source]

        for record in data:
            try:
                # Map to unified format first
                dividend = self._map_record_to_unified(source, record, mapping)

                # Map to master symbol
                source_symbol = dividend.master_symbol  # This was originally 'symbol'
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
                    # Keep original symbol but mark as unmapped
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
                               mapping: Dict[str, str]) -> UnifiedCashDividend:
        """Map a single record from source format to unified format."""
        unified_data = {
            'master_symbol': '',  # Will be set later
            'source': source,
            'raw_data': record.copy()
        }

        for unified_field, source_field in mapping.items():
            if source_field in record and record[source_field] is not None:
                value = record[source_field]

                if unified_field == 'symbol':
                    unified_data['master_symbol'] = str(value)
                elif unified_field in ['dividend_amount', 'adjusted_dividend']:
                    unified_data[unified_field] = self._normalize_decimal_value(value)
                elif unified_field == 'currency':
                    unified_data[unified_field] = str(value).upper()
                elif unified_field in ['is_foreign', 'is_special']:
                    unified_data[unified_field] = bool(value)
                elif unified_field == 'frequency':
                    unified_data[unified_field] = int(value) if value is not None else None
                else:
                    unified_data[unified_field] = value

        if 'currency' not in unified_data:
            unified_data['currency'] = 'USD'

        return UnifiedCashDividend(**unified_data)

    def _normalize_decimal_value(self, value: Any) -> Optional[Decimal]:
        """Normalize dividend amounts to Decimal for precision."""
        if value is None:
            return None
        try:
            return Decimal(str(value))
        except Exception as e:
            logger.warning(f"Could not convert value to Decimal: {value}, error: {e}")
            return None

    def _calculate_completeness_score(self, dividend: UnifiedCashDividend) -> float:
        """Calculate data completeness score."""
        important_fields = [
            dividend.master_symbol, dividend.ex_date, dividend.dividend_amount,
            dividend.record_date, dividend.payment_date, dividend.currency
        ]
        filled_fields = sum(1 for field in important_fields if field is not None)
        return filled_fields / len(important_fields)

    def _group_by_master_symbol(self, processed_by_source: Dict[str, List[UnifiedCashDividend]]) -> Dict[
        str, Dict[str, List[UnifiedCashDividend]]]:
        """Group dividends by master symbol across sources."""
        symbol_groups = {}

        for source, dividends in processed_by_source.items():
            for dividend in dividends:
                master_symbol = dividend.master_symbol
                if master_symbol not in symbol_groups:
                    symbol_groups[master_symbol] = {}
                if source not in symbol_groups[master_symbol]:
                    symbol_groups[master_symbol][source] = []
                symbol_groups[master_symbol][source].append(dividend)

        return symbol_groups

    def _create_match_result(self, master_symbol: str,
                             dividends_by_source: Dict[str, List[UnifiedCashDividend]]) -> DividendMatchResult:
        """Create a match result for dividends with the same master symbol."""

        # For now, take the first dividend from each source
        # In practice, you might want more sophisticated matching by dates
        representative_dividends = []
        for source, dividends in dividends_by_source.items():
            if dividends:
                representative_dividends.append(dividends[0])

        # Merge with confidence analysis
        merged = self.merge_dividends_with_confidence([representative_dividends])

        # Calculate match quality
        match_quality = self._calculate_match_quality(dividends_by_source, merged)

        # Create match details
        match_details = {
            'sources_matched': list(dividends_by_source.keys()),
            'total_dividends': sum(len(divs) for divs in dividends_by_source.values()),
            'date_agreement': merged.field_confidences.get('ex_date',
                                                           FieldConfidence(None, 0, 0, 0, [])).agreement_ratio,
            'amount_agreement': merged.field_confidences.get('dividend_amount',
                                                             FieldConfidence(None, 0, 0, 0, [])).agreement_ratio,
            'currency_agreement': merged.field_confidences.get('currency',
                                                               FieldConfidence(None, 0, 0, 0, [])).agreement_ratio,
        }

        return DividendMatchResult(
            master_symbol=master_symbol,
            merged_dividend=merged,
            match_quality=match_quality,
            match_details=match_details
        )

    def _calculate_match_quality(self, dividends_by_source: Dict[str, List[UnifiedCashDividend]],
                                 merged: UnifiedCashDividend) -> float:
        """Calculate overall match quality for debugging."""

        # Base quality on number of sources
        source_count = len(dividends_by_source)
        source_score = min(1.0, source_count / 4.0)  # Max quality with 4+ sources

        # Factor in confidence scores
        confidence_score = merged.overall_confidence
        agreement_score = merged.source_agreement_score

        # Factor in symbol mapping success
        mapping_score = merged.symbol_mapping.mapping_confidence if merged.symbol_mapping else 0.0

        # Weighted average
        quality = (
                source_score * 0.2 +
                confidence_score * 0.4 +
                agreement_score * 0.3 +
                mapping_score * 0.1
        )

        return quality

    def _create_debug_entry(self, match_result: DividendMatchResult) -> Dict[str, Any]:
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
                'frequency': dividend.frequency,
                #'dividend_type': dividend.dividend_type
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
            raw_data={div.source: div.raw_data for div in all_dividends},
            symbol_mapping=all_dividends[0].symbol_mapping
        )

        # Set field values from confidence analysis
        for field_name, confidence in field_confidences.items():
            setattr(merged, field_name, confidence.value)

        merged.field_confidences = field_confidences

        # Calculate overall metrics
        field_weights = {
            'dividend_amount': 0.4,
            'ex_date': 0.3,
            'currency': 0.1,
            'record_date': 0.1,
            'payment_date': 0.05,
            'declaration_date': 0.05
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
            filename = f'dividend_debug_report_{timestamp}.json'

        # Ensure debug directory exists
        os.makedirs(debug_dir, exist_ok=True)

        debug_file_path = os.path.join(debug_dir, filename)
        with open(debug_file_path, 'w') as f:
            json.dump(self.debug_results, f, indent=2)

        # Also create a summary CSV for quick review
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
                'amount_agreement': result['field_agreements']['dividend_amount'],
                'sources': ', '.join(result['sources']),
                'has_disagreements': len(result['disagreements']) > 0,
                'mapping_confidence': result['symbol_mapping_info']['mapping_confidence']
            })

        pd.DataFrame(summary_data).to_csv(summary_file_path, index=False)
        print(f"Debug report exported to {debug_file_path}")
        print(f"Summary CSV exported to {summary_file_path}")

    def export_unified_dividends(self, results: List[DividendMatchResult], data_dir: str, filename: str = None):
        """Export unified dividend results to data directory."""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d")
            filename = f'unified_cash_dividends_{timestamp}.json'

        # Ensure data directory exists
        os.makedirs(data_dir, exist_ok=True)

        # Convert results to serializable format
        unified_data = []
        for result in results:
            dividend = result.merged_dividend

            # Convert Decimal fields to strings for JSON serialization
            dividend_dict = {
                'master_symbol': dividend.master_symbol,
                'source': dividend.source,
                # 'source_id': dividend.source_id,
                'ex_date': dividend.ex_date,
                'record_date': dividend.record_date,
                'payment_date': dividend.payment_date,
                'declaration_date': dividend.declaration_date,
                #'process_date': dividend.process_date,
                'dividend_amount': str(dividend.dividend_amount) if dividend.dividend_amount else None,
                'adjusted_dividend': str(dividend.adjusted_dividend) if dividend.adjusted_dividend else None,
                'currency': dividend.currency,
                'frequency': dividend.frequency,
                #'dividend_type': dividend.dividend_type,
                'is_foreign': dividend.is_foreign,
                'is_special': dividend.is_special,
                'overall_confidence': dividend.overall_confidence,
                'source_agreement_score': dividend.source_agreement_score,
                'data_completeness': dividend.data_completeness,
                'source_list': dividend.source_list,
                'match_quality': result.match_quality,
                'field_confidences': {
                    field: {
                        'value': str(conf.value) if isinstance(conf.value, Decimal) else conf.value,
                        'confidence_score': conf.confidence_score,
                        'source_count': conf.source_count,
                        'agreement_ratio': conf.agreement_ratio,
                        'disagreement_details': conf.disagreement_details
                    }
                    for field, conf in dividend.field_confidences.items()
                },
                'symbol_mapping': {
                    'master_symbol': dividend.symbol_mapping.master_symbol if dividend.symbol_mapping else dividend.master_symbol,
                    'source_mappings': dividend.symbol_mapping.source_mappings if dividend.symbol_mapping else {},
                    'unmapped_sources': dividend.symbol_mapping.unmapped_sources if dividend.symbol_mapping else [],
                    'mapping_confidence': dividend.symbol_mapping.mapping_confidence if dividend.symbol_mapping else 0.0
                },
                'raw_data': dividend.raw_data
            }

            unified_data.append(dividend_dict)

        # Save to JSON
        #json_file_path = os.path.join(data_dir, filename)
        #with open(json_file_path, 'w') as f:
        #    json.dump(unified_data, f, indent=2)

        # Also save as CSV for easier analysis
        csv_filename = filename.replace('.json', '.csv')
        csv_file_path = os.path.join(data_dir, csv_filename)

        # Flatten for CSV export
        csv_data = []
        for item in unified_data:
            csv_row = {
                'master_symbol': item['master_symbol'],
                'source': item['source'],
                #'source_id': item['source_id'],
                'ex_date': item['ex_date'],
                'record_date': item['record_date'],
                'payment_date': item['payment_date'],
                'declaration_date': item['declaration_date'],
                'dividend_amount': item['dividend_amount'],
                'adjusted_dividend': item['adjusted_dividend'],
                'currency': item['currency'],
                'frequency': item['frequency'],
                #'dividend_type': item['dividend_type'],
                'is_foreign': item['is_foreign'],
                'is_special': item['is_special'],
                'overall_confidence': item['overall_confidence'],
                'source_agreement_score': item['source_agreement_score'],
                'data_completeness': item['data_completeness'],
                'match_quality': item['match_quality'],
                'source_count': len(item['source_list']),
                'sources': ', '.join(item['source_list']),
                'mapping_confidence': item['symbol_mapping']['mapping_confidence'],
                'unmapped_sources': ', '.join(item['symbol_mapping']['unmapped_sources']) if item['symbol_mapping'][
                    'unmapped_sources'] else ''
            }
            csv_data.append(csv_row)

        pd.DataFrame(csv_data).to_csv(csv_file_path, index=False)

        #print(f"Unified dividends exported to {json_file_path}")
        print(f"CSV summary exported to {csv_file_path}")

        return csv_file_path


# Usage example
if __name__ == "__main__":

    base_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.join(base_dir, '../..')

    data_dir = os.path.join(parent_dir, "data")
    debug_dir = os.path.join(parent_dir, "debug")
    example_dir = os.path.join(parent_dir, "example")

    # Fix the glob pattern - remove leading slash
    master_files = glob.glob(os.path.join(example_dir, 'master/*.csv'))
    if not master_files:
        raise FileNotFoundError("No master CSV files found in example/master/ directory")

    master_file = max(master_files)  # Get the most recent master file
    print(f"Using master file: {master_file}")

    processor = EnhancedCashDividendProcessor(master_file)

    # Example data from different sources
    source_data = {
        'alpaca': [{'symbol': 'AAPL', 'ex_date': '2025-08-15', 'payable_date': '2025-08-22', 'rate': 0.25}],
        'fmp': [{'symbol': 'AAPL', 'date': '2025-08-15', 'dividend': 0.24, 'paymentDate': '2025-08-23'}],
        'poly': [{'ticker': 'AAPL', 'ex_dividend_date': '2025-08-15', 'cash_amount': 0.25}]
    }

    results = processor.process_all_sources(source_data)

    # Export to appropriate directories
    processor.export_debug_report(debug_dir)
    processor.export_unified_dividends(results, data_dir)

    print(f"Processed {len(results)} dividend matches")
    for result in results:
        print(f"{result.master_symbol}: Quality {result.match_quality:.2%}, "
              f"Confidence {result.merged_dividend.overall_confidence:.2%}")
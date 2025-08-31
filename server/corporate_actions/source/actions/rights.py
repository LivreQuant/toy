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
class UnifiedRightsOffering:
    """Unified rights offering representation with master symbol mapping."""

    # Core identifiers
    master_symbol: str  # The unified master symbol (company offering rights)
    source: str
    symbol_mapping: Optional[SymbolMappingInfo] = None

    # Dates
    ex_date: Optional[str] = None
    record_date: Optional[str] = None
    payable_date: Optional[str] = None

    # Company information
    issuing_symbol: Optional[str] = None

    # Rights details
    rights_symbol: Optional[str] = None
    rights_cusip: Optional[str] = None
    rights_ratio: Optional[Decimal] = None  # Rights received per share owned
    subscription_price: Optional[Decimal] = None  # Price to exercise rights

    # Confidence tracking
    field_confidences: Dict[str, FieldConfidence] = field(default_factory=dict)
    overall_confidence: float = 1.0
    source_agreement_score: float = 1.0
    data_completeness: float = 1.0

    # Raw data
    raw_data: Dict[str, Any] = field(default_factory=dict)
    source_list: List[str] = field(default_factory=list)


@dataclass
class RightsOfferingMatchResult:
    """Result of matching rights offerings across sources."""
    master_symbol: str
    merged_rights: UnifiedRightsOffering
    match_quality: float  # 0.0 to 1.0
    match_details: Dict[str, Any]


class EnhancedRightsOfferingProcessor:
    """Enhanced processor for rights offerings with symbol mapping and debug reporting."""

    FIELD_MAPPINGS = {
        'alpaca': {
            'symbol': 'symbol',
            'ex_date': 'ex_date',
            'record_date': 'record_date',
            'payable_date': 'payable_date',
            'issuing_symbol': 'symbol',
            'rights_symbol': 'new_symbol',
            'rights_cusip': 'new_cusip',
            'rights_ratio': 'rate',
            'subscription_price': 'price'
        }
    }

    SOURCE_RELIABILITY = {
        'alpaca': 9
    }

    def __init__(self, master_csv_path: str):
        self.confidence_calculator = ConfidenceCalculator()
        self.symbol_mapper = SymbolMapper(master_csv_path)
        self.debug_results = []

    def process_all_sources(self, source_data_dict: Dict[str, List[Dict[str, Any]]]) -> List[RightsOfferingMatchResult]:
        """Process rights offerings from all sources and match by master symbol."""

        # Process each source separately
        processed_by_source = {}
        for source, data in source_data_dict.items():
            processed_by_source[source] = self.process_source_data(source, data)

        # Group by master symbol (company issuing rights)
        symbol_groups = self._group_by_master_symbol(processed_by_source)

        # Merge and analyze matches
        match_results = []
        for master_symbol, rights_by_source in symbol_groups.items():
            try:
                match_result = self._create_match_result(master_symbol, rights_by_source)
                match_results.append(match_result)
                self.debug_results.append(self._create_debug_entry(match_result))
            except Exception as e:
                logger.error(f"Error processing rights offerings for {master_symbol}: {e}")
                continue

        # Sort debug results by match quality (worst first)
        self.debug_results.sort(key=lambda x: x['match_quality'])

        return match_results

    def process_source_data(self, source: str, data: List[Dict[str, Any]]) -> List[UnifiedRightsOffering]:
        """Process rights offering data from a specific source with symbol mapping."""
        if source not in self.FIELD_MAPPINGS:
            raise ValueError(f"Unknown source: {source}")

        rights_offerings = []
        mapping = self.FIELD_MAPPINGS[source]

        for record in data:
            try:
                # Map to unified format first
                rights = self._map_record_to_unified(source, record, mapping)

                # Map to master symbol (issuing company)
                source_symbol = rights.master_symbol
                master_symbol = self.symbol_mapper.map_to_master_symbol(source, source_symbol)

                if master_symbol:
                    rights.master_symbol = master_symbol
                    rights.symbol_mapping = SymbolMappingInfo(
                        master_symbol=master_symbol,
                        source_mappings={source: source_symbol},
                        unmapped_sources=[],
                        mapping_confidence=1.0
                    )
                else:
                    rights.master_symbol = source_symbol
                    rights.symbol_mapping = SymbolMappingInfo(
                        master_symbol=source_symbol,
                        source_mappings={},
                        unmapped_sources=[source],
                        mapping_confidence=0.0
                    )

                rights.data_completeness = self._calculate_completeness_score(rights)
                rights_offerings.append(rights)

            except Exception as e:
                logger.error(f"Error processing {source} record: {e}, record: {record}")
                continue

        return rights_offerings

    def _map_record_to_unified(self, source: str, record: Dict[str, Any],
                               mapping: Dict[str, str]) -> UnifiedRightsOffering:
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
                elif unified_field in ['rights_ratio', 'subscription_price']:
                    unified_data[unified_field] = self._normalize_decimal_value(value)
                else:
                    unified_data[unified_field] = str(value) if value is not None else None

        return UnifiedRightsOffering(**unified_data)

    def _normalize_decimal_value(self, value: Any) -> Optional[Decimal]:
        """Normalize numeric values to Decimal for precision."""
        if value is None:
            return None
        try:
            return Decimal(str(value))
        except Exception as e:
            logger.warning(f"Could not convert value to Decimal: {value}, error: {e}")
            return None

    def _calculate_completeness_score(self, rights: UnifiedRightsOffering) -> float:
        """Calculate data completeness score."""
        important_fields = [
            rights.master_symbol, rights.ex_date, rights.issuing_symbol, rights.rights_symbol
        ]
        filled_fields = sum(1 for field in important_fields if field is not None)
        return filled_fields / len(important_fields)

    def _group_by_master_symbol(self, processed_by_source: Dict[str, List[UnifiedRightsOffering]]) -> Dict[
        str, Dict[str, List[UnifiedRightsOffering]]]:
        """Group rights offerings by master symbol (issuing company) across sources."""
        symbol_groups = {}

        for source, rights_offerings in processed_by_source.items():
            for rights in rights_offerings:
                master_symbol = rights.master_symbol
                if master_symbol not in symbol_groups:
                    symbol_groups[master_symbol] = {}
                if source not in symbol_groups[master_symbol]:
                    symbol_groups[master_symbol][source] = []
                symbol_groups[master_symbol][source].append(rights)

        return symbol_groups

    def _create_match_result(self, master_symbol: str,
                             rights_by_source: Dict[str, List[UnifiedRightsOffering]]) -> RightsOfferingMatchResult:
        """Create a match result for rights offerings with the same master symbol."""

        representative_rights = []
        for source, rights_offerings in rights_by_source.items():
            if rights_offerings:
                representative_rights.append(rights_offerings[0])

        merged = self.merge_rights_with_confidence([representative_rights])
        match_quality = self._calculate_match_quality(rights_by_source, merged)

        match_details = {
            'sources_matched': list(rights_by_source.keys()),
            'total_rights': sum(len(rights_offerings) for rights_offerings in rights_by_source.values()),
            'date_agreement': merged.field_confidences.get('ex_date',
                                                           FieldConfidence(None, 0, 0, 0, [])).agreement_ratio,
            'rights_symbol_agreement': merged.field_confidences.get('rights_symbol',
                                                                    FieldConfidence(None, 0, 0, 0, [])).agreement_ratio,
            'ratio_agreement': merged.field_confidences.get('rights_ratio',
                                                            FieldConfidence(None, 0, 0, 0, [])).agreement_ratio,
        }

        return RightsOfferingMatchResult(
            master_symbol=master_symbol,
            merged_rights=merged,
            match_quality=match_quality,
            match_details=match_details
        )

    def _calculate_match_quality(self, rights_by_source: Dict[str, List[UnifiedRightsOffering]],
                                 merged: UnifiedRightsOffering) -> float:
        """Calculate overall match quality for debugging."""
        source_count = len(rights_by_source)
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

    def _create_debug_entry(self, match_result: RightsOfferingMatchResult) -> Dict[str, Any]:
        """Create a debug entry for a match result."""
        merged = match_result.merged_rights

        return {
            'master_symbol': match_result.master_symbol,
            'match_quality': match_result.match_quality,
            'sources': match_result.match_details['sources_matched'],
            'source_count': len(match_result.match_details['sources_matched']),
            'overall_confidence': merged.overall_confidence,
            'source_agreement': merged.source_agreement_score,
            'data_completeness': merged.data_completeness,
            'ex_date': merged.ex_date,
            'issuing_symbol': merged.issuing_symbol,
            'rights_symbol': merged.rights_symbol,
            'rights_ratio': str(merged.rights_ratio) if merged.rights_ratio else None,
            'subscription_price': str(merged.subscription_price) if merged.subscription_price else None,
            'field_agreements': {
                'ex_date': merged.field_confidences.get('ex_date', FieldConfidence(None, 0, 0, 0, [])).agreement_ratio,
                'rights_symbol': merged.field_confidences.get('rights_symbol',
                                                              FieldConfidence(None, 0, 0, 0, [])).agreement_ratio,
                'rights_ratio': merged.field_confidences.get('rights_ratio',
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
                    'rights_symbol': data.get('new_symbol'),
                    'ex_date': data.get('ex_date'),
                    'rights_ratio': data.get('rate'),
                    'subscription_price': data.get('price')
                }
                for source, data in merged.raw_data.items()
            }
        }

    def merge_rights_with_confidence(self, rights_groups: List[List[UnifiedRightsOffering]]) -> UnifiedRightsOffering:
        """Merge rights offerings with confidence analysis."""
        if not rights_groups or not any(rights_groups):
            raise ValueError("No rights offerings to merge")

        all_rights = [rights for group in rights_groups for rights in group if rights]

        if not all_rights:
            raise ValueError("No valid rights offerings to merge")

        field_values = defaultdict(dict)
        source_reliabilities = {}

        for rights in all_rights:
            source_reliabilities[rights.source] = self.SOURCE_RELIABILITY.get(rights.source, 5) / 10.0

            fields_to_analyze = {
                'ex_date': rights.ex_date,
                'record_date': rights.record_date,
                'payable_date': rights.payable_date,
                'issuing_symbol': rights.issuing_symbol,
                'rights_symbol': rights.rights_symbol,
                'rights_cusip': rights.rights_cusip,
                'rights_ratio': rights.rights_ratio,
                'subscription_price': rights.subscription_price
            }

            for field_name, value in fields_to_analyze.items():
                if value is not None:
                    field_values[field_name][rights.source] = value

        field_confidences = {}
        for field_name, values_by_source in field_values.items():
            if field_name in ['rights_ratio', 'subscription_price']:
                field_confidences[field_name] = self.confidence_calculator.calculate_field_confidence(
                    field_name.replace('_ratio', '_amount').replace('_price', '_amount'),
                    values_by_source, source_reliabilities
                )
            else:
                field_confidences[field_name] = self.confidence_calculator.calculate_field_confidence(
                    field_name, values_by_source, source_reliabilities
                )

        merged = UnifiedRightsOffering(
            master_symbol=all_rights[0].master_symbol,
            source='+'.join(sorted(set(rights.source for rights in all_rights))),
            source_list=[rights.source for rights in all_rights],
            raw_data={rights.source: rights.raw_data for rights in all_rights},
            symbol_mapping=all_rights[0].symbol_mapping
        )

        for field_name, confidence in field_confidences.items():
            setattr(merged, field_name, confidence.value)

        merged.field_confidences = field_confidences

        field_weights = {
            'rights_symbol': 0.25,
            'ex_date': 0.25,
            'rights_ratio': 0.2,
            'subscription_price': 0.15,
            'issuing_symbol': 0.15
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
            filename = f'rights_offerings_debug_report_{timestamp}.json'

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
                'rights_symbol_agreement': result['field_agreements']['rights_symbol'],
                'ratio_agreement': result['field_agreements']['rights_ratio'],
                'sources': ', '.join(result['sources']),
                'issuing_symbol': result['issuing_symbol'],
                'rights_symbol': result['rights_symbol'],
                'has_disagreements': len(result['disagreements']) > 0,
                'mapping_confidence': result['symbol_mapping_info']['mapping_confidence']
            })

        pd.DataFrame(summary_data).to_csv(summary_file_path, index=False)
        print(f"Debug report exported to {debug_file_path}")
        print(f"Summary CSV exported to {summary_file_path}")

    def export_unified_rights_offerings(self, results: List[RightsOfferingMatchResult], data_dir: str,
                                        filename: str = None):
        """Export unified rights offering results to data directory."""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d")
            filename = f'unified_rights_offerings_{timestamp}.csv'

        os.makedirs(data_dir, exist_ok=True)
        csv_file_path = os.path.join(data_dir, filename)

        csv_data = []
        for result in results:
            rights = result.merged_rights

            csv_row = {
                'master_symbol': rights.master_symbol,
                'source': rights.source,
                'ex_date': rights.ex_date,
                'record_date': rights.record_date,
                'payable_date': rights.payable_date,
                'issuing_symbol': rights.issuing_symbol,
                'rights_symbol': rights.rights_symbol,
                'rights_cusip': rights.rights_cusip,
                'rights_ratio': str(rights.rights_ratio) if rights.rights_ratio else None,
                'subscription_price': str(rights.subscription_price) if rights.subscription_price else None,
                'overall_confidence': rights.overall_confidence,
                'source_agreement_score': rights.source_agreement_score,
                'data_completeness': rights.data_completeness,
                'match_quality': result.match_quality,
                'source_count': len(rights.source_list),
                'sources': ', '.join(rights.source_list),
                'mapping_confidence': rights.symbol_mapping.mapping_confidence if rights.symbol_mapping else 0.0,
                'unmapped_sources': ', '.join(
                    rights.symbol_mapping.unmapped_sources) if rights.symbol_mapping and rights.symbol_mapping.unmapped_sources else ''
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

    processor = EnhancedRightsOfferingProcessor(master_file)

    source_data = {
        'alpaca': [{'symbol': 'XYZ', 'new_symbol': 'XYZ.RT', 'ex_date': '2025-08-15', 'rate': '0.5', 'price': '10.00'}]
    }

    results = processor.process_all_sources(source_data)
    processor.export_debug_report(debug_dir)
    processor.export_unified_rights_offerings(results, data_dir)

    print(f"Processed {len(results)} rights offering matches")
    for result in results:
        print(f"{result.master_symbol}: Quality {result.match_quality:.2%}, "
              f"Confidence {result.merged_rights.overall_confidence:.2%}")
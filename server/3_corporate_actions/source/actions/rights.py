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
        },
        'sharadar': {
            'symbol': 'ticker',
            'ex_date': 'date',
            'issuing_symbol': 'ticker',
            'rights_symbol': 'contraticker',
            'rights_ratio': 'value'
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

    def process_all_sources(self, source_data_dict: Dict[str, List[Dict[str, Any]]]) -> List[RightsOfferingMatchResult]:
        """Process rights offerings from all sources and match by master symbol."""

        # FILTER OUT EMPTY SOURCES
        filtered_source_data = {source: data for source, data in source_data_dict.items() if data}

        if not filtered_source_data:
            return []

        # Process each source separately
        processed_by_source = {}
        for source, data in filtered_source_data.items():
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
        symbol_groups = defaultdict(lambda: defaultdict(list))

        for source, rights_offerings in processed_by_source.items():
            for rights in rights_offerings:
                symbol_groups[rights.master_symbol][source].append(rights)

        return dict(symbol_groups)

    def _create_match_result(self, master_symbol: str,
                             rights_by_source: Dict[str, List[UnifiedRightsOffering]]) -> RightsOfferingMatchResult:
        """Create a match result for rights offerings with the same master symbol."""

        # Flatten rights offerings from all sources
        all_rights = []
        for source_rights in rights_by_source.values():
            all_rights.extend(source_rights)

        if not all_rights:
            raise ValueError(f"No rights offerings found for {master_symbol}")

        # Group rights offerings that are likely the same (by ex_date and rights_symbol)
        rights_groups = self._group_similar_rights(all_rights)

        # Merge the largest group (most common rights offering)
        largest_group = max(rights_groups, key=len) if rights_groups else []

        if not largest_group:
            raise ValueError(f"No valid rights offering groups for {master_symbol}")

        merged_rights = self.merge_rights_with_confidence([largest_group])

        # Calculate match quality
        match_quality = self._calculate_match_quality(largest_group, rights_by_source)

        match_details = {
            'sources_matched': list(rights_by_source.keys()),
            'total_rights': len(all_rights),
            'merged_rights': len(largest_group),
            'rights_groups': len(rights_groups)
        }

        return RightsOfferingMatchResult(
            master_symbol=master_symbol,
            merged_rights=merged_rights,
            match_quality=match_quality,
            match_details=match_details
        )

    def _group_similar_rights(self, rights: List[UnifiedRightsOffering]) -> List[List[UnifiedRightsOffering]]:
        """Group rights offerings that appear to be the same event."""
        groups = []
        remaining_rights = rights.copy()

        while remaining_rights:
            current = remaining_rights.pop(0)
            current_group = [current]

            # Find similar rights offerings
            to_remove = []
            for i, rights_offering in enumerate(remaining_rights):
                if self._are_rights_similar(current, rights_offering):
                    current_group.append(rights_offering)
                    to_remove.append(i)

            # Remove grouped rights offerings
            for i in reversed(to_remove):
                remaining_rights.pop(i)

            groups.append(current_group)

        return groups

    def _are_rights_similar(self, rights1: UnifiedRightsOffering, rights2: UnifiedRightsOffering) -> bool:
        """Check if two rights offerings are likely the same event."""

        # Same ex_date and similar rights symbols
        if rights1.ex_date and rights2.ex_date and rights1.ex_date == rights2.ex_date:
            # Check if rights symbols match
            if rights1.rights_symbol and rights2.rights_symbol:
                if rights1.rights_symbol == rights2.rights_symbol:
                    return True
            else:
                # If no rights symbols, check ratios
                if rights1.rights_ratio and rights2.rights_ratio:
                    ratio_diff = abs(rights1.rights_ratio - rights2.rights_ratio)
                    if ratio_diff < Decimal('0.001'):  # Allow small differences
                        return True
                elif rights1.rights_ratio == rights2.rights_ratio:  # Both None
                    return True

        return False

    def _calculate_match_quality(self, merged_rights: List[UnifiedRightsOffering],
                                 all_rights_by_source: Dict[str, List[UnifiedRightsOffering]]) -> float:
        """Calculate the quality of the match."""

        if not merged_rights:
            return 0.0

        # Base quality on source agreement
        sources_in_merge = set(rights.source for rights in merged_rights)
        total_sources = len(all_rights_by_source)

        source_coverage = len(sources_in_merge) / total_sources if total_sources > 0 else 0

        # Quality score based on coverage and data completeness
        data_completeness = sum(rights.data_completeness for rights in merged_rights) / len(merged_rights)

        return (source_coverage * 0.7 + data_completeness * 0.3)

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
            'rights_ratio': 0.3,
            'ex_date': 0.25,
            'rights_symbol': 0.2,
            'subscription_price': 0.15,
            'issuing_symbol': 0.1
        }

        merged.overall_confidence = self.confidence_calculator.calculate_overall_confidence(
            field_confidences, field_weights
        )
        merged.source_agreement_score = self.confidence_calculator.calculate_source_agreement_score(
            field_confidences
        )
        merged.data_completeness = self._calculate_completeness_score(merged)

        return merged

    def _create_debug_entry(self, match_result: RightsOfferingMatchResult) -> Dict[str, Any]:
        """Create debug entry for a match result."""
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
                    'symbol': data.get('symbol') or data.get('ticker'),
                    'rights_symbol': data.get('new_symbol') or data.get('contraticker'),
                    'ex_date': data.get('ex_date') or data.get('date'),
                    'rights_ratio': data.get('rate') or data.get('value'),
                    'subscription_price': data.get('price')
                }
                for source, data in merged.raw_data.items()
            }
        }

    def export_debug_report(self, debug_dir: str):
        """Export debug report to JSON file."""
        debug_file_path = os.path.join(debug_dir, 'rights_offering_debug.json')
        summary_file_path = os.path.join(debug_dir, 'rights_offering_summary.csv')

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
                'rights_symbol': result['rights_symbol'],
                'rights_ratio': result['rights_ratio']
            })

        pd.DataFrame(summary_data).to_csv(summary_file_path, index=False, sep="|")

        print(f"Debug report exported to {debug_file_path}")
        print(f"Summary CSV exported to {summary_file_path}")

    def export_unified_rights_offerings(self, results, filename):
        """Export unified rights offerings to CSV file."""

        if not results:
            print("No rights offering results to export.")
            return

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

        pd.DataFrame(csv_data).to_csv(filename, index=False, sep="|")
        print(f"Unified rights offerings exported to {filename}")


def extract_rights_from_sources(alpaca_data: Dict[str, pd.DataFrame],
                                fmp_data: Dict[str, pd.DataFrame],
                                poly_data: Dict[str, pd.DataFrame],
                                sharadar_data: pd.DataFrame) -> Dict[str, List[Dict[str, Any]]]:
    """Extract rights offering data from all sources."""
    extracted_data = {}

    # Extract from Alpaca - look for rights offering actions
    alpaca_rights = []
    for action_type, df in alpaca_data.items():
        if 'rights' in action_type.lower():
            if not df.empty:
                alpaca_rights.extend(df.to_dict('records'))
    extracted_data['alpaca'] = alpaca_rights

    # Extract from FMP - no rights offering data typically
    extracted_data['fmp'] = []

    # Extract from Polygon - no rights offering data typically
    extracted_data['poly'] = []

    # Extract from Sharadar (filter for rights offering actions)
    if not sharadar_data.empty:
        rights_records = sharadar_data[sharadar_data['action'] == 'rights']
        extracted_data['sharadar'] = rights_records.to_dict('records')
    else:
        extracted_data['sharadar'] = []

    return extracted_data


def run(alpaca_data: Dict[str, pd.DataFrame],
        fmp_data: Dict[str, pd.DataFrame],
        poly_data: Dict[str, pd.DataFrame],
        sharadar_data: pd.DataFrame):
    """Main function to process rights offerings from all sources."""

    # Ensure directories exist
    config.ensure_directories()

    # Find master files using configured path
    master_files = glob.glob(os.path.join(config.master_files_dir, '*_MASTER_UPDATED.csv'))
    if not master_files:
        raise FileNotFoundError(f"No master CSV files found in {config.master_files_dir}")

    master_file = max(master_files)  # Get the most recent master file
    print(f"Using master file: {master_file}")

    # Extract rights offering data from all sources
    print("Extracting rights offering data from sources...")
    source_data = extract_rights_from_sources(alpaca_data, fmp_data, poly_data, sharadar_data)

    # Print extraction summary
    total_records = sum(len(data) for data in source_data.values())
    for source, data in source_data.items():
        print(f"  - {source}: {len(data)} rights offering records extracted")

    if total_records == 0:
        print("No rights offering records found in any source. Skipping rights offering processing.")
        return

    # Initialize processor
    processor = EnhancedRightsOfferingProcessor(master_file)

    # Process all sources
    print("Processing rights offerings from all sources...")
    results = processor.process_all_sources(source_data)

    # Always export debug report (even if empty)
    processor.export_debug_report(config.debug_dir)

    # Only export CSV if we have results
    if results:
        # Ensure the filename is set properly
        rights_filename = config.unified_rights_file or 'unified_rights.csv'
        processor.export_unified_rights_offerings(results, os.path.join(config.data_dir, rights_filename))

        print(f"Processed {len(results)} rights offering matches")
        for result in results:
            print(f"{result.master_symbol}: Quality {result.match_quality:.2%}, "
                  f"Confidence {result.merged_rights.overall_confidence:.2%}")
    else:
        print("No rights offering matches found after processing.")


if __name__ == "__main__":
    # Test run with sample data
    config.ensure_directories()

    # Find master files using configured path
    master_files = glob.glob(os.path.join(config.master_files_dir, '*.csv'))
    if not master_files:
        raise FileNotFoundError(f"No master CSV files found in {config.master_files_dir}")

    master_file = max(master_files)
    print(f"Using master file: {master_file}")

    processor = EnhancedRightsOfferingProcessor(master_file)

    # Sample test data
    source_data = {
        'alpaca': [{'symbol': 'XYZ', 'ex_date': '2025-08-15', 'new_symbol': 'XYZRT', 'rate': '1:10', 'price': '5.00'}],
        'sharadar': [{'ticker': 'XYZ', 'date': '2025-08-15', 'contraticker': 'XYZRT', 'value': '0.1'}]
    }

    results = processor.process_all_sources(source_data)
    processor.export_debug_report(config.debug_dir)
    if results:
        rights_filename = config.unified_rights_file or 'unified_rights.csv'
        processor.export_unified_rights_offerings(results, os.path.join(config.data_dir, rights_filename))

    print(f"Processed {len(results)} rights offering matches")
    for result in results:
        print(f"{result.master_symbol}: Quality {result.match_quality:.2%}, "
              f"Confidence {result.merged_rights.overall_confidence:.2%}")
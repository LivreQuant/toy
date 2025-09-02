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
    mappi
def export_unified_symbol_changes(self, results, data_dir=None, filename=None):
    """Export unified symbol changes to CSV format"""
    if data_dir is None:
        data_dir = config.data_dir
        
    if filename is None:
        filename = config.get_unified_filename(config.unified_symbol_changes_file)

    os.makedirs(data_dir, exist_ok=True)
    csv_file_path = os.path.join(data_dir, filename)

    csv_data = []
    for result in results:
        change = result.merged_change

        csv_row = {
            'master_symbol': change.master_symbol,
            'source': change.source,
            'process_date': change.process_date,
            'old_symbol': change.old_symbol,
            'new_symbol': change.new_symbol,
            'old_cusip': change.old_cusip,
            'new_cusip': change.new_cusip,
            'overall_confidence': change.overall_confidence,
            'source_agreement_score': change.source_agreement_score,
            'data_completeness': change.data_completeness,
            'match_quality': result.match_quality,
            'source_count': len(change.source_list),
            'sources': ', '.join(change.source_list),
            'mapping_confidence': change.symbol_mapping.mapping_confidence if change.symbol_mapping else 0.0,
            'unmapped_sources': ', '.join(
                change.symbol_mapping.unmapped_sources) if change.symbol_mapping and change.symbol_mapping.unmapped_sources else ''
        }
        csv_data.append(csv_row)

    pd.DataFrame(csv_data).to_csv(csv_file_path, index=False)
    print(f"CSV summary exported to {csv_file_path}")
    return csv_file_pathng_confidence: float


@dataclass
class UnifiedSymbolChange:
    """Unified symbol change representation with master symbol mapping."""

    # Core identifiers
    master_symbol: str  # The unified master symbol
    source: str
    symbol_mapping: Optional[SymbolMappingInfo] = None

    # Dates
    change_date: Optional[str] = None
    process_date: Optional[str] = None

    # Symbol change information
    old_symbol: Optional[str] = None
    new_symbol: Optional[str] = None
    company_name: Optional[str] = None

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
class SymbolChangeMatchResult:
    """Result of matching symbol changes across sources."""
    master_symbol: str
    merged_change: UnifiedSymbolChange
    match_quality: float  # 0.0 to 1.0
    match_details: Dict[str, Any]


class EnhancedSymbolChangeProcessor:
    """Enhanced processor for symbol changes with symbol mapping and debug reporting."""

    FIELD_MAPPINGS = {
        'alpaca': {
            'symbol': 'new_symbol',  # Use new_symbol as the primary identifier
            'change_date': 'process_date',
            'process_date': 'process_date',
            'old_symbol': 'old_symbol',
            'new_symbol': 'new_symbol',
            'old_cusip': 'old_cusip',
            'new_cusip': 'new_cusip'
        },
        'fmp': {
            'symbol': 'newSymbol',  # Use newSymbol as the primary identifier
            'change_date': 'date',
            'old_symbol': 'oldSymbol',
            'new_symbol': 'newSymbol',
            'company_name': 'name'
        },
        'sharadar': {
            'symbol': 'contraticker',  # Use contraticker (new symbol) as the primary identifier
            'change_date': 'date',
            'old_symbol': 'ticker',
            'new_symbol': 'contraticker',
            'company_name': 'name'
        }
    }

    SOURCE_RELIABILITY = {
        'alpaca': 9,
        'fmp': 8,
        'sharadar': 7
    }

    def __init__(self, master_csv_path: str):
        self.confidence_calculator = ConfidenceCalculator()
        self.symbol_mapper = SymbolMapper(master_csv_path)
        self.debug_results = []

    def process_all_sources(self, source_data_dict: Dict[str, List[Dict[str, Any]]]) -> List[SymbolChangeMatchResult]:
        """Process symbol changes from all sources and match by master symbol."""

        # Process each source separately
        processed_by_source = {}
        for source, data in source_data_dict.items():
            processed_by_source[source] = self.process_source_data(source, data)

        # Group by master symbol
        symbol_groups = self._group_by_master_symbol(processed_by_source)

        # Merge and analyze matches
        match_results = []
        for master_symbol, changes_by_source in symbol_groups.items():
            try:
                match_result = self._create_match_result(master_symbol, changes_by_source)
                match_results.append(match_result)
                self.debug_results.append(self._create_debug_entry(match_result))
            except Exception as e:
                logger.error(f"Error processing symbol changes for {master_symbol}: {e}")
                continue

        # Sort debug results by match quality (worst first)
        self.debug_results.sort(key=lambda x: x['match_quality'])

        return match_results

    def process_source_data(self, source: str, data: List[Dict[str, Any]]) -> List[UnifiedSymbolChange]:
        """Process symbol change data from a specific source with symbol mapping."""
        if source not in self.FIELD_MAPPINGS:
            raise ValueError(f"Unknown source: {source}")

        changes = []
        mapping = self.FIELD_MAPPINGS[source]

        for record in data:
            try:
                # Map to unified format first
                change = self._map_record_to_unified(source, record, mapping)

                # Map to master symbol
                source_symbol = change.master_symbol
                master_symbol = self.symbol_mapper.map_to_master_symbol(source, source_symbol)

                if master_symbol:
                    change.master_symbol = master_symbol
                    change.symbol_mapping = SymbolMappingInfo(
                        master_symbol=master_symbol,
                        source_mappings={source: source_symbol},
                        unmapped_sources=[],
                        mapping_confidence=1.0
                    )
                else:
                    change.master_symbol = source_symbol
                    change.symbol_mapping = SymbolMappingInfo(
                        master_symbol=source_symbol,
                        source_mappings={},
                        unmapped_sources=[source],
                        mapping_confidence=0.0
                    )

                change.data_completeness = self._calculate_completeness_score(change)
                changes.append(change)

            except Exception as e:
                logger.error(f"Error processing {source} record: {e}, record: {record}")
                continue

        return changes

    def _map_record_to_unified(self, source: str, record: Dict[str, Any],
                               mapping: Dict[str, str]) -> UnifiedSymbolChange:
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
                else:
                    unified_data[unified_field] = str(value) if value is not None else None

        return UnifiedSymbolChange(**unified_data)

    def _calculate_completeness_score(self, change: UnifiedSymbolChange) -> float:
        """Calculate data completeness score."""
        important_fields = [
            change.master_symbol, change.change_date, change.old_symbol, change.new_symbol
        ]
        filled_fields = sum(1 for field in important_fields if field is not None)
        return filled_fields / len(important_fields)

    def _group_by_master_symbol(self, processed_by_source: Dict[str, List[UnifiedSymbolChange]]) -> Dict[
        str, Dict[str, List[UnifiedSymbolChange]]]:
        """Group symbol changes by master symbol across sources."""
        symbol_groups = {}

        for source, changes in processed_by_source.items():
            for change in changes:
                master_symbol = change.master_symbol
                if master_symbol not in symbol_groups:
                    symbol_groups[master_symbol] = {}
                if source not in symbol_groups[master_symbol]:
                    symbol_groups[master_symbol][source] = []
                symbol_groups[master_symbol][source].append(change)

        return symbol_groups

    def _create_match_result(self, master_symbol: str,
                             changes_by_source: Dict[str, List[UnifiedSymbolChange]]) -> SymbolChangeMatchResult:
        """Create a match result for symbol changes with the same master symbol."""

        representative_changes = []
        for source, changes in changes_by_source.items():
            if changes:
                representative_changes.append(changes[0])

        merged = self.merge_changes_with_confidence([representative_changes])
        match_quality = self._calculate_match_quality(changes_by_source, merged)

        match_details = {
            'sources_matched': list(changes_by_source.keys()),
            'total_changes': sum(len(changes) for changes in changes_by_source.values()),
            'date_agreement': merged.field_confidences.get('change_date',
                                                           FieldConfidence(None, 0, 0, 0, [])).agreement_ratio,
            'old_symbol_agreement': merged.field_confidences.get('old_symbol',
                                                                 FieldConfidence(None, 0, 0, 0, [])).agreement_ratio,
            'new_symbol_agreement': merged.field_confidences.get('new_symbol',
                                                                 FieldConfidence(None, 0, 0, 0, [])).agreement_ratio,
        }

        return SymbolChangeMatchResult(
            master_symbol=master_symbol,
            merged_change=merged,
            match_quality=match_quality,
            match_details=match_details
        )

    def _calculate_match_quality(self, changes_by_source: Dict[str, List[UnifiedSymbolChange]],
                                 merged: UnifiedSymbolChange) -> float:
        """Calculate overall match quality for debugging."""
        source_count = len(changes_by_source)
        source_score = min(1.0, source_count / 3.0)  # Max quality with 3+ sources
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

    def _create_debug_entry(self, match_result: SymbolChangeMatchResult) -> Dict[str, Any]:
        """Create a debug entry for a match result."""
        merged = match_result.merged_change

        return {
            'master_symbol': match_result.master_symbol,
            'match_quality': match_result.match_quality,
            'sources': match_result.match_details['sources_matched'],
            'source_count': len(match_result.match_details['sources_matched']),
            'overall_confidence': merged.overall_confidence,
            'source_agreement': merged.source_agreement_score,
            'data_completeness': merged.data_completeness,
            'change_date': merged.change_date,
            'old_symbol': merged.old_symbol,
            'new_symbol': merged.new_symbol,
            'company_name': merged.company_name,
            'field_agreements': {
                'change_date': merged.field_confidences.get('change_date',
                                                            FieldConfidence(None, 0, 0, 0, [])).agreement_ratio,
                'old_symbol': merged.field_confidences.get('old_symbol',
                                                           FieldConfidence(None, 0, 0, 0, [])).agreement_ratio,
                'new_symbol': merged.field_confidences.get('new_symbol',
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
                    'old_symbol': data.get('old_symbol') or data.get('oldSymbol') or data.get('ticker'),
                    'new_symbol': data.get('new_symbol') or data.get('newSymbol') or data.get('contraticker'),
                    'company_name': data.get('name'),
                    'date': data.get('date') or data.get('process_date')
                }
                for source, data in merged.raw_data.items()
            }
        }

    def merge_changes_with_confidence(self, change_groups: List[List[UnifiedSymbolChange]]) -> UnifiedSymbolChange:
        """Merge symbol changes with confidence analysis."""
        if not change_groups or not any(change_groups):
            raise ValueError("No symbol changes to merge")

        all_changes = [change for group in change_groups for change in group if change]

        if not all_changes:
            raise ValueError("No valid symbol changes to merge")

        field_values = defaultdict(dict)
        source_reliabilities = {}

        for change in all_changes:
            source_reliabilities[change.source] = self.SOURCE_RELIABILITY.get(change.source, 5) / 10.0

            fields_to_analyze = {
                'change_date': change.change_date,
                'process_date': change.process_date,
                'old_symbol': change.old_symbol,
                'new_symbol': change.new_symbol,
                'company_name': change.company_name,
                'old_cusip': change.old_cusip,
                'new_cusip': change.new_cusip
            }

            for field_name, value in fields_to_analyze.items():
                if value is not None:
                    field_values[field_name][change.source] = value

        field_confidences = {}
        for field_name, values_by_source in field_values.items():
            field_confidences[field_name] = self.confidence_calculator.calculate_field_confidence(
                field_name, values_by_source, source_reliabilities
            )

        merged = UnifiedSymbolChange(
            master_symbol=all_changes[0].master_symbol,
            source='+'.join(sorted(set(change.source for change in all_changes))),
            source_list=[change.source for change in all_changes],
            raw_data={change.source: change.raw_data for change in all_changes},
            symbol_mapping=all_changes[0].symbol_mapping
        )

        for field_name, confidence in field_confidences.items():
            setattr(merged, field_name, confidence.value)

        merged.field_confidences = field_confidences

        field_weights = {
            'old_symbol': 0.3,
            'new_symbol': 0.3,
            'change_date': 0.25,
            'company_name': 0.1,
            'process_date': 0.05
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
            filename = f'symbol_changes_debug_report_{timestamp}.json'

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
                'date_agreement': result['field_agreements']['change_date'],
                'old_symbol_agreement': result['field_agreements']['old_symbol'],
                'new_symbol_agreement': result['field_agreements']['new_symbol'],
                'sources': ', '.join(result['sources']),
                'old_symbol': result['old_symbol'],
                'new_symbol': result['new_symbol'],
                'has_disagreements': len(result['disagreements']) > 0,
                'mapping_confidence': result['symbol_mapping_info']['mapping_confidence']
            })

        pd.DataFrame(summary_data).to_csv(summary_file_path, index=False)
        print(f"Debug report exported to {debug_file_path}")
        print(f"Summary CSV exported to {summary_file_path}")

        
    def export_unified_symbol_changes(self, results, data_dir=None, filename=None):
        """Export unified symbol changes to CSV format"""
        if data_dir is None:
            data_dir = config.data_dir
            
        if filename is None:
            filename = config.get_unified_filename(config.unified_symbol_changes_file)

        os.makedirs(data_dir, exist_ok=True)
        csv_file_path = os.path.join(data_dir, filename)

        csv_data = []
        for result in results:
            change = result.merged_change

            csv_row = {
                'master_symbol': change.master_symbol,
                'source': change.source,
                'process_date': change.process_date,
                'old_symbol': change.old_symbol,
                'new_symbol': change.new_symbol,
                'old_cusip': change.old_cusip,
                'new_cusip': change.new_cusip,
                'overall_confidence': change.overall_confidence,
                'source_agreement_score': change.source_agreement_score,
                'data_completeness': change.data_completeness,
                'match_quality': result.match_quality,
                'source_count': len(change.source_list),
                'sources': ', '.join(change.source_list),
                'mapping_confidence': change.symbol_mapping.mapping_confidence if change.symbol_mapping else 0.0,
                'unmapped_sources': ', '.join(
                    change.symbol_mapping.unmapped_sources) if change.symbol_mapping and change.symbol_mapping.unmapped_sources else ''
            }
            csv_data.append(csv_row)

        pd.DataFrame(csv_data).to_csv(csv_file_path, index=False)
        print(f"CSV summary exported to {csv_file_path}")
        return csv_file_path
        


if __name__ == "__main__":
    # Ensure directories exist
    config.ensure_directories()
    
    # Use configuration paths
    data_dir = config.data_dir
    debug_dir = config.debug_dir

    # Find master files using configured path
    master_files = glob.glob(os.path.join(config.master_files_dir, '*.csv'))
    if not master_files:
        raise FileNotFoundError(f"No master CSV files found in {config.master_files_dir}")

    master_file = max(master_files)
    print(f"Using master file: {master_file}")

    processor = EnhancedSymbolChangeProcessor(master_file)

    source_data = {
        'alpaca': [{'old_symbol': 'AAPL', 'new_symbol': 'APPL', 'process_date': '2025-08-15'}],
        'fmp': [{'oldSymbol': 'AAPL', 'newSymbol': 'APPL', 'date': '2025-08-15', 'name': 'Apple Inc.'}],
        'sharadar': [{'ticker': 'AAPL', 'contraticker': 'APPL', 'date': '2025-08-15', 'name': 'Apple Inc.'}]
    }

    results = processor.process_all_sources(source_data)
    processor.export_debug_report(debug_dir)
    processor.export_unified_symbol_changes(results, data_dir)

    print(f"Processed {len(results)} symbol change matches")
    for result in results:
        print(f"{result.master_symbol}: Quality {result.match_quality:.2%}, "
              f"Confidence {result.merged_change.overall_confidence:.2%}")
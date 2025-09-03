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
class UnifiedIPO:
    """Unified IPO representation with master symbol mapping."""

    # Core identifiers
    master_symbol: str  # The unified master symbol (company going public)
    source: str
    symbol_mapping: Optional[SymbolMappingInfo] = None

    # Dates
    listing_date: Optional[str] = None
    announced_date: Optional[str] = None

    # Company information
    ipo_symbol: Optional[str] = None
    company_name: Optional[str] = None

    # IPO details
    listing_exchange: Optional[str] = None
    primary_exchange: Optional[str] = None
    issue_price: Optional[Decimal] = None
    shares_offered: Optional[int] = None
    isin: Optional[str] = None
    security_type: Optional[str] = None

    # Confidence tracking
    field_confidences: Dict[str, FieldConfidence] = field(default_factory=dict)
    overall_confidence: float = 1.0
    source_agreement_score: float = 1.0
    data_completeness: float = 1.0

    # Raw data
    raw_data: Dict[str, Any] = field(default_factory=dict)
    source_list: List[str] = field(default_factory=list)


@dataclass
class IPOMatchResult:
    """Result of matching IPOs across sources."""
    master_symbol: str
    merged_ipo: UnifiedIPO
    match_quality: float  # 0.0 to 1.0
    match_details: Dict[str, Any]


class EnhancedIPOProcessor:
    """Enhanced processor for IPOs with symbol mapping and debug reporting."""

    FIELD_MAPPINGS = {
        'poly': {
            'symbol': 'ticker',
            'listing_date': 'listing_date',
            'announced_date': 'announced_date',
            'ipo_symbol': 'ticker',
            'company_name': 'issuer_name',
            'isin': 'isin',
            'primary_exchange': 'primary_exchange',
            'shares_offered': 'max_shares_offered',
            'issue_price': 'final_issue_price',
            'security_type': 'security_type'
        },
        'sharadar': {
            'symbol': 'ticker',
            'listing_date': 'date',
            'ipo_symbol': 'ticker',
            'company_name': 'name',
            'listing_exchange': 'exchange'
        },
        'nasdaq': {
            'symbol': 'Symbol',
            'ipo_symbol': 'Symbol',
            'company_name': 'Company Name',
            'listing_exchange': lambda x: 'XNAS'
        }
    }

    SOURCE_RELIABILITY = {
        'poly': 8,
        'sharadar': 7
    }

    def __init__(self, master_csv_path: str):
        self.confidence_calculator = ConfidenceCalculator()
        self.symbol_mapper = SymbolMapper(master_csv_path)
        self.debug_results = []

    def process_all_sources(self, source_data_dict: Dict[str, List[Dict[str, Any]]]) -> List[IPOMatchResult]:
        """Process IPOs from all sources and match by master symbol."""

        # Process each source separately
        processed_by_source = {}
        for source, data in source_data_dict.items():
            processed_by_source[source] = self.process_source_data(source, data)

        # Group by master symbol
        symbol_groups = self._group_by_master_symbol(processed_by_source)

        # Merge and analyze matches
        match_results = []
        for master_symbol, ipos_by_source in symbol_groups.items():
            try:
                match_result = self._create_match_result(master_symbol, ipos_by_source)
                match_results.append(match_result)
                self.debug_results.append(self._create_debug_entry(match_result))
            except Exception as e:
                logger.error(f"Error processing IPOs for {master_symbol}: {e}")
                continue

        # Sort debug results by match quality (worst first)
        self.debug_results.sort(key=lambda x: x['match_quality'])

        return match_results

    def process_source_data(self, source: str, data: List[Dict[str, Any]]) -> List[UnifiedIPO]:
        """Process IPO data from a specific source with symbol mapping."""

        if not data:
            return []

        field_mapping = self.FIELD_MAPPINGS.get(source, {})
        unified_ipos = []

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
                if unified_data.get('issue_price') is not None:
                    try:
                        unified_data['issue_price'] = Decimal(str(unified_data['issue_price']))
                    except (ValueError, TypeError):
                        unified_data['issue_price'] = None

                if unified_data.get('shares_offered') is not None:
                    try:
                        unified_data['shares_offered'] = int(unified_data['shares_offered'])
                    except (ValueError, TypeError):
                        unified_data['shares_offered'] = None

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

                # Create unified IPO
                ipo = UnifiedIPO(
                    master_symbol=master_symbol,
                    source=source,
                    symbol_mapping=symbol_mapping,
                    listing_date=unified_data.get('listing_date'),
                    announced_date=unified_data.get('announced_date'),
                    ipo_symbol=unified_data.get('ipo_symbol'),
                    company_name=unified_data.get('company_name'),
                    listing_exchange=unified_data.get('listing_exchange'),
                    primary_exchange=unified_data.get('primary_exchange'),
                    issue_price=unified_data.get('issue_price'),
                    shares_offered=unified_data.get('shares_offered'),
                    isin=unified_data.get('isin'),
                    security_type=unified_data.get('security_type'),
                    raw_data={source: raw_data},
                    source_list=[source]
                )

                # Calculate data completeness
                ipo.data_completeness = self._calculate_completeness_score(ipo)
                unified_ipos.append(ipo)

            except Exception as e:
                logger.error(f"Error processing IPO row from {source}: {e}")
                continue

        return unified_ipos

    def _calculate_completeness_score(self, ipo: UnifiedIPO) -> float:
        """Calculate data completeness score."""
        required_fields = ['master_symbol', 'listing_date', 'ipo_symbol', 'company_name']
        optional_fields = ['listing_exchange', 'primary_exchange', 'issue_price', 'shares_offered', 'isin']

        required_score = sum(1 for field in required_fields if getattr(ipo, field))
        optional_score = sum(1 for field in optional_fields if getattr(ipo, field))

        return (required_score / len(required_fields)) * 0.7 + (optional_score / len(optional_fields)) * 0.3

    def _group_by_master_symbol(self, processed_by_source: Dict[str, List[UnifiedIPO]]) -> Dict[
        str, Dict[str, List[UnifiedIPO]]]:
        """Group IPOs by master symbol and source."""

        symbol_groups = defaultdict(lambda: defaultdict(list))

        for source, ipos in processed_by_source.items():
            for ipo in ipos:
                symbol_groups[ipo.master_symbol][source].append(ipo)

        return dict(symbol_groups)

    def _create_match_result(self, master_symbol: str, ipos_by_source: Dict[str, List[UnifiedIPO]]) -> IPOMatchResult:
        """Create a match result for a master symbol."""

        # Flatten IPOs from all sources
        all_ipos = []
        for source_ipos in ipos_by_source.values():
            all_ipos.extend(source_ipos)

        if not all_ipos:
            raise ValueError(f"No IPOs found for {master_symbol}")

        # Group IPOs that are likely the same (by listing_date)
        ipo_groups = self._group_similar_ipos(all_ipos)

        # Merge the largest group (most common IPO)
        largest_group = max(ipo_groups, key=len) if ipo_groups else []

        if not largest_group:
            raise ValueError(f"No valid IPO groups for {master_symbol}")

        merged_ipo = self.merge_ipos_with_confidence([largest_group])

        # Calculate match quality
        match_quality = self._calculate_match_quality(largest_group, ipos_by_source)

        match_details = {
            'sources_matched': list(ipos_by_source.keys()),
            'total_ipos': len(all_ipos),
            'merged_ipos': len(largest_group),
            'ipo_groups': len(ipo_groups)
        }

        return IPOMatchResult(
            master_symbol=master_symbol,
            merged_ipo=merged_ipo,
            match_quality=match_quality,
            match_details=match_details
        )

    def _group_similar_ipos(self, ipos: List[UnifiedIPO]) -> List[List[UnifiedIPO]]:
        """Group IPOs that appear to be the same event."""

        groups = []
        remaining_ipos = ipos.copy()

        while remaining_ipos:
            current = remaining_ipos.pop(0)
            current_group = [current]

            # Find similar IPOs
            to_remove = []
            for i, ipo in enumerate(remaining_ipos):
                if self._are_ipos_similar(current, ipo):
                    current_group.append(ipo)
                    to_remove.append(i)

            # Remove grouped IPOs
            for i in reversed(to_remove):
                remaining_ipos.pop(i)

            groups.append(current_group)

        return groups

    def _are_ipos_similar(self, ipo1: UnifiedIPO, ipo2: UnifiedIPO) -> bool:
        """Check if two IPOs are likely the same event."""

        # Same listing_date (most important)
        if ipo1.listing_date and ipo2.listing_date and ipo1.listing_date == ipo2.listing_date:
            return True

        # If no dates, consider them similar if from different sources (likely same event)
        if not ipo1.listing_date and not ipo2.listing_date:
            return ipo1.source != ipo2.source

        return False

    def _calculate_match_quality(self, merged_ipos: List[UnifiedIPO],
                                 all_ipos_by_source: Dict[str, List[UnifiedIPO]]) -> float:
        """Calculate the quality of the match."""

        if not merged_ipos:
            return 0.0

        # Base quality on source agreement
        sources_in_merge = set(ipo.source for ipo in merged_ipos)
        total_sources = len(all_ipos_by_source)

        source_coverage = len(sources_in_merge) / total_sources if total_sources > 0 else 0

        # Quality score based on coverage and data completeness
        data_completeness = sum(ipo.data_completeness for ipo in merged_ipos) / len(merged_ipos)

        return (source_coverage * 0.7 + data_completeness * 0.3)

    def merge_ipos_with_confidence(self, ipo_groups: List[List[UnifiedIPO]]) -> UnifiedIPO:
        """Merge IPOs with confidence analysis."""

        if not ipo_groups or not any(ipo_groups):
            raise ValueError("No IPOs to merge")

        all_ipos = [ipo for group in ipo_groups for ipo in group if ipo]

        if not all_ipos:
            raise ValueError("No valid IPOs to merge")

        # Collect values by field and source
        field_values = defaultdict(dict)
        source_reliabilities = {}

        for ipo in all_ipos:
            source_reliabilities[ipo.source] = self.SOURCE_RELIABILITY.get(ipo.source, 5) / 10.0

            fields_to_analyze = {
                'listing_date': ipo.listing_date,
                'announced_date': ipo.announced_date,
                'ipo_symbol': ipo.ipo_symbol,
                'company_name': ipo.company_name,
                'listing_exchange': ipo.listing_exchange,
                'primary_exchange': ipo.primary_exchange,
                'issue_price': ipo.issue_price,
                'shares_offered': ipo.shares_offered,
                'isin': ipo.isin,
                'security_type': ipo.security_type
            }

            for field_name, value in fields_to_analyze.items():
                if value is not None:
                    field_values[field_name][ipo.source] = value

        # Calculate confidence for each field
        field_confidences = {}
        for field_name, values_by_source in field_values.items():
            field_confidences[field_name] = self.confidence_calculator.calculate_field_confidence(
                field_name, values_by_source, source_reliabilities
            )

        # Build merged IPO
        merged = UnifiedIPO(
            master_symbol=all_ipos[0].master_symbol,
            source='+'.join(sorted(set(ipo.source for ipo in all_ipos))),
            source_list=[ipo.source for ipo in all_ipos],
            raw_data={ipo.source: ipo.raw_data[ipo.source] for ipo in all_ipos if ipo.source in ipo.raw_data},
            symbol_mapping=all_ipos[0].symbol_mapping
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

    def _create_debug_entry(self, match_result: IPOMatchResult) -> Dict[str, Any]:
        """Create debug entry for a match result."""

        merged = match_result.merged_ipo

        return {
            'master_symbol': match_result.master_symbol,
            'match_quality': match_result.match_quality,
            'sources': match_result.match_details['sources_matched'],
            'source_count': len(match_result.match_details['sources_matched']),
            'overall_confidence': merged.overall_confidence,
            'source_agreement': merged.source_agreement_score,
            'data_completeness': merged.data_completeness,
            'listing_date': merged.listing_date,
            'ipo_symbol': merged.ipo_symbol,
            'company_name': merged.company_name,
            'listing_exchange': merged.listing_exchange,
            'field_agreements': {
                'listing_date': merged.field_confidences.get('listing_date',
                                                             FieldConfidence(None, 0, 0, 0, [])).agreement_ratio,
                'ipo_symbol': merged.field_confidences.get('ipo_symbol',
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
                    'symbol': data.get('ticker'),
                    'listing_date': data.get('listing_date') or data.get('date'),
                    'company_name': data.get('issuer_name') or data.get('name'),
                    'exchange': data.get('primary_exchange') or data.get('exchange')
                }
                for source, data in merged.raw_data.items()
            }
        }

    def export_debug_report(self, debug_dir: str):
        """Export debug report to JSON file."""

        debug_file_path = os.path.join(debug_dir, 'ipo_debug.json')
        summary_file_path = os.path.join(debug_dir, 'ipo_summary.csv')

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
                'listing_date': result['listing_date'],
                'company_name': result['company_name']
            })

        pd.DataFrame(summary_data).to_csv(summary_file_path, index=False)

        print(f"Debug report exported to {debug_file_path}")
        print(f"Summary CSV exported to {summary_file_path}")

    def export_unified_ipos(self, results, filename):
        """Export unified IPOs to CSV file."""

        if not results:
            print("No IPO results to export.")
            return None

        os.makedirs(os.path.dirname(filename), exist_ok=True)
        csv_file_path = os.path.join(filename)

        csv_data = []
        for result in results:
            ipo = result.merged_ipo

            csv_row = {
                'master_symbol': ipo.master_symbol,
                'source': ipo.source,
                'listing_date': ipo.listing_date,
                'announced_date': ipo.announced_date,
                'ipo_symbol': ipo.ipo_symbol,
                'company_name': ipo.company_name,
                'listing_exchange': ipo.listing_exchange,
                'primary_exchange': ipo.primary_exchange,
                'issue_price': str(ipo.issue_price) if ipo.issue_price else None,
                'shares_offered': ipo.shares_offered,
                'isin': ipo.isin,
                'security_type': ipo.security_type,
                'overall_confidence': ipo.overall_confidence,
                'source_agreement_score': ipo.source_agreement_score,
                'data_completeness': ipo.data_completeness,
                'match_quality': result.match_quality,
                'source_count': len(ipo.source_list),
                'sources': ', '.join(ipo.source_list),
                'mapping_confidence': ipo.symbol_mapping.mapping_confidence if ipo.symbol_mapping else 0.0,
                'unmapped_sources': ', '.join(
                    ipo.symbol_mapping.unmapped_sources) if ipo.symbol_mapping and ipo.symbol_mapping.unmapped_sources else ''
            }
            csv_data.append(csv_row)

        pd.DataFrame(csv_data).to_csv(csv_file_path, index=False)
        print(f"CSV summary exported to {csv_file_path}")

        return csv_file_path


def extract_ipo_from_sources(alpaca_data: Dict[str, pd.DataFrame],
                             fmp_data: Dict[str, pd.DataFrame],
                             poly_data: Dict[str, pd.DataFrame],
                             sharadar_data: pd.DataFrame,
                             nasdaq_data: Dict[str, pd.DataFrame]) -> Dict[str, List[Dict[str, Any]]]:
    """Extract IPO data from all sources and return in standardized format."""

    extracted_data = {}

    # Extract from Alpaca - no IPO data typically
    extracted_data['alpaca'] = []

    # Extract from FMP - no IPO data typically
    extracted_data['fmp'] = []

    # Extract from Polygon
    if 'ipos' in poly_data and not poly_data['ipos'].empty:
        extracted_data['poly'] = poly_data['ipos'].to_dict('records')
    else:
        extracted_data['poly'] = []

    # Extract from Sharadar (filter for IPO actions)
    if not sharadar_data.empty:
        ipo_records = sharadar_data[sharadar_data['action'] == 'ipo']
        extracted_data['sharadar'] = ipo_records.to_dict('records')
    else:
        extracted_data['sharadar'] = []

    # Extract from NASDAQ
    if 'ipos' in nasdaq_data and not nasdaq_data['ipos'].empty:
        extracted_data['nasdaq'] = nasdaq_data['ipos'].to_dict('records')
    else:
        extracted_data['nasdaq'] = []

    return extracted_data



def run(alpaca_data: Dict[str, pd.DataFrame],
        fmp_data: Dict[str, pd.DataFrame],
        poly_data: Dict[str, pd.DataFrame],
        sharadar_data: pd.DataFrame,
        nasdaq_data: Dict[str, pd.DataFrame]):
    """Main function to process IPOs from all sources."""

    # Ensure directories exist
    config.ensure_directories()

    # Find master files using configured path
    master_files = glob.glob(os.path.join(config.master_files_dir, '*_MASTER_UPDATED.csv'))
    if not master_files:
        raise FileNotFoundError(f"No master CSV files found in {config.master_files_dir}")

    master_file = max(master_files)  # Get the most recent master file
    print(f"Using master file: {master_file}")

    # Extract IPO data from all sources
    print("Extracting IPO data from sources...")
    source_data = extract_ipo_from_sources(alpaca_data, fmp_data, poly_data, sharadar_data, nasdaq_data)

    # Print extraction summary
    total_records = sum(len(data) for data in source_data.values())
    for source, data in source_data.items():
        print(f"  - {source}: {len(data)} IPO records extracted")

    if total_records == 0:
        print("No IPO records found in any source. Skipping IPO processing.")
        return

    # Initialize processor
    processor = EnhancedIPOProcessor(master_file)

    # Process all sources
    print("Processing IPOs from all sources...")
    results = processor.process_all_sources(source_data)

    # Always export debug report (even if empty)
    processor.export_debug_report(config.debug_dir)

    # Only export CSV if we have results
    if results:
        # Ensure the filename is set properly
        ipo_filename = config.unified_ipos_file or 'unified_ipos.csv'
        processor.export_unified_ipos(results, os.path.join(config.data_dir, ipo_filename))

        print(f"Processed {len(results)} IPO matches")
        for result in results:
            print(f"{result.master_symbol}: Quality {result.match_quality:.2%}, "
                  f"Confidence {result.merged_ipo.overall_confidence:.2%}")
    else:
        print("No IPO matches found after processing.")
import json
import os
import glob
from collections import defaultdict
from source.config import config


def analyze_historical_corporate_actions():
    """
    Analyze all historical corporate action files to generate comprehensive schema.
    """

    """
    # History analysis patterns
    ALPACA_CA_PATTERN=*/alpaca/*.json
    FMP_DIVIDENDS_PATTERN=*/fmp/dividends.json
    FMP_SPLITS_PATTERN=*/fmp/splits.json
    FMP_MERGERS_PATTERN=*/fmp/mergers.json
    POLY_DIVIDENDS_PATTERN=*/poly/dividends.json
    POLY_SPLITS_PATTERN=*/poly/splits.json
    POLY_IPOS_PATTERN=*/poly/ipos.json
    SHARADAR_CA_PATTERN=*/sharadar/*.csv
    """

    # Use configured file patterns
    file_patterns = {
        'dividends': os.path.join(config.source_ca_dir, 'poly/dividends.json'),
        'splits': os.path.join(config.source_ca_dir, 'poly/splits.json'),
        'ipos': os.path.join(config.source_ca_dir, 'poly/ipos.json')
    }

    schemas = {}

    print("=" * 80)
    print("HISTORICAL CORPORATE ACTION FILES SCHEMA ANALYSIS")
    print("=" * 80)

    for file_type, pattern in file_patterns.items():
        print(f"\nAnalyzing {file_type} files...")
        print(f"Pattern: {pattern}")

        # Find all matching files
        files = glob.glob(pattern)
        print(f"Found {len(files)} {file_type} files")

        if not files:
            print(f"No {file_type} files found")
            continue

        # Initialize field statistics
        field_stats = defaultdict(lambda: {
            'count': 0,
            'null_count': 0,
            'data_types': set(),
            'sample_values': [],
            'min_length': float('inf'),
            'max_length': 0,
            'unique_values': set(),
            'all_unique_values': set()  # Store ALL unique values for enumeration
        })

        total_records = 0
        processed_files = 0
        skipped_files = 0

        # Process each file
        for file_path in files:
            try:
                # Check file size
                file_size = os.path.getsize(file_path)
                if file_size < 50:  # Skip very small files
                    skipped_files += 1
                    continue

                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                # Handle different JSON structures
                records = []
                if isinstance(data, list):
                    records = data
                elif isinstance(data, dict):
                    if 'results' in data:
                        records = data['results']
                    else:
                        records = [data]

                # Process each record
                for record in records:
                    if isinstance(record, dict):
                        total_records += 1
                        for field_name, field_value in record.items():
                            analyze_poly_field(field_stats[field_name], field_value)

                processed_files += 1

                # Progress indicator
                if processed_files % 50 == 0:
                    print(f"Processed {processed_files} files...")

            except Exception as e:
                print(f"Error processing {file_path}: {e}")
                skipped_files += 1
                continue

        # Save schema for this file type
        schemas[file_type] = {
            'total_files_found': len(files),
            'processed_files': processed_files,
            'skipped_files': skipped_files,
            'total_records': total_records,
            'field_schemas': dict(field_stats)
        }

        print(f"Processed {processed_files} {file_type} files ({total_records} records)")

    # Generate comprehensive output
    output_file = os.path.join(config.debug_dir, config.poly_schema_file)
    save_poly_analysis(schemas, output_file)

    print(f"\nPoly corporate actions analysis saved to: {output_file}")
    return schemas


def analyze_poly_field(field_stats, field_value):
    """Analyze individual field from Polygon data"""
    field_stats['count'] += 1
    
    if field_value is None:
        field_stats['null_count'] += 1
        return
    
    # Data type detection
    field_stats['data_types'].add(type(field_value).__name__)
    
    # String length analysis
    if isinstance(field_value, str):
        length = len(field_value)
        field_stats['min_length'] = min(field_stats['min_length'], length)
        field_stats['max_length'] = max(field_stats['max_length'], length)
    
    # Sample values (limit to avoid memory issues)
    if len(field_stats['sample_values']) < 10:
        field_stats['sample_values'].append(str(field_value))
    
    # Unique values tracking (with reasonable limits)
    if len(field_stats['all_unique_values']) < 100:
        field_stats['all_unique_values'].add(str(field_value))
    
    field_stats['unique_values'].add(str(field_value))


def save_poly_analysis(schemas, output_file):
    """Save Polygon analysis to JSON file"""
    # Ensure output directory exists
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    
    # Convert to JSON-serializable format
    json_output = {
        'analysis_timestamp': datetime.now().isoformat(),
        'file_type_analyses': {}
    }
    
    for file_type, schema in schemas.items():
        json_output['file_type_analyses'][file_type] = {
            'summary': {
                'total_files_found': schema['total_files_found'],
                'processed_files': schema['processed_files'],
                'skipped_files': schema['skipped_files'],
                'total_records': schema['total_records']
            },
            'fields': {}
        }
        
        for field_name, stats in schema['field_schemas'].items():
            json_output['file_type_analyses'][file_type]['fields'][field_name] = {
                'count': stats['count'],
                'null_count': stats['null_count'],
                'null_percentage': round((stats['null_count'] / stats['count']) * 100, 2) if stats['count'] > 0 else 0,
                'data_types': sorted(list(stats['data_types'])),
                'sample_values': stats['sample_values'],
                'unique_value_count': len(stats['unique_values']),
                'string_length': {
                    'min': stats['min_length'] if stats['min_length'] != float('inf') else 0,
                    'max': stats['max_length']
                },
                'enumeration_complete': len(stats['all_unique_values']) < 100
            }
            
            # Add complete enumeration for small sets
            if len(stats['all_unique_values']) <= 20:
                json_output['file_type_analyses'][file_type]['fields'][field_name]['all_possible_values'] = sorted(list(stats['all_unique_values']))
    
    # Save to file
    with open(output_file, 'w') as f:
        json.dump(json_output, f, indent=2, default=str)


if __name__ == "__main__":
    from datetime import datetime
    
    # Ensure directories exist
    config.ensure_directories()
    
    analyze_historical_corporate_actions()
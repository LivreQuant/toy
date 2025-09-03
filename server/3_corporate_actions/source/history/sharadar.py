import csv
import os
import glob
import json
from collections import defaultdict
from typing import Dict, Any, List
from source.config import config


def analyze_sharadar_corporate_actions():
    """
    Analyze Sharadar corporate action CSV files to generate schema by action type.
    """
    # Use configured file pattern
    file_pattern = config.sharadar_ca_pattern

    print("=" * 80)
    print("SHARADAR CORPORATE ACTIONS SCHEMA ANALYSIS")
    print("=" * 80)
    print(f"Using pattern: {file_pattern}")

    # Find all CSV files
    csv_files = glob.glob(file_pattern)
    print(f"Found {len(csv_files)} CSV files")

    if not csv_files:
        print("No CSV files found matching the pattern")
        return {}

    # Data structures for analysis
    action_schemas = defaultdict(lambda: defaultdict(lambda: {
        'count': 0,
        'null_count': 0,
        'empty_count': 0,
        'data_types': set(),
        'sample_values': [],
        'unique_values': set(),
        'all_unique_values': set(),  # Store ALL unique values for enumeration
        'min_length': float('inf'),
        'max_length': 0
    }))

    action_counts = defaultdict(int)
    total_records = 0
    processed_files = 0

    # Process each CSV file
    for file_path in csv_files:
        try:
            file_size = os.path.getsize(file_path)
            if file_size < 100:  # Skip very small files
                continue

            print(f"Processing: {file_path}")

            with open(file_path, 'r', encoding='utf-8') as csvfile:
                # Try to detect the CSV format
                sample = csvfile.read(1024)
                csvfile.seek(0)
                sniffer = csv.Sniffer()
                delimiter = sniffer.sniff(sample).delimiter

                reader = csv.DictReader(csvfile, delimiter=delimiter)

                # Get headers
                headers = reader.fieldnames
                
                # Process each record
                for record in reader:
                    total_records += 1
                    action_type = record.get('action', 'unknown')
                    action_counts[action_type] += 1

                    # Analyze each field
                    for field_name, field_value in record.items():
                        analyze_field(action_schemas[action_type][field_name], field_value)

            processed_files += 1

        except Exception as e:
            print(f"Error processing {file_path}: {e}")
            continue

    # Generate and save comprehensive schema
    output_file = os.path.join(config.debug_dir, config.sharadar_schema_file)
    save_schema_analysis(action_schemas, action_counts, total_records, processed_files, output_file)

    print(f"\nSchema analysis saved to: {output_file}")
    return action_schemas


def analyze_field(field_stats, field_value):
    """Analyze individual field statistics"""
    field_stats['count'] += 1
    
    if field_value is None or field_value == '':
        if field_value is None:
            field_stats['null_count'] += 1
        else:
            field_stats['empty_count'] += 1
        return
    
    # Data type detection
    field_stats['data_types'].add(type(field_value).__name__)
    
    # String length analysis
    if isinstance(field_value, str):
        length = len(field_value)
        field_stats['min_length'] = min(field_stats['min_length'], length)
        field_stats['max_length'] = max(field_stats['max_length'], length)
    
    # Sample values
    if len(field_stats['sample_values']) < 5:
        field_stats['sample_values'].append(str(field_value))
    
    # Unique values tracking
    field_stats['unique_values'].add(str(field_value))
    field_stats['all_unique_values'].add(str(field_value))


def save_schema_analysis(action_schemas, action_counts, total_records, processed_files, output_file):
    """Save comprehensive schema analysis to JSON file"""
    # Ensure output directory exists
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    
    # Convert analysis to JSON-serializable format
    json_output = {
        'summary': {
            'total_records': total_records,
            'processed_files': processed_files,
            'action_types': list(action_counts.keys()),
            'action_counts': dict(action_counts)
        },
        'schemas': {}
    }
    
    for action_type, fields in action_schemas.items():
        json_output['schemas'][action_type] = {
            'total_records': action_counts[action_type],
            'percentage_of_total': round((action_counts[action_type] / total_records) * 100, 2),
            'fields': {}
        }
        
        for field_name, stats in fields.items():
            json_output['schemas'][action_type]['fields'][field_name] = {
                'type': 'string',  # Simplified for now
                'required': stats['null_count'] == 0,
                'nullable_or_empty': stats['null_count'] > 0 or stats['empty_count'] > 0,
                'null_empty_count': stats['null_count'] + stats['empty_count'],
                'null_empty_percentage': round(((stats['null_count'] + stats['empty_count']) / stats['count']) * 100, 2),
                'total_unique_values': len(stats['unique_values']),
                'sample_values': stats['sample_values'],
                'string_length': {
                    'min': stats['min_length'] if stats['min_length'] != float('inf') else 0,
                    'max': stats['max_length']
                }
            }
            
            # Add enumeration for small unique sets
            if len(stats['all_unique_values']) <= 20:
                json_output['schemas'][action_type]['fields'][field_name]['all_possible_values'] = sorted(list(stats['all_unique_values']))
                json_output['schemas'][action_type]['fields'][field_name]['enumeration_complete'] = True
            else:
                json_output['schemas'][action_type]['fields'][field_name]['enumeration_complete'] = False
    
    # Save to file
    with open(output_file, 'w') as f:
        json.dump(json_output, f, indent=2, default=str)


if __name__ == "__main__":
    # Ensure directories exist
    config.ensure_directories()
    
    analyze_sharadar_corporate_actions()
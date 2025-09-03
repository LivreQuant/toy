import json
import os
from collections import defaultdict
from typing import Dict, Any


def analyze_corporate_action_files():
    """
    Analyze corporate action files and generate schema information only.
    """
    # Define the files to analyze
    base_date = "20250829"
    files_config = {
        'dividends': f'/media/samaral/Horse1/market/US_EQUITY/live/corporate_actions/{base_date}/fmp/dividends.json',
        'splits': f'/media/samaral/Horse1/market/US_EQUITY/live/corporate_actions/{base_date}/fmp/splits.json',
        'mergers': f'/media/samaral/Horse1/market/US_EQUITY/live/corporate_actions/{base_date}/fmp/mergers.json',
        'symbol_changes': f'/media/samaral/Horse1/market/US_EQUITY/live/symbols/{base_date}/fmp/symbol_change.json'
    }

    # Data structures for analysis
    schemas = {}

    print("=" * 80)
    print("CORPORATE ACTION FILES SCHEMA ANALYSIS")
    print("=" * 80)

    # Process each file
    for file_type, file_path in files_config.items():
        print(f"\nAnalyzing {file_type}...")

        try:
            if not os.path.exists(file_path):
                print(f"  File not found: {file_path}")
                continue

            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            if not isinstance(data, list):
                print(f"  Expected list, got {type(data).__name__}")
                continue

            print(f"  Found {len(data)} records")

            # Analyze fields
            field_stats = defaultdict(lambda: {
                'count': 0,
                'null_count': 0,
                'data_types': set(),
                'sample_values': [],
                'all_unique_values': set()  # Store ALL unique values for enumeration
            })

            for record in data:
                if isinstance(record, dict):
                    for field_name, field_value in record.items():
                        field_stats[field_name]['count'] += 1

                        if field_value is None:
                            field_stats[field_name]['null_count'] += 1
                            field_stats[field_name]['data_types'].add('null')
                            field_stats[field_name]['all_unique_values'].add(None)
                        else:
                            field_stats[field_name]['data_types'].add(type(field_value).__name__)
                            if len(field_stats[field_name]['sample_values']) < 3:
                                field_stats[field_name]['sample_values'].append(field_value)

                            # Store ALL unique values for enumeration
                            field_stats[field_name]['all_unique_values'].add(field_value)

            # Build schema
            schema = {}
            total_records = len(data)

            for field_name, stats in field_stats.items():
                data_types = list(stats['data_types'])
                primary_type = [t for t in data_types if t != 'null']
                primary_type = primary_type[0] if len(
                    primary_type) == 1 else f"mixed({','.join(primary_type)})" if primary_type else 'null'

                all_unique_count = len(stats['all_unique_values'])

                field_schema = {
                    'type': primary_type,
                    'required': stats['null_count'] == 0,
                    'nullable': stats['null_count'] > 0,
                    'null_count': stats['null_count'],
                    'total_count': stats['count'],
                    'null_percentage': round((stats['null_count'] / total_records) * 100, 1),
                    'total_unique_values': all_unique_count,
                    'sample_values': stats['sample_values'][:3]
                }

                # Add complete enumeration for small sets (<=10 unique values)
                if all_unique_count <= 10:
                    # Convert all values to a sorted list for consistent output
                    all_values = list(stats['all_unique_values'])
                    all_values.sort(key=lambda x: (x is None, x))  # Sort with None first
                    field_schema['all_possible_values'] = all_values
                    field_schema['enumeration_complete'] = True
                else:
                    field_schema['enumeration_complete'] = False

                schema[field_name] = field_schema

            schemas[file_type] = {
                'total_records': total_records,
                'fields': schema
            }

        except Exception as e:
            print(f"  Error: {e}")

    # Print results
    print("\n" + "=" * 80)
    print("SCHEMA RESULTS")
    print("=" * 80)

    for file_type, schema_data in schemas.items():
        print(f"\n{file_type.upper()} ({schema_data['total_records']} records):")
        print("-" * 60)

        for field_name, field_info in schema_data['fields'].items():
            required_text = "REQUIRED" if field_info['required'] else "OPTIONAL"
            nullable_text = "NULLABLE" if field_info['nullable'] else "NOT NULL"

            print(f"  {field_name}:")
            print(f"    Type: {field_info['type']}")
            print(f"    Status: {required_text}, {nullable_text}")
            print(
                f"    Nulls: {field_info['null_count']}/{field_info['total_count']} ({field_info['null_percentage']}%)")
            print(f"    Total unique values: {field_info['total_unique_values']}")

            # Complete enumeration for small sets
            if field_info['enumeration_complete']:
                print(f"    ALL POSSIBLE VALUES: {field_info['all_possible_values']}")
            else:
                # Sample values for large sets
                if field_info['sample_values']:
                    print(f"    Sample values: {field_info['sample_values']}")
            print()

    # Save schema to JSON
    output_file = f"schema_analysis_FMP.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(schemas, f, indent=2, ensure_ascii=False, default=str)

    print(f"Schema saved to: {output_file}")

    return schemas


if __name__ == "__main__":
    analyze_corporate_action_files()
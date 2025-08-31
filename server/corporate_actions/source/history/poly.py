import json
import os
import glob
from collections import defaultdict
from typing import Dict, Any


def analyze_historical_corporate_actions():
    """
    Analyze all historical corporate action files to generate comprehensive schema.
    """
    # File patterns to search
    file_patterns = {
        'dividends': '/media/samaral/Horse1/market/US_EQUITY/live/corporate_actions/*/poly/dividends.json',
        'splits': '/media/samaral/Horse1/market/US_EQUITY/live/corporate_actions/*/poly/splits.json'
    }

    schemas = {}

    print("=" * 80)
    print("HISTORICAL CORPORATE ACTION FILES SCHEMA ANALYSIS")
    print("=" * 80)

    for file_type, pattern in file_patterns.items():
        print(f"\nAnalyzing {file_type} files...")

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
                        # Skip files that don't have expected structure
                        continue

                if not records:
                    continue

                processed_files += 1
                total_records += len(records)

                # Analyze each record
                for record in records:
                    if isinstance(record, dict):
                        for field_name, field_value in record.items():
                            field_stats[field_name]['count'] += 1

                            if field_value is None:
                                field_stats[field_name]['null_count'] += 1
                                field_stats[field_name]['data_types'].add('null')
                                field_stats[field_name]['all_unique_values'].add(None)
                            else:
                                # Track data type
                                data_type = type(field_value).__name__
                                field_stats[field_name]['data_types'].add(data_type)

                                # String length analysis
                                if isinstance(field_value, str):
                                    length = len(field_value)
                                    field_stats[field_name]['min_length'] = min(
                                        field_stats[field_name]['min_length'], length
                                    )
                                    field_stats[field_name]['max_length'] = max(
                                        field_stats[field_name]['max_length'], length
                                    )

                                # Sample values (limit to avoid memory issues)
                                if len(field_stats[field_name]['sample_values']) < 5:
                                    str_value = str(field_value)
                                    if len(str_value) <= 100:
                                        field_stats[field_name]['sample_values'].append(field_value)

                                # Limited unique values for display
                                if len(field_stats[field_name]['unique_values']) < 100:
                                    field_stats[field_name]['unique_values'].add(str(field_value))

                                # ALL unique values for enumeration (for small sets)
                                field_stats[field_name]['all_unique_values'].add(field_value)

                # Progress indicator
                if processed_files % 50 == 0:
                    print(f"  Processed {processed_files} files...")

            except (json.JSONDecodeError, FileNotFoundError, PermissionError) as e:
                skipped_files += 1
                continue
            except Exception as e:
                print(f"  Error processing {file_path}: {e}")
                skipped_files += 1
                continue

        print(f"  Processed: {processed_files} files")
        print(f"  Skipped: {skipped_files} files")
        print(f"  Total records: {total_records}")

        # Build schema
        if not field_stats:
            print(f"  No valid data found for {file_type}")
            continue

        schema = {}
        for field_name, stats in field_stats.items():
            # Determine primary data type
            data_types = list(stats['data_types'])
            non_null_types = [t for t in data_types if t != 'null']

            if not non_null_types:
                primary_type = 'null'
            elif len(non_null_types) == 1:
                primary_type = non_null_types[0]
            else:
                primary_type = f"mixed({','.join(sorted(non_null_types))})"

            # Calculate statistics
            null_percentage = round((stats['null_count'] / total_records) * 100, 2)
            unique_count = len(stats['unique_values'])
            all_unique_count = len(stats['all_unique_values'])

            field_schema = {
                'type': primary_type,
                'required': stats['null_count'] == 0,
                'nullable': stats['null_count'] > 0,
                'occurrences': stats['count'],
                'null_count': stats['null_count'],
                'null_percentage': null_percentage,
                'unique_values_sampled': unique_count,
                'total_unique_values': all_unique_count,
                'sample_values': stats['sample_values']
            }

            # Add string length info if applicable
            if stats['min_length'] != float('inf'):
                field_schema['string_length'] = {
                    'min': stats['min_length'],
                    'max': stats['max_length']
                }

            # Add complete enumeration for small sets (<=10 unique values)
            if all_unique_count <= 10:
                # Convert all values to strings for consistent JSON serialization
                # but keep original values for display
                all_values = list(stats['all_unique_values'])
                all_values.sort(key=lambda x: (x is None, x))  # Sort with None first
                field_schema['all_possible_values'] = all_values
                field_schema['enumeration_complete'] = True
            else:
                field_schema['enumeration_complete'] = False

            schema[field_name] = field_schema

        schemas[file_type] = {
            'total_files_processed': processed_files,
            'total_files_skipped': skipped_files,
            'total_records': total_records,
            'fields': schema
        }

    # Generate report
    generate_schema_report(schemas)
    return schemas


def generate_schema_report(schemas: Dict[str, Any]):
    """
    Generate and display the schema report.
    """
    print("\n" + "=" * 80)
    print("COMPREHENSIVE SCHEMA ANALYSIS")
    print("=" * 80)

    for file_type, schema_data in schemas.items():
        print(f"\n{file_type.upper()} SCHEMA:")
        print(f"Files processed: {schema_data['total_files_processed']}")
        print(f"Total records: {schema_data['total_records']}")
        print("-" * 60)

        # Sort fields by name for consistent output
        for field_name in sorted(schema_data['fields'].keys()):
            field_info = schema_data['fields'][field_name]

            required_status = "REQUIRED" if field_info['required'] else "OPTIONAL"
            nullable_status = "NULLABLE" if field_info['nullable'] else "NOT NULL"

            print(f"\n  {field_name}:")
            print(f"    Type: {field_info['type']}")
            print(f"    Status: {required_status}, {nullable_status}")
            print(f"    Occurrences: {field_info['occurrences']:,}")
            print(f"    Nulls: {field_info['null_count']:,} ({field_info['null_percentage']}%)")
            print(f"    Total unique values: {field_info['total_unique_values']:,}")

            # String length info
            if 'string_length' in field_info:
                print(
                    f"    String length: {field_info['string_length']['min']}-{field_info['string_length']['max']} chars")

            # Complete enumeration for small sets
            if field_info['enumeration_complete']:
                print(f"    ALL POSSIBLE VALUES: {field_info['all_possible_values']}")
            else:
                # Sample values for large sets
                if field_info['sample_values']:
                    print(f"    Sample values: {field_info['sample_values']}")

    # Save schema to file
    output_file = "schema_analysis_POLY.json"
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(schemas, f, indent=2, ensure_ascii=False, default=str)
        print(f"\n✓ Complete schema saved to: {output_file}")
    except Exception as e:
        print(f"\n✗ Error saving schema: {e}")


if __name__ == "__main__":
    print("Starting historical corporate actions schema analysis...")
    print("This will process all dividend and split files in the directory structure...")

    try:
        schemas = analyze_historical_corporate_actions()

        print("\n" + "=" * 80)
        print("ANALYSIS COMPLETE")
        print("=" * 80)
        print("Schema analysis covers:")
        for file_type, data in schemas.items():
            print(f"  - {file_type}: {data['total_records']:,} records from {data['total_files_processed']} files")

    except KeyboardInterrupt:
        print("\nAnalysis interrupted by user.")
    except Exception as e:
        print(f"Fatal error: {e}")
        raise
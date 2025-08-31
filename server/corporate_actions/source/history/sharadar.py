import csv
import os
import glob
import json
from collections import defaultdict
from typing import Dict, Any, List


def analyze_sharadar_corporate_actions():
    """
    Analyze Sharadar corporate action CSV files to generate schema by action type.
    """
    # File pattern to search
    file_pattern = '/media/samaral/Horse1/market/US_EQUITY/live/corporate_actions/*/sharadar/*.csv'

    print("=" * 80)
    print("SHARADAR CORPORATE ACTIONS SCHEMA ANALYSIS")
    print("=" * 80)

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
                print(f"  Headers: {headers}")

                file_record_count = 0

                for row in reader:
                    file_record_count += 1
                    total_records += 1

                    # Get action type
                    action_type = row.get('action', '').strip()
                    if not action_type:
                        continue

                    action_counts[action_type] += 1

                    # Analyze each field for this action type
                    for field_name, field_value in row.items():
                        if field_name is None:
                            continue

                        field_name = field_name.strip()
                        field_stats = action_schemas[action_type][field_name]
                        field_stats['count'] += 1

                        # Handle null/empty values
                        if field_value is None:
                            field_stats['null_count'] += 1
                            field_stats['data_types'].add('null')
                            field_stats['all_unique_values'].add(None)
                        elif field_value.strip() == '':
                            field_stats['empty_count'] += 1
                            field_stats['data_types'].add('empty_string')
                            field_stats['all_unique_values'].add('')
                        else:
                            # Clean the value
                            cleaned_value = field_value.strip()

                            # Determine data type
                            data_type = detect_data_type(cleaned_value)
                            field_stats['data_types'].add(data_type)

                            # String length analysis
                            length = len(cleaned_value)
                            field_stats['min_length'] = min(field_stats['min_length'], length)
                            field_stats['max_length'] = max(field_stats['max_length'], length)

                            # Sample values (limit to 5 per field per action)
                            if len(field_stats['sample_values']) < 5:
                                if len(cleaned_value) <= 100:  # Avoid very long values
                                    field_stats['sample_values'].append(cleaned_value)

                            # Limited unique values for display (legacy)
                            if len(field_stats['unique_values']) < 50:
                                field_stats['unique_values'].add(cleaned_value)

                            # ALL unique values for enumeration
                            field_stats['all_unique_values'].add(cleaned_value)

                print(f"  Records: {file_record_count:,}")
                processed_files += 1

        except Exception as e:
            print(f"  Error processing {file_path}: {e}")
            continue

    print(f"\nProcessed {processed_files} files with {total_records:,} total records")

    # Generate comprehensive report
    generate_sharadar_report(action_schemas, action_counts, total_records)

    return action_schemas, action_counts


def detect_data_type(value: str) -> str:
    """
    Detect the data type of a string value.
    """
    # Try integer
    try:
        int(value)
        return 'int'
    except ValueError:
        pass

    # Try float
    try:
        float(value)
        return 'float'
    except ValueError:
        pass

    # Check if it looks like a date
    if len(value) == 10 and value.count('-') == 2:
        try:
            parts = value.split('-')
            if len(parts[0]) == 4 and len(parts[1]) == 2 and len(parts[2]) == 2:
                return 'date'
        except:
            pass

    # Default to string
    return 'string'


def generate_sharadar_report(action_schemas: Dict, action_counts: Dict, total_records: int):
    """
    Generate comprehensive report of Sharadar corporate actions schema.
    """
    print("\n" + "=" * 80)
    print("SHARADAR CORPORATE ACTIONS ANALYSIS REPORT")
    print("=" * 80)

    print(f"\nTOTAL RECORDS ANALYZED: {total_records:,}")
    print(f"UNIQUE ACTION TYPES: {len(action_counts)}")

    # Action type summary
    print(f"\nACTION TYPES SUMMARY:")
    print("-" * 40)
    for action_type in sorted(action_counts.keys()):
        count = action_counts[action_type]
        percentage = (count / total_records) * 100
        print(f"  {action_type}: {count:,} records ({percentage:.2f}%)")

    # Detailed schema for each action type
    print(f"\nDETAILED SCHEMA BY ACTION TYPE:")
    print("=" * 80)

    schemas_output = {}

    for action_type in sorted(action_schemas.keys()):
        print(f"\n{action_type.upper()} ({action_counts[action_type]:,} records):")
        print("-" * 60)

        action_schema = {}
        field_schemas = action_schemas[action_type]

        for field_name in sorted(field_schemas.keys()):
            field_stats = field_schemas[field_name]

            # Determine primary data type
            data_types = list(field_stats['data_types'])
            non_empty_types = [t for t in data_types if t not in ['null', 'empty_string']]

            if not non_empty_types:
                primary_type = 'null/empty'
            elif len(non_empty_types) == 1:
                primary_type = non_empty_types[0]
            else:
                primary_type = f"mixed({','.join(sorted(non_empty_types))})"

            # Calculate statistics
            total_nulls_empties = field_stats['null_count'] + field_stats['empty_count']
            null_empty_percentage = round((total_nulls_empties / action_counts[action_type]) * 100, 2)
            unique_count = len(field_stats['unique_values'])
            all_unique_count = len(field_stats['all_unique_values'])

            # Determine if field is effectively required
            is_required = total_nulls_empties == 0

            print(f"\n  {field_name}:")
            print(f"    Type: {primary_type}")
            print(f"    Status: {'REQUIRED' if is_required else 'OPTIONAL'}")
            print(f"    Nullable/Empty: {'NO' if is_required else 'YES'}")
            print(f"    Null/Empty count: {total_nulls_empties:,} ({null_empty_percentage}%)")
            print(f"    Total unique values: {all_unique_count:,}")

            # String length info
            if field_stats['min_length'] != float('inf'):
                print(f"    String length: {field_stats['min_length']}-{field_stats['max_length']} chars")

            # Complete enumeration for small sets or samples for large sets
            if all_unique_count <= 10:
                # Show all possible values for bounded sets
                all_values = list(field_stats['all_unique_values'])
                all_values.sort(key=lambda x: (x is None, x == '', x))  # Sort with None and empty first
                print(f"    ALL POSSIBLE VALUES: {all_values}")
            else:
                # Show sample values for large sets
                if field_stats['sample_values']:
                    print(f"    Sample values: {field_stats['sample_values']}")

            # Build schema object
            field_schema = {
                'type': primary_type,
                'required': is_required,
                'nullable_or_empty': not is_required,
                'null_empty_count': total_nulls_empties,
                'null_empty_percentage': null_empty_percentage,
                'total_unique_values': all_unique_count,
                'sample_values': field_stats['sample_values']
            }

            if field_stats['min_length'] != float('inf'):
                field_schema['string_length'] = {
                    'min': field_stats['min_length'],
                    'max': field_stats['max_length']
                }

            # Add complete enumeration for small sets (<=10 unique values)
            if all_unique_count <= 10:
                all_values = list(field_stats['all_unique_values'])
                all_values.sort(key=lambda x: (x is None, x == '', x))
                field_schema['all_possible_values'] = all_values
                field_schema['enumeration_complete'] = True
            else:
                field_schema['enumeration_complete'] = False

            action_schema[field_name] = field_schema

        schemas_output[action_type] = {
            'total_records': action_counts[action_type],
            'percentage_of_total': round((action_counts[action_type] / total_records) * 100, 2),
            'fields': action_schema
        }

    # Save comprehensive schema
    output_data = {
        'metadata': {
            'total_records': total_records,
            'total_action_types': len(action_counts),
            'analysis_summary': dict(action_counts)
        },
        'schemas_by_action': schemas_output
    }

    # Save to JSON file
    output_file = "schema_analysis_SHARADAR.json"
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False, default=str)
        print(f"\n✓ Complete schema saved to: {output_file}")
    except Exception as e:
        print(f"\n✗ Error saving schema: {e}")

    # Print summary with enumeration info
    print(f"\n" + "=" * 80)
    print("ANALYSIS SUMMARY")
    print("=" * 80)
    print(f"Total Records: {total_records:,}")
    print(f"Action Types: {len(action_counts)}")
    print("Most Common Actions:")
    sorted_actions = sorted(action_counts.items(), key=lambda x: x[1], reverse=True)
    for action, count in sorted_actions[:5]:
        percentage = (count / total_records) * 100
        print(f"  {action}: {count:,} ({percentage:.1f}%)")


if __name__ == "__main__":
    print("Starting Sharadar corporate actions analysis...")

    try:
        action_schemas, action_counts = analyze_sharadar_corporate_actions()

        print("\n" + "=" * 80)
        print("ANALYSIS COMPLETE")
        print("=" * 80)
        print("Schema file generated: schema_analysis_SHARADAR.json")

    except KeyboardInterrupt:
        print("\nAnalysis interrupted by user.")
    except Exception as e:
        print(f"Fatal error: {e}")
        raise
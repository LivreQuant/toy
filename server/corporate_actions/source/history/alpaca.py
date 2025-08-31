import json
import os
import glob
from collections import defaultdict
from typing import Dict, Any, Set, List


def analyze_corporate_actions():
    """
    Analyze corporate action files to understand all possible types and their structures.
    """
    # Path pattern for the files
    file_pattern = "/media/samaral/Horse1/market/US_EQUITY/live/corporate_actions/*/alpaca/*.json"

    # Data structures to collect information
    corporate_action_types = set()
    field_analysis = defaultdict(lambda: {
        'count': 0,
        'data_types': set(),
        'sample_values': set(),
        'all_unique_values': set(),  # Store ALL unique values for enumeration
        'null_count': 0
    })

    # Statistics
    total_files = 0
    processed_files = 0
    skipped_files = 0
    total_actions = defaultdict(int)

    # Get all matching files
    files = glob.glob(file_pattern)
    total_files = len(files)

    print(f"Found {total_files} files to analyze...")

    for file_path in files:
        try:
            # Check file size
            file_size = os.path.getsize(file_path)
            if file_size < 75:
                skipped_files += 1
                continue

            processed_files += 1

            # Load and parse JSON
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Extract corporate actions
            corporate_actions = data.get('corporate_actions', {})

            # Process each type of corporate action
            for action_type, actions_list in corporate_actions.items():
                if isinstance(actions_list, list) and actions_list:
                    corporate_action_types.add(action_type)
                    total_actions[action_type] += len(actions_list)

                    # Analyze each action in the list
                    for action in actions_list:
                        if isinstance(action, dict):
                            analyze_action_fields(action, field_analysis, action_type)

            # Progress indicator
            if processed_files % 100 == 0:
                print(f"Processed {processed_files} files...")

        except (json.JSONDecodeError, FileNotFoundError, PermissionError) as e:
            print(f"Error processing {file_path}: {e}")
            continue
        except Exception as e:
            print(f"Unexpected error processing {file_path}: {e}")
            continue

    # Generate comprehensive report
    generate_report(
        corporate_action_types,
        field_analysis,
        total_files,
        processed_files,
        skipped_files,
        total_actions
    )


def analyze_action_fields(action: Dict[str, Any], field_analysis: Dict, action_type: str):
    """
    Analyze individual action fields to understand data types and patterns.
    """
    for field_name, field_value in action.items():
        # Create unique field key with action type
        field_key = f"{action_type}.{field_name}"

        # Count occurrences
        field_analysis[field_key]['count'] += 1

        # Track data types
        if field_value is None:
            field_analysis[field_key]['null_count'] += 1
            field_analysis[field_key]['data_types'].add('null')
            field_analysis[field_key]['all_unique_values'].add(None)
        else:
            field_analysis[field_key]['data_types'].add(type(field_value).__name__)

            # Store sample values (limit to prevent memory issues)
            if len(field_analysis[field_key]['sample_values']) < 10:
                # Convert to string for consistent storage
                sample_value = str(field_value)
                if len(sample_value) <= 100:  # Avoid very long strings
                    field_analysis[field_key]['sample_values'].add(sample_value)

            # Store ALL unique values for enumeration
            field_analysis[field_key]['all_unique_values'].add(field_value)


def generate_report(corporate_action_types: Set[str],
                    field_analysis: Dict,
                    total_files: int,
                    processed_files: int,
                    skipped_files: int,
                    total_actions: Dict[str, int]):
    """
    Generate a comprehensive report of the analysis.
    """
    print("\n" + "=" * 80)
    print("CORPORATE ACTIONS ANALYSIS REPORT")
    print("=" * 80)

    # File statistics
    print(f"\nFILE STATISTICS:")
    print(f"Total files found: {total_files}")
    print(f"Files processed: {processed_files}")
    print(f"Files skipped (< 75B): {skipped_files}")

    # Corporate action types
    print(f"\nCORPORATE ACTION TYPES DISCOVERED:")
    print(f"Total unique types: {len(corporate_action_types)}")
    for action_type in sorted(corporate_action_types):
        count = total_actions.get(action_type, 0)
        print(f"  - {action_type}: {count} total actions")

    # Detailed field analysis
    print(f"\nDETAILED FIELD ANALYSIS:")
    print("-" * 80)

    # Group fields by action type
    fields_by_action = defaultdict(list)
    for field_key in field_analysis.keys():
        action_type, field_name = field_key.split('.', 1)
        fields_by_action[action_type].append((field_name, field_key))

    for action_type in sorted(fields_by_action.keys()):
        print(f"\n{action_type.upper()}:")

        for field_name, field_key in sorted(fields_by_action[action_type]):
            field_info = field_analysis[field_key]
            data_types = ', '.join(sorted(field_info['data_types']))
            all_unique_count = len(field_info['all_unique_values'])

            print(f"  {field_name}:")
            print(f"    Count: {field_info['count']}")
            print(f"    Data Types: {data_types}")
            print(f"    Null Count: {field_info['null_count']}")
            print(f"    Total unique values: {all_unique_count}")

            # Complete enumeration for small sets or samples for large sets
            if all_unique_count <= 10:
                # Show all possible values for bounded sets
                all_values = list(field_info['all_unique_values'])
                all_values.sort(key=lambda x: (x is None, x))  # Sort with None first
                print(f"    ALL POSSIBLE VALUES: {all_values}")
            else:
                # Show sample values for large sets
                if field_info['sample_values']:
                    sample_values = list(field_info['sample_values'])[:5]  # Show max 5 samples
                    print(f"    Sample values: {sample_values}")
            print()

    # Generate schema template
    generate_schema_template(fields_by_action, field_analysis)


def generate_schema_template(fields_by_action: Dict[str, List], field_analysis: Dict):
    """
    Generate a schema template based on the discovered fields.
    """
    print("\n" + "=" * 80)
    print("SCHEMA TEMPLATE FOR REAL-TIME PROCESSING")
    print("=" * 80)

    schema = {}

    for action_type in sorted(fields_by_action.keys()):
        schema[action_type] = {}

        for field_name, field_key in sorted(fields_by_action[action_type]):
            field_info = field_analysis[field_key]

            # Determine primary data type
            data_types = field_info['data_types'] - {'null'}
            if data_types:
                primary_type = list(data_types)[0] if len(data_types) == 1 else 'mixed'
            else:
                primary_type = 'null'

            # Determine if field is required (appears in most records)
            is_required = field_info['null_count'] == 0
            all_unique_count = len(field_info['all_unique_values'])

            field_schema = {
                'type': primary_type,
                'required': is_required,
                'null_count': field_info['null_count'],
                'total_count': field_info['count'],
                'total_unique_values': all_unique_count
            }

            # Add complete enumeration for small sets (<=10 unique values)
            if all_unique_count <= 10:
                all_values = list(field_info['all_unique_values'])
                all_values.sort(key=lambda x: (x is None, x))  # Sort with None first
                field_schema['all_possible_values'] = all_values
                field_schema['enumeration_complete'] = True
            else:
                field_schema['enumeration_complete'] = False
                field_schema['sample_values'] = list(field_info['sample_values'])[:5]

            schema[action_type][field_name] = field_schema

    # Print schema as JSON
    print(json.dumps(schema, indent=2, default=str))

    # Save schema to file
    schema_file = "schema_analysis_ALPACA.json"
    try:
        with open(schema_file, 'w') as f:
            json.dump(schema, f, indent=2, default=str)
        print(f"\nSchema saved to: {schema_file}")
    except Exception as e:
        print(f"Error saving schema: {e}")


if __name__ == "__main__":
    print("Starting Corporate Actions Analysis...")
    print("This may take a few minutes to process ~270 days of data...")

    try:
        analyze_corporate_actions()

        print("\n" + "=" * 80)
        print("ANALYSIS COMPLETE!")
        print("=" * 80)
        print("Files generated:")
        print("  - schema_analysis_ALPACA.json")

    except KeyboardInterrupt:
        print("\nAnalysis interrupted by user.")
    except Exception as e:
        print(f"Fatal error during analysis: {e}")
        raise
import json
import os
import glob
from collections import defaultdict
from typing import Dict, Any, Set, List
from source.config import config


def analyze_corporate_actions():
    """
    Analyze corporate action files to understand all possible types and their structures.
    """
    # Use configured file pattern
    file_pattern = config.alpaca_ca_pattern

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
    print(f"Using pattern: {file_pattern}")

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
        
        field_analysis[field_key]['count'] += 1
        
        if field_value is None:
            field_analysis[field_key]['null_count'] += 1
        else:
            # Track data types
            field_analysis[field_key]['data_types'].add(type(field_value).__name__)
            
            # Store sample values (limit to avoid memory issues)
            if len(field_analysis[field_key]['sample_values']) < 10:
                field_analysis[field_key]['sample_values'].add(str(field_value))
            
            # Store all unique values for enumeration (with reasonable limit)
            if len(field_analysis[field_key]['all_unique_values']) < 100:
                field_analysis[field_key]['all_unique_values'].add(str(field_value))


def generate_report(
    corporate_action_types: Set[str],
    field_analysis: Dict,
    total_files: int,
    processed_files: int,
    skipped_files: int,
    total_actions: Dict[str, int]
):
    """
    Generate comprehensive analysis report and save to file.
    """
    # Ensure output directory exists
    os.makedirs(config.debug_dir, exist_ok=True)
    
    output_file = os.path.join(config.debug_dir, config.alpaca_schema_file)
    
    # Create comprehensive JSON output
    json_output = {
        'analysis_summary': {
            'total_files_found': total_files,
            'processed_files': processed_files,
            'skipped_files': skipped_files,
            'corporate_action_types': sorted(list(corporate_action_types)),
            'total_actions_by_type': dict(total_actions)
        },
        'field_analysis': {}
    }
    
    # Process field analysis
    for field_key, analysis in field_analysis.items():
        action_type, field_name = field_key.split('.', 1)
        
        if action_type not in json_output['field_analysis']:
            json_output['field_analysis'][action_type] = {}
        
        json_output['field_analysis'][action_type][field_name] = {
            'count': analysis['count'],
            'null_count': analysis['null_count'],
            'data_types': sorted(list(analysis['data_types'])),
            'sample_values': sorted(list(analysis['sample_values']))[:10],
            'unique_value_count': len(analysis['all_unique_values']),
            'enumeration_complete': len(analysis['all_unique_values']) < 100
        }
        
        # Add complete enumeration for small sets
        if len(analysis['all_unique_values']) <= 20:
            json_output['field_analysis'][action_type][field_name]['all_possible_values'] = sorted(list(analysis['all_unique_values']))
    
    # Save analysis to file
    with open(output_file, 'w') as f:
        json.dump(json_output, f, indent=2, default=str)
    
    print(f"\nAlpaca corporate actions analysis saved to: {output_file}")
    
    # Print summary to console
    print(f"\nANALYSIS SUMMARY:")
    print(f"Files processed: {processed_files}/{total_files} (skipped: {skipped_files})")
    print(f"Corporate action types found: {len(corporate_action_types)}")
    for action_type in sorted(corporate_action_types):
        print(f"  - {action_type}: {total_actions[action_type]} records")


if __name__ == "__main__":
    # Ensure directories exist
    config.ensure_directories()
    
    analyze_corporate_actions()
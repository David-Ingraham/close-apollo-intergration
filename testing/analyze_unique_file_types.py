#!/usr/bin/env python3
"""
Analyze one instance of each unique file type pattern
Strips numbers/dates from filenames to identify unique structures
"""

import os
import json
import glob
import re

def strip_numbers_from_filename(filename):
    """Remove all numbers, dates, and timestamps from filename"""
    # Remove .json extension first
    base = filename.replace('.json', '')
    
    # Remove date patterns like 20250819_182037_1755642037
    base = re.sub(r'\d{8}_\d{6}_\d{10}', '', base)
    
    # Remove other date patterns like 2025-08-19_15-14-47
    base = re.sub(r'\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}', '', base)
    
    # Remove any remaining numbers
    base = re.sub(r'\d+', '', base)
    
    # Clean up any double underscores or trailing underscores
    base = re.sub(r'_+', '_', base)
    base = base.strip('_')
    
    return base

def analyze_file_structure(file_path):
    """Quick analysis of a single file structure"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Get basic info
        if isinstance(data, dict):
            keys = list(data.keys())
            root_type = "object"
        elif isinstance(data, list):
            keys = [f"array[{len(data)}]"]
            root_type = "array"
        else:
            keys = [str(type(data))]
            root_type = str(type(data))
        
        # Look for phone patterns
        phone_count = 0
        if isinstance(data, (dict, list)):
            # Count actual phone numbers, not just the key
            def count_phones_recursive(obj):
                count = 0
                if isinstance(obj, dict):
                    for key, value in obj.items():
                        if key == 'raw_number' and isinstance(value, str) and value.startswith('+'):
                            count += 1
                        elif key == 'sanitized_number' and isinstance(value, str) and value.startswith('+'):
                            count += 1
                        elif key == 'phone_numbers' and isinstance(value, list):
                            count += len(value)  # Each item in phone_numbers array
                        else:
                            count += count_phones_recursive(value)
                elif isinstance(obj, list):
                    for item in obj:
                        count += count_phones_recursive(item)
                return count
            
            phone_count = count_phones_recursive(data)
        
        return {
            'status': 'valid',
            'root_type': root_type,
            'keys': keys[:5],  # First 5 keys
            'phone_count': phone_count,
            'size': len(str(data))
        }
        
    except json.JSONDecodeError as e:
        return {
            'status': 'malformed',
            'error': str(e),
            'phone_count': 0
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e),
            'phone_count': 0
        }

def main():
    print("="*60)
    print("UNIQUE FILE TYPE ANALYSIS")
    print("="*60)
    
    # Get all JSON files
    json_files = glob.glob('json/*.json')
    print(f"Found {len(json_files)} total JSON files\n")
    
    # Create list of base filename patterns (without numbers)
    base_patterns = []
    for filename in json_files:
        base_name = os.path.basename(filename)
        base_pattern = strip_numbers_from_filename(base_name)
        base_patterns.append(base_pattern)
    
    # Convert to set to get unique patterns
    unique_patterns = set(base_patterns)
    print(f"Found {len(unique_patterns)} unique file types:\n")
    
    # Analyze one instance of each pattern
    for pattern in sorted(unique_patterns):
        # Find first file matching this pattern
        matching_files = glob.glob(f'json/{pattern}*.json')
        if matching_files:
            first_file = sorted(matching_files)[0]
            filename = os.path.basename(first_file)
            
            print(f"--- {pattern.upper()} ---")
            print(f"Example file: {filename}")
            
            # Analyze the file
            analysis = analyze_file_structure(first_file)
            
            if analysis['status'] == 'valid':
                print(f"  Root type: {analysis['root_type']}")
                print(f"  Keys: {analysis['keys']}")
                print(f"  Phone patterns: {analysis['phone_count']}")
                print(f"  Size: {analysis['size']:,} chars")
            else:
                print(f"  Status: {analysis['status']}")
                if 'error' in analysis:
                    print(f"  Error: {analysis['error']}")
                print(f"  Phone patterns: {analysis['phone_count']}")
            
            print(f"  Total files with this pattern: {len(matching_files)}")
            print()

if __name__ == "__main__":
    main()

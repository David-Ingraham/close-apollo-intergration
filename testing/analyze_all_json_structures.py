#!/usr/bin/env python3
"""
Comprehensive JSON Structure Analysis Script
Analyzes every JSON file in the json/ folder to understand data structures
"""

import os
import json
import glob
from collections import defaultdict, Counter

def safe_get_type(obj):
    """Get type description for any object"""
    if obj is None:
        return "null"
    elif isinstance(obj, bool):
        return "boolean"
    elif isinstance(obj, int):
        return "integer"
    elif isinstance(obj, float):
        return "float"
    elif isinstance(obj, str):
        return "string"
    elif isinstance(obj, list):
        if len(obj) == 0:
            return "array(empty)"
        else:
            # Sample first few items to understand array content
            sample_types = [safe_get_type(item) for item in obj[:3]]
            if len(set(sample_types)) == 1:
                return f"array({sample_types[0]}, len={len(obj)})"
            else:
                return f"array(mixed: {', '.join(set(sample_types))}, len={len(obj)})"
    elif isinstance(obj, dict):
        return f"object({len(obj)} keys)"
    else:
        return f"unknown({type(obj).__name__})"

def analyze_object_structure(obj, path="", max_depth=3, current_depth=0):
    """Recursively analyze object structure"""
    structure = {}
    
    if current_depth >= max_depth:
        return {"...": "max_depth_reached"}
    
    if isinstance(obj, dict):
        for key, value in obj.items():
            key_path = f"{path}.{key}" if path else key
            if isinstance(value, (dict, list)) and current_depth < max_depth - 1:
                structure[key] = analyze_object_structure(value, key_path, max_depth, current_depth + 1)
            else:
                structure[key] = safe_get_type(value)
    elif isinstance(obj, list) and len(obj) > 0:
        # Analyze first item to understand array structure
        first_item = obj[0]
        if isinstance(first_item, (dict, list)) and current_depth < max_depth - 1:
            structure = {"[0]": analyze_object_structure(first_item, f"{path}[0]", max_depth, current_depth + 1)}
        else:
            structure = {"[items]": safe_get_type(first_item)}
    
    return structure

def find_phone_patterns(obj, file_path="", path=""):
    """Find all phone-related patterns in the object"""
    patterns = []
    
    if isinstance(obj, dict):
        for key, value in obj.items():
            key_path = f"{path}.{key}" if path else key
            
            # Check for phone-related keys
            if any(phone_key in key.lower() for phone_key in ['phone', 'number', 'raw_number', 'sanitized']):
                patterns.append({
                    'file': file_path,
                    'path': key_path,
                    'key': key,
                    'value_type': safe_get_type(value),
                    'value': str(value)[:100] if isinstance(value, str) else value
                })
            
            # Recursively search in nested objects
            patterns.extend(find_phone_patterns(value, file_path, key_path))
    
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            patterns.extend(find_phone_patterns(item, file_path, f"{path}[{i}]"))
    
    return patterns

def analyze_json_file(file_path):
    """Analyze a single JSON file"""
    filename = os.path.basename(file_path)
    result = {
        'filename': filename,
        'size_bytes': os.path.getsize(file_path),
        'status': 'unknown',
        'structure': None,
        'phone_patterns': [],
        'error': None,
        'root_type': None,
        'sample_keys': []
    }
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Try to parse as JSON
        try:
            data = json.loads(content)
            result['status'] = 'valid_json'
            result['root_type'] = safe_get_type(data)
            
            # Get sample keys if it's an object
            if isinstance(data, dict):
                result['sample_keys'] = list(data.keys())[:10]
            
            # Analyze structure
            result['structure'] = analyze_object_structure(data)
            
            # Find phone patterns
            result['phone_patterns'] = find_phone_patterns(data, filename)
            
        except json.JSONDecodeError as e:
            result['status'] = 'malformed_json'
            result['error'] = str(e)
            
            # Try to count raw_number occurrences in malformed JSON
            raw_number_count = content.count('"raw_number"')
            if raw_number_count > 0:
                result['phone_patterns'] = [{'note': f'Found {raw_number_count} raw_number occurrences in malformed JSON'}]
    
    except Exception as e:
        result['status'] = 'file_error'
        result['error'] = str(e)
    
    return result

def main():
    print("="*80)
    print("COMPREHENSIVE JSON FILE STRUCTURE ANALYSIS")
    print("="*80)
    
    # Get all JSON files
    json_files = glob.glob('json/*.json')
    print(f"Found {len(json_files)} JSON files to analyze\n")
    
    all_results = []
    phone_summary = Counter()
    structure_summary = Counter()
    error_files = []
    
    for file_path in sorted(json_files):
        result = analyze_json_file(file_path)
        all_results.append(result)
        
        # Track summaries
        phone_summary[len(result['phone_patterns'])] += 1
        structure_summary[result['status']] += 1
        
        if result['status'] != 'valid_json':
            error_files.append(result)
        
        # Print brief status
        status_char = "✓" if result['status'] == 'valid_json' else "✗"
        phone_count = len(result['phone_patterns'])
        print(f"{status_char} {result['filename']:<50} | {result['status']:<15} | {phone_count:>3} phone patterns")
    
    print("\n" + "="*80)
    print("SUMMARY STATISTICS")
    print("="*80)
    
    print(f"Total files: {len(all_results)}")
    print(f"File status breakdown:")
    for status, count in structure_summary.items():
        print(f"  - {status}: {count}")
    
    print(f"\nPhone pattern distribution:")
    for phone_count, file_count in sorted(phone_summary.items()):
        print(f"  - {phone_count} phone patterns: {file_count} files")
    
    # Show files with most phone patterns
    print(f"\nFiles with most phone patterns:")
    top_phone_files = sorted(all_results, key=lambda x: len(x['phone_patterns']), reverse=True)[:10]
    for result in top_phone_files:
        if len(result['phone_patterns']) > 0:
            print(f"  - {result['filename']}: {len(result['phone_patterns'])} patterns")
    
    # Show unique file structures
    print(f"\nUnique root data types:")
    root_types = Counter(r['root_type'] for r in all_results if r['root_type'])
    for root_type, count in root_types.items():
        print(f"  - {root_type}: {count} files")
    
    # Show error files in detail
    if error_files:
        print(f"\n" + "="*80)
        print("PROBLEMATIC FILES DETAILED ANALYSIS")
        print("="*80)
        
        for result in error_files:
            print(f"\nFile: {result['filename']}")
            print(f"Status: {result['status']}")
            print(f"Error: {result['error']}")
            print(f"Size: {result['size_bytes']} bytes")
            if result['phone_patterns']:
                print(f"Phone patterns found: {result['phone_patterns']}")
    
    # Show sample structures
    print(f"\n" + "="*80)
    print("SAMPLE FILE STRUCTURES")
    print("="*80)
    
    # Group files by similar structures
    structure_groups = defaultdict(list)
    for result in all_results:
        if result['status'] == 'valid_json' and result['sample_keys']:
            key_signature = tuple(sorted(result['sample_keys']))
            structure_groups[key_signature].append(result)
    
    for keys, files in structure_groups.items():
        if len(files) > 1:  # Only show common structures
            print(f"\nStructure with keys {list(keys)[:5]}{'...' if len(keys) > 5 else ''}:")
            print(f"  Found in {len(files)} files:")
            for file_result in files[:3]:  # Show first 3 examples
                print(f"    - {file_result['filename']}")
            if len(files) > 3:
                print(f"    ... and {len(files) - 3} more files")
    
    # Detailed analysis of a few representative files
    print(f"\n" + "="*80)
    print("DETAILED STRUCTURE EXAMPLES")
    print("="*80)
    
    # Show structure of files with different patterns
    example_files = []
    
    # Pick one file from each major category
    categories = {
        'apollo_num_response': lambda f: f.startswith('apollo_num_response'),
        'enrichment_results': lambda f: f.startswith('enrichment_results'),
        'raw_webhook_data': lambda f: f.startswith('raw_webhook_data'),
        'debug_webhook': lambda f: f.startswith('debug_webhook'),
        'webhook_logs': lambda f: f == 'webhook_logs.json'
    }
    
    for category, filter_func in categories.items():
        matching_files = [r for r in all_results if filter_func(r['filename']) and r['status'] == 'valid_json']
        if matching_files:
            example = matching_files[0]
            print(f"\n--- {category.upper()} EXAMPLE: {example['filename']} ---")
            print(f"Root type: {example['root_type']}")
            if example['sample_keys']:
                print(f"Keys: {example['sample_keys']}")
            print(f"Structure:")
            import pprint
            pprint.pprint(example['structure'], depth=3, width=100)
            if example['phone_patterns']:
                print(f"Phone patterns ({len(example['phone_patterns'])}):")
                for pattern in example['phone_patterns'][:5]:  # Show first 5
                    print(f"  - {pattern['path']}: {pattern['value_type']} = {pattern.get('value', 'N/A')}")

if __name__ == "__main__":
    main()

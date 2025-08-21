#!/usr/bin/env python3
import glob
import json
import os

# Check first 10 apollo_num_response files
files = sorted(glob.glob('json/apollo_num_response.*.json'))[:10]

for file_path in files:
    filename = os.path.basename(file_path)
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
        
        # Check if it has phone data
        if 'data' in data and 'people' in data['data']:
            people_count = len(data['data']['people'])
            total_phones = sum(len(person.get('phone_numbers', [])) for person in data['data']['people'])
            print(f"{filename}: {people_count} people, {total_phones} phones")
        else:
            print(f"{filename}: no phone data")
            
    except Exception as e:
        print(f"{filename}: error - {e}")

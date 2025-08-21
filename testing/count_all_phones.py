import json
import glob
import os

print("=== COMPREHENSIVE PHONE NUMBER COUNT ===")

total_files = 0
files_with_phones = 0
total_phone_numbers = 0
files_with_errors = 0
error_files = []

# Check all JSON files
for file_path in glob.glob('json/*.json'):
    total_files += 1
    filename = os.path.basename(file_path)
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Count raw_number occurrences in this file
        phone_count = content.count('"raw_number"')
        
        if phone_count > 0:
            files_with_phones += 1
            total_phone_numbers += phone_count
            print(f"{filename}: {phone_count} phones")
            
    except Exception as e:
        files_with_errors += 1
        error_files.append(filename)
        print(f"ERROR reading {filename}: {e}")

print(f"\n=== SUMMARY ===")
print(f"Total JSON files checked: {total_files}")
print(f"Files with phone numbers: {files_with_phones}")
print(f"Files with errors: {files_with_errors}")
print(f"Total phone numbers found: {total_phone_numbers}")

if error_files:
    print(f"\nError files:")
    for filename in error_files:
        print(f"  {filename}")

# Compare with database
import sqlite3
conn = sqlite3.connect('apollo_cache.db')
cursor = conn.cursor()
cursor.execute("SELECT COUNT(*) FROM apollo_people WHERE phone IS NOT NULL AND TRIM(phone) <> ''")
db_phone_count = cursor.fetchone()[0]
conn.close()

print(f"\nDatabase phone count: {db_phone_count}")
print(f"JSON phone count: {total_phone_numbers}")
print(f"Missing phones: {total_phone_numbers - db_phone_count}")

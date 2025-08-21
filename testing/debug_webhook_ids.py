import sqlite3
import json
import glob
import os

# Connect to database
conn = sqlite3.connect('apollo_cache.db')
cursor = conn.cursor()

print("=== WEBHOOK ID ANALYSIS ===")

# Get all person IDs from database
cursor.execute("SELECT person_id FROM apollo_people")
db_person_ids = set(row[0] for row in cursor.fetchall())
print(f"Total person IDs in database: {len(db_person_ids)}")

# Check webhook files for person IDs
webhook_person_ids = set()
webhook_files_checked = 0

for file_path in glob.glob('json/apollo_num_response.*.json'):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        response_data = data.get('data', {})
        people = response_data.get('people', [])
        
        for person in people:
            person_id = person.get('id')
            if person_id:
                webhook_person_ids.add(person_id)
        
        webhook_files_checked += 1
        
    except Exception as e:
        print(f"Error reading {file_path}: {e}")

print(f"Webhook files checked: {webhook_files_checked}")
print(f"Unique person IDs in webhooks: {len(webhook_person_ids)}")

# Find overlap
overlap = db_person_ids & webhook_person_ids
print(f"Person IDs that exist in both: {len(overlap)}")

# Show some examples
print(f"\nSample webhook person IDs:")
for i, person_id in enumerate(list(webhook_person_ids)[:10]):
    print(f"  {person_id}")

print(f"\nSample database person IDs:")
for i, person_id in enumerate(list(db_person_ids)[:10]):
    print(f"  {person_id}")

print(f"\nSample overlapping IDs:")
for i, person_id in enumerate(list(overlap)[:10]):
    print(f"  {person_id}")

# Check if any webhook IDs exist in database
if overlap:
    print(f"\nFound {len(overlap)} matching IDs - these should get phone updates")
    
    # Check if any of these actually have phone numbers
    cursor.execute("""
        SELECT COUNT(*) FROM apollo_people 
        WHERE person_id IN ({}) AND phone IS NOT NULL AND TRIM(phone) <> ''
    """.format(','.join(['?' for _ in overlap])), list(overlap))
    
    with_phones = cursor.fetchone()[0]
    print(f"Of these matching IDs, {with_phones} have phone numbers")
else:
    print("\nNO MATCHING IDs FOUND - this explains why webhooks aren't updating phones!")

conn.close()

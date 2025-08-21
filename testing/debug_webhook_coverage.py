import sqlite3
import json
import glob
import os

conn = sqlite3.connect('apollo_cache.db')
cursor = conn.cursor()

print("=== WEBHOOK COVERAGE ANALYSIS ===")

# Count total webhook files
webhook_files = glob.glob('json/apollo_num_response.*.json')
print(f"Total webhook files found: {len(webhook_files)}")

# Get all person IDs from database
cursor.execute("SELECT person_id FROM apollo_people")
db_person_ids = set(row[0] for row in cursor.fetchall())
print(f"Total person IDs in database: {len(db_person_ids)}")

# Analyze each webhook file
webhook_person_ids = set()
webhook_files_with_data = 0
webhook_files_with_people = 0
total_webhook_people = 0

for file_path in webhook_files:
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        response_data = data.get('data', {})
        people = response_data.get('people', [])
        
        if people:
            webhook_files_with_people += 1
            total_webhook_people += len(people)
            
            for person in people:
                person_id = person.get('id')
                if person_id:
                    webhook_person_ids.add(person_id)
        
        webhook_files_with_data += 1
        
    except Exception as e:
        print(f"Error reading {os.path.basename(file_path)}: {e}")

print(f"Webhook files with data: {webhook_files_with_data}")
print(f"Webhook files with people: {webhook_files_with_people}")
print(f"Total people in webhooks: {total_webhook_people}")
print(f"Unique person IDs in webhooks: {len(webhook_person_ids)}")

# Find overlap
overlap = db_person_ids & webhook_person_ids
print(f"Person IDs that exist in both: {len(overlap)}")

# Check if there are webhook IDs that don't exist in database
webhook_only = webhook_person_ids - db_person_ids
print(f"Webhook IDs not in database: {len(webhook_only)}")

if webhook_only:
    print("\nSample webhook-only IDs:")
    for person_id in list(webhook_only)[:10]:
        print(f"  {person_id}")

# Check if there are database IDs that should be in webhooks
# (people who were enriched but never got phone numbers)
db_without_phone = set()
cursor.execute("""
    SELECT person_id FROM apollo_people 
    WHERE phone IS NULL OR TRIM(phone) = ''
""")
for row in cursor.fetchall():
    db_without_phone.add(row[0])

print(f"\nDatabase IDs without phones: {len(db_without_phone)}")

# Check how many of these are in webhooks
potential_matches = db_without_phone & webhook_person_ids
print(f"Database IDs without phones that ARE in webhooks: {len(potential_matches)}")

if potential_matches:
    print("\nThese people should get phone numbers from webhooks:")
    for person_id in list(potential_matches)[:10]:
        cursor.execute("SELECT name FROM apollo_people WHERE person_id = ?", (person_id,))
        result = cursor.fetchone()
        name = result[0] if result else "Unknown"
        print(f"  {person_id}: {name}")

conn.close()

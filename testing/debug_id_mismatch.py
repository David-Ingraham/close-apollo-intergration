import sqlite3
import json
import glob

conn = sqlite3.connect('apollo_cache.db')
cursor = conn.cursor()

print("=== PERSON ID FORMAT ANALYSIS ===")

# Check database person ID formats
cursor.execute("SELECT person_id FROM apollo_people LIMIT 10")
db_ids = [row[0] for row in cursor.fetchall()]

print("Database person ID formats:")
for person_id in db_ids:
    print(f"  {person_id} (length: {len(person_id)})")

# Check webhook person ID formats
webhook_ids = []
for file_path in glob.glob('json/apollo_num_response.*.json'):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        response_data = data.get('data', {})
        people = response_data.get('people', [])
        
        for person in people:
            person_id = person.get('id')
            if person_id:
                webhook_ids.append(person_id)
                
    except Exception as e:
        continue

print(f"\nWebhook person ID formats (showing first 10):")
for person_id in webhook_ids[:10]:
    print(f"  {person_id} (length: {len(person_id)})")

# Check if there are any obvious format differences
print(f"\n=== FORMAT COMPARISON ===")
db_id_lengths = set(len(pid) for pid in db_ids)
webhook_id_lengths = set(len(pid) for pid in webhook_ids)

print(f"Database ID lengths: {sorted(db_id_lengths)}")
print(f"Webhook ID lengths: {sorted(webhook_id_lengths)}")

# Check if there are any webhook IDs that look like they might be truncated
print(f"\n=== POTENTIAL ID ISSUES ===")
if db_id_lengths != webhook_id_lengths:
    print("WARNING: Different ID lengths found - this could cause matching failures!")
    
    # Check for truncated IDs
    for webhook_id in webhook_ids:
        if len(webhook_id) < max(db_id_lengths):
            print(f"  Short webhook ID: {webhook_id} (length: {len(webhook_id)})")
            
            # Check if this ID is a prefix of any database ID
            cursor.execute("""
                SELECT person_id FROM apollo_people 
                WHERE person_id LIKE ? || '%'
            """, (webhook_id,))
            
            matches = cursor.fetchall()
            if matches:
                print(f"    Matches database IDs: {[m[0] for m in matches]}")
else:
    print("ID lengths match - format should be compatible")

conn.close()

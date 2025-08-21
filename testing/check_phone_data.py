import sqlite3

# Check what's actually in the database
conn = sqlite3.connect('apollo_cache.db')
cursor = conn.cursor()

print("=== COMPREHENSIVE DATABASE ANALYSIS ===")

# Check total counts
cursor.execute("SELECT COUNT(*) FROM apollo_people")
total_people = cursor.fetchone()[0]

cursor.execute("SELECT COUNT(*) FROM apollo_people WHERE phone IS NOT NULL")
people_with_phone = cursor.fetchone()[0]

cursor.execute("SELECT COUNT(*) FROM apollo_people WHERE phone IS NOT NULL AND TRIM(phone) <> ''")
people_with_phone_not_empty = cursor.fetchone()[0]

print(f"Total people: {total_people}")
print(f"People with phone (not null): {people_with_phone}")
print(f"People with phone (not empty): {people_with_phone_not_empty}")

# Check phone field types and values
print("\n=== PHONE FIELD ANALYSIS ===")
cursor.execute("""
    SELECT 
        COUNT(*) as total,
        COUNT(phone) as phone_not_null,
        SUM(CASE WHEN phone IS NOT NULL AND TRIM(phone) <> '' THEN 1 ELSE 0 END) as phone_not_empty,
        SUM(CASE WHEN phone LIKE '+%' THEN 1 ELSE 0 END) as phone_formatted,
        SUM(CASE WHEN phone LIKE '%+%' THEN 1 ELSE 0 END) as phone_contains_plus
    FROM apollo_people
""")

row = cursor.fetchone()
total, phone_not_null, phone_not_empty, phone_formatted, phone_contains_plus = row
print(f"Total records: {total}")
print(f"Phone not null: {phone_not_null}")  
print(f"Phone not empty: {phone_not_empty}")
print(f"Phone formatted (+): {phone_formatted}")
print(f"Phone contains +: {phone_contains_plus}")

# Show sample phone values to see what's actually stored
print("\n=== SAMPLE PHONE VALUES ===")
cursor.execute("""
    SELECT person_id, name, phone, source
    FROM apollo_people 
    WHERE phone IS NOT NULL AND TRIM(phone) <> ''
    LIMIT 10
""")

for person_id, name, phone, source in cursor.fetchall():
    print(f"ID: {person_id}, Name: {name}, Phone: '{phone}', Source: {source}")

# Check webhook sources specifically
print("\n=== WEBHOOK SOURCE ANALYSIS ===")
cursor.execute("""
    SELECT 
        source,
        COUNT(*) as total,
        SUM(CASE WHEN phone IS NOT NULL AND TRIM(phone) <> '' THEN 1 ELSE 0 END) as with_phone
    FROM apollo_people 
    WHERE source LIKE '%webhook%' OR source LIKE '%apollo_num_response%'
    GROUP BY source
    ORDER BY with_phone DESC
""")

for source, total, with_phone in cursor.fetchall():
    print(f"Source: {source}")
    print(f"  Total: {total}, With phone: {with_phone}")

# Check if there are any phone numbers that don't match the expected format
print("\n=== PHONE FORMAT ANALYSIS ===")
cursor.execute("""
    SELECT DISTINCT phone
    FROM apollo_people 
    WHERE phone IS NOT NULL AND TRIM(phone) <> ''
    LIMIT 20
""")

print("Sample phone formats found:")
for (phone,) in cursor.fetchall():
    print(f"  '{phone}'")

conn.close()

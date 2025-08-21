import sqlite3

conn = sqlite3.connect('apollo_cache.db')
cursor = conn.cursor()

print("=== PHONE COUNT DEBUG ===")

# Check the exact query the stats script uses
query = "SELECT COUNT(*) FROM apollo_people WHERE phone IS NOT NULL AND TRIM(phone) <> ''"
cursor.execute(query)
count = cursor.fetchone()[0]
print(f"Stats script query result: {count}")

# Let's break this down step by step
print("\n=== BREAKDOWN ===")

# Total people
cursor.execute("SELECT COUNT(*) FROM apollo_people")
total = cursor.fetchone()[0]
print(f"Total people: {total}")

# People with phone not null
cursor.execute("SELECT COUNT(*) FROM apollo_people WHERE phone IS NOT NULL")
not_null = cursor.fetchone()[0]
print(f"Phone not null: {not_null}")

# People with phone not empty
cursor.execute("SELECT COUNT(*) FROM apollo_people WHERE phone IS NOT NULL AND TRIM(phone) <> ''")
not_empty = cursor.fetchone()[0]
print(f"Phone not empty: {not_empty}")

# People with phone that's just whitespace
cursor.execute("SELECT COUNT(*) FROM apollo_people WHERE phone IS NOT NULL AND TRIM(phone) = ''")
just_whitespace = cursor.fetchone()[0]
print(f"Phone just whitespace: {just_whitespace}")

# Check for any weird phone values
print("\n=== WEIRD PHONE VALUES ===")
cursor.execute("""
    SELECT person_id, name, phone, LENGTH(phone) as phone_length
    FROM apollo_people 
    WHERE phone IS NOT NULL 
    ORDER BY phone_length DESC
    LIMIT 10
""")

for person_id, name, phone, length in cursor.fetchall():
    print(f"ID: {person_id}, Name: {name}, Phone: '{phone}', Length: {length}")

# Check if there are any phone numbers that don't start with +
print("\n=== PHONE FORMAT CHECK ===")
cursor.execute("""
    SELECT COUNT(*) FROM apollo_people 
    WHERE phone IS NOT NULL AND TRIM(phone) <> '' AND phone NOT LIKE '+%'
""")
non_plus_format = cursor.fetchone()[0]
print(f"Phone numbers not starting with +: {non_plus_format}")

if non_plus_format > 0:
    cursor.execute("""
        SELECT person_id, name, phone 
        FROM apollo_people 
        WHERE phone IS NOT NULL AND TRIM(phone) <> '' AND phone NOT LIKE '+%'
        LIMIT 5
    """)
    print("Examples:")
    for person_id, name, phone in cursor.fetchall():
        print(f"  {person_id}: {name} - '{phone}'")

conn.close()

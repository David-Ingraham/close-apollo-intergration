#!/usr/bin/env python3
import sqlite3

def find_duplicate_phones():
    """Find duplicated phone numbers in the database"""
    conn = sqlite3.connect('apollo_cache.db')
    cursor = conn.cursor()
    
    print("=== DUPLICATE PHONE ANALYSIS ===")
    
    # Find phone numbers that appear more than once
    cursor.execute("""
        SELECT phone, COUNT(*) as count, GROUP_CONCAT(person_id) as person_ids
        FROM apollo_people 
        WHERE phone IS NOT NULL AND TRIM(phone) <> ''
        GROUP BY phone 
        HAVING COUNT(*) > 1
        ORDER BY count DESC
    """)
    
    duplicates = cursor.fetchall()
    
    if not duplicates:
        print("No duplicate phone numbers found!")
        return
    
    print(f"Found {len(duplicates)} phone numbers with duplicates:")
    print()
    
    total_duplicates = 0
    for phone, count, person_ids in duplicates:
        print(f"Phone: {phone}")
        print(f"  Appears {count} times")
        print(f"  Person IDs: {person_ids}")
        
        # Get details for each person with this phone
        person_id_list = person_ids.split(',')
        for person_id in person_id_list:
            cursor.execute("""
                SELECT person_id, name, email, title, organization_name, source
                FROM apollo_people 
                WHERE person_id = ?
            """, (person_id,))
            
            person = cursor.fetchone()
            if person:
                print(f"    - {person[1]} ({person[0]}) - {person[2]} - {person[3]} - {person[4]} - {person[5]}")
        
        total_duplicates += count - 1  # Subtract 1 since one is the "original"
        print()
    
    print(f"Total duplicate entries: {total_duplicates}")
    print(f"This explains why we have 190 people with phones but only 176 unique phones")

if __name__ == "__main__":
    find_duplicate_phones()

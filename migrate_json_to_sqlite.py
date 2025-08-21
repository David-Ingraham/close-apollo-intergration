import sqlite3
import json
import os
import glob
from datetime import datetime

def create_database():
    """Create SQLite database with apollo_people and apollo_companies tables"""
    conn = sqlite3.connect('apollo_cache.db')
    cursor = conn.cursor()
    
    # Create apollo_people table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS apollo_people (
            person_id TEXT PRIMARY KEY,
            name TEXT,
            email TEXT,
            phone TEXT,
            title TEXT,
            organization_id TEXT,
            organization_name TEXT,
            last_updated DATETIME DEFAULT CURRENT_TIMESTAMP,
            source TEXT
        )
    ''')
    
    # Create apollo_companies table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS apollo_companies (
            organization_id TEXT PRIMARY KEY,
            name TEXT,
            primary_domain TEXT,
            website_url TEXT,
            phone TEXT,
            search_term TEXT,
            last_updated DATETIME DEFAULT CURRENT_TIMESTAMP,
            source TEXT
        )
    ''')
    
    # Create indexes for performance
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_people_email ON apollo_people(email)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_people_org_id ON apollo_people(organization_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_companies_domain ON apollo_companies(primary_domain)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_companies_search_term ON apollo_companies(search_term)')
    
    conn.commit()
    conn.close()
    print(" Database created with tables and indexes")

def person_is_complete(cursor, person_id):
    """Check if we already have complete data for this person"""
    cursor.execute('''
        SELECT email, phone FROM apollo_people WHERE person_id = ?
    ''', (person_id,))
    
    result = cursor.fetchone()
    if not result:
        return False  # Person doesn't exist
    
    email, phone = result
    # Complete if we have both email and phone (or at least email)
    return email is not None and email != ''

def company_is_complete(cursor, organization_id):
    """Check if we already have complete data for this company"""
    cursor.execute('''
        SELECT name, primary_domain FROM apollo_companies WHERE organization_id = ?
    ''', (organization_id,))
    
    result = cursor.fetchone()
    if not result:
        return False  # Company doesn't exist
    
    name, domain = result
    # Complete if we have both name and domain
    return name is not None and domain is not None

def insert_or_update_person(cursor, person_data, source):
    """Insert new person or update existing person with missing data"""
    person_id = person_data.get('person_id')
    if not person_id:
        return
    
    if person_is_complete(cursor, person_id):
        return  # Skip - we already have complete data
    
    # Check if person exists
    cursor.execute('SELECT person_id FROM apollo_people WHERE person_id = ?', (person_id,))
    exists = cursor.fetchone()
    
    if exists:
        # Update existing person with any missing data
        cursor.execute('''
            UPDATE apollo_people 
            SET name = COALESCE(?, name),
                email = COALESCE(?, email),
                phone = COALESCE(?, phone),
                title = COALESCE(?, title),
                organization_id = COALESCE(?, organization_id),
                organization_name = COALESCE(?, organization_name),
                last_updated = CURRENT_TIMESTAMP,
                source = ?
            WHERE person_id = ?
        ''', (
            person_data.get('name'),
            person_data.get('email'),
            person_data.get('phone'),
            person_data.get('title'),
            person_data.get('organization_id'),
            person_data.get('organization_name'),
            source,
            person_id
        ))
    else:
        # Insert new person
        cursor.execute('''
            INSERT INTO apollo_people 
            (person_id, name, email, phone, title, organization_id, organization_name, source)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            person_id,
            person_data.get('name'),
            person_data.get('email'),
            person_data.get('phone'),
            person_data.get('title'),
            person_data.get('organization_id'),
            person_data.get('organization_name'),
            source
        ))

def insert_or_update_company(cursor, company_data, source, search_term=None):
    """Insert new company or update existing company with missing data"""
    organization_id = company_data.get('organization_id') or company_data.get('id')
    if not organization_id:
        return
    
    if company_is_complete(cursor, organization_id):
        return  # Skip - we already have complete data
    
    # Check if company exists
    cursor.execute('SELECT organization_id FROM apollo_companies WHERE organization_id = ?', (organization_id,))
    exists = cursor.fetchone()
    
    if exists:
        # Update existing company with any missing data
        cursor.execute('''
            UPDATE apollo_companies 
            SET name = COALESCE(?, name),
                primary_domain = COALESCE(?, primary_domain),
                website_url = COALESCE(?, website_url),
                phone = COALESCE(?, phone),
                search_term = COALESCE(?, search_term),
                last_updated = CURRENT_TIMESTAMP,
                source = ?
            WHERE organization_id = ?
        ''', (
            company_data.get('name'),
            company_data.get('primary_domain'),
            company_data.get('website_url'),
            company_data.get('phone'),
            search_term,
            source,
            organization_id
        ))
    else:
        # Insert new company
        cursor.execute('''
            INSERT INTO apollo_companies 
            (organization_id, name, primary_domain, website_url, phone, search_term, source)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            organization_id,
            company_data.get('name'),
            company_data.get('primary_domain'),
            company_data.get('website_url'),
            company_data.get('phone'),
            search_term,
            source
        ))

def parse_enrichment_results(file_path, cursor):
    """Parse enrichment_results_*.json files"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # Gracefully exit if the data is not in the expected dictionary format
        if not isinstance(data, dict):
            return 0, 0
        
        detailed_results = data.get('detailed_results', [])
        processed_people = 0
        processed_companies = 0
        
        if not isinstance(detailed_results, list):
            return 0, 0
        
        for result in detailed_results:
            if not isinstance(result, dict):
                continue
                
            # Process attorney contact
            attorney_enrichment = result.get('attorney_enrichment', {})
            if isinstance(attorney_enrichment, dict):
                attorney_contact = attorney_enrichment.get('attorney_contact')
                if attorney_contact and isinstance(attorney_contact, dict):
                    insert_or_update_person(cursor, attorney_contact, f"enrichment_results:{os.path.basename(file_path)}")
                    processed_people += 1
            
            # Process Apollo search results
            apollo_search = result.get('apollo_search', {})
            if isinstance(apollo_search, dict):
                # Process firm found
                firm_found = apollo_search.get('firm_found')
                if firm_found and isinstance(firm_found, dict):
                    insert_or_update_company(cursor, firm_found, f"enrichment_results:{os.path.basename(file_path)}")
                    processed_companies += 1
                
                # Process contacts found
                contacts_found = apollo_search.get('contacts_found', [])
                if isinstance(contacts_found, list):
                    for contact in contacts_found:
                        if isinstance(contact, dict) and contact.get('person_id'):
                            insert_or_update_person(cursor, contact, f"enrichment_results:{os.path.basename(file_path)}")
                            processed_people += 1
        
        return processed_people, processed_companies
        
    except Exception as e:
        print(f"✗ Error parsing {file_path}: {e}")
        return 0, 0

def parse_raw_apollo_results(file_path, cursor):
    """Parse raw_apollo_results_*.json files"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # Gracefully exit if the data is not in the expected dictionary format
        if not isinstance(data, dict):
            return 0, 0
        
        search_results = data.get('search_results', [])
        processed_people = 0
        processed_companies = 0
        
        if not isinstance(search_results, list):
            return 0, 0
        
        for result in search_results:
            if not isinstance(result, dict):
                continue
                
            # Process attorney contact
            attorney_contact = result.get('attorney_contact')
            if attorney_contact and isinstance(attorney_contact, dict):
                insert_or_update_person(cursor, attorney_contact, f"raw_apollo:{os.path.basename(file_path)}")
                processed_people += 1
            
            # Process organization found
            organizations_found = result.get('organizations_found', [])
            if isinstance(organizations_found, list):
                for org in organizations_found:
                    if org and isinstance(org, dict):
                        insert_or_update_company(cursor, org, f"raw_apollo:{os.path.basename(file_path)}")
                        processed_companies += 1
            
            # Process contacts
            contacts = result.get('contacts', [])
            if isinstance(contacts, list):
                for contact in contacts:
                    if isinstance(contact, dict) and contact.get('person_id'):
                        insert_or_update_person(cursor, contact, f"raw_apollo:{os.path.basename(file_path)}")
                        processed_people += 1
        
        return processed_people, processed_companies
        
    except Exception as e:
        print(f"✗ Error parsing {file_path}: {e}")
        return 0, 0

def parse_webhook_data(file_path, cursor):
    """
    Parse webhook data files with various formats, including "log stream"
    style files with multiple JSON objects.
    """
    processed_people = 0
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        # print(f"  ✗ Could not read file {os.path.basename(file_path)}: {e}")
        return 0, 0

    # Handle various malformed JSON patterns by splitting content into chunks
    json_chunks = []
    if '==================================================' in content:
        parts = content.split('==================================================')
        for part in parts:
            clean_part = part.strip()
            if clean_part:
                json_chunks.append(clean_part)
    elif '},\n{' in content and not content.strip().startswith('['):
         # Handle comma-separated objects that aren't a formal JSON array
        parts = content.strip().split('},\n{')
        for i, part in enumerate(parts):
            if not part.strip(): continue
            if i == 0:
                json_chunks.append(part + '}')
            elif i == len(parts) - 1:
                json_chunks.append('{' + part)
            else:
                json_chunks.append('{' + part + '}')
    else:
        # Assume it's a single (potentially malformed) JSON object or array
        json_chunks.append(content)

    for chunk in json_chunks:
        try:
            # Attempt to load the chunk as JSON
            data = json.loads(chunk)
            
            # The loaded data could be a list of objects or a single object
            if isinstance(data, list):
                responses = data
            else:
                responses = [data]

            for response in responses:
                if not isinstance(response, dict):
                    continue

                # --- Standardized person extraction logic ---
                people_to_process = []
                # Structure 1: response.data.people or response.data.person
                if 'data' in response and isinstance(response.get('data'), dict):
                    data_section = response['data']
                    if 'people' in data_section and isinstance(data_section['people'], list):
                        people_to_process.extend(data_section['people'])
                    if 'person' in data_section and isinstance(data_section['person'], dict):
                        people_to_process.append(data_section['person'])
                
                # Structure 2: direct people array or person object
                if 'people' in response and isinstance(response.get('people'), list):
                    people_to_process.extend(response['people'])
                
                # Structure 3: root level object is a person
                if 'id' in response and 'phone_numbers' in response:
                    people_to_process.append(response)

                for person in people_to_process:
                    if not isinstance(person, dict) or not person.get('id'):
                        continue
                    
                    phone_numbers = person.get('phone_numbers', [])
                    if not phone_numbers:
                        continue

                    # Get the first available phone number
                    phone = None
                    first_phone = phone_numbers[0]
                    if isinstance(first_phone, dict):
                        phone = first_phone.get('raw_number') or first_phone.get('sanitized_number')
                    elif isinstance(first_phone, str):
                        phone = first_phone

                    if phone:
                        person_id = person.get('id')
                        # First, try to update an existing record that is missing a phone
                        cursor.execute("""
                            UPDATE apollo_people 
                            SET phone = ?, last_updated = CURRENT_TIMESTAMP, source = ?
                            WHERE person_id = ? AND (phone IS NULL OR phone = '')
                        """, (phone, f"webhook:{os.path.basename(file_path)}", person_id))
                        
                        if cursor.rowcount > 0:
                            processed_people += 1
                        else:
                            # If no update happened, check if the person exists at all
                            cursor.execute("SELECT 1 FROM apollo_people WHERE person_id = ?", (person_id,))
                            if cursor.fetchone() is None:
                                # Person doesn't exist, so insert them
                                person_data = {
                                    'person_id': person_id,
                                    'name': person.get('name', f"{person.get('first_name', '')} {person.get('last_name', '')}".strip()),
                                    'email': person.get('email'),
                                    'phone': phone,
                                    'title': person.get('title'),
                                    'organization_id': person.get('organization_id'),
                                    'organization_name': person.get('organization_name')
                                }
                                insert_or_update_person(cursor, person_data, f"webhook:{os.path.basename(file_path)}")
                                processed_people += 1
        
        except json.JSONDecodeError:
            # Silently ignore chunks that are not valid JSON
            # print(f"  ✗ Skipping malformed JSON chunk in {os.path.basename(file_path)}")
            continue
        except Exception as e:
            # print(f"  ✗ An unexpected error occurred in {os.path.basename(file_path)}: {e}")
            continue
            
    return processed_people, 0

def parse_apollo_num_response(file_path, cursor):
    """
    Parse apollo_num_response files specifically, handling log-stream style
    files with multiple JSON objects.
    """
    processed_people = 0
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception:
        return 0, 0

    # Split content by the known separator for these files if it exists
    json_chunks = []
    if '}\n{' in content and not content.strip().startswith('['):
        # This is a common pattern for malformed, concatenated JSON
        parts = content.strip().split('}\n{')
        for i, part in enumerate(parts):
            if not part.strip(): continue
            if i == 0:
                json_chunks.append(part + '}')
            else:
                json_chunks.append('{' + part)
    else:
        json_chunks.append(content)
    
    for chunk in json_chunks:
        try:
            data = json.loads(chunk)
            
            if not isinstance(data, dict) or 'data' not in data:
                continue
                
            data_section = data.get('data', {})
            if not isinstance(data_section, dict) or 'people' not in data_section:
                continue
                
            people = data_section.get('people', [])
            if not isinstance(people, list):
                continue

            for person in people:
                if not isinstance(person, dict) or not person.get('id'):
                    continue
                
                phone_numbers = person.get('phone_numbers', [])
                if not phone_numbers:
                    continue
                
                phone = None
                first_phone = phone_numbers[0]
                if isinstance(first_phone, dict):
                    phone = first_phone.get('raw_number') or first_phone.get('sanitized_number')
                
                if phone:
                    person_id = person.get('id')
                    cursor.execute("""
                        UPDATE apollo_people 
                        SET phone = ?, last_updated = CURRENT_TIMESTAMP, source = ?
                        WHERE person_id = ? AND (phone IS NULL OR phone = '')
                    """, (phone, f"apollo_num:{os.path.basename(file_path)}", person_id))
                    
                    if cursor.rowcount == 0:
                        cursor.execute("SELECT 1 FROM apollo_people WHERE person_id = ?", (person_id,))
                        if cursor.fetchone() is None:
                            person_data = {
                                'person_id': person_id,
                                'name': person.get('name', 'Unknown'),
                                'phone': phone
                            }
                            insert_or_update_person(cursor, person_data, f"apollo_num:{os.path.basename(file_path)}")
                            processed_people += 1

        except (json.JSONDecodeError, AttributeError):
            continue
            
    return processed_people, 0

def brute_force_phone_extraction(file_path, cursor):
    """Brute force approach to extract phone numbers from any JSON structure"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Look for any phone number patterns
        import re
        phone_pattern = r'"raw_number":\s*"([^"]+)"'
        matches = re.findall(phone_pattern, content)
        
        if not matches:
            # Try other phone patterns
            phone_pattern = r'"sanitized_number":\s*"([^"]+)"'
            matches = re.findall(phone_pattern, content)
        
        if not matches:
            # Try sanitized_phone
            phone_pattern = r'"sanitized_phone":\s*"([^"]+)"'
            matches = re.findall(phone_pattern, content)
        
        if not matches:
            return 0
        
        # Look for person IDs near phone numbers
        person_pattern = r'"id":\s*"([^"]+)"'
        person_matches = re.findall(person_pattern, content)
        
        processed = 0
        for i, phone in enumerate(matches):
            if i < len(person_matches):
                person_id = person_matches[i]
                
                # Try to update existing person
                cursor.execute("""
                    UPDATE apollo_people 
                    SET phone = ?, last_updated = CURRENT_TIMESTAMP
                    WHERE person_id = ?
                """, (phone, person_id))
                
                if cursor.rowcount > 0:
                    processed += 1
                else:
                    # Create new person record
                    person_data = {
                        'person_id': person_id,
                        'name': f"Person_{person_id}",
                        'phone': phone,
                        'source': f"brute_force:{os.path.basename(file_path)}"
                    }
                    insert_or_update_person(cursor, person_data, f"brute_force:{os.path.basename(file_path)}")
                    processed += 1
        
        return processed
        
    except Exception as e:
        return 0

def migrate_all_json_files():
    """Migrate all JSON files in the json/ directory to SQLite"""
    print("Starting migration from JSON files to SQLite...")
    
    # Create database
    create_database()
    
    # Connect to database
    conn = sqlite3.connect('apollo_cache.db')
    cursor = conn.cursor()
    
    total_people = 0
    total_companies = 0
    files_processed = 0
    
    try:
        # Get all JSON files in json/ directory
        json_files = glob.glob('json/*.json')
        print(f"Found {len(json_files)} JSON files to process")
        
        for file_path in json_files:
            filename = os.path.basename(file_path)
            print(f"\nProcessing: {filename}")
            
            # Try all parsers for each file - let them handle their own data validation
            people_count = 0
            companies_count = 0
            
            # Special handling for apollo_num_response files
            if filename.startswith('apollo_num_response.'):
                try:
                    p, c = parse_apollo_num_response(file_path, cursor)
                    people_count += p
                    companies_count += c
                    if p > 0 or c > 0:
                        print(f"  → Apollo Num Response parser: {p} people, {c} companies")
                except:
                    pass
            
            # Try enrichment results parser
            try:
                p, c = parse_enrichment_results(file_path, cursor)
                people_count += p
                companies_count += c
                if p > 0 or c > 0:
                    print(f"  → Enrichment parser: {p} people, {c} companies")
            except:
                pass
            
            # Try raw apollo results parser
            try:
                p, c = parse_raw_apollo_results(file_path, cursor)
                people_count += p
                companies_count += c
                if p > 0 or c > 0:
                    print(f"  → Raw apollo parser: {p} people, {c} companies")
            except:
                pass
            
            # Try webhook data parser
            try:
                p, c = parse_webhook_data(file_path, cursor)
                people_count += p
                companies_count += c
                if p > 0 or c > 0:
                    print(f"  → Webhook parser: {p} people, {c} companies")
            except:
                pass
            
            # If no parsers worked, try a brute force approach for phone numbers
            if people_count == 0 and companies_count == 0:
                try:
                    p = brute_force_phone_extraction(file_path, cursor)
                    people_count += p
                    if p > 0:
                        print(f"  → Brute force parser: {p} people")
                except:
                    pass
            
            if people_count == 0 and companies_count == 0:
                print(f"  → No data extracted by any parser")
            
            print(f"  → Added/Updated {people_count} people, {companies_count} companies")
            total_people += people_count
            total_companies += companies_count
            files_processed += 1
            
            # Commit after each file
            conn.commit()
        
        # Final statistics
        cursor.execute('SELECT COUNT(*) FROM apollo_people')
        final_people_count = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM apollo_companies')
        final_companies_count = cursor.fetchone()[0]
        
        # Phone-specific statistics
        cursor.execute('SELECT COUNT(*) FROM apollo_people WHERE phone IS NOT NULL AND TRIM(phone) <> ""')
        final_phone_count = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(DISTINCT phone) FROM apollo_people WHERE phone IS NOT NULL AND TRIM(phone) <> ""')
        unique_phone_count = cursor.fetchone()[0]
        
        print(f"\n" + "="*60)
        print("MIGRATION COMPLETE")
        print("="*60)
        print(f"Files processed: {files_processed}")
        print(f"Total people processed: {total_people}")
        print(f"Total companies processed: {total_companies}")
        print(f"Final database counts:")
        print(f"  - People: {final_people_count}")
        print(f"  - Companies: {final_companies_count}")
        print(f"  - People with phones: {final_phone_count}")
        print(f"  - Unique phone numbers: {unique_phone_count}")
        print(f"Database saved as: apollo_cache.db")
        
    except Exception as e:
        print(f"Migration failed: {e}")
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    migrate_all_json_files()

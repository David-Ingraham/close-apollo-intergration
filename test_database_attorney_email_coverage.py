import os
import sqlite3
from dotenv import load_dotenv
import requests
import json
from base64 import b64encode

# Load environment variables
load_dotenv()

def get_db_connection():
    """Get connection to the apollo_cache database"""
    return sqlite3.connect('apollo_cache.db')

def check_attorney_email_in_db(email):
    """Check if attorney email exists in apollo_people table"""
    if not email or email == 'N/A':
        return False, None
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            SELECT person_id, name, title, organization_name, phone 
            FROM apollo_people 
            WHERE email = ? COLLATE NOCASE
        ''', (email,))
        
        result = cursor.fetchone()
        if result:
            return True, {
                'person_id': result[0],
                'name': result[1], 
                'title': result[2],
                'organization_name': result[3],
                'phone': result[4]
            }
        return False, None
        
    finally:
        conn.close()

def check_firm_name_in_db(firm_name):
    """Check if firm name exists in apollo_companies table"""
    if not firm_name or firm_name == 'N/A':
        return False, None
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Check exact match first
        cursor.execute('''
            SELECT organization_id, name, primary_domain, website_url, phone 
            FROM apollo_companies 
            WHERE name = ? COLLATE NOCASE
        ''', (firm_name,))
        
        result = cursor.fetchone()
        if result:
            return True, {
                'organization_id': result[0],
                'name': result[1],
                'primary_domain': result[2], 
                'website_url': result[3],
                'phone': result[4],
                'match_type': 'exact'
            }
        
        # Check partial match (firm name contained within company name)
        cursor.execute('''
            SELECT organization_id, name, primary_domain, website_url, phone 
            FROM apollo_companies 
            WHERE name LIKE ? COLLATE NOCASE
        ''', (f'%{firm_name}%',))
        
        result = cursor.fetchone()
        if result:
            return True, {
                'organization_id': result[0],
                'name': result[1],
                'primary_domain': result[2],
                'website_url': result[3], 
                'phone': result[4],
                'match_type': 'partial'
            }
            
        return False, None
        
    finally:
        conn.close()

def check_domain_in_db(domain):
    """Check if domain exists in apollo_companies table"""
    if not domain:
        return False, None
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            SELECT organization_id, name, primary_domain, website_url, phone 
            FROM apollo_companies 
            WHERE primary_domain = ? COLLATE NOCASE
        ''', (domain,))
        
        result = cursor.fetchone()
        if result:
            return True, {
                'organization_id': result[0],
                'name': result[1],
                'primary_domain': result[2],
                'website_url': result[3],
                'phone': result[4]
            }
        return False, None
        
    finally:
        conn.close()

def check_all_people_by_domain(domain):
    """Check for ALL people with email addresses containing the domain"""
    if not domain:
        return False, []
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            SELECT person_id, name, email, phone, title, organization_id, organization_name, last_updated, source
            FROM apollo_people 
            WHERE email LIKE ? COLLATE NOCASE
        ''', (f'%@{domain}%',))
        
        results = cursor.fetchall()
        if results:
            people_data = []
            for result in results:
                people_data.append({
                    'person_id': result[0],
                    'name': result[1],
                    'email': result[2],
                    'phone': result[3],
                    'title': result[4],
                    'organization_id': result[5],
                    'organization_name': result[6],
                    'last_updated': result[7],
                    'source': result[8]
                })
            return True, people_data
        return False, []
        
    finally:
        conn.close()

def check_all_people_by_firm_name(firm_name):
    """Check for ALL people who work at firms matching the firm name"""
    if not firm_name or firm_name == 'N/A':
        return False, []
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Search by organization_name in apollo_people table
        cursor.execute('''
            SELECT person_id, name, email, phone, title, organization_id, organization_name, last_updated, source
            FROM apollo_people 
            WHERE organization_name LIKE ? COLLATE NOCASE
        ''', (f'%{firm_name}%',))
        
        results = cursor.fetchall()
        people_data = []
        
        for result in results:
            people_data.append({
                'person_id': result[0],
                'name': result[1],
                'email': result[2],
                'phone': result[3],
                'title': result[4],
                'organization_id': result[5],
                'organization_name': result[6],
                'last_updated': result[7],
                'source': result[8]
            })
        
        # Also search by finding organization_ids that match the firm name in apollo_companies
        cursor.execute('''
            SELECT organization_id FROM apollo_companies 
            WHERE name LIKE ? COLLATE NOCASE
        ''', (f'%{firm_name}%',))
        
        org_ids = [row[0] for row in cursor.fetchall()]
        
        # Find all people with those organization_ids
        for org_id in org_ids:
            cursor.execute('''
                SELECT person_id, name, email, phone, title, organization_id, organization_name, last_updated, source
                FROM apollo_people 
                WHERE organization_id = ?
            ''', (org_id,))
            
            org_results = cursor.fetchall()
            for result in org_results:
                # Avoid duplicates
                person_data = {
                    'person_id': result[0],
                    'name': result[1],
                    'email': result[2],
                    'phone': result[3],
                    'title': result[4],
                    'organization_id': result[5],
                    'organization_name': result[6],
                    'last_updated': result[7],
                    'source': result[8]
                }
                if person_data not in people_data:
                    people_data.append(person_data)
        
        return len(people_data) > 0, people_data
        
    finally:
        conn.close()

def extract_domain_from_email(email):
    """Extract domain from email address"""
    if email and '@' in email:
        return email.split('@')[1]
    return None

def fetch_sample_leads():
    """Fetch a sample of leads from Close API (mimics get_lawyer_contacts.py)"""
    # Get API key from environment
    api_key = os.getenv('CLOSE_API_KEY')
    if not api_key:
        raise ValueError("CLOSE_API_KEY not found in environment variables")

    # Encode API key properly for Basic Auth
    encoded_key = b64encode(f"{api_key}:".encode('utf-8')).decode('utf-8')
    
    headers = {
        'Authorization': f'Basic {encoded_key}',
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    }

    # Use one of the smart views from get_lawyer_contacts.py
    # Using "Today's Leads" as a sample
    view_id = "save_ebxRoBR5KEXJz0jTSCfn1xyaXMQYBHmskqU6iCOoZd9"
    
    print("Fetching sample leads from Close API...")
    url = 'https://api.close.com/api/v1/data/search/'
    
    payload = {
        "query": {
            "type": "saved_search",
            "saved_search_id": view_id
        },
        "_fields": {
            "lead": ["id", "display_name", "status_id", "name", "contacts", "custom"]
        },
        "_limit": 200  # Small sample for testing
    }

    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        
        api_response = response.json()
        leads = api_response.get('data', [])
        
        print(f"Retrieved {len(leads)} sample leads")
        return leads
        
    except requests.exceptions.RequestException as e:
        print(f"Error fetching leads: {e}")
        return None

def analyze_lead_coverage(leads):
    """Analyze database coverage for the fetched leads"""
    if not leads:
        print("No leads to analyze")
        return
    
    print(f"\n{'='*80}")
    print("DATABASE COVERAGE ANALYSIS")
    print(f"{'='*80}")
    
    total_leads = len(leads)
    email_matches = 0
    firm_matches = 0
    domain_matches = 0
    no_coverage = 0
    
    coverage_results = []
    
    for i, lead in enumerate(leads, 1):
        print(f"\nLead #{i}: {lead.get('display_name', 'Unknown')}")
        
        # Extract attorney information (same logic as get_lawyer_contacts.py)
        attorney_email = 'N/A'
        firm_name = 'N/A'
        
        if lead.get('contacts') and len(lead['contacts']) > 0:
            client_contact = lead['contacts'][0]
            
            # Extract custom fields
            law_office = client_contact.get('custom.cf_lQKyH0EhHsNDLZn8KqfFSb0342doHgTNfWdTcfWCljw', 'N/A')
            attorney_name_field = client_contact.get('custom.cf_bB8dqX4BWGbISOehyNVVaZhJpfV9OZNOqs5WfYjaRYv', 'N/A') 
            attorney_email = client_contact.get('custom.cf_vq0cl2Sj1h0QaSePdnTdf3NyAjx3w4QcgmlhgJrWrZE', 'N/A')
            
            # Determine firm name (same priority as get_lawyer_contacts.py)
            if law_office != 'N/A' and law_office.strip():
                firm_name = law_office
            elif attorney_name_field != 'N/A' and attorney_name_field.strip():
                firm_name = attorney_name_field
        
        # Extract domain from email
        domain = extract_domain_from_email(attorney_email) if attorney_email != 'N/A' else None
        
        print(f"  Attorney Email: {attorney_email}")
        print(f"  Firm Name: {firm_name}")
        print(f"  Domain: {domain}")
        
        # Check database coverage
        has_coverage = False
        coverage_details = []
        
        # Check attorney email
        email_found, email_data = check_attorney_email_in_db(attorney_email)
        if email_found:
            email_matches += 1
            has_coverage = True
            coverage_details.append(f"EMAIL MATCH: {email_data['name']} ({email_data.get('title', 'No title')})")
            if email_data.get('phone'):
                coverage_details.append(f"  Phone: {email_data['phone']}")
            
            # Print full database row
            print(f"    EMAIL ROW DATA:")
            for key, value in email_data.items():
                print(f"      {key}: {value}")
        
        # Check firm name
        firm_found, firm_data = check_firm_name_in_db(firm_name)
        if firm_found:
            firm_matches += 1
            has_coverage = True
            match_type = firm_data.get('match_type', 'exact')
            coverage_details.append(f"FIRM MATCH ({match_type}): {firm_data['name']}")
            if firm_data.get('primary_domain'):
                coverage_details.append(f"  Domain: {firm_data['primary_domain']}")
            if firm_data.get('phone'):
                coverage_details.append(f"  Phone: {firm_data['phone']}")
            
            # Print full database row
            print(f"    FIRM ROW DATA:")
            for key, value in firm_data.items():
                print(f"      {key}: {value}")
        
        # Check domain - ENHANCED VERSION
        domain_found, domain_data = check_domain_in_db(domain)
        all_domain_people_found, all_domain_people = check_all_people_by_domain(domain)
        
        if domain_found and not firm_found:  # Only count if we didn't already find firm
            domain_matches += 1
            has_coverage = True
            coverage_details.append(f"DOMAIN MATCH: {domain_data['name']}")
            if domain_data.get('phone'):
                coverage_details.append(f"  Phone: {domain_data['phone']}")
            
            # Print full database row
            print(f"    DOMAIN COMPANY ROW DATA:")
            for key, value in domain_data.items():
                print(f"      {key}: {value}")
        
        # Print ALL people with this domain
        if all_domain_people_found:
            has_coverage = True
            print(f"    ALL PEOPLE WITH DOMAIN '{domain}' ({len(all_domain_people)} found):")
            for i, person in enumerate(all_domain_people, 1):
                print(f"      Person #{i}:")
                for key, value in person.items():
                    print(f"        {key}: {value}")
                print()  # Empty line between people
        
        # If no domain matches, search by firm name for all people
        elif not domain_found and firm_name != 'N/A':
            all_firm_people_found, all_firm_people = check_all_people_by_firm_name(firm_name)
            
            if all_firm_people_found:
                has_coverage = True
                print(f"    ALL PEOPLE AT FIRM '{firm_name}' ({len(all_firm_people)} found):")
                for i, person in enumerate(all_firm_people, 1):
                    print(f"      Person #{i}:")
                    for key, value in person.items():
                        print(f"        {key}: {value}")
                    print()  # Empty line between people

        if has_coverage:
            print(f"  DATABASE COVERAGE FOUND:")
            for detail in coverage_details:
                print(f"    {detail}")
        else:
            print(f"  NO DATABASE COVERAGE")
            no_coverage += 1
        
        # Store results for summary
        coverage_results.append({
            'lead_id': lead.get('id'),
            'lead_name': lead.get('display_name', 'Unknown'),
            'attorney_email': attorney_email,
            'firm_name': firm_name,
            'domain': domain,
            'has_email_match': email_found,
            'has_firm_match': firm_found,
            'has_domain_match': domain_found,
            'has_any_coverage': has_coverage
        })
    
    # Print summary
    print(f"\n{'='*80}")
    print("COVERAGE SUMMARY")
    print(f"{'='*80}")
    print(f"Total leads analyzed: {total_leads}")
    print(f"Leads with email matches: {email_matches} ({email_matches/total_leads*100:.1f}%)")
    print(f"Leads with firm name matches: {firm_matches} ({firm_matches/total_leads*100:.1f}%)")
    print(f"Leads with domain matches: {domain_matches} ({domain_matches/total_leads*100:.1f}%)")
    
    total_with_coverage = len([r for r in coverage_results if r['has_any_coverage']])
    print(f"Leads with ANY database coverage: {total_with_coverage} ({total_with_coverage/total_leads*100:.1f}%)")
    print(f"Leads with NO database coverage: {no_coverage} ({no_coverage/total_leads*100:.1f}%)")
    
    return coverage_results

def get_database_stats():
    """Get basic statistics about the database"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # People stats
        cursor.execute('SELECT COUNT(*) FROM apollo_people')
        total_people = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM apollo_people WHERE email IS NOT NULL AND email != ""')
        people_with_emails = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM apollo_people WHERE phone IS NOT NULL AND phone != ""')
        people_with_phones = cursor.fetchone()[0]
        
        # Company stats
        cursor.execute('SELECT COUNT(*) FROM apollo_companies')
        total_companies = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM apollo_companies WHERE primary_domain IS NOT NULL AND primary_domain != ""')
        companies_with_domains = cursor.fetchone()[0]
        
        print(f"\n{'='*80}")
        print("DATABASE STATISTICS")
        print(f"{'='*80}")
        print(f"Apollo People: {total_people:,}")
        print(f"  - With emails: {people_with_emails:,} ({people_with_emails/total_people*100:.1f}%)")
        print(f"  - With phones: {people_with_phones:,} ({people_with_phones/total_people*100:.1f}%)")
        print(f"Apollo Companies: {total_companies:,}")
        print(f"  - With domains: {companies_with_domains:,} ({companies_with_domains/total_companies*100:.1f}%)")
        
    finally:
        conn.close()

def main():
    """Main function to run the database coverage test"""
    print("DATABASE COVERAGE TEST")
    print("This script mimics get_lawyer_contacts.py and checks database coverage")
    
    # Check if database exists
    if not os.path.exists('apollo_cache.db'):
        print("ERROR: apollo_cache.db not found!")
        print("Please run migrate_json_to_sqlite.py first to create the database.")
        return
    
    # Get database statistics
    get_database_stats()
    
    # Fetch sample leads from Close API
    try:
        leads = fetch_sample_leads()
        if leads:
            # Analyze coverage
            coverage_results = analyze_lead_coverage(leads)
        else:
            print("Failed to fetch leads from Close API")
    
    except Exception as e:
        print(f"Error: {e}")
        print("Make sure CLOSE_API_KEY is set in your .env file")

if __name__ == "__main__":
    main()

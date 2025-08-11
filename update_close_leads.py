import os
import json
import requests
from base64 import b64encode
from dotenv import load_dotenv
import time

load_dotenv()

# Defensive string helper functions to prevent NoneType errors
def safe_str(value):
    """Convert None to empty string, keep strings as-is"""
    return str(value) if value is not None else ''

def safe_lower(text):
    """Safely convert to lowercase, handles None"""
    return safe_str(text).lower()

def safe_strip(text):
    """Safely strip whitespace, handles None"""
    return safe_str(text).strip()

def safe_split(text, delimiter):
    """Safely split string, handles None"""
    return safe_str(text).split(delimiter)

def get_close_auth_header():
    """Get Close CRM authentication header"""
    api_key = os.getenv('CLOSE_API_KEY')
    if not api_key:
        raise ValueError("CLOSE_API_KEY not found in environment variables")
    
    encoded_key = b64encode(f"{api_key}:".encode('utf-8')).decode('utf-8')
    return f'Basic {encoded_key}'

def extract_domain_root(domain):
    """Extract the root domain (e.g., 'example' from 'example.com')"""
    if not domain:
        return None
    return domain.split('.')[0].lower()

def is_domain_related(contact_email, attorney_firm_domain):
    """Check if contact email domain is related to the attorney firm domain"""
    if not contact_email or not attorney_firm_domain:
        return True  # If we don't have domain info, allow the contact
    
    if '@' not in contact_email:
        return False
    
    contact_domain = safe_lower(safe_split(contact_email, '@')[1])
    attorney_domain = safe_lower(attorney_firm_domain)
    
    # Exact domain match
    if contact_domain == attorney_domain:
        return True
    
    # Check if domain roots match (e.g., andersonhemmat.com vs andersonhemmat.net)
    contact_root = extract_domain_root(contact_domain)
    attorney_root = extract_domain_root(attorney_domain)
    
    if contact_root and attorney_root and contact_root == attorney_root:
        return True
    
    # Check if one domain contains the other (subdomain relationships)
    if attorney_domain in contact_domain or contact_domain in attorney_domain:
        return True
    
    return False

def check_existing_contacts(lead_id):
    """Get all existing contacts for a lead"""
    url = f"https://api.close.com/api/v1/contact/?lead_id={lead_id}"
    headers = {
        'Authorization': get_close_auth_header(),
        'Content-Type': 'application/json'
    }
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        contacts = response.json().get('data', [])
        return contacts
        
    except Exception as e:
        print(f"    ERROR checking existing contacts: {e}")
        return []

def find_matching_contact(existing_contacts, lawyer_name, lawyer_email):
    """Find if lawyer already exists by name or email"""
    lawyer_name_lower = safe_lower(safe_strip(lawyer_name))
    lawyer_email_lower = safe_lower(safe_strip(lawyer_email))
    
    for contact in existing_contacts:
        # Check by name match
        contact_name = safe_lower(safe_strip(contact.get('name')))
        if contact_name == lawyer_name_lower:
            return contact
        
        # Check by email match
        contact_emails = contact.get('emails', [])
        for email_obj in contact_emails:
            if safe_lower(safe_strip(email_obj.get('email'))) == lawyer_email_lower:
                return contact
    
    return None

def update_existing_contact(contact_id, lawyer_data, phone_data=None):
    """Update existing contact with missing phone/email data"""
    url = f"https://api.close.com/api/v1/contact/{contact_id}/"
    headers = {
        'Authorization': get_close_auth_header(),
        'Content-Type': 'application/json'
    }
    
    try:
        # Get current contact data
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        current_data = response.json()
        
        current_emails = current_data.get('emails', [])
        current_phones = current_data.get('phones', [])
        
        # Check what needs to be added
        new_emails = []
        new_phones = []
        updates_made = []
        
        # Check if lawyer email needs to be added
        lawyer_email = lawyer_data.get('email')
        if lawyer_email and lawyer_email != 'email_not_unlocked@domain.com':
            email_exists = any(
                email_obj.get('email', '').lower() == lawyer_email.lower() 
                for email_obj in current_emails
            )
            
            if not email_exists:
                new_emails.append({
                    "email": lawyer_email,
                    "type": "work"
                })
                updates_made.append(f"Added email: {lawyer_email}")
        
        # Check if phone numbers need to be added
        if phone_data:
            existing_phone_numbers = [
                phone_obj.get('phone', '').replace(' ', '').replace('-', '').replace('(', '').replace(')', '')
                for phone_obj in current_phones
            ]
            
            for phone_info in phone_data.get('phone_numbers', []):
                new_phone = phone_info.get('sanitized_number') or phone_info.get('raw_number')
                if new_phone:
                    # Normalize phone for comparison
                    normalized_new = new_phone.replace(' ', '').replace('-', '').replace('(', '').replace(')', '')
                    
                    # Check if this phone already exists
                    if not any(normalized_new in existing_phone for existing_phone in existing_phone_numbers):
                        new_phones.append({
                            "phone": new_phone,
                            "type": phone_info.get('type_cd', 'work')
                        })
                        updates_made.append(f"Added phone: {new_phone}")
        
        # Update contact if we have new data
        if new_emails or new_phones:
            update_payload = {
                "emails": current_emails + new_emails,
                "phones": current_phones + new_phones
            }
            
            response = requests.put(url, headers=headers, json=update_payload)
            response.raise_for_status()
            
            print(f"    [UPDATED] {lawyer_data['name']}: {', '.join(updates_made)}")
            return True
        else:
            print(f"    [SKIP] {lawyer_data['name']} already has all available contact info")
            return False
            
    except Exception as e:
        print(f"    [ERROR] Error updating {lawyer_data['name']}: {e}")
        return False

def add_lawyer_to_lead(lead_id, client_name, firm_name, lawyer_data, phone_data=None, existing_contacts=None, attorney_firm_domain=None):
    """Add a lawyer as a contact or update existing contact with new info"""
    
    lawyer_email = lawyer_data.get('email')
    if not lawyer_email or lawyer_email == 'email_not_unlocked@domain.com':
        print(f"    [SKIP] {lawyer_data['name']} - no valid email")
        return None
    
    # Domain validation - ensure contact email domain matches the attorney firm domain
    if attorney_firm_domain:
        if not is_domain_related(lawyer_email, attorney_firm_domain):
            contact_domain = safe_split(lawyer_email, '@')[1] if '@' in safe_str(lawyer_email) else 'unknown'
            print(f"    [SKIP] {lawyer_data['name']} - email domain mismatch")
            print(f"           Attorney firm domain: {attorney_firm_domain}")
            print(f"           Contact email domain: {contact_domain}")
            print(f"           This contact appears to be from a different organization")
            return None
    
    # Check if lawyer already exists
    if existing_contacts is None:
        existing_contacts = check_existing_contacts(lead_id)
    
    existing_contact = find_matching_contact(existing_contacts, lawyer_data['name'], lawyer_email)
    
    if existing_contact:
        # Update existing contact
        print(f"    [EXISTS] {lawyer_data['name']} already exists - checking for updates...")
        success = update_existing_contact(existing_contact['id'], lawyer_data, phone_data)
        return existing_contact['id'] if success else None
    
    else:
        # Create new contact
        url = "https://api.close.com/api/v1/contact/"
        headers = {
            'Authorization': get_close_auth_header(),
            'Content-Type': 'application/json'
        }
        
        # Prepare contact payload
        emails = [{
            "email": lawyer_email,
            "type": "work"
        }]
        
        phones = []
        if phone_data:
            for phone_info in phone_data.get('phone_numbers', []):
                phones.append({
                    "phone": phone_info.get('sanitized_number') or phone_info.get('raw_number'),
                    "type": phone_info.get('type_cd', 'work')
                })
        
        payload = {
            "lead_id": lead_id,
            "name": lawyer_data['name'],
            "title": lawyer_data.get('title', 'Attorney'),
            "emails": emails,
            "phones": phones
        }
        
        try:
            response = requests.post(url, headers=headers, json=payload)
            response.raise_for_status()
            
            # Show what was added
            contact_info = [f"{lawyer_data['name']} ({lawyer_data.get('title', 'Attorney')})"]
            contact_info.append(f"Email: {lawyer_email}")
            if phones:
                contact_info.append(f"{len(phones)} phone(s)")
            
            print(f"    [CREATED] New contact: {' | '.join(contact_info)}")
            return response.json()['id']
            
        except Exception as e:
            print(f"    [ERROR] Failed to create {lawyer_data['name']}: {e}")
            return None

def load_phone_data():
    """Load phone data from webhook responses if available"""
    phone_data = {}
    
    if os.path.exists('webhook_data.json'):
        try:
            with open('webhook_data.json', 'r', encoding='utf-8') as f:
                webhook_responses = json.load(f)
                
            for response in webhook_responses:
                response_data = response.get('data', {})
                people = response_data.get('people', [])
                
                for person in people:
                    person_id = person.get('id')
                    if person_id and person.get('phone_numbers'):
                        phone_data[person_id] = person
                        
            print(f"Loaded phone data for {len(phone_data)} people from webhook responses")
        except Exception as e:
            print(f"Warning: Could not load phone data: {e}")
    
    return phone_data

def process_company_results():
    """Process apollo_company_results.json and update Close leads"""
    
    # Load company results
    try:
        with open('apollo_company_results.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError:
        print("ERROR: apollo_company_results.json not found")
        print("Run apollo_enrich.py first to generate company data")
        return
    
    print("UPDATING CLOSE CRM LEADS WITH APOLLO DATA")
    print("=" * 60)
    print(f"Processing {data['successful_searches']} successful firm matches...")
    
    # Check for phone data and prompt user
    phone_data = {}
    include_phones = False
    
    if os.path.exists('webhook_data.json'):
        try:
            with open('webhook_data.json', 'r', encoding='utf-8') as f:
                webhook_responses = json.load(f)
            
            # Count available phone numbers
            phone_count = 0
            for response in webhook_responses:
                response_data = response.get('data', {})
                people = response_data.get('people', [])
                for person in people:
                    if person.get('phone_numbers'):
                        phone_count += len(person.get('phone_numbers', []))
            
            if phone_count > 0:
                print(f"\n[PHONE DATA] Found webhook_data.json with {phone_count} phone numbers available")
                
                while True:
                    choice = input("Include phone numbers in the update? (y/n): ").lower().strip()
                    if choice in ['y', 'yes']:
                        include_phones = True
                        print("[OK] Will include phone numbers from webhook data")
                        break
                    elif choice in ['n', 'no']:
                        include_phones = False
                        print("[OK] Will update emails only")
                        break
                    else:
                        print("Please enter 'y' or 'n'")
                
                if include_phones:
                    # Load phone data
                    for response in webhook_responses:
                        response_data = response.get('data', {})
                        people = response_data.get('people', [])
                        for person in people:
                            person_id = person.get('id')
                            if person_id and person.get('phone_numbers'):
                                phone_data[person_id] = person
                    
                    print(f"Loaded phone data for {len(phone_data)} people")
            else:
                print("\n[PHONE DATA] webhook_data.json found but no phone numbers available")
                print("[OK] Will update emails only")
        
        except Exception as e:
            print(f"\n[WARNING] Could not load webhook_data.json: {e}")
            print("[OK] Will update emails only")
    
    else:
        print("\n[PHONE DATA] No webhook_data.json found")
        print("[OK] Will update emails only")
        print("   Run get_apollo_nums.py and wait for webhook responses to get phone numbers")
    
    total_contacts_added = 0
    
    print(f"\n{'=' * 60}")
    print("STARTING CLOSE CRM UPDATES")
    print(f"{'=' * 60}")
    
    # Process each successful search result
    for result in data['search_results']:
        if not result.get('search_successful'):
            continue
            
        lead_id = result['lead_id']
        client_name = result['client_name']
        firm_name = result['firm_name']
        attorney_firm_domain = result.get('firm_domain')  # Get original attorney firm domain
        contacts = result.get('contacts', [])
        
        print(f"\n{client_name} -> {firm_name} ({len(contacts)} lawyers)")
        print(f"Lead ID: {lead_id}")
        if attorney_firm_domain:
            print(f"Attorney domain: {attorney_firm_domain}")
        
        if not contacts:
            print("  No contacts to add")
            continue
        
        # Get existing contacts once for this lead
        existing_contacts = check_existing_contacts(lead_id)
        if existing_contacts:
            print(f"  Found {len(existing_contacts)} existing contacts on this lead")
        
        for lawyer in contacts:
            # Get phone data for this lawyer if available and requested
            lawyer_phone_data = None
            if include_phones:
                person_id = lawyer.get('person_id')
                lawyer_phone_data = phone_data.get(person_id) if person_id else None
                
                if lawyer_phone_data:
                    phone_count = len(lawyer_phone_data.get('phone_numbers', []))
                    print(f"    [PHONE] Found {phone_count} phone numbers for {lawyer['name']}")
            
            # Add/update lawyer in Close lead with domain validation
            contact_id = add_lawyer_to_lead(lead_id, client_name, firm_name, lawyer, lawyer_phone_data, existing_contacts, attorney_firm_domain)
            if contact_id:
                total_contacts_added += 1
            
            # Rate limiting
            time.sleep(0.5)
    
    print(f"\n{'=' * 60}")
    print(f"CLOSE CRM UPDATE COMPLETE")
    print(f"Total contacts added: {total_contacts_added}")
    if include_phones:
        print(f"Included phone numbers: [OK]")
    else:
        print(f"Phone numbers: Not included")
    print(f"{'=' * 60}")

if __name__ == "__main__":
    try:
        process_company_results()
    except KeyboardInterrupt:
        print("\nScript interrupted by user")
    except Exception as e:
        print(f"Unexpected error: {e}")
        raise

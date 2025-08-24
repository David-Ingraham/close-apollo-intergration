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
    """
    Check if contact email domain matches attorney firm domain exactly or is a legitimate subdomain.
    
    Examples:
    - john@smithlaw.com vs smithlaw.com → True (exact match)
    - mail@mail.smithlaw.com vs smithlaw.com → True (legitimate subdomain)
    - john@smithlaw.org vs smithlaw.com → False (different TLD)
    - harry@1call.org.uk vs 1call.org → False (different TLD structure)
    """
    if not contact_email or not attorney_firm_domain:
        return True  # If we don't have domain info, allow the contact
    
    if '@' not in contact_email:
        return False
    
    contact_domain = safe_lower(safe_split(contact_email, '@')[1])
    attorney_domain = safe_lower(attorney_firm_domain)
    
    # ONLY exact domain match
    if contact_domain == attorney_domain:
        return True
    
    # Extract base domain and TLD for comparison
    def get_domain_parts(domain):
        """Split domain into base name and TLD parts"""
        parts = domain.split('.')
        if len(parts) < 2:
            return None, None
        
        # Handle common TLD patterns
        if len(parts) >= 3 and parts[-2] in ['co', 'com', 'org', 'net', 'gov', 'edu']:
            # e.g., domain.co.uk, domain.org.uk
            return '.'.join(parts[:-2]), '.'.join(parts[-2:])
        else:
            # e.g., domain.com, domain.org
            return '.'.join(parts[:-1]), parts[-1]
    
    contact_base, contact_tld = get_domain_parts(contact_domain)
    attorney_base, attorney_tld = get_domain_parts(attorney_domain)
    
    # Both domains must have the same base domain and TLD structure
    if not (contact_base and attorney_base and contact_tld and attorney_tld):
        return False
    
    if contact_tld != attorney_tld:
        return False  # Different TLD structures (e.g., .org vs .org.uk)
    
    if contact_base == attorney_base:
        return True  # Same base domain and TLD
    
    # Check for legitimate subdomain relationships
    # Valid: mail.smithlaw vs smithlaw (with same TLD)
    if contact_base.endswith('.' + attorney_base):
        subdomain = contact_base[:-len('.' + attorney_base)]
        # Only allow simple subdomains (not complex nested ones)
        if '.' not in subdomain and len(subdomain) <= 10:
            return True
    
    if attorney_base.endswith('.' + contact_base):
        subdomain = attorney_base[:-len('.' + contact_base)]
        if '.' not in subdomain and len(subdomain) <= 10:
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

def add_main_office_contact(lead_id, firm_name, firm_phone, existing_contacts=None):
    """Create a Main Office contact for the firm's main phone number"""
    if not firm_phone:
        return None
        
    contact_name = f"{firm_name} - Main Office"
    
    # Check if Main Office contact already exists
    if existing_contacts:
        for contact in existing_contacts:
            if contact.get('name', '').endswith('- Main Office'):
                print(f"    [EXISTS] Main Office contact already exists")
                return contact['id']
    
    url = "https://api.close.com/api/v1/contact/"
    headers = {
        'Authorization': get_close_auth_header(),
        'Content-Type': 'application/json'
    }
    
    # Create Main Office contact payload
    payload = {
        "lead_id": lead_id,
        "name": contact_name,
        "title": "Main Office",
        "phones": [{
            "phone": firm_phone,
            "type": "office"
        }]
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        
        print(f"    [CREATED] Main Office contact: {firm_phone}")
        return response.json()['id']
        
    except Exception as e:
        print(f"    [ERROR] Failed to create Main Office contact: {e}")
        return None

def is_valid_contact_name(name):
    """Check if contact name is valid (not None, empty, or variations of None)"""
    if not name or not isinstance(name, str):
        return False
    
    # Clean the name
    cleaned_name = name.strip().lower()
    
    # Check for invalid patterns
    invalid_patterns = [
        'none none',
        'none',
        'null null', 
        'null',
        '',
        ' ',
        'n/a',
        'unknown unknown',
        'unknown'
    ]
    
    # Check exact matches
    if cleaned_name in invalid_patterns:
        return False
    
    # Check patterns with wildcards: "none *", "* none"
    words = cleaned_name.split()
    if len(words) == 2:
        if words[0] == 'none' or words[1] == 'none':
            return False
        if words[0] == 'null' or words[1] == 'null':
            return False
    
    return True

def add_lawyer_to_lead(lead_id, client_name, firm_name, lawyer_data, phone_data=None, existing_contacts=None, attorney_firm_domain=None):
    """Add a lawyer as a contact or update existing contact with new info"""
    
    # Debug: Check if lawyer_data is a list instead of dict
    if isinstance(lawyer_data, list):
        print(f"    [ERROR] lawyer_data is a list instead of dict: {lawyer_data}")
        return None
    
    if not isinstance(lawyer_data, dict):
        print(f"    [ERROR] lawyer_data is not a dict: {type(lawyer_data)} - {lawyer_data}")
        return None
    
    # Check for valid contact name
    lawyer_name = lawyer_data.get('name', '')
    if not is_valid_contact_name(lawyer_name):
        print(f"    [SKIP] Invalid contact name: '{lawyer_name}' - not creating contact")
        return None
    
    lawyer_email = lawyer_data.get('email')
    if not lawyer_email or lawyer_email == 'email_not_unlocked@domain.com':
        print(f"    [SKIP] {lawyer_data['name']} - no valid email")
        return None
    
    # Domain validation removed - handled upstream in apollo_enrich.py
    
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
    print(f"Processing {data.get('successful_searches', 0)} successful firm matches...")
    
    # Show attorney enrichment stats if available
    if data.get('attorney_enrichments'):
        print(f"Also processing {data.get('attorney_enrichments', 0)} attorney enrichments...")
    
    print(f"Data mode: {data.get('mode', 'unknown')}")
    
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
    attorney_contacts_added = 0
    firm_contacts_added = 0
    
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
        firm_phone = result.get('firm_phone')  # Get firm main phone number
        contacts = result.get('contacts', [])
        attorney_contact = result.get('attorney_contact')  # NEW: Get original attorney contact
        
        # Prepare contact list including original attorney
        all_contacts = []
        
        # Add original attorney if enrichment was successful
        if attorney_contact:
            all_contacts.append(attorney_contact)
        
        # Add firm contacts - flatten any nested structures
        for contact in contacts:
            if isinstance(contact, dict):
                # Individual contact dictionary
                all_contacts.append(contact)
            elif isinstance(contact, list):
                # List of contacts - flatten it
                for sub_contact in contact:
                    if isinstance(sub_contact, dict):
                        all_contacts.append(sub_contact)
            # Skip strings or other invalid types
        
        attorney_count = 1 if attorney_contact else 0
        firm_contact_count = len(all_contacts) - attorney_count  # Count actual contacts after flattening
        total_contacts = len(all_contacts)
        
        print(f"\n{client_name} -> {firm_name}")
        print(f"Lead ID: {lead_id}")
        if attorney_firm_domain:
            print(f"Attorney domain: {attorney_firm_domain}")
        if firm_phone:
            print(f"Firm phone: {firm_phone}")
        print(f"Contacts: {attorney_count} attorney + {firm_contact_count} firm = {total_contacts} total")
        
        # Get existing contacts once for this lead
        existing_contacts = check_existing_contacts(lead_id)
        if existing_contacts:
            print(f"  Found {len(existing_contacts)} existing contacts on this lead")
        
        # Create Main Office contact if we have a firm phone number AND found valid contacts
        # Conservative approach: only add firm phone if we found domain-matching people
        if firm_phone and all_contacts:
            print(f"  Creating Main Office contact...")
            main_office_id = add_main_office_contact(lead_id, firm_name, firm_phone, existing_contacts)
            if main_office_id:
                total_contacts_added += 1
        elif firm_phone and not all_contacts:
            print(f"  Skipping Main Office contact - no valid contacts found")
        
        if not all_contacts:
            print("  No individual contacts to add")
            continue
        
        # Process all contacts (attorney + firm contacts)
        print(f"  DEBUG: all_contacts type: {type(all_contacts)}, length: {len(all_contacts) if hasattr(all_contacts, '__len__') else 'N/A'}")
        for i, lawyer in enumerate(all_contacts):
            #print(f"  DEBUG: lawyer[{i}] type: {type(lawyer)}, content: {lawyer}")
            
            # Skip if lawyer is not a dict
            if not isinstance(lawyer, dict):
                print(f"    [ERROR] Skipping lawyer[{i}] - not a dictionary: {type(lawyer)}")
                continue
                
            # Identify if this is the original attorney
            is_original_attorney = (i == 0 and attorney_contact is not None)
            contact_type = "attorney" if is_original_attorney else "firm contact"
            # Get phone data for this lawyer if available and requested
            lawyer_phone_data = None
            if include_phones:
                person_id = lawyer.get('person_id')
                lawyer_phone_data = phone_data.get(person_id) if person_id else None
                
                if lawyer_phone_data:
                    phone_count = len(lawyer_phone_data.get('phone_numbers', []))
                    print(f"    [PHONE] Found {phone_count} phone numbers for {lawyer['name']} ({contact_type})")
            
            # Special handling for original attorney
            if is_original_attorney:
                print(f"    [ATTORNEY] Processing original attorney: {lawyer.get('name')}")
            
            # Add/update lawyer in Close lead with domain validation
            contact_id = add_lawyer_to_lead(lead_id, client_name, firm_name, lawyer, lawyer_phone_data, existing_contacts, attorney_firm_domain)
            if contact_id:
                total_contacts_added += 1
                if is_original_attorney:
                    attorney_contacts_added += 1
                    print(f"    [ATTORNEY] Successfully added original attorney contact")
                else:
                    firm_contacts_added += 1
            
            # Rate limiting
            time.sleep(0.5)
    
    print(f"\n{'=' * 60}")
    print(f"CLOSE CRM UPDATE COMPLETE")
    print(f"Total contacts added: {total_contacts_added}")
    print(f"  - Attorney contacts: {attorney_contacts_added}")
    print(f"  - Firm contacts: {firm_contacts_added}")
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

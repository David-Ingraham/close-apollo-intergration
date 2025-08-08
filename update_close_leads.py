import os
import json
import requests
from base64 import b64encode
from dotenv import load_dotenv
import time

load_dotenv()

def get_close_auth_header():
    """Get Close CRM authentication header"""
    api_key = os.getenv('CLOSE_API_KEY')
    if not api_key:
        raise ValueError("CLOSE_API_KEY not found in environment variables")
    
    encoded_key = b64encode(f"{api_key}:".encode('utf-8')).decode('utf-8')
    return f'Basic {encoded_key}'

def check_existing_contacts(lead_id, lawyer_email):
    """Check if lawyer already exists as contact on this lead"""
    url = f"https://api.close.com/api/v1/contact/?lead_id={lead_id}"
    headers = {
        'Authorization': get_close_auth_header(),
        'Content-Type': 'application/json'
    }
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        contacts = response.json().get('data', [])
        
        # Check if any existing contact has this email
        for contact in contacts:
            contact_emails = [email.get('email', '').lower() for email in contact.get('emails', [])]
            if lawyer_email.lower() in contact_emails:
                return contact['id']  # Return existing contact ID
        
        return None  # No existing contact found
        
    except Exception as e:
        print(f"    ERROR checking existing contacts: {e}")
        return None

def add_lawyer_to_lead(lead_id, client_name, firm_name, lawyer_data, phone_data=None):
    """Add a lawyer as a contact to the existing lead in Close CRM"""
    
    url = "https://api.close.com/api/v1/contact/"
    headers = {
        'Authorization': get_close_auth_header(),
        'Content-Type': 'application/json'
    }
    
    # Prepare contact payload
    emails = []
    if lawyer_data.get('email') and lawyer_data['email'] != 'email_not_unlocked@domain.com':
        emails.append({
            "email": lawyer_data['email'],
            "type": "work"
        })
    
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
        if emails:
            contact_info.append(f"Email: {emails[0]['email']}")
        if phones:
            contact_info.append(f"Phone: {phones[0]['phone']}")
            if len(phones) > 1:
                contact_info.append(f"+ {len(phones)-1} more phones")
        
        print(f"    ✓ Added {' | '.join(contact_info)}")
        return response.json()['id']
        
    except Exception as e:
        print(f"    ✗ Failed to add {lawyer_data['name']}: {e}")
        return None

def update_existing_contact(contact_id, lawyer_data, phone_data=None):
    """Update existing contact with new phone/email data"""
    url = f"https://api.close.com/api/v1/contact/{contact_id}/"
    headers = {
        'Authorization': get_close_auth_header(),
        'Content-Type': 'application/json'
    }
    
    # Get current contact data first
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        current_data = response.json()
        
        # Merge new phone data with existing
        existing_phones = current_data.get('phones', [])
        new_phones = []
        
        if phone_data:
            for phone_info in phone_data.get('phone_numbers', []):
                phone_number = phone_info.get('sanitized_number') or phone_info.get('raw_number')
                # Check if this phone already exists
                if not any(phone_number in existing_phone.get('phone', '') for existing_phone in existing_phones):
                    new_phones.append({
                        "phone": phone_number,
                        "type": phone_info.get('type_cd', 'work')
                    })
        
        if new_phones:
            # Update with new phone numbers
            update_payload = {
                "phones": existing_phones + new_phones
            }
            
            response = requests.put(url, headers=headers, json=update_payload)
            response.raise_for_status()
            
            print(f"    ✓ Updated {lawyer_data['name']} with {len(new_phones)} new phone numbers")
            return contact_id
        else:
            print(f"    ⚠ {lawyer_data['name']} - no new data to update")
            return contact_id
            
    except Exception as e:
        print(f"    ✗ Error updating contact {lawyer_data['name']}: {e}")
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
                print(f"\n📞 Found webhook_data.json with {phone_count} phone numbers available")
                
                while True:
                    choice = input("Include phone numbers in the update? (y/n): ").lower().strip()
                    if choice in ['y', 'yes']:
                        include_phones = True
                        print("✓ Will include phone numbers from webhook data")
                        break
                    elif choice in ['n', 'no']:
                        include_phones = False
                        print("✓ Will update emails only")
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
                print("\n📞 webhook_data.json found but no phone numbers available")
                print("✓ Will update emails only")
        
        except Exception as e:
            print(f"\n⚠ Warning: Could not load webhook_data.json: {e}")
            print("✓ Will update emails only")
    
    else:
        print("\n📞 No webhook_data.json found")
        print("✓ Will update emails only")
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
        contacts = result.get('contacts', [])
        
        print(f"\n{client_name} -> {firm_name} ({len(contacts)} lawyers)")
        print(f"Lead ID: {lead_id}")
        
        if not contacts:
            print("  No contacts to add")
            continue
        
        for lawyer in contacts:
            if not lawyer.get('email') or lawyer['email'] == 'email_not_unlocked@domain.com':
                print(f"  ⚠ Skipping {lawyer['name']} - no valid email")
                continue
            
            # Get phone data for this lawyer if available and requested
            lawyer_phone_data = None
            if include_phones:
                person_id = lawyer.get('person_id')
                lawyer_phone_data = phone_data.get(person_id) if person_id else None
                
                if lawyer_phone_data:
                    phone_count = len(lawyer_phone_data.get('phone_numbers', []))
                    print(f"    📞 Found {phone_count} phone numbers for {lawyer['name']}")
            
            # Add lawyer to Close lead
            contact_id = add_lawyer_to_lead(lead_id, client_name, firm_name, lawyer, lawyer_phone_data)
            if contact_id:
                total_contacts_added += 1
            
            # Rate limiting
            time.sleep(0.5)
    
    print(f"\n{'=' * 60}")
    print(f"CLOSE CRM UPDATE COMPLETE")
    print(f"Total contacts added: {total_contacts_added}")
    if include_phones:
        print(f"Included phone numbers: ✓")
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

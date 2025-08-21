import os
import json
import requests
from dotenv import load_dotenv
from base64 import b64encode

def extract_domain_from_email(email):
    """Extract domain from email address"""
    if email and '@' in email:
        return email.split('@')[1].lower()
    return None

def is_personal_domain(domain):
    """Check if domain is a personal email provider"""
    personal_domains = {
        "gmail.com", "yahoo.com", "outlook.com", "hotmail.com", "aol.com", 
        "icloud.com", "protonmail.com", "yandex.com", "msn.com", "live.com", 
        "me.com", "comcast.net", "verizon.net", "att.net"
    }
    return bool(domain) and domain in personal_domains

def check_contact_exists(encoded_key, email=None, firm_name=None):
    """
    Check if contacts exist in Close by domain (for emails) or firm name
    """
    headers = {
        'Authorization': f'Basic {encoded_key}',
        'Content-Type': 'application/json',
    }
    
    # Build the query based on what we're searching for
    if email:
        domain = extract_domain_from_email(email)
        if not domain:
            print(f"    Invalid email format: {email}")
            return None, None
        
        if is_personal_domain(domain):
            print(f"    Skipping personal domain: {domain}")
            return None, None
        
        print(f"    Searching for contacts at domain: {domain}")
        
        # Search for any contacts with emails containing this domain
        data = {
            "queries": [
                {
                    "type": "object_type",
                    "object_type": "contact"
                },
                {
                    "type": "field_condition",
                    "field": {
                        "type": "regular_field",
                        "object_type": "contact",
                        "field_name": "email"
                    },
                    "condition": {
                        "type": "text",
                        "mode": "contains",
                        "value": f"@{domain}"
                    }
                }
            ],
            "_fields": {
                "contact": ["id", "name", "emails", "phones", "title", "organization_id"]
            }
        }
    elif firm_name:
        data = {
            "queries": [
                {
                    "type": "object_type",
                    "object_type": "contact"
                },
                {
                    "type": "field_condition",
                    "field": {
                        "type": "regular_field",
                        "object_type": "contact",
                        "field_name": "organization_name"
                    },
                    "condition": {
                        "type": "text",
                        "mode": "full_words",
                        "value": firm_name
                    }
                }
            ],
            "_fields": {
                "contact": ["id", "name", "emails", "phones", "title", "organization_id"]
            }
        }
    else:
        return None, None
    
    print(f"    API Query: {json.dumps(data, indent=2)}")
    
    response = requests.post(
        'https://api.close.com/api/v1/data/search/',
        headers=headers,
        json=data
    )
    
    print(f"    API Response Status: {response.status_code}")
    
    if response.status_code == 200:
        response_data = response.json()
        all_results = response_data.get('data', [])
        
        # Filter to only actual contact objects (ignore leads, activities, etc.)
        actual_contacts = [item for item in all_results if item.get('__object_type') == 'contact']
        
        # Save full response to a file for analysis
        if email:
            domain = extract_domain_from_email(email)
            filename = f"domain_search_{domain.replace('.', '_')}.json"
        else:
            filename = f"firm_search_{firm_name.replace(' ', '_')}.json"
            
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(response_data, f, indent=2)
            print(f"    Full response saved to {filename}")
        except Exception as e:
            print(f"    Error saving response to file: {e}")
        
        print(f"    Total results: {len(all_results)}, Actual contacts: {len(actual_contacts)}")
        
        if actual_contacts:
            print(f"    Contact details:")
            for contact in actual_contacts[:3]:  # Show first 3 contacts
                contact_emails = contact.get('emails', [])
                contact_phones = contact.get('phones', [])
                contact_name = contact.get('name', 'No name')
                
                emails_list = [e.get('email', '') for e in contact_emails if e.get('email')]
                phones_list = [p.get('phone', '') for p in contact_phones if p.get('phone')]
                
                print(f"      • {contact_name}")
                print(f"        Emails: {', '.join(emails_list) if emails_list else 'None'}")
                print(f"        Phones: {', '.join(phones_list) if phones_list else 'None'}")
        
        return actual_contacts, response_data
    else:
        print(f"    API Error: {response.text}")
        return None, None

def test_field_discovery(encoded_key):
    """
    Test different field names to see what works
    """
    headers = {
        'Authorization': f'Basic {encoded_key}',
        'Content-Type': 'application/json',
    }
    
    # Try different field names that might work for email
    test_fields = [
        "emails",
        "emails.email", 
        "email",
        "contact_email.email",
        "contact_emails"
    ]
    
    print("Testing different field names...")
    
    for field_name in test_fields:
        print(f"\nTesting field: {field_name}")
        
        data = {
            "queries": [
                {
                    "type": "field_condition",
                    "field": {
                        "type": "regular_field",
                        "object_type": "contact",
                        "field_name": field_name
                    },
                    "condition": {
                        "type": "text",
                        "mode": "full_words",
                        "value": "test@example.com"
                    }
                }
            ]
        }
        
        response = requests.post(
            'https://api.close.com/api/v1/data/search/',
            headers=headers,
            json=data
        )
        
        print(f"  Status: {response.status_code}")
        if response.status_code != 200:
            error_text = response.text[:200]
            if "field_name" in error_text:
                print(f"  Field name invalid")
            elif "mode" in error_text:
                print(f"  Mode invalid, but field name might be OK")
            else:
                print(f"  Other error: {error_text}")
        else:
            print(f"  SUCCESS! Field name '{field_name}' works")
            return field_name
    
    return None

def main():
    """
    Main function to test existence of contacts in Close
    """
    load_dotenv()
    api_key = os.getenv('CLOSE_API_KEY')
    
    # Encode API key properly for Basic Auth
    encoded_key = b64encode(f"{api_key}:".encode('utf-8')).decode('utf-8')
    
    # First, test different field names
    print("=== FIELD DISCOVERY TEST ===")
    working_field = test_field_discovery(encoded_key)
    if working_field:
        print(f"\nFound working field: {working_field}")
    else:
        print("\nNo working field found, proceeding with original test...")
    
    print("\n=== MAIN TEST ===")
    
    # Smart View Configuration (copied from get_lawyer_contacts.py)
    SMART_VIEWS = {
        "closed_lost": {
            "id": "save_pkn62aAZeRFBxpo26Ued3BG8gKqoltIN5h9k9cBUvkL",
            "name": "Closed Lost"
        },
        "todays_leads": {
            "id": "save_ebxRoBR5KEXJz0jTSCfn1xyaXMQYBHmskqU6iCOoZd9", 
            "name": "Today's Leads"
        },
        "uncalled_leads": {
            "id": "save_PF9vEDVO1gpuE96xWcJheorDdvwTzZC78h7VSUNWtpz",
            "name": "Uncalled Leads"
        },
        "full_week_no_contact": {
            "id": "save_4vCZn8S0aEOI7LITSdgww6NHyEYPK42OKKo0UUq9xK0",
            "name": "Full Week No Contact"
        },
        "leads_created_by_mattias": {
            "id": "save_uWiE0ZujkNKqQHG19ugGz5dIba891rC9Jd8sgIGqgXh",
            "name": "Leads Created by Mattias"
        },
        "full_week_no_outbound": {
            "id": "save_5ICv93dt5AbFSfrSL7wdEQEgTYFH8bIidyBZ4U67USG",
            "name": "Full Week No Outbound"
        },
        "surgery_in_discovery": {
            "id": "save_O73Z1YkRGhLrN5qtyhti2lLoBYVeTqkKWsiG2ZUj4cE",
            "name": "Surgery in Discovery"
        },
        "All meta leads": {
            "id": "save_TOTstqdumHKQcNUaztinosJBnRDPYd7IAMhU2SuKyVH",
            "name": "All Meta Leads"
        },
        "yesterday_leads": {
            "id": "save_uFHbgnOiKu9tQiuZDfLM5JzrkZEOOMG2IF15qxONwaV",
            "name": "Yesterday's Leads"
        }
    }
    
    # Prompt user to select smart view
    print("\nAvailable Smart Views:")
    view_options = list(SMART_VIEWS.keys())
    for i, view_key in enumerate(view_options, 1):
        view_name = SMART_VIEWS[view_key]["name"]
        print(f"  {i}. {view_name}")
    
    while True:
        try:
            choice = input(f"\nSelect smart view (1-{len(view_options)}): ").strip()
            choice_num = int(choice)
            if 1 <= choice_num <= len(view_options):
                selected_view_key = view_options[choice_num - 1]
                break
            else:
                print(f"Please enter a number between 1-{len(view_options)}")
        except ValueError:
            print("Please enter a valid number")
    
    current_smart_view = SMART_VIEWS[selected_view_key]
    view_id = current_smart_view["id"]
    view_name = current_smart_view["name"]
    
    print(f"Selected: {view_name}")
    
    headers = {
        'Authorization': f'Basic {encoded_key}',
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    }
    
    # Get the leads from the chosen smart view
    payload = {
        "query": {
            "type": "saved_search",
            "saved_search_id": view_id
        },
        "_fields": {
            "lead": ["id", "display_name", "status_id", "name", "contacts", "custom"]
        },
        "_limit": 200
    }
    
    response = requests.post(
        'https://api.close.com/api/v1/data/search/',
        headers=headers,
        json=payload
    )
    
    if response.status_code != 200:
        print(f"Failed to get leads. Status code: {response.status_code}")
        return

    leads = response.json().get('data', [])
    print(f"\nFound {len(leads)} leads in smart view '{view_name}'")
    print("-" * 80)

    # Track statistics
    total_leads = len(leads)
    email_matches = 0
    firm_matches = 0
    no_info = 0

    # Limit to first 3 leads for detailed debugging
    leads_to_check = leads[:3]
    print(f"(Testing first {len(leads_to_check)} leads for detailed debugging)")
    
    # Check each lead
    for i, lead in enumerate(leads_to_check, 1):
        # Extract attorney info from contacts custom fields (same as get_lawyer_contacts.py)
        attorney_email = 'N/A'
        attorney_firm = 'N/A'
        
        if lead.get('contacts') and len(lead['contacts']) > 0:
            client_contact = lead['contacts'][0]
            
            # Extract custom fields
            law_office = client_contact.get('custom.cf_lQKyH0EhHsNDLZn8KqfFSb0342doHgTNfWdTcfWCljw', 'N/A')
            attorney_name_field = client_contact.get('custom.cf_bB8dqX4BWGbISOehyNVVaZhJpfV9OZNOqs5WfYjaRYv', 'N/A')
            attorney_email = client_contact.get('custom.cf_vq0cl2Sj1h0QaSePdnTdf3NyAjx3w4QcgmlhgJrWrZE', 'N/A')
            
            # Set firm name (prioritize Law Office field)
            if law_office != 'N/A' and law_office.strip():
                attorney_firm = law_office
            elif attorney_name_field != 'N/A' and attorney_name_field.strip():
                attorney_firm = attorney_name_field
        
        attorney_email = attorney_email.strip() if attorney_email != 'N/A' else ''
        attorney_firm = attorney_firm.strip() if attorney_firm != 'N/A' else ''
        
        print(f"\nLead {i}/{len(leads_to_check)}:")
        print(f"Attorney: {attorney_email or 'No email'}")
        print(f"Firm: {attorney_firm or 'No firm name'}")
        
        if not attorney_email and not attorney_firm:
            print("  [NO INFO] No email or firm name to check")
            no_info += 1
            continue

        # Check email domain first if available
        if attorney_email:
            print(f"  Checking domain for email: {attorney_email}")
            results, raw_response = check_contact_exists(encoded_key, email=attorney_email)
            if results and len(results) > 0:
                email_matches += 1
                domain = extract_domain_from_email(attorney_email)
                print(f"  [DOMAIN MATCH] Found {len(results)} existing contact(s) at domain {domain}")
                continue

        # If no email match, check firm name
        if attorney_firm:
            print(f"  Searching for firm: {attorney_firm}")
            results, raw_response = check_contact_exists(encoded_key, firm_name=attorney_firm)
            if results and len(results) > 0:
                firm_matches += 1
                print(f"  [FIRM MATCH] Found {len(results)} existing contact(s) at {attorney_firm}")
                continue
        
        print("  [NO MATCH] No existing contacts found")
    
    # Update summary to reflect we only checked 3 leads
    total_leads = len(leads_to_check)

    # Print summary
    print("\n" + "="*80)
    print("                         SEARCH RESULTS SUMMARY")
    print("="*80)
    print(f"Total Leads Checked: {total_leads}")
    print(f"Email Matches Found: {email_matches}")
    print(f"Firm Name Matches Found: {firm_matches}")
    print(f"Leads with No Info: {no_info}")
    print(f"No Matches Found: {total_leads - email_matches - firm_matches - no_info}")
    print("="*80)

if __name__ == "__main__":
    main()


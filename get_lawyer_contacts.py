import os
from dotenv import load_dotenv
import requests
import json
import time
from base64 import b64encode

# Load environment variables
load_dotenv()

def fetch_leads_via_export_api(headers, view_id, view_name):
    """Fetch leads using Close CRM Export API for large datasets"""
    try:
        # Step 1: Initiate export with date filter (matches smart view criteria)
        export_url = "https://api.close.com/api/v1/export/lead/"
        export_payload = {
            "query": "date_created >= 2025-07-08",  # Matches smart view date filter
            "format": "json",
            "type": "leads",
            "send_done_email": False
        }
        
        print("  Initiating export...")
        response = requests.post(export_url, headers=headers, json=export_payload, timeout=30)
        
        if response.status_code not in [200, 201]:
            print(f"  Export initiation failed: {response.status_code}")
            return None
        
        export_data = response.json()
        export_id = export_data.get('id')
        print(f"  Export ID: {export_id}")
        
        # Step 2: Wait for export completion
        status_url = f"https://api.close.com/api/v1/export/{export_id}/"
        max_wait = 300  # 5 minutes
        start_time = time.time()
        
        while time.time() - start_time < max_wait:
            response = requests.get(status_url, headers=headers, timeout=30)
            if response.status_code != 200:
                print(f"  Status check failed: {response.status_code}")
                return None
            
            status_data = response.json()
            status = status_data.get('status')
            print(f"  Export status: {status}")
            
            if status == 'done':
                download_url = status_data.get('download_url')
                print(f"  Downloading data...")
                
                # Step 3: Download the data
                download_response = requests.get(download_url, headers=headers, timeout=60)
                if download_response.status_code == 200:
                    leads_data = download_response.json()
                    print(f"  Downloaded {len(leads_data)} leads")
                    return leads_data
                else:
                    print(f"  Download failed: {download_response.status_code}")
                    return None
            
            elif status == 'error':
                print(f"  Export failed with error")
                return None
            
            elif status in ['created', 'started', 'in_progress']:
                time.sleep(10)
            else:
                print(f"  Unknown status: {status}")
                return None
        
        print(f"  Export timed out after {max_wait} seconds")
        return None
        
    except Exception as e:
        print(f"  Export API error: {e}")
        return None



def get_todays_leads():
    # Get API key from environment
    api_key = os.getenv('CLOSE_API_KEY')
    if not api_key:
        raise ValueError("CLOSE_API_KEY not found in environment variables")

    # Encode API key properly for Basic Auth
    # The ':' after the API key is important!
    encoded_key = b64encode(f"{api_key}:".encode('utf-8')).decode('utf-8')

    # Smart View Configuration - CHANGE THIS TO SWITCH VIEWS
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

    # Special handling for "All Meta Leads" - use Export API instead of cursor pagination
    if "All Meta Leads" in view_name:
        print(f"Using Export API for {view_name} (bypasses pagination issues)...")
        all_leads = fetch_leads_via_export_api(headers, view_id, view_name)
        if all_leads is None:
            print("Export API failed, falling back to cursor pagination...")
        else:
            print(f"Export API successful: {len(all_leads)} leads retrieved")
            # Format data to match cursor API response format and return it
            return {'data': all_leads}
    
    # Standard cursor pagination for other smart views
    print(f"Fetching {view_name} smart view using cursor pagination...")
    url = 'https://api.close.com/api/v1/data/search/'
    
    # Fresh payload for each run - cursor-based pagination
    payload = {
        "query": {
            "type": "saved_search",
            "saved_search_id": view_id
        },
        "_fields": {
            "lead": ["id", "display_name", "status_id", "name", "contacts", "custom", "addresses"]
        },
        "_limit": 200
        # Note: _cursor will be added in the loop when available
    }

    try:
        all_leads = []
        page_count = 0
        cursor = None  # Start with no cursor for first page
        
        while True:
            page_count += 1
            
            # Add cursor to payload if we have one (not for first page)
            if cursor:
                payload['_cursor'] = cursor
            elif '_cursor' in payload:
                # Remove cursor if we don't have one (first page)
                del payload['_cursor']
            
            # Make the POST request to Advanced Filtering API
            response = requests.post(url, headers=headers, json=payload)
            print(f"Requesting page {page_count} (cursor: {cursor[:20] + '...' if cursor else 'None'})")
            response.raise_for_status()  # Raise an error for bad status codes
            
            api_response = response.json()
            page_leads = api_response.get('data', [])
            
            print(f"Found {len(page_leads)} leads on page {page_count}")
            print(f"API Response keys: {list(api_response.keys())}")
            
            # Check for total count information on first page
            if page_count == 1:
                for key in api_response.keys():
                    if 'total' in key.lower() or 'count' in key.lower() or 'has_more' in key.lower():
                        print(f"Total info found - {key}: {api_response[key]}")
                
                # Print full first response for debugging (excluding the actual data)
                debug_response = {k: v for k, v in api_response.items() if k != 'data'}
                print(f"First page metadata: {debug_response}")
            
            # Check for empty page - means we're done
            if not page_leads:
                print("No more pages (empty results)")
                break
            
            # Add all leads from this page
            all_leads.extend(page_leads)
            print(f"Added {len(page_leads)} leads (total: {len(all_leads)})")
            
            # If we got fewer leads than requested, we've reached the end
            if len(page_leads) < payload['_limit']:
                print(f"Got {len(page_leads)} leads (less than limit {payload['_limit']}) - reached end")
                break
            
            # Get cursor for next page
            next_cursor = api_response.get('cursor')
            
            # Debug: Print full cursors for comparison
            print(f"Current cursor: {cursor}")
            print(f"Next cursor:    {next_cursor}")
            
            # If no cursor returned, we're at the end
            if not next_cursor:
                print("No cursor returned - reached end of results")
                break
                
            # If cursor hasn't changed, we're stuck (safety check)
            if next_cursor == cursor:
                print("WARNING: Cursor hasn't changed - stopping to prevent infinite loop")
                print(f"Stuck cursor: {cursor}")
                break
                
            # Update cursor for next iteration
            cursor = next_cursor
            
            # Safety limit to prevent runaway loops
            if page_count >= 20:
                print(f"WARNING: Reached safety limit of 20 pages ({len(all_leads)} leads)")
                break
                
            # Add delay to be API-friendly
            print("Waiting 1 second before next page...")
            import time
            time.sleep(1)
        
        print(f"Total leads retrieved: {len(all_leads)} across {page_count} pages")
        
        if len(all_leads) > 0:
            # Return in the same format as before
            final_result = api_response.copy()  # Keep metadata from last response
            final_result['data'] = all_leads
            return final_result
        else:
            print(f"No leads found in {view_name}, returning empty result...")
            
            # Return empty result instead of fallback
            empty_result = api_response.copy()  # Keep metadata from last response
            empty_result['data'] = []
            return empty_result
        
    except requests.exceptions.RequestException as e:
        print(f"Error fetching leads: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response status: {e.response.status_code}")
            print(f"Response text: {e.response.text}")
        return None

def extract_domain_from_email(email):
    """Extract domain from email address"""
    if email and '@' in email:
        return email.split('@')[1]
    return None

def extract_state_from_address_string(address_string):
    """Extract state code from home address string like '110 west hartcort rd ingola IN 46703'"""
    if not address_string or address_string == 'N/A':
        return ''
    
    # Common state abbreviations and full names
    states = {
        'AL', 'AK', 'AZ', 'AR', 'CA', 'CO', 'CT', 'DE', 'FL', 'GA',
        'HI', 'ID', 'IL', 'IN', 'IA', 'KS', 'KY', 'LA', 'ME', 'MD',
        'MA', 'MI', 'MN', 'MS', 'MO', 'MT', 'NE', 'NV', 'NH', 'NJ',
        'NM', 'NY', 'NC', 'ND', 'OH', 'OK', 'OR', 'PA', 'RI', 'SC',
        'SD', 'TN', 'TX', 'UT', 'VT', 'VA', 'WA', 'WV', 'WI', 'WY', 'DC'
    }
    
    # Handle common state name variations
    state_mappings = {
        'MASS': 'MA',
        'MASSACHUSETTS': 'MA',
        'FLORIDA': 'FL',
        'CALIFORNIA': 'CA',
        'TEXAS': 'TX',
        'NEWYORK': 'NY',
        'ILLINOIS': 'IL'
    }
    
    # Split the address into words and look for state codes or names
    words = address_string.upper().split()
    
    for word in words:
        # Remove common punctuation
        clean_word = word.strip('.,;:')
        
        # Check for standard 2-letter codes
        if clean_word in states:
            return clean_word
        
        # Check for state name variations
        if clean_word in state_mappings:
            return state_mappings[clean_word]
    
    return ''  # No state found

def is_public_domain(domain):
    """Check if domain is a public email provider"""
    public_domains = {
        "gmail.com", "yahoo.com", "outlook.com", "hotmail.com", "aol.com", 
        "icloud.com", "protonmail.com", "yandex.com", "msn.com", "live.com", "me.com"
    }
    return bool(domain) and domain.lower() in public_domains

def derive_firm_name_from_domain(domain):
    """Derive likely firm name from email domain"""
    if not domain:
        return 'N/A'
    
    # Remove common TLDs and get the root
    domain_root = domain.replace('.com', '').replace('.org', '').replace('.net', '').replace('.law', '')
    
    # Common patterns to clean up
    # Remove 'law' suffix if it exists
    if domain_root.endswith('law'):
        domain_root = domain_root[:-3]
    
    # Split on common separators and capitalize
    if 'and' in domain_root:
        parts = domain_root.split('and')
        return ' and '.join(part.strip().title() for part in parts if part.strip())
    elif '&' in domain_root:
        parts = domain_root.split('&')
        return ' & '.join(part.strip().title() for part in parts if part.strip())
    else:
        # Handle camelCase or combined words
        # Simple approach: capitalize first letter
        return domain_root.title()
    
    # Examples:
    # johnfoy.com -> "Johnfoy" 
    # smith-jones.com -> "Smith-jones"
    # cellinolaw.com -> "Cellino"
    # scottbaronassociates.com -> "Scottbaronassociates"

def process_leads_data(leads_data, limit=None):
    """Extract and process lead information into structured format"""
    if not leads_data or 'data' not in leads_data:
        print("No lead data found")
        return None
    
    leads = leads_data.get('data', [])
    
    # Apply limit if specified
    if limit and limit > 0:
        leads = leads[:limit]
        print(f"Processing first {len(leads)} leads (limited by user request)")
    
    processed_leads = []
    
    print(f"\n{'='*80}")
    print("LEAD INFORMATION:")
    print("="*80)
    
    excluded_leads_count = 0
    
    for i, lead in enumerate(leads, 1):
        # Initialize all variables at the start of each iteration
        first_name = 'N/A'
        personal_email = 'N/A'
        attorney_name = 'N/A'
        attorney_email = 'N/A'
        firm_domain = None
        law_office = 'N/A'
        attorney_name_field = 'N/A'
        firm_name_source = None
        state_code = ''  # Two-letter state code like "TX", "CA"
        
        # Extract state code from lead addresses (do this for all leads, even excluded ones)
        if lead.get('addresses') and len(lead['addresses']) > 0:
            state_code = lead['addresses'][0].get('state', '')
            if state_code:
                state_code = state_code.upper().strip()  # Ensure uppercase and clean
        
        # Fallback: If no state from addresses, try home address custom field
        if not state_code and lead.get('contacts') and len(lead['contacts']) > 0:
            client_contact = lead['contacts'][0]
            home_address = client_contact.get('custom.cf_9jn7jli1kHQD1ori1puDHIehKGtMz3SlA3gWK2NUz0N', '')
            if home_address:
                state_code = extract_state_from_address_string(home_address)
        
        # Check if lead already has more than 2 contacts (completely exclude from processing)
        total_contacts = len(lead.get('contacts', []))
        if total_contacts > 2:
            excluded_leads_count += 1
            print(f"\nLead #{i}: {lead.get('display_name', 'Unknown')} - EXCLUDED")
            print(f"  Reason: Already has {total_contacts} contacts (>2) - skipping completely")
            continue  # Skip this lead entirely, don't add to processed_leads
        
        if lead.get('contacts') and len(lead['contacts']) > 0:
            # Get the first contact (the client)
            client_contact = lead['contacts'][0]
            first_name = client_contact.get('name', client_contact.get('display_name', 'N/A'))
            if client_contact.get('emails') and len(client_contact['emails']) > 0:
                personal_email = client_contact['emails'][0].get('email', 'N/A')
            
            # Extract custom fields (attorney info) from the client contact
            # The custom fields are stored directly on the contact with "custom." prefix
            
            # Get all available fields
            law_office = client_contact.get('custom.cf_lQKyH0EhHsNDLZn8KqfFSb0342doHgTNfWdTcfWCljw', 'N/A')  # Law Office field
            attorney_name_field = client_contact.get('custom.cf_bB8dqX4BWGbISOehyNVVaZhJpfV9OZNOqs5WfYjaRYv', 'N/A')  # Attorney Name field
            attorney_email = client_contact.get('custom.cf_vq0cl2Sj1h0QaSePdnTdf3NyAjx3w4QcgmlhgJrWrZE', 'N/A')
            
            # PRIORITY: Law Office > Domain-derived name > Attorney Name
            firm_name_source = None  # Track source for logging later
            if law_office != 'N/A' and law_office.strip():
                firm_name = law_office
                firm_name_source = f"Using Law Office field: {firm_name}"
            elif attorney_email != 'N/A' and '@' in attorney_email and not extract_domain_from_email(attorney_email) in ['gmail.com', 'yahoo.com', 'outlook.com', 'hotmail.com', 'aol.com']:
                # Derive firm name from business email domain
                domain = extract_domain_from_email(attorney_email)
                firm_name = derive_firm_name_from_domain(domain)
                firm_name_source = f"Derived from domain {domain}: {firm_name}"
            elif attorney_name_field != 'N/A' and attorney_name_field.strip():
                firm_name = attorney_name_field
                firm_name_source = f"Using Attorney Name field: {firm_name}"
            else:
                firm_name = 'N/A'
            
            # Set attorney_name to firm_name for consistency with existing code
            attorney_name = firm_name
            
            # If no firm name found in custom fields, check for separate attorney contact
            if attorney_name == 'N/A' and len(lead.get('contacts', [])) > 1:
                for contact in lead['contacts'][1:]:  # Skip first contact (client)
                    contact_title = contact.get('title', '').lower()
                    if 'attorney' in contact_title or 'law' in contact_title or 'firm' in contact_title:
                        # Try to get firm name from contact name or organization
                        attorney_name = contact.get('name', contact.get('display_name', 'N/A'))
                        # Also get attorney email from this contact if available
                        if contact.get('emails') and len(contact['emails']) > 0:
                            attorney_email = contact['emails'][0].get('email', attorney_email)
                        break
            

        
        # Determine enrichment needs and extract domain
        firm_domain = extract_domain_from_email(attorney_email) if attorney_email != 'N/A' else None
        needs_enrichment = True
        skip_reason = None
        search_strategy = None
        
        # Determine search strategy - prioritize firm name over domain
        if attorney_name != 'N/A':
            search_strategy = "firm_name"
        elif firm_domain:
            search_strategy = "domain"
        
        # Skip if no Law Office field AND personal email domain
        if (law_office == 'N/A' or not law_office.strip()) and firm_domain and is_public_domain(firm_domain):
            needs_enrichment = False
            skip_reason = "No Law Office field and personal email domain - cannot validate results"
        
        # Also skip if we have absolutely no searchable information
        elif attorney_name == 'N/A' and not firm_domain:
            needs_enrichment = False
            skip_reason = "No firm name or domain available for search"

        # Create lead record
        lead_record = {
            "lead_id": lead.get('id'),
            "client_name": first_name,
            "client_email": personal_email,
            "attorney_firm": attorney_name,
            "attorney_email": attorney_email,
            "firm_domain": firm_domain,
            "state_code": state_code,
            "search_strategy": search_strategy,
            "needs_apollo_enrichment": needs_enrichment,
            "skip_reason": skip_reason,
            "total_contacts": total_contacts
        }
        
        processed_leads.append(lead_record)
        
        # Print lead info
        print(f"\nLead #{i}:")
        print(f"  Client Name: {first_name}")
        print(f"  Client Email: {personal_email}")
        print(f"  Attorney/Firm: {attorney_name}")
        print(f"  Attorney Email: {attorney_email}")
        print(f"  Firm Domain: {firm_domain}")
        print(f"  State: {state_code if state_code else 'N/A'}")
        
        # Show home address field for debugging
        if lead.get('contacts') and len(lead['contacts']) > 0:
            client_contact = lead['contacts'][0]
            home_address = client_contact.get('custom.cf_9jn7jli1kHQD1ori1puDHIehKGtMz3SlA3gWK2NUz0N', '')
            if home_address:
                print(f"  Home Address: {home_address}")
        
        print(f"  Search Strategy: {search_strategy}")
        print(f"  Needs Enrichment: {needs_enrichment}")
        if skip_reason:
            print(f"  Skip Reason: {skip_reason}")
        print(f"  Total Contacts: {len(lead.get('contacts', []))}")
        
        # Print firm name source info AFTER the lead info
        if firm_name_source:
            print(f"    {firm_name_source}")
    
    # Print exclusion summary
    if excluded_leads_count > 0:
        print(f"\n{'='*80}")
        print(f"EXCLUSION SUMMARY:")
        print(f"  Leads excluded (>2 contacts): {excluded_leads_count}")
        print(f"  Leads processed: {len(processed_leads)}")
        print(f"  Total leads analyzed: {excluded_leads_count + len(processed_leads)}")
    
    return processed_leads

if __name__ == "__main__":
    # Test the function
    print("Fetching uncalled leads...")
    leads = get_todays_leads()
    if leads:
        total_available = len(leads.get('data', []))
        print(f"Successfully retrieved {total_available} leads")
        
        # Prompt user for how many leads to process
        print(f"\nHow many leads would you like to process?")
        print(f"Available: {total_available} leads")
        print("Options:")
        print("  'a' or 'all' - Process all leads")
        print("  1-20 - Process specific number of leads")
        
        while True:
            choice = input("Enter choice: ").lower().strip()
            
            if choice in ['a', 'all']:
                limit = None
                print("Processing all leads")
                break
            elif choice.isdigit():
                num = int(choice)
                if 1 <= num <= 20:
                    limit = num
                    print(f"Processing first {num} leads")
                    break
                else:
                    print("Please enter a number between 1-20")
            else:
                print("Please enter 'a', 'all', or a number between 1-20")
        
        # Process leads data with limit
        processed_leads = process_leads_data(leads, limit)
        
        if processed_leads:
            # Save to JSON file
            output_data = {
                "timestamp": leads.get('timestamp', 'unknown'),
                "total_leads": len(processed_leads),
                "leads_needing_enrichment": len([l for l in processed_leads if l['needs_apollo_enrichment']]),
                "leads": processed_leads
            }
            
            try:
                with open('lawyers_of_lead_poor.json', 'w', encoding='utf-8') as f:
                    json.dump(output_data, f, indent=2, ensure_ascii=False)
                
                print(f"\nSaved {len(processed_leads)} leads to lawyers_of_lead_poor.json")
                print(f"Leads needing Apollo enrichment: {output_data['leads_needing_enrichment']}")
                
            except Exception as e:
                print(f"Error saving to JSON: {e}")
        else:
            print("No processed leads data to save")
    else:
        print("Failed to retrieve leads")
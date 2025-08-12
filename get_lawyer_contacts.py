import os
from dotenv import load_dotenv
import requests
import json
from base64 import b64encode

# Load environment variables
load_dotenv()

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
    
    url = 'https://api.close.com/api/v1/data/search/'
    
    headers = {
        'Authorization': f'Basic {encoded_key}',
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    }

    print(f"Fetching {view_name} smart view...")
    
    # Fresh payload for each run - pagination starts at 0
    payload = {
        "query": {
            "type": "saved_search",
            "saved_search_id": view_id
        },
        "_fields": {
            "lead": ["id", "display_name", "status_id", "name", "contacts", "custom"]
        },
        "_limit": 100,
        "_skip": 0  # Always start fresh
    }

    try:
        all_leads = []
        page_count = 0
        seen_lead_ids = set()
        
        while True:
            page_count += 1
            # Make the POST request to Advanced Filtering API
            response = requests.post(url, headers=headers, json=payload)
            print(f"asking for uncalled leads view (page {page_count})")
            response.raise_for_status()  # Raise an error for bad status codes
            
            leads = response.json()
            page_leads = leads.get('data', [])
            
            print(f"Found {len(page_leads)} leads on page {page_count}")
            
            # Debug: Show pagination info
            print(f"API Response keys: {list(leads.keys())}")
            
            # Check for empty page or no new leads
            if not page_leads:
                print("No more pages (empty results)")
                break
            
            # For skip-based pagination, if we get fewer results than requested, we're at the end
            if len(page_leads) < payload['_limit']:
                print(f"Got {len(page_leads)} leads (less than limit {payload['_limit']}) - reached end")
                all_leads.extend(page_leads)
                print(f"Added {len(page_leads)} leads (total: {len(all_leads)})")
                break
            
            # Check for duplicate leads (shouldn't happen with skip-based, but safety check)
            new_leads = []
            duplicates_found = 0
            for lead in page_leads:
                lead_id = lead.get('id')
                if lead_id not in seen_lead_ids:
                    seen_lead_ids.add(lead_id)
                    new_leads.append(lead)
                else:
                    duplicates_found += 1
            
            if duplicates_found > 0:
                print(f"WARNING: Found {duplicates_found} duplicate leads with skip-based pagination")
                
            all_leads.extend(new_leads)
            print(f"Added {len(new_leads)} new leads (total: {len(all_leads)})")
                
            # Continue to next page using skip-based pagination
                
            # Set skip for next page (skip-based pagination)
            payload['_skip'] = page_count * payload['_limit']
            print(f"Setting skip to: {payload['_skip']}")
            
            # Small delay to avoid overwhelming the API
            if page_count > 1:
                print("Waiting 1 second before next page...")
                import time
                time.sleep(1)
        
        print(f"Total leads retrieved: {len(all_leads)} across {page_count} pages")
        
        if len(all_leads) > 0:
            # Return in the same format as before
            final_result = leads.copy()  # Keep metadata from last response
            final_result['data'] = all_leads
            return final_result
        else:
            print("No leads found in uncalled leads view, falling back to all meta leads...")
            
            # Reset pagination for fallback
            payload["query"]["saved_search_id"] = leads_created_by_mattias
            payload["results_limit"] = 100  # Process more leads
            payload["_cursor"] = None  # Reset cursor
            
            print(f"DEBUG: Requesting from smart view: {leads_created_by_mattias}")
            print(f"DEBUG: Request payload: {json.dumps(payload, indent=2)}")
            
            response = requests.post(url, headers=headers, json=payload)
            response.raise_for_status()
            
            leads = response.json()
            print(f"DEBUG: Full API response keys: {list(leads.keys())}")
            print(f"DEBUG: Response: {json.dumps(leads, indent=2)[:500]}...")  # First 500 chars
            
            lead_count = len(leads.get('data', []))
            total_in_view = leads.get('total_results', leads.get('has_more', 'unknown'))
            print(f"Found {lead_count} leads in all meta leads view (showing {lead_count} of {total_in_view} total)")
            return leads
        
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
    
    for i, lead in enumerate(leads, 1):
        # Extract first name and personal email from the first contact (client)
        first_name = 'N/A'
        personal_email = 'N/A'
        attorney_name = 'N/A'
        attorney_email = 'N/A'
        
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
            if law_office != 'N/A' and law_office.strip():
                firm_name = law_office
                print(f"    Using Law Office field: {firm_name}")
            elif attorney_email != 'N/A' and '@' in attorney_email and not extract_domain_from_email(attorney_email) in ['gmail.com', 'yahoo.com', 'outlook.com', 'hotmail.com', 'aol.com']:
                # Derive firm name from business email domain
                domain = extract_domain_from_email(attorney_email)
                firm_name = derive_firm_name_from_domain(domain)
                print(f"    Derived from domain {domain}: {firm_name}")
            elif attorney_name_field != 'N/A' and attorney_name_field.strip():
                firm_name = attorney_name_field
                print(f"    Using Attorney Name field: {firm_name}")
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
        # This means we have no reliable way to validate search results
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
            "search_strategy": search_strategy,
            "needs_apollo_enrichment": needs_enrichment,
            "skip_reason": skip_reason,
            "total_contacts": len(lead.get('contacts', []))
        }
        
        processed_leads.append(lead_record)
        
        # Print lead info
        print(f"\nLead #{i}:")
        print(f"  Client Name: {first_name}")
        print(f"  Client Email: {personal_email}")
        print(f"  Attorney/Firm: {attorney_name}")
        print(f"  Attorney Email: {attorney_email}")
        print(f"  Firm Domain: {firm_domain}")
        print(f"  Search Strategy: {search_strategy}")
        print(f"  Needs Enrichment: {needs_enrichment}")
        if skip_reason:
            print(f"  Skip Reason: {skip_reason}")
        print(f"  Total Contacts: {len(lead.get('contacts', []))}")
    
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
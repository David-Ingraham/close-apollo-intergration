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

    # Set up the request using Advanced Filtering API
    smart_view_id = "save_ebxRoBR5KEXJz0jTSCfn1xyaXMQYBHmskqU6iCOoZd9"
    url = 'https://api.close.com/api/v1/data/search/'
    
    headers = {
        'Authorization': f'Basic {encoded_key}',
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    }

    # Use the Advanced Filtering API with saved search
    # This approach uses the saved search to filter the results
    payload = {
        "query": {
            "type": "saved_search",
            "saved_search_id": smart_view_id
        },
        "_fields": {
            "lead": ["id", "display_name", "status_id", "name", "contacts", "custom"]
        },
        "results_limit": 100
    }

    try:
        # Make the POST request to Advanced Filtering API
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()  # Raise an error for bad status codes
        
        # Parse and return the leads
        leads = response.json()
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

def process_leads_data(leads_data):
    """Extract and process lead information into structured format"""
    if not leads_data or 'data' not in leads_data:
        print("No lead data found")
        return None
    
    leads = leads_data.get('data', [])
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
            attorney_name = client_contact.get('custom.cf_bB8dqX4BWGbISOehyNVVaZhJpfV9OZNOqs5WfYjaRYv', 'N/A')
            attorney_email = client_contact.get('custom.cf_vq0cl2Sj1h0QaSePdnTdf3NyAjx3w4QcgmlhgJrWrZE', 'N/A')
            
            # If attorney name not found, try the law firm name field
            if attorney_name == 'N/A':
                attorney_name = client_contact.get('custom.cf_lQKyH0EhHsNDLZn8KqfFSb0342doHgTNfWdTcfWCljw', 'N/A')
            
            # If attorney name not found in custom fields, check for separate attorney contact
            if attorney_name == 'N/A' and len(lead.get('contacts', [])) > 1:
                for contact in lead['contacts'][1:]:  # Skip first contact (client)
                    contact_title = contact.get('title', '').lower()
                    if 'attorney' in contact_title or 'law' in contact_title or 'firm' in contact_title:
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
        
        # Only skip if we have absolutely no searchable information
        if attorney_name == 'N/A' and not firm_domain:
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
    print("Fetching today's leads...")
    leads = get_todays_leads()
    if leads:
        print(f"Successfully retrieved {len(leads.get('data', []))} leads")
        
        # Process leads data
        processed_leads = process_leads_data(leads)
        
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
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

def print_lead_info(leads_data):
    """Extract and print key information for each lead"""
    if not leads_data or 'data' not in leads_data:
        print("No lead data found")
        return
    
    leads = leads_data.get('data', [])
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
        
        print(f"\nLead #{i}:")
        print(f"  First Name: {first_name}")
        print(f"  Personal Email: {personal_email}")
        print(f"  Attorney Name: {attorney_name}")
        print(f"  Attorney Email: {attorney_email}")

if __name__ == "__main__":
    # Test the function
    print("Fetching today's leads...")
    leads = get_todays_leads()
    if leads:
        print(f"Successfully retrieved {len(leads.get('data', []))} leads")
        print_lead_info(leads)
    else:
        print("Failed to retrieve leads")
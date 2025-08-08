import json
import requests
from base64 import b64encode
import os
from dotenv import load_dotenv

load_dotenv()

def test_close_connection():
    """Simple test of Close API connectivity"""
    
    # Get API key
    api_key = os.getenv('CLOSE_API_KEY')
    if not api_key:
        print("ERROR: CLOSE_API_KEY not found in environment variables")
        return
    
    # Set up auth
    encoded_key = b64encode(f"{api_key}:".encode('utf-8')).decode('utf-8')
    headers = {
        'Authorization': f'Basic {encoded_key}',
        'Content-Type': 'application/json'
    }
    
    # Load a test lead ID from your results
    try:
        with open('apollo_company_results.json', 'r') as f:
            data = json.load(f)
    except FileNotFoundError:
        print("ERROR: apollo_company_results.json not found")
        return
    
    # Get first successful result for testing
    test_lead = None
    for result in data['search_results']:
        if result.get('search_successful'):
            test_lead = result
            break
    
    if not test_lead:
        print("No successful leads found to test with")
        return
    
    lead_id = test_lead['lead_id']
    client_name = test_lead['client_name']
    
    print(f"Testing Close API with lead: {client_name}")
    print(f"Lead ID: {lead_id}")
    
    # Test 1: Get lead details
    print("\n1. Testing lead access...")
    try:
        url = f"https://api.close.com/api/v1/lead/{lead_id}/"
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        lead_data = response.json()
        print(f"   ✓ Successfully accessed lead: {lead_data['name']}")
        print(f"   Status: {lead_data.get('status_label', 'Unknown')}")
        
    except Exception as e:
        print(f"   ✗ Failed to access lead: {e}")
        return
    
    # Test 2: Get existing contacts
    print("\n2. Testing contact listing...")
    try:
        url = f"https://api.close.com/api/v1/contact/?lead_id={lead_id}"
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        contacts_data = response.json()
        existing_contacts = contacts_data.get('data', [])
        print(f"   ✓ Found {len(existing_contacts)} existing contacts")
        
        for contact in existing_contacts[:3]:  # Show first 3
            print(f"     - {contact['name']} ({contact.get('title', 'No title')})")
        
    except Exception as e:
        print(f"   ✗ Failed to list contacts: {e}")
        return
    
    print("\n" + "="*50)
    print("✓ Close CRM API connection test PASSED")
    print("Ready to add lawyer contacts to leads")
    print("="*50)

if __name__ == "__main__":
    test_close_connection()
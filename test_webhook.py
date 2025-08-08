import requests
import os
from dotenv import load_dotenv
import json

load_dotenv()

def test_webhook_server(ngrok_url):
    """Test that our webhook server is working"""
    
    # Test 1: Health check
    print("1. Testing health check...")
    response = requests.get(f"{ngrok_url}/webhook-health")
    print(f"   Status: {response.status_code}")
    print(f"   Response: {response.json()}")
    
    # Test 2: Mock webhook data
    print("\n2. Testing mock webhook...")
    response = requests.post(f"{ngrok_url}/test-webhook")
    print(f"   Status: {response.status_code}")
    print(f"   Response: {response.json()}")
    
    # Test 3: Check received data
    print("\n3. Checking received data...")
    response = requests.get(f"{ngrok_url}/webhook-data")
    data = response.json()
    print(f"   Received {len(data)} webhook calls")
    if data:
        print(f"   Latest: {data[-1]['timestamp']}")

def test_apollo_people_enrichment(webhook_url):
    """Test Apollo people enrichment with webhook"""
    api_key = os.getenv('APOLLO_API_KEY')
    if not api_key:
        print("ERROR: APOLLO_API_KEY not found")
        return
    
    print(f"\n4. Testing Apollo enrichment with webhook: {webhook_url}")
    
    url = "https://api.apollo.io/api/v1/people/match"
    headers = {
        'Content-Type': 'application/json',
        'Cache-Control': 'no-cache',
        'X-Api-Key': api_key
    }
    
    # Use specific person data from your company results to ensure exact match
    payload = {
        "first_name": "Johnny",
        "last_name": "Phillips", 
        "email": "phillips.johnny@gmail.com",
        "organization_name": "Law Office of Johnny Phillips",
        "title": "Trial Attorney",
        "linkedin_url": "http://www.linkedin.com/in/johnny-phillips-8a380976",  # If available
        "reveal_phone_number": True,
        "webhook_url": f"{webhook_url}/apollo-webhook"
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload)
        print(f"   Apollo API Status: {response.status_code}")
        print(f"   Apollo Response: {response.json()}")
        
        if response.status_code == 200:
            print("   ✓ Enrichment request sent to Apollo!")
            print("   → Apollo will lookup Johnny Phillips at Law Office of Johnny Phillips")
            print("   → Matching by: name + email + company + title + LinkedIn")
            print("   → Phone data will be sent to your webhook in 5-30 minutes")
            print("   → Watch your webhook server console for incoming data")
        else:
            print("   ✗ Enrichment request failed")
            
    except Exception as e:
        print(f"   ERROR: {e}")

def search_people_at_organization(org_id, org_name):
    """Search for attorneys/partners at a specific organization"""
    api_key = os.getenv('APOLLO_API_KEY')
    if not api_key:
        raise ValueError("APOLLO_API_KEY not found in environment variables")

    url = "https://api.apollo.io/api/v1/mixed_people/search"
    headers = {
        'Content-Type': 'application/json',
        'Cache-Control': 'no-cache',
        'X-Api-Key': api_key
    }

    # Search for legal professionals at this org
    payload = {
        "organization_ids": [org_id],
        "person_titles": ["attorney", "partner", "lawyer", "counsel", "paralegal", "associate"],
        "email_statuses": ["verified"],
        "page": 1,
        "per_page": 25
    }

    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        result = response.json()
        
        people = result.get("people", [])
        print(f"      Found {len(people)} legal professionals")
        
        # Process each person 
        contacts = []
        for person in people:
            contact = {
                'name': f"{person.get('first_name', '')} {person.get('last_name', '')}".strip(),
                'title': person.get('title'),
                'email': person.get('email'),
                'linkedin_url': person.get('linkedin_url'),
                'phone': None,  # Will be filled by enrichment later
                'organization_id': org_id,
                'person_id': person.get('id')
            }
            contacts.append(contact)
            
        return contacts
        
    except requests.exceptions.RequestException as e:
        print(f"      ERROR: People search failed for '{org_name}': {e}")
        return []

def test_apollo_people_search():
    """Test Apollo people search (no webhook needed)"""
    api_key = os.getenv('APOLLO_API_KEY')
    if not api_key:
        print("ERROR: APOLLO_API_KEY not found")
        return
    
    print(f"\n5. Testing Apollo people search...")
    
    url = "https://api.apollo.io/api/v1/mixed_people/search"
    headers = {
        'Content-Type': 'application/json',
        'Cache-Control': 'no-cache',
        'X-Api-Key': api_key
    }
    
    # Use one of your successful org IDs from apollo_company_results.json
    payload = {
        "organization_ids": ["6710cff081ba560001cf7781"],  # Johnny Phillips law office from your results
        "person_titles": ["attorney", "partner", "lawyer"],
        "email_statuses": ["verified"],
        "page": 1,
        "per_page": 10
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload)
        print(f"   People Search Status: {response.status_code}")
        result = response.json()
        people = result.get("people", [])
        print(f"   Found {len(people)} people")
        
        for person in people[:3]:  # Show first 3
            name = f"{person.get('first_name', '')} {person.get('last_name', '')}".strip()
            title = person.get('title', 'No title')
            email = person.get('email', 'No email')
            print(f"     - {name} ({title}) - {email}")
            
    except Exception as e:
        print(f"   ERROR: {e}")

if __name__ == "__main__":
    # Get ngrok URL from environment
    ngrok_url = os.getenv('NGROK_URL')
    if not ngrok_url:
        print("ERROR: NGROK_URL not found in environment variables")
        print("Please set NGROK_URL in your .env file")
        exit(1)
    
    # Run all tests
    test_webhook_server(ngrok_url)
    test_apollo_people_enrichment(ngrok_url)
    test_apollo_people_search()
    
    print("\n" + "="*60)
    print("Test complete! Check your webhook server logs for any incoming data.")
    print("Apollo phone data may take 5-30 minutes to arrive via webhook.")

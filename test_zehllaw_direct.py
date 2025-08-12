import os
import requests
import json
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def is_law_firm_by_industry(org):
    """Check if organization is a law firm based on Apollo industry/keywords data"""
    if not org:
        return False
    
    # Check industries field (Apollo provides this)
    industries = org.get('industries', [])
    if industries:
        industries_text = ' '.join(str(ind).lower() for ind in industries)
        if any(term in industries_text for term in ['law', 'legal', 'attorney', 'counsel']):
            return True
    
    # Check keywords field (Apollo provides this)  
    keywords = org.get('keywords', [])
    if keywords:
        keywords_text = ' '.join(str(kw).lower() for kw in keywords)
        if any(term in keywords_text for term in ['law', 'legal', 'attorney', 'counsel', 'litigation', 'paralegal']):
            return True
    
    # Check organization name as fallback
    org_name = org.get('name', '')
    legal_hints = {'law','lawyer','lawyers','attorney','attorneys','legal','counsel','llp','law office','law offices'}
    if org_name:
        n = org_name.lower()
        if any(h in n for h in legal_hints):
            return True
    
    return False

def test_zehllaw_direct():
    """Test direct Apollo API call for zehllaw.com"""
    
    apollo_api_key = os.getenv('APOLLO_API_KEY')
    if not apollo_api_key:
        print("ERROR: APOLLO_API_KEY not found in environment")
        return
    
    print("=" * 80)
    print("TESTING DIRECT APOLLO API CALL FOR zehllaw.com")
    print("=" * 80)
    
    # Test 1: Exact domain search
    print("\n1. TESTING EXACT DOMAIN SEARCH")
    print("-" * 40)
    
    url = "https://api.apollo.io/v1/mixed_companies/search"
    headers = {
        'Content-Type': 'application/json',
        'X-Api-Key': apollo_api_key
    }
    
    # Test exact domain search (try all 3 parameter names like apollo_enrich.py does)
    domain_params = [
        {"company_domains": ["zehllaw.com"]},
        {"domains": ["zehllaw.com"]}, 
        {"q_company_domains": ["zehllaw.com"]}
    ]
    
    try:
        response = requests.post(url, headers=headers, json=payload)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            orgs = data.get('organizations', [])
            print(f"Found {len(orgs)} organizations")
            
            if orgs:
                for i, org in enumerate(orgs, 1):
                    print(f"\n--- ORGANIZATION {i} ---")
                    print(f"Name: {org.get('name', 'N/A')}")
                    print(f"Domain: {org.get('primary_domain', 'N/A')}")
                    print(f"Industries: {org.get('industries', [])}")
                    print(f"Keywords: {org.get('keywords', [])}")
                    print(f"LinkedIn: {org.get('linkedin_url', 'N/A')}")
                    
                    # Test our law firm detection
                    is_law_firm = is_law_firm_by_industry(org)
                    print(f"Our Detection: {'✅ LAW FIRM' if is_law_firm else '❌ NOT LAW FIRM'}")
            else:
                print("No organizations found")
        else:
            print(f"Error: {response.status_code}")
            print(f"Response: {response.text}")
            
    except Exception as e:
        print(f"Exception: {e}")
    
    # Test 2: Organization name search  
    print("\n\n2. TESTING ORGANIZATION NAME SEARCH")
    print("-" * 40)
    
    payload = {
        "q_organization_name": "zehllaw",
        "page": 1,
        "per_page": 10
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            orgs = data.get('organizations', [])
            print(f"Found {len(orgs)} organizations")
            
            if orgs:
                for i, org in enumerate(orgs, 1):
                    print(f"\n--- ORGANIZATION {i} ---")
                    print(f"Name: {org.get('name', 'N/A')}")
                    print(f"Domain: {org.get('primary_domain', 'N/A')}")
                    print(f"Industries: {org.get('industries', [])}")
                    print(f"Keywords: {org.get('keywords', [])}")
                    print(f"LinkedIn: {org.get('linkedin_url', 'N/A')}")
                    
                    # Test our law firm detection
                    is_law_firm = is_law_firm_by_industry(org)
                    print(f"Our Detection: {'✅ LAW FIRM' if is_law_firm else '❌ NOT LAW FIRM'}")
            else:
                print("No organizations found")
        else:
            print(f"Error: {response.status_code}")
            print(f"Response: {response.text}")
            
    except Exception as e:
        print(f"Exception: {e}")

    # Test 3: Show what fields are actually available
    print("\n\n3. FULL FIELD ANALYSIS")
    print("-" * 40)
    
    payload = {
        "domains": ["zehllaw.com"],
        "page": 1,
        "per_page": 1
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload)
        if response.status_code == 200:
            data = response.json()
            orgs = data.get('organizations', [])
            if orgs:
                org = orgs[0]
                print("ALL AVAILABLE FIELDS:")
                for key, value in org.items():
                    print(f"  {key}: {value}")
    except Exception as e:
        print(f"Exception: {e}")

if __name__ == "__main__":
    test_zehllaw_direct()

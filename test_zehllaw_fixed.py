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

def test_apollo_api():
    """Test Apollo API exactly like apollo_enrich.py does it"""
    
    apollo_api_key = os.getenv('APOLLO_API_KEY')
    if not apollo_api_key:
        print("ERROR: APOLLO_API_KEY not found in environment")
        return
    
    print("=" * 80)
    print("TESTING APOLLO API EXACTLY LIKE apollo_enrich.py")
    print("=" * 80)
    
    url = "https://api.apollo.io/v1/mixed_companies/search"
    headers = {
        'Content-Type': 'application/json',
        'Cache-Control': 'no-cache',
        'X-Api-Key': apollo_api_key
    }
    
    # Test 1: Name search (what apollo_enrich.py tries first)
    print("\n1. TESTING NAME SEARCH")
    print("-" * 40)
    
    payload = {"q_organization_name": "zehllaw", "page": 1, "per_page": 100}
    
    try:
        response = requests.post(url, headers=headers, json=payload)
        print(f"Parameter: q_organization_name")
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            orgs = data.get('organizations', [])
            print(f"Found {len(orgs)} organizations")
            
            if orgs:
                print("\nFIRST 3 ORGANIZATIONS:")
                for i, org in enumerate(orgs[:3], 1):
                    print(f"\n--- ORGANIZATION {i} ---")
                    print(f"Name: {org.get('name', 'N/A')}")
                    print(f"Domain: {org.get('primary_domain', 'N/A')}")
                    print(f"Industries: {org.get('industries', [])}")
                    print(f"Keywords: {org.get('keywords', [])}")
                    
                    # Test our law firm detection
                    is_law_firm = is_law_firm_by_industry(org)
                    print(f"Our Detection: {'✅ LAW FIRM' if is_law_firm else '❌ NOT LAW FIRM'}")
        else:
            print(f"Error: {response.status_code}")
            print(f"Response: {response.text}")
            
    except Exception as e:
        print(f"Exception: {e}")
    
    # Test 2: Domain searches (what apollo_enrich.py tries for domains)
    print("\n\n2. TESTING DOMAIN SEARCHES")
    print("-" * 40)
    
    # Try all 3 domain parameter formats like apollo_enrich.py does
    domain_params = [
        ("company_domains", {"company_domains": ["zehllaw.com"], "page": 1, "per_page": 100}),
        ("domains", {"domains": ["zehllaw.com"], "page": 1, "per_page": 100}),
        ("q_company_domains", {"q_company_domains": ["zehllaw.com"], "page": 1, "per_page": 100})
    ]
    
    for param_name, payload in domain_params:
        print(f"\nTrying parameter: {param_name}")
        
        try:
            response = requests.post(url, headers=headers, json=payload)
            print(f"Status Code: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                orgs = data.get('organizations', [])
                print(f"Found {len(orgs)} organizations")
                
                if orgs:
                    print("FIRST 3 ORGANIZATIONS:")
                    for i, org in enumerate(orgs[:3], 1):
                        print(f"\n--- ORGANIZATION {i} ---")
                        print(f"Name: {org.get('name', 'N/A')}")
                        print(f"Domain: {org.get('primary_domain', 'N/A')}")
                        print(f"Industries: {org.get('industries', [])}")
                        print(f"Keywords: {org.get('keywords', [])}")
                        
                        # Test our law firm detection
                        is_law_firm = is_law_firm_by_industry(org)
                        print(f"Our Detection: {'✅ LAW FIRM' if is_law_firm else '❌ NOT LAW FIRM'}")
                    
                    # If we found results, continue to see others too
                    print(f"(Showing first 3 of {len(orgs)} total)")
                    break
                else:
                    print("No organizations found")
            else:
                print(f"Error: {response.status_code}")
                print(f"Response: {response.text}")
                
        except Exception as e:
            print(f"Exception: {e}")

    # Test 3: Show raw response for debugging
    print("\n\n3. RAW RESPONSE ANALYSIS")
    print("-" * 40)
    
    # Use the working parameter if we found one
    payload = {"q_organization_name": "zehllaw", "page": 1, "per_page": 1}
    
    try:
        response = requests.post(url, headers=headers, json=payload)
        if response.status_code == 200:
            data = response.json()
            print("FULL API RESPONSE STRUCTURE:")
            print(json.dumps(data, indent=2)[:1000] + "..." if len(str(data)) > 1000 else json.dumps(data, indent=2))
        else:
            print(f"Error: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"Exception: {e}")

if __name__ == "__main__":
    test_apollo_api()

#!/usr/bin/env python3
"""
Test alternative ways to find people at Zehl & Associates
Instead of just using organization_ids
"""

import os
import json
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_alternative_searches(firm_name, domain):
    """Test different ways to find people at a company"""
    print(f"\n{'='*80}")
    print(f"ALTERNATIVE PEOPLE SEARCHES FOR: {firm_name}")
    print(f"Domain: {domain}")
    print(f"{'='*80}")
    
    api_key = os.getenv('APOLLO_API_KEY')
    headers = {
        'Content-Type': 'application/json',
        'Cache-Control': 'no-cache',
        'X-Api-Key': api_key
    }
    
    # Alternative search strategies for people
    search_strategies = [
        {
            "name": "By organization_ids (current method)",
            "payload": {
                "organization_ids": ["67a187902dfbd900012ecd70"],  # Zehl ID
                "page": 1,
                "per_page": 25
            }
        },
        {
            "name": "By organization_name",
            "payload": {
                "organization_names": [firm_name],
                "page": 1,
                "per_page": 25
            }
        },
        {
            "name": "By q_organization_name",
            "payload": {
                "q_organization_name": firm_name,
                "page": 1,
                "per_page": 25
            }
        },
        {
            "name": "By current_employer",
            "payload": {
                "current_employer": firm_name,
                "page": 1,
                "per_page": 25
            }
        },
        {
            "name": "By organization_domains",
            "payload": {
                "organization_domains": [domain],
                "page": 1,
                "per_page": 25
            }
        },
        {
            "name": "By email_domains",
            "payload": {
                "email_domains": [domain],
                "page": 1,
                "per_page": 25
            }
        },
        {
            "name": "By partial organization name",
            "payload": {
                "q_organization_name": "Zehl",
                "page": 1,
                "per_page": 25
            }
        },
        {
            "name": "By keywords + domain",
            "payload": {
                "q_keywords": "attorney law injury",
                "organization_domains": [domain],
                "page": 1,
                "per_page": 25
            }
        }
    ]
    
    for strategy in search_strategies:
        print(f"\n--- {strategy['name']} ---")
        print(f"Payload: {json.dumps(strategy['payload'], indent=2)}")
        
        try:
            response = requests.post(
                "https://api.apollo.io/api/v1/mixed_people/search",
                headers=headers,
                json=strategy['payload']
            )
            
            print(f"Status Code: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                total_entries = data.get("pagination", {}).get("total_entries", 0)
                people = data.get("people", [])
                
                print(f"Total Entries: {total_entries}")
                print(f"People Found: {len(people)}")
                
                if people:
                    print("Sample people:")
                    for i, person in enumerate(people[:5], 1):
                        name = f"{person.get('first_name', '')} {person.get('last_name', '')}".strip()
                        title = person.get('title', 'No title')
                        company = person.get('organization', {}).get('name', 'No company')
                        print(f"  {i}. {name} - {title} @ {company}")
                else:
                    print("No people found")
                    
            elif response.status_code == 400:
                print(f"Bad Request - Invalid parameter: {response.text}")
            else:
                print(f"Error: {response.text}")
                
        except Exception as e:
            print(f"Exception: {e}")

def main():
    """Test alternative people search methods"""
    
    print("TESTING ALTERNATIVE PEOPLE SEARCH METHODS")
    print("Trying to find Zehl employees using different API parameters")
    
    # Test with Zehl first
    test_alternative_searches("Zehl & Associates Injury & Accident Lawyers", "zehllaw.com")
    
    # Also test with John Foy
    print(f"\n{'='*100}")
    test_alternative_searches("John Foy & Associates", "johnfoy.com")

if __name__ == "__main__":
    main()

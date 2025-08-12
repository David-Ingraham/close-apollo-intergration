#!/usr/bin/env python3
"""
Test if this is a pattern with law firms in general
"""

import os
import json
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_random_law_firms():
    """Test some random law firms to see if this is a pattern"""
    print("TESTING RANDOM LAW FIRMS")
    print("Looking for pattern in people data availability")
    
    api_key = os.getenv('APOLLO_API_KEY')
    headers = {
        'Content-Type': 'application/json',
        'Cache-Control': 'no-cache',
        'X-Api-Key': api_key
    }
    
    # Search for law firms
    search_payload = {
        "q_organization_name": "law firm",
        "page": 1,
        "per_page": 20
    }
    
    try:
        response = requests.post(
            "https://api.apollo.io/v1/mixed_companies/search",
            headers=headers,
            json=search_payload
        )
        
        if response.status_code == 200:
            data = response.json()
            orgs = data.get("organizations", []) or data.get("accounts", [])
            
            print(f"Found {len(orgs)} organizations with 'law firm' in name:")
            
            for i, org in enumerate(orgs[:10], 1):
                name = org.get('name', 'No name')
                org_id = org.get('id', 'No ID')
                domain = org.get('primary_domain', org.get('website_url', 'No domain'))
                
                print(f"\n{i}. {name}")
                print(f"   ID: {org_id}")
                print(f"   Domain: {domain}")
                
                # Test people search
                people_payload = {
                    "organization_ids": [org_id],
                    "page": 1,
                    "per_page": 5
                }
                
                try:
                    people_response = requests.post(
                        "https://api.apollo.io/api/v1/mixed_people/search",
                        headers=headers,
                        json=people_payload
                    )
                    
                    if people_response.status_code == 200:
                        people_data = people_response.json()
                        total_entries = people_data.get("pagination", {}).get("total_entries", 0)
                        
                        if total_entries > 0:
                            print(f"   ✅ HAS PEOPLE: {total_entries} total")
                            people = people_data.get("people", [])
                            for person in people[:2]:
                                person_name = f"{person.get('first_name', '')} {person.get('last_name', '')}".strip()
                                title = person.get('title', 'No title')
                                print(f"     - {person_name} ({title})")
                        else:
                            print(f"   ❌ NO PEOPLE: 0 total")
                    else:
                        print(f"   Error: {people_response.status_code}")
                        
                except Exception as e:
                    print(f"   Exception: {e}")
                    
        else:
            print(f"Error: {response.status_code} - {response.text}")
            
    except Exception as e:
        print(f"Exception: {e}")

def main():
    test_random_law_firms()

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Compare working vs non-working firms to find the difference
"""

import os
import json
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def compare_firm_details(org_id, org_name, expected_result):
    """Get detailed info about an organization and its people search"""
    print(f"\n{'='*80}")
    print(f"ANALYZING: {org_name} ({expected_result})")
    print(f"Organization ID: {org_id}")
    print(f"{'='*80}")
    
    api_key = os.getenv('APOLLO_API_KEY')
    headers = {
        'Content-Type': 'application/json',
        'Cache-Control': 'no-cache',
        'X-Api-Key': api_key
    }
    
    # Step 1: Get organization details
    print("\n--- ORGANIZATION DETAILS ---")
    org_payload = {
        "q_organization_name": org_name.split()[0],  # Search by first word
        "page": 1,
        "per_page": 10
    }
    
    try:
        org_response = requests.post(
            "https://api.apollo.io/v1/mixed_companies/search",
            headers=headers,
            json=org_payload
        )
        
        if org_response.status_code == 200:
            org_data = org_response.json()
            orgs = org_data.get("organizations", []) or org_data.get("accounts", [])
            
            print(f"Found {len(orgs)} organizations matching '{org_name.split()[0]}':")
            for i, org in enumerate(orgs[:5], 1):
                name = org.get('name', 'No name')
                found_id = org.get('id', 'No ID')
                domain = org.get('primary_domain', org.get('website_url', 'No domain'))
                employees = org.get('estimated_num_employees', 'Unknown')
                match_indicator = "👈 THIS ONE" if found_id == org_id else ""
                print(f"  {i}. {name}")
                print(f"     ID: {found_id} {match_indicator}")
                print(f"     Domain: {domain}")
                print(f"     Estimated Employees: {employees}")
                print()
        
    except Exception as e:
        print(f"Error getting org details: {e}")
    
    # Step 2: Test people search with the specific org ID
    print(f"--- PEOPLE SEARCH FOR ORG ID: {org_id} ---")
    people_payload = {
        "organization_ids": [org_id],
        "page": 1,
        "per_page": 25
    }
    
    try:
        people_response = requests.post(
            "https://api.apollo.io/api/v1/mixed_people/search",
            headers=headers,
            json=people_payload
        )
        
        print(f"Status Code: {people_response.status_code}")
        
        if people_response.status_code == 200:
            people_data = people_response.json()
            people = people_data.get("people", [])
            total_entries = people_data.get("pagination", {}).get("total_entries", 0)
            
            print(f"Total Entries: {total_entries}")
            print(f"People in Response: {len(people)}")
            
            if people:
                print("Found people:")
                for i, person in enumerate(people[:5], 1):
                    name = f"{person.get('first_name', '')} {person.get('last_name', '')}".strip()
                    title = person.get('title', 'No title')
                    print(f"  {i}. {name} - {title}")
            else:
                print("NO PEOPLE FOUND")
                print("Full response:")
                print(json.dumps(people_data, indent=2))
        else:
            print(f"Error: {people_response.text}")
            
    except Exception as e:
        print(f"Error in people search: {e}")

def main():
    """Compare working vs broken firms"""
    
    print("COMPARING WORKING vs BROKEN FIRMS")
    print("Looking for differences in API responses")
    
    test_cases = [
        # WORKING - returns people
        {
            "org_name": "Cellino Law",
            "org_id": "60b2fd658d4dd10001229633",
            "expected": "WORKING - should find people"
        },
        
        # NOT WORKING - returns 0 people  
        {
            "org_name": "Zehl & Associates Injury & Accident Lawyers",
            "org_id": "67a187902dfbd900012ecd70", 
            "expected": "BROKEN - returns 0 people"
        },
        
        # Another working one for comparison
        {
            "org_name": "Scott Baron & Associates",
            "org_id": "5ed7c4bbf699060001bc7f39",
            "expected": "WORKING - should find people"
        },
        
        # Another broken one
        {
            "org_name": "John Foy & Associates", 
            "org_id": "678eea447a153701b10f5ef1",
            "expected": "BROKEN - returns 0 people"
        }
    ]
    
    for case in test_cases:
        compare_firm_details(case["org_id"], case["org_name"], case["expected"])

if __name__ == "__main__":
    main()

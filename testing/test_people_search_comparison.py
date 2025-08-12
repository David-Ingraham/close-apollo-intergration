#!/usr/bin/env python3
"""
Test script to compare people search API calls for different firms
Compare why some firms return contacts and others don't
"""

import os
import json
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_people_search(org_id, org_name, description):
    """Test people search for a specific organization"""
    print(f"\n{'='*60}")
    print(f"Testing: {description}")
    print(f"Organization: {org_name} (ID: {org_id})")
    print(f"{'='*60}")
    
    api_key = os.getenv('APOLLO_API_KEY')
    if not api_key:
        print("ERROR: APOLLO_API_KEY not found")
        return
    
    headers = {
        'Content-Type': 'application/json',
        'Cache-Control': 'no-cache',
        'X-Api-Key': api_key
    }
    
    # Test different payload configurations
    test_configs = [
        {
            "name": "Current apollo_enrich.py config",
            "payload": {
                "organization_ids": [org_id],
                "page": 1,
                "per_page": 25
            }
        },
        {
            "name": "With person_titles filter",
            "payload": {
                "organization_ids": [org_id],
                "person_titles": ["Partner", "Attorney", "Lawyer", "Counsel", "Legal", "Paralegal"],
                "page": 1,
                "per_page": 25
            }
        },
        {
            "name": "Higher per_page limit",
            "payload": {
                "organization_ids": [org_id],
                "page": 1,
                "per_page": 100
            }
        }
    ]
    
    for config in test_configs:
        print(f"\n--- {config['name']} ---")
        print(f"Payload: {json.dumps(config['payload'], indent=2)}")
        
        try:
            response = requests.post(
                "https://api.apollo.io/api/v1/mixed_people/search",
                headers=headers,
                json=config['payload']
            )
            
            print(f"Status Code: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                
                # Print raw response for debugging
                print(f"RAW RESPONSE:")
                print(json.dumps(data, indent=2))
                print("-" * 40)
                
                people = data.get("people", [])
                print(f"Total People Found: {len(people)}")
                
                if people:
                    print("Sample contacts:")
                    for i, person in enumerate(people[:5], 1):
                        name = f"{person.get('first_name', '')} {person.get('last_name', '')}".strip()
                        title = person.get('title', 'No title')
                        print(f"  {i}. {name} - {title}")
                else:
                    print("  No people found")
                    
                # Check for other fields that might contain people data
                print(f"Other fields in response: {list(data.keys())}")
                for key in data.keys():
                    if key != 'people' and isinstance(data[key], list) and len(data[key]) > 0:
                        print(f"  {key}: {len(data[key])} items")
            else:
                print(f"Error: {response.text}")
                
        except Exception as e:
            print(f"Exception: {e}")

def main():
    """Test people search for firms that work vs don't work"""
    
    print("PEOPLE SEARCH COMPARISON TEST")
    print("Comparing firms that return contacts vs those that don't")
    
    # Organizations found from Step 1
    test_cases = [
        # WORKING firms (return contacts in apollo_enrich.py)
        {
            "description": "WORKING - Cellino Law",
            "org_name": "Cellino Law", 
            "org_id": "60b2fd658d4dd10001229633"
        },
        {
            "description": "WORKING - Scott Baron Associates",
            "org_name": "Scott Baron & Associates",
            "org_id": "5ed7c4bbf699060001bc7f39"
        },
        
        # NOT WORKING firms (0 contacts despite having employees)
        {
            "description": "NOT WORKING - Zehl & Associates", 
            "org_name": "Zehl & Associates Injury & Accident Lawyers",
            "org_id": "67a187902dfbd900012ecd70"
        },
        {
            "description": "NOT WORKING - John Foy & Associates",
            "org_name": "John Foy & Associates",
            "org_id": "678eea447a153701b10f5ef1"
        }
    ]
    
    print("\nStep 2: Testing People Search for Each Organization...")
    
    for case in test_cases:
        test_people_search(case["org_id"], case["org_name"], case["description"])

if __name__ == "__main__":
    main()

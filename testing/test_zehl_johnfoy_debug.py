#!/usr/bin/env python3
"""
Debug script to see raw API responses for Zehl and John Foy people searches
"""

import os
import json
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def debug_people_search(org_id, org_name):
    """Debug people search with raw response"""
    print(f"\n{'='*60}")
    print(f"DEBUGGING: {org_name}")
    print(f"Organization ID: {org_id}")
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
    
    # Test the exact payload our apollo_enrich.py uses
    payload = {
        "organization_ids": [org_id],
        "page": 1,
        "per_page": 25
    }
    
    print(f"Payload: {json.dumps(payload, indent=2)}")
    
    try:
        response = requests.post(
            "https://api.apollo.io/api/v1/mixed_people/search",
            headers=headers,
            json=payload
        )
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            
            print(f"\nRAW RESPONSE:")
            print(json.dumps(data, indent=2))
            
        else:
            print(f"Error Response: {response.text}")
            
    except Exception as e:
        print(f"Exception: {e}")

def main():
    """Debug the failing cases"""
    
    print("RAW RESPONSE DEBUG - FAILING CASES")
    print("Looking at Zehl and John Foy to see why they return 0 people")
    
    # Cases that return 0 people despite having employees on dashboard
    failing_cases = [
        {
            "org_name": "Zehl & Associates Injury & Accident Lawyers",
            "org_id": "67a187902dfbd900012ecd70"
        },
        {
            "org_name": "John Foy & Associates",
            "org_id": "678eea447a153701b10f5ef1"
        }
    ]
    
    for case in failing_cases:
        debug_people_search(case["org_id"], case["org_name"])

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Test script for the specific case that was failing: Precious Makai
"""

import os
import requests
import json
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_precious_makai():
    """Test enrichment for Precious Makai specifically"""
    api_key = os.getenv('APOLLO_API_KEY')
    if not api_key:
        print("ERROR: APOLLO_API_KEY not found in environment variables")
        return

    url = "https://api.apollo.io/api/v1/people/match"
    headers = {
        'Content-Type': 'application/json',
        'Cache-Control': 'no-cache',
        'X-Api-Key': api_key
    }

    # Test the exact case that was failing
    print("=== Testing Precious Makai Enrichment ===")
    payload = {
        "reveal_personal_emails": True,
        "first_name": "Precious",
        "last_name": "Makai",
        "organization_name": "Some Law Firm",  # We don't know the exact firm
        "title": "Candidate Attorney"
    }
    
    print(f"Request payload: {json.dumps(payload, indent=2)}")
    
    try:
        response = requests.post(url, headers=headers, json=payload)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"Success! Response: {json.dumps(result, indent=2)}")
            
            # Check if we got enriched data
            if result.get('person'):
                person = result['person']
                print(f"\nEnriched Person Data:")
                print(f"  Name: {person.get('name')}")
                print(f"  Email: {person.get('email')}")
                print(f"  Organization: {person.get('employment_history', [{}])[0].get('organization_name') if person.get('employment_history') else 'Unknown'}")
                print(f"  LinkedIn: {person.get('linkedin_url')}")
            else:
                print("No person data returned")
        else:
            print(f"Error Response: {response.text}")
            
    except Exception as e:
        print(f"Exception: {e}")
        if hasattr(e, 'response'):
            print(f"Response text: {e.response.text}")

    print("\n" + "="*50 + "\n")

    # Test without title to see if that's causing issues
    print("=== Testing without title ===")
    payload2 = {
        "reveal_personal_emails": True,
        "first_name": "Precious",
        "last_name": "Makai"
    }
    
    print(f"Request payload: {json.dumps(payload2, indent=2)}")
    
    try:
        response = requests.post(url, headers=headers, json=payload2)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
    except Exception as e:
        print(f"Error: {e}")
        if hasattr(e, 'response'):
            print(f"Response text: {e.response.text}")

if __name__ == "__main__":
    test_precious_makai()
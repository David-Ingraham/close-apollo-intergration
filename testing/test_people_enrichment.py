#!/usr/bin/env python3
"""
Test script for Apollo People Enrichment API
Helps us understand the correct request format and parameters
"""

import os
import requests
import json
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_people_enrichment():
    """Test the People Enrichment API with different parameter combinations"""
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

    # Test 1: Minimal required parameters
    print("=== TEST 1: Minimal Parameters ===")
    payload1 = {
        "first_name": "John",
        "last_name": "Smith",
        "organization_name": "Microsoft"
    }
    
    print(f"Request payload: {json.dumps(payload1, indent=2)}")
    
    try:
        response = requests.post(url, headers=headers, json=payload1)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
    except Exception as e:
        print(f"Error: {e}")
        if hasattr(e, 'response'):
            print(f"Response text: {e.response.text}")
    
    print("\n" + "="*50 + "\n")

    # Test 2: With reveal parameters
    print("=== TEST 2: With Reveal Parameters ===")
    payload2 = {
        "first_name": "John",
        "last_name": "Smith", 
        "organization_name": "Microsoft",
        "reveal_personal_emails": True,
        "reveal_phone_number": True
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
    
    print("\n" + "="*50 + "\n")

    # Test 3: Different parameter format (maybe they expect different field names)
    print("=== TEST 3: Alternative Parameter Names ===")
    payload3 = {
        "name": "John Smith",
        "company": "Microsoft"
    }
    
    print(f"Request payload: {json.dumps(payload3, indent=2)}")
    
    try:
        response = requests.post(url, headers=headers, json=payload3)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
    except Exception as e:
        print(f"Error: {e}")
        if hasattr(e, 'response'):
            print(f"Response text: {e.response.text}")

    print("\n" + "="*50 + "\n")

    # Test 4: Check if we need different endpoint or method
    print("=== TEST 4: Check API Documentation Format ===")
    
    # Sometimes APIs expect different structures
    payload4 = {
        "person": {
            "first_name": "John",
            "last_name": "Smith",
            "organization_name": "Microsoft"
        },
        "reveal_personal_emails": True,
        "reveal_phone_number": True
    }
    
    print(f"Request payload: {json.dumps(payload4, indent=2)}")
    
    try:
        response = requests.post(url, headers=headers, json=payload4)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
    except Exception as e:
        print(f"Error: {e}")
        if hasattr(e, 'response'):
            print(f"Response text: {e.response.text}")

if __name__ == "__main__":
    test_people_enrichment()
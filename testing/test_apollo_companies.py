#!/usr/bin/env python3
"""
Simple Apollo Company Search Test Script
Tests the Apollo mixed_companies/search API to debug why dashboard results differ from API results
"""

import os
import requests
import json
from dotenv import load_dotenv

load_dotenv()

def test_apollo_company_search():
    """Test Apollo company search with the exact query that works in dashboard"""
    
    # Get API key
    api_key = os.getenv('APOLLO_API_KEY')
    if not api_key:
        print("ERROR: APOLLO_API_KEY not found in environment variables")
        return
    
    # Test query that should return results
    test_query = "lauferlawgroup"
    
    print("=" * 60)
    print("APOLLO COMPANY SEARCH TEST")
    print("=" * 60)
    print(f"Testing query: '{test_query}'")
    print(f"API Key: {api_key[:10]}...{api_key[-4:]}")
    
    # Apollo API endpoint
    url = "https://api.apollo.io/v1/mixed_companies/search"
    
    headers = {
        'Content-Type': 'application/json',
        'Cache-Control': 'no-cache',
        'X-Api-Key': api_key
    }
    
    # Test multiple payload variations
    test_payloads = [
        {
            "name": "Basic name search",
            "payload": {
                "q_organization_name": test_query,
                "page": 1,
                "per_page": 25
            }
        },
        {
            "name": "Keywords search",
            "payload": {
                "q_keywords": test_query,
                "page": 1,
                "per_page": 25
            }
        },
        {
            "name": "Organization name with exact match",
            "payload": {
                "q_organization_name": f'"{test_query}"',
                "page": 1,
                "per_page": 25
            }
        },
        {
            "name": "Domain search (if applicable)",
            "payload": {
                "organization_domains": [f"{test_query}.com"],
                "page": 1,
                "per_page": 25
            }
        },
        {
            "name": "Mixed search with organization industries",
            "payload": {
                "q_organization_name": test_query,
                "organization_industry_tag_ids": ["5567cd4e7369644a52060000"],  # Legal Services
                "page": 1,
                "per_page": 25
            }
        }
    ]
    
    for test in test_payloads:
        print("\n" + "-" * 50)
        print(f"TEST: {test['name']}")
        print("-" * 50)
        print(f"Payload: {json.dumps(test['payload'], indent=2)}")
        
        try:
            response = requests.post(url, headers=headers, json=test['payload'])
            print(f"Status Code: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                organizations = data.get('organizations', [])
                print(f"Organizations found: {len(organizations)}")
                
                if organizations:
                    print("\nFIRST 3 RESULTS:")
                    for i, org in enumerate(organizations[:3], 1):
                        print(f"  {i}. {org.get('name', 'No name')}")
                        print(f"     Domain: {org.get('primary_domain', 'No domain')}")
                        print(f"     Website: {org.get('website_url', 'No website')}")
                        print(f"     Industry: {org.get('industry', 'No industry')}")
                        print()
                else:
                    print("No organizations found!")
                    
                # Show pagination info
                print(f"Pagination info:")
                print(f"  Current page: {data.get('page', 'Unknown')}")
                print(f"  Per page: {data.get('per_page', 'Unknown')}")
                print(f"  Total entries: {data.get('total_entries', 'Unknown')}")
                print(f"  Total pages: {data.get('total_pages', 'Unknown')}")
                
            else:
                print(f"ERROR: {response.status_code}")
                try:
                    error_data = response.json()
                    print(f"Error details: {json.dumps(error_data, indent=2)}")
                except:
                    print(f"Error text: {response.text}")
                    
        except Exception as e:
            print(f"REQUEST FAILED: {e}")
    
    print("\n" + "=" * 60)
    print("TEST COMPLETE")
    print("=" * 60)
    print("\nIf you see different results here vs Apollo dashboard:")
    print("1. Check if dashboard uses different search parameters")
    print("2. Verify API key has same permissions as dashboard login")
    print("3. Dashboard might use different endpoints or filters")
    print("4. Check for rate limiting or quota issues")

if __name__ == "__main__":
    test_apollo_company_search()

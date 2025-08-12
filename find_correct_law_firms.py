#!/usr/bin/env python3
"""
Search specifically for the law firms with exact names and domains
"""

import os
import json
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def search_law_firm_specifically(firm_name, domain):
    """Search for law firm using exact name and domain"""
    print(f"\n{'='*80}")
    print(f"SEARCHING FOR: {firm_name}")
    print(f"Expected Domain: {domain}")
    print(f"{'='*80}")
    
    api_key = os.getenv('APOLLO_API_KEY')
    headers = {
        'Content-Type': 'application/json',
        'Cache-Control': 'no-cache',
        'X-Api-Key': api_key
    }
    
    # Try multiple search strategies
    search_strategies = [
        {
            "name": "Exact firm name",
            "payload": {"q_organization_name": firm_name}
        },
        {
            "name": "Domain search", 
            "payload": {"company_domains": [domain]}
        },
        {
            "name": "Partial name search",
            "payload": {"q_organization_name": firm_name.split()[0]}
        },
        {
            "name": "Name + domain",
            "payload": {
                "q_organization_name": firm_name,
                "company_domains": [domain]
            }
        }
    ]
    
    for strategy in search_strategies:
        print(f"\n--- {strategy['name']} ---")
        print(f"Payload: {json.dumps(strategy['payload'], indent=2)}")
        
        try:
            response = requests.post(
                "https://api.apollo.io/v1/mixed_companies/search",
                headers=headers,
                json={**strategy['payload'], "page": 1, "per_page": 10}
            )
            
            if response.status_code == 200:
                data = response.json()
                orgs = data.get("organizations", []) or data.get("accounts", [])
                
                print(f"Found {len(orgs)} organizations:")
                for i, org in enumerate(orgs[:5], 1):
                    name = org.get('name', 'No name')
                    org_id = org.get('id', 'No ID')
                    org_domain = org.get('primary_domain', org.get('website_url', 'No domain'))
                    employees = org.get('estimated_num_employees', 'Unknown')
                    
                    # Check if this looks like our target
                    domain_match = org_domain == domain if org_domain else False
                    name_similarity = firm_name.lower() in name.lower() or name.lower() in firm_name.lower()
                    
                    indicators = []
                    if domain_match:
                        indicators.append("🎯 DOMAIN MATCH")
                    if name_similarity:
                        indicators.append("📝 NAME SIMILAR")
                    
                    indicator_str = " ".join(indicators) if indicators else ""
                    
                    print(f"  {i}. {name} {indicator_str}")
                    print(f"     ID: {org_id}")
                    print(f"     Domain: {org_domain}")
                    print(f"     Employees: {employees}")
                    
                    # Test people search for promising candidates
                    if domain_match or (name_similarity and 'law' in name.lower()):
                        print(f"     Testing people search...")
                        test_people_search(org_id, name)
                    print()
            else:
                print(f"Error: {response.status_code} - {response.text}")
                
        except Exception as e:
            print(f"Exception: {e}")

def test_people_search(org_id, org_name):
    """Quick test of people search for an org"""
    api_key = os.getenv('APOLLO_API_KEY')
    headers = {
        'Content-Type': 'application/json',
        'Cache-Control': 'no-cache',
        'X-Api-Key': api_key
    }
    
    payload = {
        "organization_ids": [org_id],
        "page": 1,
        "per_page": 5
    }
    
    try:
        response = requests.post(
            "https://api.apollo.io/api/v1/mixed_people/search",
            headers=headers,
            json=payload
        )
        
        if response.status_code == 200:
            data = response.json()
            total_entries = data.get("pagination", {}).get("total_entries", 0)
            people = data.get("people", [])
            
            if total_entries > 0:
                print(f"     🎉 FOUND {total_entries} PEOPLE!")
                for person in people[:3]:
                    name = f"{person.get('first_name', '')} {person.get('last_name', '')}".strip()
                    title = person.get('title', 'No title')
                    print(f"       - {name} ({title})")
            else:
                print(f"     ❌ 0 people found")
        else:
            print(f"     Error: {response.status_code}")
            
    except Exception as e:
        print(f"     Exception: {e}")

def main():
    """Search for the correct law firm organizations"""
    
    print("FINDING CORRECT LAW FIRM ORGANIZATION IDS")
    print("Testing multiple search strategies")
    
    law_firms = [
        {
            "name": "Zehl & Associates Injury & Accident Lawyers",
            "domain": "zehllaw.com"
        },
        {
            "name": "John Foy & Associates", 
            "domain": "johnfoy.com"
        }
    ]
    
    for firm in law_firms:
        search_law_firm_specifically(firm["name"], firm["domain"])

if __name__ == "__main__":
    main()

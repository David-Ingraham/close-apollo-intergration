#!/usr/bin/env python3
"""
Simple test: Collect 3 pages from All Meta Leads and deduplicate
to see if we get ~443 unique leads from 600 total
"""

import requests
import json
import base64

def load_env():
    env_vars = {}
    try:
        with open('.env', 'r') as f:
            for line in f:
                if '=' in line and not line.strip().startswith('#'):
                    key, value = line.strip().split('=', 1)
                    env_vars[key] = value.strip().strip('"\'')
    except FileNotFoundError:
        print("ERROR: .env file not found")
        return None
    return env_vars

def main():
    env_vars = load_env()
    if not env_vars:
        return
    
    api_key = env_vars.get('CLOSE_API_KEY')
    if not api_key:
        print("ERROR: CLOSE_API_KEY not found")
        return
    
    encoded_key = base64.b64encode(f"{api_key}:".encode()).decode()
    headers = {
        'Authorization': f'Basic {encoded_key}',
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    }
    
    url = "https://api.close.com/api/v1/data/search/"
    view_id = 'save_TOTstqdumHKQcNUaztinosJBnRDPYd7IAMhU2SuKyVH'
    
    payload = {
        "query": {"type": "saved_search", "saved_search_id": view_id},
        "_fields": {"lead": ["id", "display_name"]},
        "_limit": 200
    }
    
    all_leads = []
    unique_ids = set()
    cursor = None
    
    print("Testing deduplication theory - collecting 3 pages...")
    
    for page in range(1, 4):  # Pages 1, 2, 3
        if cursor:
            payload["_cursor"] = cursor
        elif "_cursor" in payload:
            del payload["_cursor"]
        
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            if response.status_code != 200:
                print(f"Page {page} ERROR: {response.status_code}")
                break
            
            data = response.json()
            leads = data.get('data', [])
            cursor = data.get('cursor')
            
            new_unique = 0
            for lead in leads:
                lead_id = lead.get('id')
                if lead_id not in unique_ids:
                    unique_ids.add(lead_id)
                    new_unique += 1
                all_leads.append(lead)
            
            print(f"Page {page}: {len(leads)} leads, {new_unique} new unique, {len(unique_ids)} total unique")
            
            if len(leads) == 0:
                break
                
        except Exception as e:
            print(f"Page {page} ERROR: {e}")
            break
    
    print(f"\nRESULTS:")
    print(f"Total leads collected: {len(all_leads)}")
    print(f"Unique leads: {len(unique_ids)}")
    print(f"Expected: 443")
    print(f"Duplicates: {len(all_leads) - len(unique_ids)}")
    
    if len(unique_ids) == 443:
        print("SUCCESS: Deduplication gives exact expected count!")
    elif abs(len(unique_ids) - 443) <= 10:
        print("CLOSE: Within 10 leads of expected count")
    else:
        print("DIFFERENT: Unique count significantly different from expected")

if __name__ == "__main__":
    main()

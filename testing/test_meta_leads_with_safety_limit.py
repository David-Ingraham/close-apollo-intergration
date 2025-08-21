#!/usr/bin/env python3
"""
Test script to collect ALL leads from "All Meta Leads" smart view
using a simple safety limit approach (443 leads expected)
"""

import requests
import json
import base64
import time

def load_env():
    """Load environment variables from .env file"""
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

def get_close_headers(api_key: str):
    """Generate Close CRM API headers"""
    encoded_key = base64.b64encode(f"{api_key}:".encode()).decode()
    return {
        'Authorization': f'Basic {encoded_key}',
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    }

def collect_meta_leads_with_safety_limit(api_key: str):
    """Collect All Meta Leads with safety limit to prevent infinite loops"""
    
    # Smart view configuration
    view_id = 'save_TOTstqdumHKQcNUaztinosJBnRDPYd7IAMhU2SuKyVH'
    view_name = 'All Meta Leads'
    all_meta_leads_count = 443  # Expected count - our safety limit
    
    print(f"Collecting leads from: {view_name}")
    print(f"Expected count: {all_meta_leads_count}")
    print(f"Safety limit: {all_meta_leads_count} (will stop if exceeded)")
    print("="*60)
    
    url = "https://api.close.com/api/v1/data/search/"
    headers = get_close_headers(api_key)
    
    payload = {
        "query": {
            "type": "saved_search",
            "saved_search_id": view_id
        },
        "_fields": {
            "lead": ["id", "display_name", "status_id", "name", "contacts", "custom"]
        },
        "_limit": 200
    }
    
    all_leads = []
    page_count = 0
    cursor = None
    
    # Retry configuration
    max_retries = 3
    retry_delay = 2
    
    while True:
        page_count += 1
        
        # Safety limit check
        if len(all_leads) >= all_meta_leads_count:
            print(f"\nSAFETY LIMIT REACHED: {len(all_leads)} >= {all_meta_leads_count}")
            print("Stopping to prevent infinite loop")
            break
        
        if cursor:
            payload["_cursor"] = cursor
        elif "_cursor" in payload:
            del payload["_cursor"]
        
        print(f"\nPage {page_count}:")
        print(f"  Cursor: {cursor[:50] + '...' if cursor else 'None'}")
        print(f"  Leads collected so far: {len(all_leads)}")
        print(f"  Progress: {len(all_leads)}/{all_meta_leads_count} ({len(all_leads)/all_meta_leads_count*100:.1f}%)")
        
        # Retry logic for network issues
        success = False
        for attempt in range(max_retries):
            try:
                if attempt > 0:
                    print(f"  Retry attempt {attempt + 1}/{max_retries}")
                    time.sleep(retry_delay * attempt)
                
                response = requests.post(url, headers=headers, json=payload, timeout=45)
                
                if response.status_code != 200:
                    print(f"  ERROR: {response.status_code} - {response.text}")
                    break
                
                success = True
                break
                
            except requests.exceptions.Timeout:
                print(f"  TIMEOUT on attempt {attempt + 1}/{max_retries}")
                if attempt == max_retries - 1:
                    print(f"  FAILED: All {max_retries} attempts timed out")
                    return all_leads
            except Exception as e:
                print(f"  ERROR on attempt {attempt + 1}/{max_retries}: {e}")
                if attempt == max_retries - 1:
                    print(f"  FAILED: All {max_retries} attempts failed")
                    return all_leads
        
        if not success:
            print(f"  FAILED: Could not get page {page_count}")
            break
        
        # Process successful response
        data = response.json()
        leads = data.get('data', [])
        new_cursor = data.get('cursor')
        
        print(f"  API returned: {len(leads)} leads")
        print(f"  Response keys: {list(data.keys())}")
        
        # Show sample leads
        if leads and page_count <= 3:  # Show samples for first 3 pages
            print(f"  Sample leads:")
            for i, lead in enumerate(leads[:2]):
                lead_name = lead.get('display_name', lead.get('name', 'No name'))
                custom_fields = lead.get('custom', {})
                attorney_name = custom_fields.get('Attorney Name', 'N/A')
                attorney_email = custom_fields.get('Attorney Email', 'N/A')
                print(f"    {i+1}. {lead_name} | Attorney: {attorney_name} | Email: {attorney_email}")
        
        # Check stopping conditions
        if len(leads) == 0:
            print(f"  STOP: No more leads returned")
            break
        
        if new_cursor is None:
            print(f"  STOP: Cursor is None")
            break
        
        if cursor == new_cursor:
            print(f"  STOP: Cursor unchanged")
            break
        
        # Add leads to collection
        all_leads.extend(leads)
        print(f"  Total collected: {len(all_leads)}")
        
        # Check if we're close to expected count
        if len(all_leads) >= all_meta_leads_count:
            print(f"  SUCCESS: Reached expected count of {all_meta_leads_count}")
            break
        
        # Check if we got fewer leads than limit (natural end)
        if len(leads) < payload['_limit']:
            print(f"  NATURAL END: Got {len(leads)} leads (less than limit {payload['_limit']})")
            break
        
        cursor = new_cursor
        time.sleep(1)  # Rate limiting
    
    print(f"\n" + "="*60)
    print(f"COLLECTION COMPLETE")
    print("="*60)
    print(f"Total pages fetched: {page_count}")
    print(f"Expected leads: {all_meta_leads_count}")
    print(f"Actual leads collected: {len(all_leads)}")
    print(f"Accuracy: {len(all_leads)/all_meta_leads_count*100:.1f}%")
    
    if len(all_leads) == all_meta_leads_count:
        print("SUCCESS: Collected exact expected number of leads!")
    elif len(all_leads) < all_meta_leads_count:
        print(f"WARNING: Missing {all_meta_leads_count - len(all_leads)} leads")
    else:
        print(f"WARNING: Got {len(all_leads) - all_meta_leads_count} extra leads")
    
    return all_leads

def main():
    """Main execution"""
    env_vars = load_env()
    if not env_vars:
        return
    
    api_key = env_vars.get('CLOSE_API_KEY')
    if not api_key:
        print("ERROR: CLOSE_API_KEY not found in .env file")
        return
    
    # Collect All Meta Leads
    leads = collect_meta_leads_with_safety_limit(api_key)
    
    if leads:
        # Save results
        timestamp = time.strftime('%Y-%m-%d_%H-%M-%S')
        result_file = f"meta_leads_safety_limit_{timestamp}.json"
        
        with open(result_file, 'w') as f:
            json.dump({
                'view_name': 'All Meta Leads',
                'view_id': 'save_TOTstqdumHKQcNUaztinosJBnRDPYd7IAMhU2SuKyVH',
                'expected_count': 443,
                'actual_count': len(leads),
                'leads': leads,
                'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
                'method': 'safety_limit'
            }, f, indent=2)
        
        print(f"\nResults saved to: {result_file}")
        print(f"Ready to use {len(leads)} leads for apollo enrichment!")
    else:
        print("No leads collected")

if __name__ == "__main__":
    main()

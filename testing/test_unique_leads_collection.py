#!/usr/bin/env python3
"""
Test script to collect ALL unique leads from "All Meta Leads" smart view
by tracking lead IDs to detect when we stop getting new leads
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

def collect_all_unique_leads(api_key: str, view_id: str, view_name: str, expected_count: int = 443):
    """Collect all unique leads from a smart view by tracking lead IDs"""
    print(f"Collecting ALL unique leads from: {view_name}")
    print(f"Expected count: {expected_count}")
    print("="*60)
    
    url = "https://api.close.com/api/v1/data/search/"
    headers = get_close_headers(api_key)
    
    all_lead_ids = set()  # Track unique lead IDs
    all_leads = []  # Store actual lead data
    cursor = None
    page = 0
    consecutive_no_new_leads = 0  # Track how many pages with no new leads
    
    while True:
        page += 1
        
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
        
        if cursor:
            payload["_cursor"] = cursor
        
        print(f"\nPage {page}:")
        print(f"  Cursor: {cursor[:50] + '...' if cursor and len(cursor) > 50 else cursor}")
        
        # Retry logic for network issues
        max_retries = 3
        retry_delay = 2
        
        for attempt in range(max_retries):
            try:
                if attempt > 0:
                    print(f"  Retry attempt {attempt + 1}/{max_retries}")
                    time.sleep(retry_delay * attempt)  # Exponential backoff
                
                response = requests.post(url, headers=headers, json=payload, timeout=45)
                
                if response.status_code != 200:
                    print(f"  ERROR: {response.status_code} - {response.text}")
                    break
                
                # Success - break out of retry loop
                break
                
            except requests.exceptions.Timeout:
                print(f"  TIMEOUT on attempt {attempt + 1}/{max_retries}")
                if attempt == max_retries - 1:
                    print(f"  FAILED: All {max_retries} attempts timed out")
                    return all_leads, len(all_lead_ids)  # Return what we have
            except Exception as e:
                print(f"  ERROR on attempt {attempt + 1}/{max_retries}: {e}")
                if attempt == max_retries - 1:
                    print(f"  FAILED: All {max_retries} attempts failed")
                    return all_leads, len(all_lead_ids)  # Return what we have
        else:
            # If we get here, all retries failed
            break
        
        # Process the successful response
        data = response.json()
        leads = data.get('data', [])
        new_cursor = data.get('cursor')
        
        # Track new vs duplicate leads
        new_leads_this_page = 0
        duplicate_leads_this_page = 0
        
        for lead in leads:
            lead_id = lead.get('id')
            if lead_id and lead_id not in all_lead_ids:
                all_lead_ids.add(lead_id)
                all_leads.append(lead)
                new_leads_this_page += 1
            else:
                duplicate_leads_this_page += 1
        
        print(f"  API returned: {len(leads)} leads")
        print(f"  New unique leads: {new_leads_this_page}")
        print(f"  Duplicate leads: {duplicate_leads_this_page}")
        print(f"  Total unique so far: {len(all_lead_ids)}")
        print(f"  Progress: {len(all_lead_ids)}/{expected_count} ({len(all_lead_ids)/expected_count*100:.1f}%)")
        
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
        
        # NEW: Stop if we're not getting new leads
        if new_leads_this_page == 0:
            consecutive_no_new_leads += 1
            print(f"  WARNING: No new leads this page (consecutive: {consecutive_no_new_leads})")
            
            if consecutive_no_new_leads >= 2:
                print(f"  STOP: No new leads for {consecutive_no_new_leads} consecutive pages")
                break
        else:
            consecutive_no_new_leads = 0  # Reset counter
        
        # Safety check: If we have way more than expected, something is wrong
        if len(all_lead_ids) > expected_count * 1.5:
            print(f"  STOP: Safety limit - got {len(all_lead_ids)} leads (>150% of expected {expected_count})")
            break
        
        # Perfect match check
        if len(all_lead_ids) == expected_count:
            print(f"  SUCCESS: Collected exact expected count ({expected_count})")
            # Continue one more page to confirm we're done
            if consecutive_no_new_leads >= 1:
                print(f"  CONFIRMED: No new leads after reaching expected count")
                break
        
        cursor = new_cursor
        time.sleep(2)  # Increased rate limiting
    
    print(f"\n" + "="*60)
    print(f"COLLECTION COMPLETE")
    print("="*60)
    print(f"Total pages fetched: {page}")
    print(f"Expected leads: {expected_count}")
    print(f"Actual unique leads collected: {len(all_lead_ids)}")
    print(f"Accuracy: {len(all_lead_ids)/expected_count*100:.1f}%")
    
    if len(all_lead_ids) == expected_count:
        print("SUCCESS: Collected exact expected number of leads!")
    elif len(all_lead_ids) < expected_count:
        print(f"  WARNING: Missing {expected_count - len(all_lead_ids)} leads")
    else:
        print(f"  WARNING: Got {len(all_lead_ids) - expected_count} extra leads")
    
    return all_leads, len(all_lead_ids)

def main():
    """Main execution"""
    env_vars = load_env()
    if not env_vars:
        return
    
    api_key = env_vars.get('CLOSE_API_KEY')
    if not api_key:
        print("ERROR: CLOSE_API_KEY not found in .env file")
        return
    
    # Test with All Meta Leads
    view_id = 'save_TOTstqdumHKQcNUaztinosJBnRDPYd7IAMhU2SuKyVH'
    view_name = ' 03 All Meta Leads'
    expected_count = 443
    
    leads, actual_count = collect_all_unique_leads(api_key, view_id, view_name, expected_count)
    
    # Save results for verification
    result_file = "all_meta_leads_collected.json"
    with open(result_file, 'w') as f:
        json.dump({
            'view_name': view_name,
            'view_id': view_id,
            'expected_count': expected_count,
            'actual_count': actual_count,
            'leads': leads,
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
        }, f, indent=2)
    
    print(f"\nResults saved to: {result_file}")
    print(f"Ready to use {actual_count} leads for apollo enrichment!")

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Focused pagination test for specific Close CRM smart views
Tests "Closed Lost" and "All Meta Leads" views with detailed response debugging
"""

import requests
import json
import time
import base64
import os

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

def test_smart_view_pagination(api_key: str, view_id: str, view_name: str, max_pages: int = 5, safety_limit_multiplier: float = 1.5):
    """Test pagination for a specific smart view with detailed debugging"""
    print(f"\n" + "="*80)
    print(f"TESTING: {view_name}")
    print(f"View ID: {view_id}")
    print("="*80)
    
    url = "https://api.close.com/api/v1/data/search/"
    headers = get_close_headers(api_key)
    
    # Test 1: Cursor pagination with safety limits
    print(f"\n--- CURSOR PAGINATION TEST (with safety limits) ---")
    cursor = None
    total_leads_cursor = 0
    initial_count = None
    safety_limit = None
    
    for page in range(1, max_pages + 1):
        payload = {
            "query": {
                "type": "saved_search",
                "saved_search_id": view_id
            },
            "_fields": {
                "lead": ["id", "display_name"]
            },
            "_limit": 200
        }
        
        if cursor:
            payload["_cursor"] = cursor
        
        print(f"\nPage {page}:")
        print(f"  Payload: {json.dumps(payload, indent=2)}")
        
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            print(f"  Status: {response.status_code}")
            
            if response.status_code != 200:
                print(f"  ERROR: {response.text}")
                break
            
            data = response.json()
            
            # DETAILED RESPONSE DEBUGGING
            print(f"  RESPONSE KEYS: {list(data.keys())}")
            print(f"  FULL RESPONSE STRUCTURE:")
            for key, value in data.items():
                if key == 'data':
                    print(f"    {key}: [{len(value)} leads]")
                    if value:  # Show first lead structure
                        print(f"    First lead keys: {list(value[0].keys())}")
                else:
                    print(f"    {key}: {value} (type: {type(value)})")
            
            leads = data.get('data', [])
            new_cursor = data.get('cursor')
            has_more = data.get('has_more')
            
            # Set safety limit based on first page
            if page == 1 and len(leads) > 0:
                initial_count = len(leads)
                # If first page is full (at limit), assume there might be more
                if len(leads) == 200:
                    # Estimate total based on first page and set safety limit
                    estimated_total = len(leads) * 3  # Conservative estimate
                    safety_limit = int(estimated_total * safety_limit_multiplier)
                    print(f"  SAFETY LIMIT SET: {safety_limit} leads (estimated: {estimated_total}, multiplier: {safety_limit_multiplier})")
                else:
                    # First page not full, so this is likely all the data
                    safety_limit = len(leads) * 2  # Small buffer
                    print(f"  SAFETY LIMIT SET: {safety_limit} leads (first page not full)")
            
            print(f"  Leads count: {len(leads)}")
            print(f"  Cursor: {new_cursor}")
            print(f"  Has_more: {has_more}")
            print(f"  Total so far: {total_leads_cursor + len(leads)}")
            if safety_limit:
                print(f"  Safety limit: {safety_limit}")
            
            total_leads_cursor += len(leads)
            
            # Check stopping conditions
            if len(leads) == 0:
                print(f"  STOP: No more leads")
                break
            if new_cursor is None:
                print(f"  STOP: Cursor is None")
                break
            if cursor == new_cursor:
                print(f"  STOP: Cursor unchanged")
                break
            if has_more is False:
                print(f"  STOP: has_more is False")
                break
            
            # NEW: Safety limit check
            if safety_limit and total_leads_cursor >= safety_limit:
                print(f"  STOP: Safety limit reached ({total_leads_cursor} >= {safety_limit})")
                print(f"  This prevents infinite pagination loops")
                break
            
            cursor = new_cursor
            time.sleep(1)
            
        except Exception as e:
            print(f"  ERROR: {e}")
            break
    
    print(f"\nCURSOR PAGINATION TOTAL: {total_leads_cursor} leads")
    
    # Skip the problematic skip/limit test for now
    print(f"\n--- SKIP/LIMIT PAGINATION TEST ---")
    print(f"Skipping skip/limit test due to SSL connection issues with this endpoint")
    total_leads_skip = 0
    
    return {
        'view_name': view_name,
        'cursor_total': total_leads_cursor,
        'skip_total': total_leads_skip
    }

def main():
    """Main test execution"""
    print("Focused Close CRM Pagination Test")
    print("="*50)
    
    # Load environment
    env_vars = load_env()
    if not env_vars:
        return
    
    api_key = env_vars.get('CLOSE_API_KEY')
    if not api_key:
        print("ERROR: CLOSE_API_KEY not found in .env file")
        return
    
    # Test specific views
    test_views = [
        {
            'name': '🟢 03 All Meta Leads', 
            'id': 'save_TOTstqdumHKQcNUaztinosJBnRDPYd7IAMhU2SuKyVH',  # >200 leads
            'expected': 'over 400 leads'
        },
        {
            'name': '🌐 02 Full Week No Outbound',
            'id': 'save_5ICv93dt5AbFSfrSL7wdEQEgTYFH8bIidyBZ4U67USG',  # 16 leads
            'expected': '16 leads'
        }
    ]
    
    results = []
    for view in test_views:
        # Use different safety multipliers based on expected size
        if 'over 400' in view['expected']:
            safety_multiplier = 1.2  # Tighter limit for large views
            max_pages = 8  # Allow more pages for large views
        else:
            safety_multiplier = 2.0  # Looser limit for small views
            max_pages = 3  # Fewer pages needed for small views
            
        print(f"\nUsing safety multiplier: {safety_multiplier} for {view['name']}")
        result = test_smart_view_pagination(api_key, view['id'], view['name'], max_pages=max_pages, safety_limit_multiplier=safety_multiplier)
        results.append(result)
    
    # Summary
    print(f"\n" + "="*80)
    print(f"SUMMARY")
    print("="*80)
    
    for i, result in enumerate(results):
        expected = test_views[i]['expected']
        print(f"View: {result['view_name']} (Expected: {expected})")
        print(f"  Cursor pagination: {result['cursor_total']} leads")
        print(f"  Skip/limit pagination: {result['skip_total']} leads")
        if result['cursor_total'] != result['skip_total']:
            print(f"  WARNING: Different totals!")
        print()

if __name__ == "__main__":
    main()

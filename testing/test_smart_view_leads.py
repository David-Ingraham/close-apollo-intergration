#!/usr/bin/env python3
"""
Test script to properly fetch all leads from a smart view using documented Close API methods
"""

import os
import requests
import json
from base64 import b64encode
from dotenv import load_dotenv

load_dotenv()

def test_cursor_pagination():
    """
    Test cursor-based pagination exactly like get_lawyer_contacts.py
    """
    print("Testing Cursor Pagination")
    print("=" * 50)
    
    # Same smart views as get_lawyer_contacts.py
    SMART_VIEWS = {
        "closed_lost": {
            "id": "save_VhNf5m3cFu5UGT6Q7vlPbOmRZrGLdkjgXQOhBJ4Kfgc",
            "name": "Closed Lost"
        },
        "todays_leads": {
            "id": "save_5fJVdYDvHzGPZNT9bm0qwuPCLnFjK8vg1eSTWIE6Lhs",
            "name": "Today's Leads"
        },
        "uncalled_leads": {
            "id": "save_PF9vEDVO1gpuE96xWcJheorDdvwTzZC78h7VSUNWtpz",
            "name": "Uncalled Leads"
        },
        "full_week_no_contact": {
            "id": "save_4vCZn8S0aEOI7LITSdgww6NHyEYPK42OKKo0UUq9xK0",
            "name": "Full Week No Contact"
        },
        "leads_created_by_mattias": {
            "id": "save_uWiE0ZujkNKqQHG19ugGz5dIba891rC9Jd8sgIGqgXh",
            "name": "Leads Created by Mattias"
        },
        "full_week_no_outbound": {
            "id": "save_5ICv93dt5AbFSfrSL7wdEQEgTYFH8bIidyBZ4U67USG",
            "name": "Full Week No Outbound"
        },
        "surgery_in_discovery": {
            "id": "save_O73Z1YkRGhLrN5qtyhti2lLoBYVeTqkKWsiG2ZUj4cE",
            "name": "Surgery in Discovery"
        },
        "All meta leads": {
            "id": "save_TOTstqdumHKQcNUaztinosJBnRDPYd7IAMhU2SuKyVH",
            "name": "All Meta Leads"
        }
    }
    
    # Prompt user to select smart view
    print("\nAvailable Smart Views:")
    view_options = list(SMART_VIEWS.keys())
    for i, view_key in enumerate(view_options, 1):
        view_name = SMART_VIEWS[view_key]["name"]
        print(f"  {i}. {view_name}")
    
    while True:
        try:
            choice = input(f"\nSelect smart view (1-{len(view_options)}): ").strip()
            choice_num = int(choice)
            if 1 <= choice_num <= len(view_options):
                selected_view_key = view_options[choice_num - 1]
                break
            else:
                print(f"Please enter a number between 1-{len(view_options)}")
        except ValueError:
            print("Please enter a valid number")
    
    current_smart_view = SMART_VIEWS[selected_view_key]
    view_id = current_smart_view["id"]
    view_name = current_smart_view["name"]
    
    print(f"Selected: {view_name}")
    print(f"View ID: {view_id}")
    
    close_api_key = os.getenv('CLOSE_API_KEY')
    if not close_api_key:
        print("ERROR: No CLOSE_API_KEY found in .env file")
        return False
    
    # Use exact same setup as get_lawyer_contacts.py
    encoded_key = b64encode(f"{close_api_key}:".encode('utf-8')).decode('utf-8')
    
    headers = {
        'Authorization': f'Basic {encoded_key}',
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    }
    
    url = 'https://api.close.com/api/v1/data/search/'
    
    # Exact same payload structure as get_lawyer_contacts.py
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
    
    try:
        all_leads = []
        page_count = 0
        cursor = None  # Start with no cursor for first page
        
        while True:
            page_count += 1
            
            # Add cursor to payload if we have one (not for first page)
            if cursor:
                payload['_cursor'] = cursor
            elif '_cursor' in payload:
                # Remove cursor if we don't have one (first page)
                del payload['_cursor']
            
            print(f"\nPage {page_count} (cursor: {cursor[:20] + '...' if cursor else 'None'})")
            
            # Make the POST request
            response = requests.post(url, headers=headers, json=payload)
            response.raise_for_status()
            
            api_response = response.json()
            page_leads = api_response.get('data', [])
            
            print(f"Found {len(page_leads)} leads on page {page_count}")
            print(f"API Response keys: {list(api_response.keys())}")
            
            # Check for empty page - means we're done
            if not page_leads:
                print("No more pages (empty results)")
                break
            
            # Add all leads from this page
            all_leads.extend(page_leads)
            print(f"Added {len(page_leads)} leads (total: {len(all_leads)})")
            
            # If we got fewer leads than requested, we've reached the end
            if len(page_leads) < payload['_limit']:
                print(f"Got {len(page_leads)} leads (less than limit {payload['_limit']}) - reached end")
                break
            
            # Get cursor for next page
            next_cursor = api_response.get('cursor')
            
            print(f"Current cursor: {cursor}")
            print(f"Next cursor:    {next_cursor}")
            
            # If no cursor returned, we're at the end
            if not next_cursor:
                print("No cursor returned - reached end of results")
                break
                
            # If cursor hasn't changed, we're stuck (safety check)
            if next_cursor == cursor:
                print("WARNING: Cursor hasn't changed - stopping to prevent infinite loop")
                break
                
            # Update cursor for next iteration
            cursor = next_cursor
            
            # Safety limit to prevent runaway loops
            if page_count >= 5:
                print(f"WARNING: Reached safety limit of 5 pages ({len(all_leads)} leads)")
                break
                
            # Add delay to be API-friendly
            print("Waiting 1 second before next page...")
            import time
            time.sleep(1)
        
        print(f"\n{'='*30}")
        print("CURSOR PAGINATION RESULTS")
        print(f"{'='*30}")
        print(f"Smart View: {view_name}")
        print(f"Total pages: {page_count}")
        print(f"Total leads collected: {len(all_leads)}")
        
        if len(all_leads) > 0:
            print("SUCCESS: Pagination working - leads retrieved!")
            return True
        else:
            print("FAILED: No leads retrieved")
            return False
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_standard_pagination():
    """
    Test standard pagination using _skip and _limit (documented method)
    """
    print("\n" + "=" * 50)
    print("Testing Standard Pagination (_skip + _limit)")
    print("=" * 50)
    
    # Test with "Closed Lost" view (should have exactly 221 leads)
    view_id = "save_VhNf5m3cFu5UGT6Q7vlPbOmRZrGLdkjgXQOhBJ4Kfgc"  # Closed Lost
    expected_total = 221
    
    base_url = "https://api.close.com/api/v1/"
    close_api_key = os.getenv('CLOSE_API_KEY')
    
    # Use same authentication as get_lawyer_contacts.py
    encoded_key = b64encode(f"{close_api_key}:".encode('utf-8')).decode('utf-8')
    
    headers = {
        "Authorization": f"Basic {encoded_key}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    
    url = f"{base_url}data/search/"
    limit = 100  # Conservative limit
    skip = 0
    all_leads = []
    page = 1
    
    while True:
        print(f"\nPage {page} (skip={skip}, limit={limit})")
        
        payload = {
            "query": {
                "type": "saved_search",
                "saved_search_id": view_id
            },
            "_fields": {
                "lead": ["id", "display_name"]
            },
            "_limit": limit,
            "_skip": skip
        }
        
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            
            if response.status_code != 200:
                print(f"Error {response.status_code}: {response.text}")
                break
            
            data = response.json()
            page_leads = data.get('data', [])
            has_more = data.get('has_more', False)
            total_results = data.get('total_results', 'unknown')
            
            print(f"  Leads: {len(page_leads)}")
            print(f"  Has more: {has_more}")
            print(f"  Total results: {total_results}")
            
            if not page_leads:
                print("  No more leads - ending")
                break
            
            all_leads.extend(page_leads)
            print(f"  Total collected: {len(all_leads)}")
            
            # Check if we have all expected leads
            if len(all_leads) >= expected_total:
                print(f"  Reached expected total of {expected_total}")
                break
            
            # Check has_more flag
            if not has_more:
                print("  has_more=False - ending")
                break
            
            # Prepare for next page
            skip += limit
            page += 1
            
            # Safety limit
            if page > 10:
                print("  Safety limit reached")
                break
                
        except Exception as e:
            print(f"  Exception: {e}")
            break
    
    print(f"\n{'='*30}")
    print("FINAL RESULTS")
    print(f"{'='*30}")
    print(f"Total leads collected: {len(all_leads)}")
    print(f"Expected leads: {expected_total}")
    print(f"Success: {len(all_leads) == expected_total}")
    
    return len(all_leads) == expected_total

if __name__ == "__main__":
    print("Close CRM Smart View Cursor Pagination Test")
    print("Select a smart view to test pagination")
    print()
    
    # Test cursor pagination (your current method)
    success = test_cursor_pagination()
    
    if success:
        print("\nSUCCESS: Cursor pagination working correctly!")
    else:
        print("\nFAILED: Cursor pagination issues detected")

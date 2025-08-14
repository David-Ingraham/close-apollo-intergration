#!/usr/bin/env python3
"""
Simple test script to pull all leads from Close CRM "Closed Lost" Smart View
No processing, just raw data retrieval with safe pagination
"""

import os
import json
import requests
from base64 import b64encode
from dotenv import load_dotenv

load_dotenv()

def pull_closed_lost_leads():
    """
    Simple function to pull all leads from Closed Lost Smart View
    """
    
    # Get API key
    api_key = os.getenv('CLOSE_API_KEY')
    if not api_key:
        print("ERROR: CLOSE_API_KEY not found in environment")
        return None
    
    # Closed Lost Smart View ID (from your get_lawyer_contacts.py)
    CLOSED_LOST_ID = "save_pkn62aAZeRFBxpo26Ued3BG8gKqoltIN5h9k9cBUvkL"
    
    # API setup
    encoded_key = b64encode(f"{api_key}:".encode('utf-8')).decode('utf-8')
    headers = {
        'Authorization': f'Basic {encoded_key}',
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    }
    
    url = 'https://api.close.com/api/v1/data/search/'
    
    payload = {
        "query": {
            "type": "saved_search",
            "saved_search_id": CLOSED_LOST_ID
        },
        "_fields": {
            "lead": ["id", "display_name", "status_id"]  # Minimal fields
        },
        "_limit": 200

    }
    
    print("=== PULLING CLOSED LOST LEADS ===")
    print(f"Smart View ID: {CLOSED_LOST_ID}")
    print(f"URL: {url}")
    print("-" * 50)
    
    all_leads = []
    page = 0
    cursor = None
    
    # Safety limit - max 10 pages
    MAX_PAGES = 10
    
    while page < MAX_PAGES:
        page += 1
        
        # Add cursor if we have one
        if cursor:
            payload['_cursor'] = cursor
        elif '_cursor' in payload:
            del payload['_cursor']
        
        print(f"\nPage {page}:")
        print(f"  Cursor: {cursor[:30] + '...' if cursor else 'None'}")
        
        # Retry logic for SSL errors
        max_retries = 3
        for attempt in range(max_retries):
            try:
                if attempt > 0:
                    print(f"  Retry attempt {attempt + 1}/{max_retries}")
                    import time
                    time.sleep(2)  # Wait 2 seconds before retry
                
                response = requests.post(url, headers=headers, json=payload, timeout=30)
                response.raise_for_status()
                
                data = response.json()
                leads_on_page = data.get('data', [])
                next_cursor = data.get('cursor')
                
                print(f"  Leads found: {len(leads_on_page)}")
                print(f"  Next cursor: {next_cursor[:30] + '...' if next_cursor else 'None'}")
                
                # Check for duplicate lead IDs before adding
                page_lead_ids = [lead.get('id') for lead in leads_on_page]
                existing_lead_ids = {lead.get('id') for lead in all_leads}
                new_leads = [lead for lead in leads_on_page if lead.get('id') not in existing_lead_ids]
                duplicate_count = len(leads_on_page) - len(new_leads)
                
                if duplicate_count > 0:
                    print(f"  DUPLICATES: {duplicate_count} duplicate leads found on this page")
                
                # Add only new leads
                all_leads.extend(new_leads)
                print(f"  New leads added: {len(new_leads)}")
                print(f"  Total so far: {len(all_leads)}")
                
                # Check termination conditions
                if not leads_on_page:
                    print("  STOP: No leads returned")
                    return all_leads  # Exit function entirely
                    
                if not next_cursor:
                    print("  STOP: No cursor returned")
                    return all_leads  # Exit function entirely
                    
                if len(leads_on_page) < payload['_limit']:
                    print(f"  STOP: Fewer leads than limit ({len(leads_on_page)} < {payload['_limit']})")
                    return all_leads  # Exit function entirely
                    
                if next_cursor == cursor:
                    print("  WARNING: Cursor didn't change - trying skip-based pagination")
                    # Try skip-based pagination instead
                    skip_value = len(all_leads)
                    payload['_skip'] = skip_value
                    if '_cursor' in payload:
                        del payload['_cursor']
                    print(f"  Switching to skip-based: _skip = {skip_value}")
                    cursor = None  # Reset cursor to try skip method
                    continue  # Try this page again with skip
                
                # Update cursor for next iteration
                cursor = next_cursor
                break  # Success, exit retry loop
                
            except requests.exceptions.SSLError as e:
                print(f"  SSL ERROR (attempt {attempt + 1}): {e}")
                if attempt == max_retries - 1:
                    print(f"  FAILED after {max_retries} attempts - stopping")
                    return all_leads
            except requests.exceptions.RequestException as e:
                print(f"  REQUEST ERROR: {e}")
                if attempt == max_retries - 1:
                    print(f"  FAILED after {max_retries} attempts - stopping")
                    return all_leads
            except Exception as e:
                print(f"  UNEXPECTED ERROR: {e}")
                if attempt == max_retries - 1:
                    print(f"  FAILED after {max_retries} attempts - stopping")
                    return all_leads
    
    print(f"\n=== RESULTS ===")
    print(f"Pages processed: {page}")
    print(f"Total leads retrieved: {len(all_leads)}")
    
    if page >= MAX_PAGES:
        print(f"WARNING: Hit safety limit of {MAX_PAGES} pages")
    
    # Save results to file for inspection
    if all_leads:
        filename = f"closed_lost_leads_{len(all_leads)}_leads.json"
        with open(filename, 'w') as f:
            json.dump({
                'total_leads': len(all_leads),
                'pages_processed': page,
                'leads': all_leads
            }, f, indent=2)
        print(f"Results saved to: {filename}")
    
    return all_leads

if __name__ == "__main__":
    leads = pull_closed_lost_leads()
    
    if leads:
        print(f"\nSUCCESS: Retrieved {len(leads)} leads from Closed Lost Smart View")
        
        # Show first few leads for verification
        print(f"\nFirst 3 leads:")
        for i, lead in enumerate(leads[:3], 1):
            print(f"  {i}. ID: {lead.get('id')} - Name: {lead.get('display_name')}")
    else:
        print("\nFAILED: No leads retrieved")

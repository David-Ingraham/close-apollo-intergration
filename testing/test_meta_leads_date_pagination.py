#!/usr/bin/env python3
"""
Test script to collect ALL leads from "All Meta Leads" smart view
using date-based pagination as recommended by Close CRM for large datasets
"""

import requests
import json
import base64
import time
from datetime import datetime, timedelta

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

def collect_meta_leads_date_based(api_key: str):
    """Collect All Meta Leads using date-based pagination"""
    
    # Smart view configuration
    view_id = 'save_TOTstqdumHKQcNUaztinosJBnRDPYd7IAMhU2SuKyVH'
    view_name = 'All Meta Leads'
    expected_count = 443
    
    print(f"Collecting leads from: {view_name}")
    print(f"Expected count: {expected_count}")
    print(f"Method: Date-based pagination (Close CRM recommended)")
    print("="*70)
    
    url = "https://api.close.com/api/v1/data/search/"
    headers = get_close_headers(api_key)
    
    all_leads = []
    all_lead_ids = set()  # Track unique IDs to prevent duplicates
    batch_count = 0
    
    # Define date range - let's go back 2 years to be safe
    end_date = datetime.now()
    start_date = end_date - timedelta(days=730)  # 2 years back
    batch_days = 30  # Process 30 days at a time
    
    current_start = start_date
    
    while current_start < end_date:
        batch_count += 1
        current_end = min(current_start + timedelta(days=batch_days), end_date)
        
        # Format dates for Close API (ISO format)
        start_str = current_start.strftime('%Y-%m-%d')
        end_str = current_end.strftime('%Y-%m-%d')
        
        print(f"\nBatch {batch_count}: {start_str} to {end_str}")
        print(f"  Unique leads so far: {len(all_lead_ids)}")
        
        # Create payload with date filter
        payload = {
            "query": {
                "type": "and",
                "queries": [
                    {
                        "type": "saved_search",
                        "saved_search_id": view_id
                    },
                    {
                        "type": "field_condition",
                        "field": {
                            "type": "regular_field",
                            "object_type": "lead",
                            "field_name": "date_created"
                        },
                        "condition": {
                            "type": "fixed_date_range",
                            "start": start_str,
                            "end": end_str
                        }
                    }
                ]
            },
            "_fields": {
                "lead": ["id", "display_name", "status_id", "name", "contacts", "custom", "date_created"]
            },
            "_limit": 200
        }
        
        # Paginate through this date range
        page = 0
        skip = 0
        batch_leads = []
        
        while True:
            page += 1
            payload["_skip"] = skip
            
            try:
                response = requests.post(url, headers=headers, json=payload, timeout=45)
                
                if response.status_code != 200:
                    print(f"    ERROR: {response.status_code} - {response.text}")
                    break
                
                data = response.json()
                leads = data.get('data', [])
                
                if not leads:
                    print(f"    No more leads in this date range")
                    break
                
                # Track new vs duplicate leads
                new_leads_this_page = 0
                duplicate_leads = 0
                
                for lead in leads:
                    lead_id = lead.get('id')
                    if lead_id and lead_id not in all_lead_ids:
                        all_lead_ids.add(lead_id)
                        all_leads.append(lead)
                        batch_leads.append(lead)
                        new_leads_this_page += 1
                    else:
                        duplicate_leads += 1
                
                print(f"    Page {page}: {len(leads)} leads, {new_leads_this_page} new, {duplicate_leads} duplicates")
                
                # Show sample leads for first few pages
                if page <= 2 and new_leads_this_page > 0:
                    print(f"    Sample new leads:")
                    sample_leads = [lead for lead in leads if lead.get('id') not in all_lead_ids or lead in batch_leads[-new_leads_this_page:]][:2]
                    for i, lead in enumerate(sample_leads):
                        lead_name = lead.get('display_name', lead.get('name', 'No name'))
                        date_created = lead.get('date_created', 'No date')
                        custom_fields = lead.get('custom', {})
                        attorney_name = custom_fields.get('Attorney Name', 'N/A')
                        print(f"      {i+1}. {lead_name} | Created: {date_created} | Attorney: {attorney_name}")
                
                # If we got fewer leads than limit, we're done with this date range
                if len(leads) < payload['_limit']:
                    print(f"    Reached end of date range ({len(leads)} < {payload['_limit']})")
                    break
                
                skip += len(leads)
                time.sleep(0.5)  # Small delay between pages
                
            except Exception as e:
                print(f"    ERROR: {e}")
                break
        
        print(f"  Date range complete: {len(batch_leads)} new leads from {start_str} to {end_str}")
        
        # Move to next date range
        current_start = current_end
        time.sleep(1)  # Delay between date ranges
    
    print(f"\n" + "="*70)
    print(f"DATE-BASED COLLECTION COMPLETE")
    print("="*70)
    print(f"Total date ranges processed: {batch_count}")
    print(f"Expected leads: {expected_count}")
    print(f"Actual unique leads collected: {len(all_lead_ids)}")
    print(f"Total records processed: {len(all_leads)}")
    print(f"Accuracy: {len(all_lead_ids)/expected_count*100:.1f}%")
    
    if len(all_lead_ids) == expected_count:
        print("SUCCESS: Collected exact expected number of unique leads!")
    elif len(all_lead_ids) < expected_count:
        print(f"WARNING: Missing {expected_count - len(all_lead_ids)} leads")
    else:
        print(f"NOTE: Got {len(all_lead_ids) - expected_count} extra leads (may be new leads)")
    
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
    
    # Collect All Meta Leads using date-based pagination
    leads = collect_meta_leads_date_based(api_key)
    
    if leads:
        # Save results
        timestamp = time.strftime('%Y-%m-%d_%H-%M-%S')
        result_file = f"meta_leads_date_based_{timestamp}.json"
        
        # Get unique leads only for final save
        unique_leads = []
        seen_ids = set()
        for lead in leads:
            lead_id = lead.get('id')
            if lead_id and lead_id not in seen_ids:
                seen_ids.add(lead_id)
                unique_leads.append(lead)
        
        with open(result_file, 'w') as f:
            json.dump({
                'view_name': 'All Meta Leads',
                'view_id': 'save_TOTstqdumHKQcNUaztinosJBnRDPYd7IAMhU2SuKyVH',
                'expected_count': 443,
                'unique_count': len(unique_leads),
                'total_records': len(leads),
                'leads': unique_leads,
                'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
                'method': 'date_based_pagination'
            }, f, indent=2)
        
        print(f"\nResults saved to: {result_file}")
        print(f"Ready to use {len(unique_leads)} unique leads for apollo enrichment!")
    else:
        print("No leads collected")

if __name__ == "__main__":
    main()

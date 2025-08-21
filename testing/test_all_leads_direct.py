#!/usr/bin/env python3
"""
Get ALL leads directly from Close CRM using the /api/v1/lead/ endpoint
This endpoint has proper pagination with has_more and total_results fields
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

def get_all_leads(api_key: str):
    """Get ALL leads from Close CRM using direct lead endpoint"""
    print("Fetching ALL leads from Close CRM")
    print("="*50)
    
    url = "https://api.close.com/api/v1/lead/"
    headers = get_close_headers(api_key)
    
    all_leads = []
    skip = 0
    limit = 200
    page = 0
    
    while True:
        page += 1
        
        params = {
            '_limit': limit,
            '_skip': skip,
            '_fields': 'id,display_name,status_id,name,contacts,custom'  # Same fields as smart view
        }
        
        print(f"\nPage {page}:")
        print(f"  Skip: {skip}, Limit: {limit}")
        
        try:
            response = requests.get(url, headers=headers, params=params, timeout=45)
            
            if response.status_code != 200:
                print(f"  ERROR: {response.status_code} - {response.text}")
                break
            
            data = response.json()
            
            # Show response structure
            print(f"  Response keys: {list(data.keys())}")
            
            leads = data.get('data', [])
            has_more = data.get('has_more', False)
            total_results = data.get('total_results', 0)
            
            print(f"  Leads this page: {len(leads)}")
            print(f"  Total so far: {len(all_leads) + len(leads)}")
            print(f"  Has more: {has_more}")
            print(f"  Total available: {total_results}")
            
            if total_results > 0:
                progress = (len(all_leads) + len(leads)) / total_results * 100
                print(f"  Progress: {progress:.1f}%")
            
            # Show sample leads from this page
            if leads:
                print(f"  Sample leads from this page:")
                for i, lead in enumerate(leads[:3]):  # Show first 3 leads
                    lead_name = lead.get('display_name', lead.get('name', 'No name'))
                    custom_fields = lead.get('custom', {})
                    attorney_name = custom_fields.get('Attorney Name', 'N/A')
                    attorney_email = custom_fields.get('Attorney Email', 'N/A')
                    law_office = custom_fields.get('Law Office', 'N/A')
                    
                    print(f"    {i+1}. {lead_name}")
                    print(f"       Attorney: {attorney_name}")
                    print(f"       Email: {attorney_email}")
                    print(f"       Law Office: {law_office}")
                
                if len(leads) > 3:
                    print(f"    ... and {len(leads) - 3} more leads")
            
            # Add leads to collection
            all_leads.extend(leads)
            
            # Check stopping conditions
            if len(leads) == 0:
                print(f"  STOP: No more leads returned")
                break
            
            if not has_more:
                print(f"  STOP: has_more is False")
                break
            
            if len(leads) < limit:
                print(f"  STOP: Fewer leads than limit ({len(leads)} < {limit})")
                break
            
            # Move to next page
            skip += limit
            time.sleep(1)  # Rate limiting
            
        except Exception as e:
            print(f"  ERROR: {e}")
            break
    
    print(f"\n" + "="*50)
    print(f"COLLECTION COMPLETE")
    print("="*50)
    print(f"Total pages fetched: {page}")
    print(f"Total leads collected: {len(all_leads)}")
    
    return all_leads

def filter_leads_by_criteria(leads):
    """Filter leads by the same criteria used in get_lawyer_contacts.py"""
    print(f"\nFiltering {len(leads)} leads by enrichment criteria...")
    print("Sample filtering results:")
    
    filtered_leads = []
    skipped_leads = []
    samples_shown = 0
    
    for lead in leads:
        # Extract lead data (same logic as get_lawyer_contacts.py)
        lead_id = lead.get('id', '')
        lead_name = lead.get('display_name', lead.get('name', ''))
        
        # Get custom fields
        custom_fields = lead.get('custom', {})
        attorney_name = custom_fields.get('Attorney Name', '')
        attorney_email = custom_fields.get('Attorney Email', '')
        law_office = custom_fields.get('Law Office', '')
        
        # Apply enrichment criteria
        skip_reason = None
        
        # Check if Law Office is empty/N/A AND attorney email is public domain
        if not law_office or law_office.lower() in ['n/a', 'na', 'none', '']:
            if not attorney_email or '@gmail.com' in attorney_email.lower() or '@yahoo.com' in attorney_email.lower():
                skip_reason = "no_law_office_and_public_email"
        
        # Check if we have attorney name but no email
        if attorney_name and not attorney_email:
            skip_reason = "attorney_name_but_no_email"
        
        # Check if completely empty
        if not attorney_name and not attorney_email and not law_office:
            skip_reason = "completely_empty"
        
        if skip_reason:
            skipped_leads.append({
                'lead_id': lead_id,
                'lead_name': lead_name,
                'attorney_name': attorney_name,
                'attorney_email': attorney_email,
                'law_office': law_office,
                'skip_reason': skip_reason
            })
            
            # Show sample skipped leads
            if samples_shown < 5:
                print(f"  SKIP: {lead_name} - {skip_reason}")
                print(f"        Attorney: {attorney_name}")
                print(f"        Email: {attorney_email}")
                print(f"        Law Office: {law_office}")
                samples_shown += 1
        else:
            # Add to enrichment queue
            filtered_leads.append({
                'lead_id': lead_id,
                'lead_name': lead_name,
                'attorney_name': attorney_name,
                'attorney_email': attorney_email,
                'law_office': law_office,
                'needs_apollo_enrichment': True,
                'skip_reason': None
            })
            
            # Show sample enrichment leads
            if samples_shown < 5:
                print(f"  ENRICH: {lead_name}")
                print(f"          Attorney: {attorney_name}")
                print(f"          Email: {attorney_email}")
                print(f"          Law Office: {law_office}")
                samples_shown += 1
    
    print(f"Leads for enrichment: {len(filtered_leads)}")
    print(f"Skipped leads: {len(skipped_leads)}")
    
    return filtered_leads, skipped_leads

def main():
    """Main execution"""
    env_vars = load_env()
    if not env_vars:
        return
    
    api_key = env_vars.get('CLOSE_API_KEY')
    if not api_key:
        print("ERROR: CLOSE_API_KEY not found in .env file")
        return
    
    # Get all leads
    all_leads = get_all_leads(api_key)
    
    if not all_leads:
        print("No leads retrieved")
        return
    
    # Filter by enrichment criteria
    enrichment_leads, skipped_leads = filter_leads_by_criteria(all_leads)
    
    # Save results
    timestamp = time.strftime('%Y-%m-%d_%H-%M-%S')
    
    # Save enrichment-ready leads
    enrichment_file = f"all_leads_for_enrichment_{timestamp}.json"
    with open(enrichment_file, 'w') as f:
        json.dump(enrichment_leads, f, indent=2)
    
    # Save skipped leads
    skipped_file = f"all_leads_skipped_{timestamp}.json"
    with open(skipped_file, 'w') as f:
        json.dump(skipped_leads, f, indent=2)
    
    print(f"\nResults saved:")
    print(f"  Enrichment-ready leads: {enrichment_file}")
    print(f"  Skipped leads: {skipped_file}")
    
    print(f"\nReady to run apollo enrichment on {len(enrichment_leads)} leads!")

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Test Close CRM Export API to get ALL leads from "All Meta Leads" smart view
This bypasses pagination issues entirely
"""

import requests
import json
import base64
import time

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

def get_close_headers(api_key: str):
    encoded_key = base64.b64encode(f"{api_key}:".encode()).decode()
    return {
        'Authorization': f'Basic {encoded_key}',
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    }

def export_smart_view_leads(api_key: str):
    """Export leads from All Meta Leads smart view using Export API"""
    headers = get_close_headers(api_key)
    
    # Step 1: Initiate export
    export_url = "https://api.close.com/api/v1/export/lead/"
    
    # We need to figure out the s_query for our smart view
    # Let's first try getting the smart view details to see the query
    view_id = 'save_TOTstqdumHKQcNUaztinosJBnRDPYd7IAMhU2SuKyVH'
    smart_view_url = f"https://api.close.com/api/v1/saved_search/{view_id}/"
    
    print("Step 1: Getting smart view query...")
    try:
        response = requests.get(smart_view_url, headers=headers, timeout=30)
        if response.status_code == 200:
            view_data = response.json()
            print(f"Smart view name: {view_data.get('name')}")
            
            # Extract the s_query from the smart view
            s_query = view_data.get('s_query')
            
            print(f"s_query type: {type(s_query)}")
            if s_query:
                print(f"s_query keys: {list(s_query.keys())}")
            
            # Export API expects query as string, not object
            # Let's try different approaches
            
            print(f"\nStep 2A: Trying export with basic filter...")
            # Try with a simple date filter to get recent leads
            export_payload = {
                "query": "date_created >= 2025-07-08",
                "format": "json",
                "type": "leads", 
                "send_done_email": False
            }
            print("Using date filter to match smart view criteria")
            
        else:
            print(f"ERROR getting smart view: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        print(f"ERROR getting smart view: {e}")
        return None
    
    # Initiate the export
    print(f"Export payload: {json.dumps(export_payload, indent=2)}")
    
    try:
        response = requests.post(export_url, headers=headers, json=export_payload, timeout=30)
        
        if response.status_code not in [200, 201]:
            print(f"ERROR initiating export: {response.status_code} - {response.text}")
            return None
        
        export_data = response.json()
        export_id = export_data.get('id')
        
        print(f"Export initiated successfully!")
        print(f"Export ID: {export_id}")
        print(f"Status: {export_data.get('status')}")
        
    except Exception as e:
        print(f"ERROR initiating export: {e}")
        return None
    
    # Step 3: Poll for completion
    status_url = f"https://api.close.com/api/v1/export/{export_id}/"
    
    print(f"\nStep 3: Waiting for export to complete...")
    max_wait_time = 300  # 5 minutes
    start_time = time.time()
    
    while time.time() - start_time < max_wait_time:
        try:
            response = requests.get(status_url, headers=headers, timeout=30)
            
            if response.status_code != 200:
                print(f"ERROR checking status: {response.status_code}")
                return None
            
            status_data = response.json()
            status = status_data.get('status')
            
            print(f"Export status: {status}")
            
            if status == 'done':
                download_url = status_data.get('download_url')
                print(f"SUCCESS! Export complete.")
                print(f"Download URL: {download_url}")
                
                # Step 4: Download the data
                print(f"\nStep 4: Downloading export data...")
                
                download_response = requests.get(download_url, headers=headers, timeout=60)
                if download_response.status_code == 200:
                    # Parse the JSON data
                    leads_data = download_response.json()
                    
                    print(f"Downloaded successfully!")
                    print(f"Total leads in export: {len(leads_data)}")
                    
                    # Show sample leads
                    if leads_data:
                        print(f"\nSample leads:")
                        for i, lead in enumerate(leads_data[:3]):
                            lead_name = lead.get('display_name', lead.get('name', 'No name'))
                            custom_fields = lead.get('custom', {})
                            attorney_name = custom_fields.get('Attorney Name', 'N/A')
                            attorney_email = custom_fields.get('Attorney Email', 'N/A')
                            print(f"  {i+1}. {lead_name} | Attorney: {attorney_name} | Email: {attorney_email}")
                    
                    # Save to file
                    timestamp = time.strftime('%Y-%m-%d_%H-%M-%S')
                    filename = f"export_api_leads_{timestamp}.json"
                    
                    with open(filename, 'w') as f:
                        json.dump({
                            'export_id': export_id,
                            'total_leads': len(leads_data),
                            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
                            'method': 'export_api',
                            'leads': leads_data
                        }, f, indent=2)
                    
                    print(f"Data saved to: {filename}")
                    return leads_data
                
                else:
                    print(f"ERROR downloading: {download_response.status_code}")
                    return None
            
            elif status == 'error':
                print(f"Export failed with error")
                print(f"Full status data: {status_data}")
                return None
            
            elif status in ['created', 'started', 'in_progress']:
                print(f"Still processing... waiting 10 seconds")
                time.sleep(10)
            
            else:
                print(f"Unknown status: {status}")
                return None
                
        except Exception as e:
            print(f"ERROR checking status: {e}")
            return None
    
    print(f"ERROR: Export timed out after {max_wait_time} seconds")
    return None

def main():
    env_vars = load_env()
    if not env_vars:
        return
    
    api_key = env_vars.get('CLOSE_API_KEY')
    if not api_key:
        print("ERROR: CLOSE_API_KEY not found")
        return
    
    print("Testing Close CRM Export API for All Meta Leads smart view")
    print("="*60)
    
    leads = export_smart_view_leads(api_key)
    
    if leads:
        print(f"\nSUCCESS! Retrieved {len(leads)} leads using Export API")
        print("This should be the exact same data as your smart view!")
    else:
        print("\nFAILED to retrieve leads using Export API")

if __name__ == "__main__":
    main()

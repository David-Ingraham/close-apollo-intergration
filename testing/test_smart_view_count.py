#!/usr/bin/env python3
"""
Test script to check if Close CRM API returns total_results field for smart views
"""

import requests
import json
import base64

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

def test_total_results_field(api_key: str):
    """Test if total_results field is returned in smart view queries"""
    print("Testing total_results field in Close CRM API responses")
    print("="*60)
    
    url = "https://api.close.com/api/v1/data/search/"
    headers = get_close_headers(api_key)
    
    # Test views
    test_views = [
        {
            'name': '🟢 03 All Meta Leads', 
            'id': 'save_TOTstqdumHKQcNUaztinosJBnRDPYd7IAMhU2SuKyVH',
            'expected': 'over 400 leads'
        },
        {
            'name': '🌐 02 Full Week No Outbound',
            'id': 'save_5ICv93dt5AbFSfrSL7wdEQEgTYFH8bIidyBZ4U67USG',
            'expected': '16 leads'
        }
    ]
    
    for view in test_views:
        print(f"\n--- Testing {view['name']} ---")
        print(f"Expected: {view['expected']}")
        
        # Test with minimal limit to see if total_results appears
        payload = {
            "query": {
                "type": "saved_search",
                "saved_search_id": view['id']
            },
            "_fields": {
                "lead": ["id"]  # Minimal fields to reduce response size
            },
            "_limit": 1  # Just get 1 record to check metadata
        }
        
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            print(f"Status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                
                print(f"Response keys: {list(data.keys())}")
                print(f"Full response structure:")
                
                for key, value in data.items():
                    if key == 'data':
                        print(f"  {key}: [{len(value)} leads returned]")
                        if value:
                            print(f"    Sample lead keys: {list(value[0].keys())}")
                    else:
                        print(f"  {key}: {value} (type: {type(value)})")
                
                # Check for total_results
                total_results = data.get('total_results')
                if total_results is not None:
                    print(f"\n✅ FOUND total_results: {total_results}")
                else:
                    print(f"\n❌ total_results field NOT found")
                
                # Check other possible count fields
                possible_count_fields = ['total', 'count', 'total_count', 'results_count', 'lead_count']
                for field in possible_count_fields:
                    if field in data:
                        print(f"✅ Found {field}: {data[field]}")
                
            else:
                print(f"ERROR: {response.text}")
                
        except Exception as e:
            print(f"ERROR: {e}")
        
        print("-" * 40)

    # Test 2: Try different API endpoint patterns
    print(f"\n--- Testing Alternative Endpoints ---")
    
    # Try the saved_search endpoint directly
    saved_search_url = f"https://api.close.com/api/v1/saved_search/{test_views[0]['id']}/"
    
    try:
        response = requests.get(saved_search_url, headers=headers, timeout=30)
        print(f"Saved search endpoint status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"Saved search response keys: {list(data.keys())}")
            
            # Look for count information
            for key, value in data.items():
                if 'count' in key.lower() or 'total' in key.lower() or 'result' in key.lower():
                    print(f"  {key}: {value}")
                    
        else:
            print(f"Saved search endpoint error: {response.text}")
            
    except Exception as e:
        print(f"Saved search endpoint error: {e}")
    
    # Test 3: Try with _limit=0 to see if we get just count
    print(f"\n--- Testing with _limit=0 (count only) ---")
    
    for view in test_views[:1]:  # Just test first view
        payload = {
            "query": {
                "type": "saved_search", 
                "saved_search_id": view['id']
            },
            "_limit": 0  # Try to get just metadata/count
        }
        
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            print(f"Status with _limit=0: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                print(f"Response keys: {list(data.keys())}")
                
                for key, value in data.items():
                    print(f"  {key}: {value} (type: {type(value)})")
                    
            else:
                print(f"Error with _limit=0: {response.text}")
                
        except Exception as e:
            print(f"Error with _limit=0: {e}")
    
    # Test 4: Try lead endpoint directly (not data/search)
    print(f"\n--- Testing Lead Endpoint Directly ---")
    lead_url = "https://api.close.com/api/v1/lead/"
    
    # This won't work for smart views, but let's see the response structure
    try:
        params = {'_limit': 1}
        response = requests.get(lead_url, headers=headers, params=params, timeout=30)
        print(f"Lead endpoint status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"Lead endpoint response keys: {list(data.keys())}")
            
            # Check if has_more or total_results exists here
            for key, value in data.items():
                if key != 'data':
                    print(f"  {key}: {value} (type: {type(value)})")
                    
        else:
            print(f"Lead endpoint error: {response.text}")
            
    except Exception as e:
        print(f"Lead endpoint error: {e}")

def main():
    """Main execution"""
    env_vars = load_env()
    if not env_vars:
        return
    
    api_key = env_vars.get('CLOSE_API_KEY')
    if not api_key:
        print("ERROR: CLOSE_API_KEY not found in .env file")
        return
    
    test_total_results_field(api_key)

if __name__ == "__main__":
    main()

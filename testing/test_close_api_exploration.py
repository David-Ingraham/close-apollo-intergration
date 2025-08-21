#!/usr/bin/env python3
"""
Close CRM API Exploration Script

This script tests various aspects of the Close CRM API to understand:
1. Smart view access and permissions
2. Pagination behavior (cursor vs offset)
3. Response structure and termination conditions
4. Rate limiting and error handling

Usage: python test_close_api_exploration.py
"""

import requests
import json
import time
import base64
import os
from typing import Dict, List, Optional, Tuple

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

def get_close_headers(api_key: str) -> Dict[str, str]:
    """Generate Close CRM API headers with proper authentication"""
    encoded_key = base64.b64encode(f"{api_key}:".encode()).decode()
    return {
        'Authorization': f'Basic {encoded_key}',
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    }

def get_smart_views(api_key: str) -> List[Dict]:
    """Fetch all available smart views"""
    print("\n" + "="*60)
    print("FETCHING ALL SMART VIEWS")
    print("="*60)
    
    url = "https://api.close.com/api/v1/saved_search/"
    headers = get_close_headers(api_key)
    
    try:
        response = requests.get(url, headers=headers)
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            smart_views = data.get('data', [])
            print(f"Found {len(smart_views)} smart views")
            
            for i, view in enumerate(smart_views, 1):
                view_id = view.get('id', 'N/A')
                view_name = view.get('name', 'Unnamed')
                created_by = view.get('created_by', 'N/A')
                is_shared = view.get('is_shared', False)
                print(f"  {i:2d}. {view_name:<25} | ID: {view_id} | Shared: {is_shared} | Created by: {created_by}")
            
            return smart_views
        else:
            print(f"ERROR: {response.status_code} - {response.text}")
            return []
            
    except Exception as e:
        print(f"EXCEPTION: {e}")
        return []

def test_smart_view_access(api_key: str, view_id: str, view_name: str) -> Tuple[bool, int, Dict]:
    """Test basic access to a smart view"""
    print(f"\n" + "-"*40)
    print(f"TESTING ACCESS: {view_name}")
    print(f"View ID: {view_id}")
    print("-"*40)
    
    url = "https://api.close.com/api/v1/data/search/"
    headers = get_close_headers(api_key)
    
    payload = {
        "query": {
            "type": "saved_search",
            "saved_search_id": view_id
        },
        "_fields": {
            "lead": ["id", "display_name", "status_id"]
        },
        "_limit": 200
    }
    
    try:
        print(f"Making API request...")
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        print(f"Response received. Status Code: {response.status_code}")
        
        if response.status_code == 200:
            try:
                data = response.json()
                leads = data.get('data', [])
                cursor = data.get('cursor')
                has_more = data.get('has_more')
                
                print(f"Leads returned: {len(leads)}")
                print(f"Cursor present: {cursor is not None}")
                print(f"Cursor value: {cursor[:50] + '...' if cursor and len(cursor) > 50 else cursor}")
                print(f"Has_more field: {has_more}")
                print(f"Response keys: {list(data.keys())}")
                
                if leads:
                    print(f"Sample lead ID: {leads[0].get('id', 'N/A')}")
                    return True, len(leads), data
                else:
                    print("WARNING: No leads returned")
                    return False, 0, data
            except json.JSONDecodeError as e:
                print(f"JSON DECODE ERROR: {e}")
                print(f"Raw response: {response.text[:200]}...")
                return False, 0, {}
        else:
            print(f"ERROR: {response.status_code}")
            try:
                error_text = response.text[:500]
                print(f"Error response: {error_text}")
            except:
                print("Could not read error response")
            return False, 0, {}
            
    except requests.exceptions.Timeout:
        print(f"TIMEOUT: Request took longer than 30 seconds")
        return False, 0, {}
    except requests.exceptions.ConnectionError as e:
        print(f"CONNECTION ERROR: {e}")
        return False, 0, {}
    except requests.exceptions.RequestException as e:
        print(f"REQUEST EXCEPTION: {e}")
        return False, 0, {}
    except Exception as e:
        print(f"UNEXPECTED EXCEPTION: {e}")
        return False, 0, {}

def test_cursor_pagination(api_key: str, view_id: str, view_name: str, max_pages: int = 5) -> Dict:
    """Test cursor-based pagination behavior"""
    print(f"\n" + "="*60)
    print(f"TESTING CURSOR PAGINATION: {view_name}")
    print("="*60)
    
    url = "https://api.close.com/api/v1/data/search/"
    headers = get_close_headers(api_key)
    
    total_leads = 0
    page_count = 0
    cursor = None
    pagination_log = []
    
    while page_count < max_pages:
        page_count += 1
        
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
        
        print(f"\nPage {page_count}:")
        print(f"  Cursor: {cursor[:50] + '...' if cursor and len(cursor) > 50 else cursor}")
        
        try:
            print(f"  Making API request...")
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            print(f"  Response received. Status: {response.status_code}")
            
            if response.status_code != 200:
                error_text = response.text[:200] if hasattr(response, 'text') else 'Unknown error'
                print(f"  ERROR: {response.status_code} - {error_text}")
                break
            
            try:
                data = response.json()
            except json.JSONDecodeError as e:
                print(f"  JSON DECODE ERROR: {e}")
                break
            
            # DEBUG: Show actual response structure
            print(f"  RAW RESPONSE KEYS: {list(data.keys())}")
            if len(data.keys()) < 10:  # Only show full structure if small
                print(f"  RAW RESPONSE: {data}")
                
            leads = data.get('data', [])
            new_cursor = data.get('cursor')
            has_more = data.get('has_more')
            
            print(f"  Leads: {len(leads)}")
            print(f"  New cursor: {new_cursor[:50] + '...' if new_cursor and len(new_cursor) > 50 else new_cursor}")
            print(f"  Has_more: {has_more}")
            print(f"  Has_more type: {type(has_more)}")
            
            # Log this page
            pagination_log.append({
                'page': page_count,
                'leads_count': len(leads),
                'cursor_in': cursor,
                'cursor_out': new_cursor,
                'has_more': has_more,
                'total_so_far': total_leads + len(leads)
            })
            
            total_leads += len(leads)
            
            # Check termination conditions
            if len(leads) == 0:
                print(f"  STOP: No leads returned")
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
            
            cursor = new_cursor
            time.sleep(1)  # Rate limiting
            
        except requests.exceptions.Timeout:
            print(f"  TIMEOUT: Request took longer than 30 seconds")
            break
        except requests.exceptions.ConnectionError as e:
            print(f"  CONNECTION ERROR: {e}")
            break
        except requests.exceptions.RequestException as e:
            print(f"  REQUEST EXCEPTION: {e}")
            break
        except Exception as e:
            print(f"  UNEXPECTED EXCEPTION: {e}")
            break
    
    print(f"\nPAGINATION SUMMARY:")
    print(f"  Total pages: {page_count}")
    print(f"  Total leads: {total_leads}")
    print(f"  Final cursor: {cursor}")
    
    return {
        'total_pages': page_count,
        'total_leads': total_leads,
        'pagination_log': pagination_log,
        'final_cursor': cursor
    }

def test_offset_pagination(api_key: str, view_id: str, view_name: str, max_pages: int = 5) -> Dict:
    """Test offset-based pagination behavior"""
    print(f"\n" + "="*60)
    print(f"TESTING OFFSET PAGINATION: {view_name}")
    print("="*60)
    
    url = "https://api.close.com/api/v1/data/search/"
    headers = get_close_headers(api_key)
    
    total_leads = 0
    page_count = 0
    skip = 0
    limit = 200
    pagination_log = []
    
    while page_count < max_pages:
        page_count += 1
        
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
        
        print(f"\nPage {page_count}:")
        print(f"  Skip: {skip}, Limit: {limit}")
        
        try:
            response = requests.post(url, headers=headers, json=payload)
            
            if response.status_code != 200:
                print(f"  ERROR: {response.status_code} - {response.text}")
                break
            
            data = response.json()
            leads = data.get('data', [])
            has_more = data.get('has_more')
            
            print(f"  Leads: {len(leads)}")
            print(f"  Has_more: {has_more}")
            
            # Log this page
            pagination_log.append({
                'page': page_count,
                'leads_count': len(leads),
                'skip': skip,
                'limit': limit,
                'has_more': has_more,
                'total_so_far': total_leads + len(leads)
            })
            
            total_leads += len(leads)
            
            # Check termination conditions
            if len(leads) == 0:
                print(f"  STOP: No leads returned")
                break
            
            if has_more is False:
                print(f"  STOP: has_more is False")
                break
            
            if len(leads) < limit:
                print(f"  STOP: Fewer leads than limit ({len(leads)} < {limit})")
                break
            
            skip += limit
            time.sleep(1)  # Rate limiting
            
        except Exception as e:
            print(f"  EXCEPTION: {e}")
            break
    
    print(f"\nOFFSET PAGINATION SUMMARY:")
    print(f"  Total pages: {page_count}")
    print(f"  Total leads: {total_leads}")
    print(f"  Final skip: {skip}")
    
    return {
        'total_pages': page_count,
        'total_leads': total_leads,
        'pagination_log': pagination_log,
        'final_skip': skip
    }

def save_results(results: Dict, filename: str = "close_api_test_results.json"):
    """Save test results to JSON file"""
    with open(filename, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"\nResults saved to: {filename}")

def main():
    """Main test execution"""
    print("Close CRM API Exploration Script")
    print("=" * 50)
    
    # Load environment variables
    env_vars = load_env()
    if not env_vars:
        return
    
    api_key = env_vars.get('CLOSE_API_KEY')
    if not api_key:
        print("ERROR: CLOSE_API_KEY not found in .env file")
        return
    
    print(f"Using API key: {api_key[:10]}...")
    
    # Test 1: Get all smart views
    smart_views = get_smart_views(api_key)
    if not smart_views:
        print("FAILED: Could not retrieve smart views")
        return
    
    # Test 2: Test access to each smart view (with rate limiting and skip option)
    print(f"\n" + "="*60)
    print(f"SMART VIEW ACCESS TESTING")
    print("="*60)
    
    # Option to test only a subset of views
    test_choice = input(f"\nTest all {len(smart_views)} views? (y/n/number): ").strip().lower()
    
    views_to_test = smart_views
    if test_choice == 'n':
        print("Skipping smart view access testing...")
        access_results = {}
    elif test_choice.isdigit():
        max_views = int(test_choice)
        views_to_test = smart_views[:max_views]
        print(f"Testing first {max_views} views only...")
    else:
        print(f"Testing all {len(smart_views)} views...")
    
    access_results = {}
    total_views = len(views_to_test)
    
    for i, view in enumerate(views_to_test, 1):
        view_id = view.get('id')
        view_name = view.get('name', 'Unnamed')
        
        print(f"\nProgress: {i}/{total_views} views tested")
        
        if view_id:
            try:
                success, count, data = test_smart_view_access(api_key, view_id, view_name)
                access_results[view_name] = {
                    'view_id': view_id,
                    'accessible': success,
                    'initial_count': count,
                    'response_keys': list(data.keys()) if data else [],
                    'has_cursor': 'cursor' in data if data else False,
                    'has_more_field': 'has_more' in data if data else False
                }
                
                # Rate limiting between tests
                if i < total_views:  # Don't sleep after the last one
                    time.sleep(2)
                    
            except KeyboardInterrupt:
                print(f"\nUser interrupted. Stopping at view {i}/{total_views}")
                print("Partial results will be saved...")
                break
            except Exception as e:
                print(f"CRITICAL ERROR testing view {view_name}: {e}")
                access_results[view_name] = {
                    'view_id': view_id,
                    'accessible': False,
                    'error': str(e),
                    'initial_count': 0,
                    'response_keys': [],
                    'has_cursor': False,
                    'has_more_field': False
                }
    
    # Test 3: Select views for pagination testing
    accessible_views = {name: info for name, info in access_results.items() if info['accessible']}
    
    if not accessible_views:
        print("\nERROR: No accessible smart views found for pagination testing")
        return
    
    print(f"\n" + "="*60)
    print(f"ACCESSIBLE VIEWS FOR PAGINATION TESTING")
    print("="*60)
    
    for i, (name, info) in enumerate(accessible_views.items(), 1):
        print(f"  {i:2d}. {name:<25} | Initial count: {info['initial_count']}")
    
    # Select a view for detailed testing
    try:
        choice = input(f"\nSelect view for pagination testing (1-{len(accessible_views)}): ")
        choice_idx = int(choice) - 1
        selected_view_name = list(accessible_views.keys())[choice_idx]
        selected_view_info = accessible_views[selected_view_name]
        
        print(f"\nSelected: {selected_view_name}")
        
        # Test both pagination methods
        print(f"\nTesting with recommended _skip/_limit pagination first...")
        offset_results = test_offset_pagination(
            api_key, 
            selected_view_info['view_id'], 
            selected_view_name,
            max_pages=10
        )
        
        print(f"\nTesting cursor pagination (may have issues)...")
        cursor_results = test_cursor_pagination(
            api_key, 
            selected_view_info['view_id'], 
            selected_view_name,
            max_pages=10
        )
        
        # Compile final results
        final_results = {
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'smart_views': {view['name']: view for view in smart_views},
            'access_results': access_results,
            'selected_view': selected_view_name,
            'cursor_pagination': cursor_results,
            'offset_pagination': offset_results
        }
        
        # Save results
        save_results(final_results)
        
        # Summary
        print(f"\n" + "="*60)
        print(f"FINAL SUMMARY")
        print("="*60)
        print(f"Total smart views: {len(smart_views)}")
        print(f"Accessible views: {len(accessible_views)}")
        print(f"Selected view: {selected_view_name}")
        print(f"Cursor pagination - Total leads: {cursor_results['total_leads']}")
        print(f"Offset pagination - Total leads: {offset_results['total_leads']}")
        
        if cursor_results['total_leads'] != offset_results['total_leads']:
            print(f"WARNING: Pagination methods returned different counts!")
        
    except (ValueError, IndexError):
        print("Invalid selection")
        return
    except KeyboardInterrupt:
        print("\nTest interrupted by user")
        return

if __name__ == "__main__":
    main()

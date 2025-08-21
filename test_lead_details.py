import os
import json
import requests
from dotenv import load_dotenv
from base64 import b64encode

def test_lead_search_with_fields():
    """
    Simple test to see what lead details we can get
    """
    load_dotenv()
    api_key = os.getenv('CLOSE_API_KEY')
    encoded_key = b64encode(f"{api_key}:".encode('utf-8')).decode('utf-8')
    
    headers = {
        'Authorization': f'Basic {encoded_key}',
        'Content-Type': 'application/json',
    }
    
    # Simple search for leads with a specific domain
    test_domain = "forthrpeople.com"
    
    print(f"Testing lead search for domain: {test_domain}")
    
    # Test 1: Basic search (just IDs)
    print("\n=== Test 1: Basic Search (IDs only) ===")
    data1 = {
        "queries": [
            {
                "type": "object_type",
                "object_type": "lead"
            },
            {
                "type": "field_condition",
                "field": {
                    "type": "regular_field",
                    "object_type": "lead",
                    "field_name": "contacts"
                },
                "condition": {
                    "type": "text",
                    "mode": "contains",
                    "value": f"@{test_domain}"
                }
            }
        ]
    }
    
    response1 = requests.post('https://api.close.com/api/v1/data/search/', headers=headers, json=data1)
    print(f"Status: {response1.status_code}")
    if response1.status_code == 200:
        result1 = response1.json()
        print(f"Results: {len(result1.get('data', []))}")
        if result1.get('data'):
            print(f"Sample result: {json.dumps(result1['data'][0], indent=2)}")
    else:
        print(f"Error: {response1.text}")
    
    # Test 2: Search with specific fields
    print("\n=== Test 2: Search with Lead Fields ===")
    data2 = {
        "queries": [
            {
                "type": "object_type",
                "object_type": "lead"
            },
            {
                "type": "field_condition",
                "field": {
                    "type": "regular_field",
                    "object_type": "lead",
                    "field_name": "contacts"
                },
                "condition": {
                    "type": "text",
                    "mode": "contains",
                    "value": f"@{test_domain}"
                }
            }
        ],
        "_fields": {
            "lead": ["id", "display_name", "name", "contacts", "custom"]
        }
    }
    
    response2 = requests.post('https://api.close.com/api/v1/data/search/', headers=headers, json=data2)
    print(f"Status: {response2.status_code}")
    if response2.status_code == 200:
        result2 = response2.json()
        print(f"Results: {len(result2.get('data', []))}")
        if result2.get('data'):
            print(f"Sample result: {json.dumps(result2['data'][0], indent=2)}")
            
            # Save full response for analysis
            with open(f"test_leads_{test_domain.replace('.', '_')}.json", 'w') as f:
                json.dump(result2, f, indent=2)
            print(f"Full response saved to test_leads_{test_domain.replace('.', '_')}.json")
    else:
        print(f"Error: {response2.text}")

if __name__ == "__main__":
    test_lead_search_with_fields()

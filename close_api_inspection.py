# field_discovery.py
import requests
import json
from base64 import b64encode
import os
from dotenv import load_dotenv

load_dotenv()

def discover_custom_fields():
    api_key = os.getenv('CLOSE_API_KEY')
    auth_header = b64encode(f"{api_key}:".encode()).decode()
    
    # Get a single lead to see its structure
    url = "https://api.close.com/api/v1/lead/?limit=10"
    headers = {'Authorization': f'Basic {auth_header}'}
    
    response = requests.get(url, headers=headers)
    lead = response.json()['data'][0]
    
    # Print all custom fields found
    print("CUSTOM FIELDS DISCOVERED:")
    print("=" * 50)
    names = []
    
    for contact in lead.get('contacts', []):
        for key, value in contact.items():
            if key.startswith('custom.cf_'):
                print(f"Field ID: {key}")
                print(f"Value: {value}")
                print("-" * 30)


discover_custom_fields()
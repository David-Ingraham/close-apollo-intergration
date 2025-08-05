import os
from dotenv import load_dotenv
import requests
import json

# Load environment variables
load_dotenv()

def test_apollo_connection():
    # Get API key from environment
    api_key = os.getenv('APOLLO_API_KEY')
    if not api_key:
        raise ValueError("APOLLO_API_KEY not found in environment variables")

    # Apollo API health check endpoint
    url = 'https://api.apollo.io/v1/auth/health'
    
    headers = {
        'X-Api-Key': api_key,
        'Cache-Control': 'no-cache',
        'Content-Type': 'application/json'
    }

    try:
        # Make the request
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        # Parse the response
        data = response.json()
        
        print("Successfully connected to Apollo API!")
        print(f"Status Code: {response.status_code}")
        print("Response:")
        print(json.dumps(data, indent=2))
        
        return data
        
    except requests.exceptions.RequestException as e:
        print(f"Error connecting to Apollo API: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response status: {e.response.status_code}")
            print(f"Response text: {e.response.text}")
        return None
    except Exception as e:
        print(f"Unexpected error: {e}")
        return None

if __name__ == "__main__":
    print("Testing Apollo API connection...")
    result = test_apollo_connection()
    if result:
        print("\nApollo API connection test successful!")
    else:
        print("\nApollo API connection test failed!")
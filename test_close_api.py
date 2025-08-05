import os
from dotenv import load_dotenv
import requests
import base64

# Load environment variables
load_dotenv()

def test_close_api_connection():
    # Get API key from environment
    api_key = os.getenv('CLOSE_API_KEY')
    if not api_key:
        raise ValueError("CLOSE_API_KEY not found in environment variables")

    # Create the base64 encoded auth string (API key + ':')
    auth_string = base64.b64encode(f"{api_key}:".encode('utf-8')).decode('utf-8')

    # Set up the request
    url = 'https://api.close.com/api/v1/me/'
    headers = {
        'Authorization': f'Basic {auth_string}',
        'Content-Type': 'application/json'
    }

    try:
        # Make the request
        response = requests.get(url, headers=headers)
        
        # Print status code and rate limit info
        print(f"\nStatus Code: {response.status_code}")
        print("\nRate Limit Info:")
        for header in response.headers:
            if 'ratelimit' in header.lower():
                print(f"{header}: {response.headers[header]}")

        # If successful, print the response
        if response.status_code == 200:
            print("\nSuccess! Response data:")
            print(response.json())
        else:
            print("\nError Response:")
            print(response.text)

    except requests.exceptions.RequestException as e:
        print(f"\nError making request: {e}")

if __name__ == "__main__":
    print("Testing Close API connection...")
    test_close_api_connection()

import os
from dotenv import load_dotenv
import requests
import base64

# Load environment variables
load_dotenv()

def get_smart_views():
    # Get API key from environment
    api_key = os.getenv('CLOSE_API_KEY')
    if not api_key:
        raise ValueError("CLOSE_API_KEY not found in environment variables")

    # Create the base64 encoded auth string (API key + ':') - SAME AS TEST SCRIPT
    auth_string = base64.b64encode(f"{api_key}:".encode('utf-8')).decode('utf-8')

    # Set up the request
    url = 'https://api.close.com/api/v1/saved_search/'
    headers = {
        'Authorization': f'Basic {auth_string}',  # Using same auth method as test script
        'Content-Type': 'application/json'
    }

    try:
        # Make the request
        response = requests.get(url, headers=headers)
        
        # Print status code
        print(f"\nStatus Code: {response.status_code}")

        if response.status_code == 200:
            # Get the data
            data = response.json()
            
            # Print all Smart Views with their IDs
            print("\nAvailable Smart Views:")
            print("-" * 50)
            
            # Store all views for searching
            all_views = data['data']
            
            for view in all_views:
                print(f"Name: {view['name']}")
                print(f"ID: {view['id']}")
                print("-" * 50)
            
            # Search for the specific view you're looking for
            print(f"\nTotal views found: {len(all_views)}")
            print("\nSearching for 'Closed Won' views:")
            closed_won_views = [v for v in all_views if 'closed won' in v['name'].lower()]
            
            if closed_won_views:
                print("Found Closed Won views:")
                for view in closed_won_views:
                    print(f"  Name: {view['name']}")
                    print(f"  ID: {view['id']}")
            else:
                print("No 'Closed Won' views found.")
                print("\nSearching for any 'won' or 'closed' views:")
                related_views = [v for v in all_views if 'won' in v['name'].lower() or 'closed' in v['name'].lower()]
                for view in related_views:
                    print(f"  Name: {view['name']}")
                    print(f"  ID: {view['id']}")
            
            # Check if there might be more results (pagination)
            has_more = data.get('has_more', False)
            if has_more:
                print(f"\nWARNING: There are more views available (pagination). This only shows the first page.")
                print("Consider adding pagination to see all views.")
        else:
            print("\nError Response:")
            print(response.text)

    except requests.exceptions.RequestException as e:
        print(f"\nError making request: {e}")

if __name__ == "__main__":
    print("Fetching Smart Views from Close...")
    get_smart_views()
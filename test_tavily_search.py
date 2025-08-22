import os
import requests
import json
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_tavily_search(attorney_name, location="", attorney_email=""):
    """
    Test Tavily Search API to find law firm websites
    """
    api_key = os.getenv('TAVILY_API_KEY')
    if not api_key:
        print("Error: TAVILY_API_KEY not found in .env file")
        print("Please add TAVILY_API_KEY=your_key_here to your .env file")
        return None
    
    # Build search query
    query_parts = [attorney_name, "personal injury lawyer"]
    if location:
        query_parts.append(location)
    query_parts.append("website")
    
    search_query = " ".join(query_parts)
    
    print(f"Searching for: '{search_query}'")
    print(f"Attorney Email: {attorney_email}")
    
    # Tavily API endpoint
    url = "https://api.tavily.com/search"
    
    payload = {
        "api_key": api_key,
        "query": search_query,
        "search_depth": "basic",  # "basic" or "advanced"
        "include_answer": True,   # Get AI-generated answer
        "include_raw_content": False,  # Don't need full page content
        "max_results": 5,         # Limit results
        "include_domains": [],    # No domain restrictions
        "exclude_domains": ["facebook.com", "linkedin.com", "twitter.com"]  # Skip social media
    }
    
    try:
        print("Making API call to Tavily...")
        response = requests.post(url, json=payload, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            
            print(f"✅ Search successful!")
            print(f"Query: {data.get('query', 'N/A')}")
            print(f"Answer: {data.get('answer', 'No AI answer provided')}")
            
            results = data.get('results', [])
            print(f"\nFound {len(results)} results:")
            
            # Look for law firm websites
            potential_websites = []
            
            for i, result in enumerate(results, 1):
                title = result.get('title', 'No title')
                url = result.get('url', 'No URL')
                content = result.get('content', 'No content')
                
                print(f"\n--- Result {i} ---")
                print(f"Title: {title}")
                print(f"URL: {url}")
                print(f"Content: {content[:200]}...")
                
                # Simple website extraction
                if 'law' in url.lower() or 'attorney' in url.lower() or attorney_name.lower().replace(' ', '') in url.lower():
                    potential_websites.append({
                        'url': url,
                        'title': title,
                        'confidence': 'high'
                    })
            
            print(f"\n🎯 Potential Law Firm Websites:")
            if potential_websites:
                for site in potential_websites:
                    print(f"  • {site['url']} - {site['title']}")
                return potential_websites[0]['url']  # Return best match
            else:
                print("  No obvious law firm websites found")
                return None
                
        else:
            print(f"❌ API Error: {response.status_code}")
            print(f"Response: {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ Request Error: {e}")
        return None

if __name__ == "__main__":
    print("=" * 60)
    print("TAVILY SEARCH API TEST")
    print("=" * 60)
    
    # Test cases
    test_cases = [
        {
            "attorney_name": "Parrish DeVaughn",
            "location": "Oklahoma",
            "attorney_email": "aleenasparks8@gmail.com"
        },
        {
            "attorney_name": "John Smith",
            "location": "Texas",
            "attorney_email": "jsmith@gmail.com"
        },
        {
            "attorney_name": "Morgan & Morgan",
            "location": "Florida",
            "attorney_email": "contact@gmail.com"
        }
    ]
    
    for i, case in enumerate(test_cases, 1):
        print(f"\n{'='*20} TEST CASE {i} {'='*20}")
        result = test_tavily_search(
            case["attorney_name"], 
            case["location"], 
            case["attorney_email"]
        )
        
        if result:
            print(f"🎉 Found website: {result}")
        else:
            print("😞 No website found")
        
        print("\n" + "-" * 60) 
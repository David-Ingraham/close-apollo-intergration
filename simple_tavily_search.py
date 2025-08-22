import os
import requests
import json
import time
import re
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def extract_domain_from_text(text):
    """Extract domains from text using regex"""
    # Look for domain patterns like website.com or www.website.com
    domain_pattern = r'(?:https?://)?(?:www\.)?([a-zA-Z0-9-]+\.[a-zA-Z]{2,})'
    matches = re.findall(domain_pattern, text)
    
    # Filter out common non-law-firm domains
    excluded_domains = {
        'facebook.com', 'linkedin.com', 'twitter.com', 'yelp.com', 
        'yellowpages.com', 'google.com', 'bing.com'
    }
    
    for match in matches:
        if match.lower() not in excluded_domains:
            return match.lower()
    
    return None

def search_firm_website_simple(attorney_name, state_code="", lead_address=""):
    """
    Simple search using Tavily's AI answer feature
    """
    api_key = os.getenv('TAVILY_API_KEY')
    if not api_key:
        return {"error": "TAVILY_API_KEY not found in .env file"}
    
    # Build search query focused on finding the website
    query = f"What is the website for {attorney_name} personal injury lawyer in {state_code}?"
    
    print(f"Query: {query}")
    
    # Tavily API call
    url = "https://api.tavily.com/search"
    payload = {
        "api_key": api_key,
        "query": query,
        "search_depth": "basic",
        "include_answer": True,  # Let Tavily's AI provide the answer
        "include_raw_content": False,
        "max_results": 3,  # Fewer results, trust Tavily's ranking
        "include_domains": [],
        "exclude_domains": [
            "facebook.com", "linkedin.com", "twitter.com", "yelp.com",
            "yellowpages.com", "wikipedia.org"
        ]
    }
    
    try:
        response = requests.post(url, json=payload, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            
            # First, try to extract domain from AI answer
            ai_answer = data.get('answer', '')
            if ai_answer:
                print(f"AI Answer: {ai_answer}")
                domain_from_answer = extract_domain_from_text(ai_answer)
                if domain_from_answer:
                    return {
                        "success": True,
                        "domain": domain_from_answer,
                        "source": "ai_answer",
                        "ai_answer": ai_answer
                    }
            
            # Fallback: Use first result URL
            results = data.get('results', [])
            if results:
                first_result = results[0]
                url_result = first_result.get('url', '')
                title = first_result.get('title', '')
                
                # Extract domain from URL
                try:
                    domain = url_result.split('//')[1].split('/')[0]
                    if domain.startswith('www.'):
                        domain = domain[4:]
                    
                    return {
                        "success": True,
                        "domain": domain,
                        "source": "first_result",
                        "url": url_result,
                        "title": title
                    }
                except:
                    pass
            
            return {
                "success": False,
                "error": "No website found in results",
                "ai_answer": ai_answer
            }
                
        else:
            return {"error": f"API Error: {response.status_code}"}
            
    except Exception as e:
        return {"error": str(e)}

def test_simple_search():
    """Test the simplified approach"""
    print("=" * 80)
    print("SIMPLE TAVILY SEARCH TEST")
    print("=" * 80)
    
    # Test cases including previous problematic ones
    test_cases = [
        {"attorney": "Alexander shunnarah", "state": "AL"},
        {"attorney": "Bennett Robbins", "state": "NJ"},
        {"attorney": "Daron Satterfield", "state": "NC"},
        {"attorney": "Doug Rallo", "state": "IL"},
        {"attorney": "Longoria law", "state": "TX"},  # Changed from NM to TX since that's where Houston is
    ]
    
    results = []
    
    for i, case in enumerate(test_cases, 1):
        print(f"\n--- Test {i}/{len(test_cases)} ---")
        print(f"Attorney: {case['attorney']}")
        print(f"State: {case['state']}")
        
        result = search_firm_website_simple(case['attorney'], case['state'])
        
        if result.get('success'):
            print(f"SUCCESS: {result['domain']}")
            print(f"  Source: {result['source']}")
            if result.get('ai_answer'):
                print(f"  AI Answer: {result['ai_answer'][:100]}...")
        else:
            print(f"FAILED: {result.get('error')}")
        
        results.append(result)
        
        # Rate limiting
        if i < len(test_cases):
            print("Waiting 2 seconds...")
            time.sleep(2)
    
    # Summary
    print("\n" + "=" * 80)
    print("SIMPLE SEARCH RESULTS")
    print("=" * 80)
    
    successful = [r for r in results if r.get('success')]
    print(f"Successful: {len(successful)}/{len(test_cases)}")
    
    for result in successful:
        print(f"  {result['domain']} ({result['source']})")

if __name__ == "__main__":
    test_simple_search() 
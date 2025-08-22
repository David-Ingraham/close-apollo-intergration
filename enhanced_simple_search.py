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
    domain_pattern = r'(?:https?://)?(?:www\.)?([a-zA-Z0-9-]+\.[a-zA-Z]{2,})'
    matches = re.findall(domain_pattern, text)
    
    # Filter out common directory domains
    excluded_domains = {
        'facebook.com', 'linkedin.com', 'twitter.com', 'yelp.com', 
        'yellowpages.com', 'google.com', 'bing.com', 'mapquest.com',
        'avvo.com', 'lawyer.com', 'justia.com', 'findlaw.com'
    }
    
    for match in matches:
        if match.lower() not in excluded_domains:
            return match.lower()
    
    return None

def search_firm_website_enhanced(attorney_name, state_code="", lead_address=""):
    """
    Enhanced search with primary query and law office fallback
    """
    api_key = os.getenv('TAVILY_API_KEY')
    if not api_key:
        return {"error": "TAVILY_API_KEY not found in .env file"}
    
    # Primary query (keep exactly as is)
    primary_query = f"What is the website for {attorney_name} personal injury lawyer in {state_code}?"
    
    # Fallback query (try law office/law firm phrasing)
    fallback_query = f"What is the website for {attorney_name} law office in {state_code}?"
    
    queries = [primary_query, fallback_query]
    
    for i, query in enumerate(queries, 1):
        print(f"Query {i}: {query}")
        
        # Tavily API call
        url = "https://api.tavily.com/search"
        payload = {
            "api_key": api_key,
            "query": query,
            "search_depth": "basic",
            "include_answer": True,
            "include_raw_content": False,
            "max_results": 3,
            "include_domains": [],
            "exclude_domains": [
                "facebook.com", "linkedin.com", "twitter.com", "yelp.com",
                "yellowpages.com", "wikipedia.org", "mapquest.com"
            ]
        }
        
        try:
            response = requests.post(url, json=payload, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                
                # Try to extract domain from AI answer
                ai_answer = data.get('answer', '')
                if ai_answer:
                    print(f"AI Answer: {ai_answer}")
                    domain_from_answer = extract_domain_from_text(ai_answer)
                    if domain_from_answer:
                        return {
                            "success": True,
                            "domain": domain_from_answer,
                            "source": f"ai_answer_query_{i}",
                            "query_used": query,
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
                        
                        # Check if it's not a directory site
                        excluded_domains = {
                            'avvo.com', 'lawyer.com', 'justia.com', 'mapquest.com',
                            'yellowpages.com', 'findlaw.com'
                        }
                        
                        if domain.lower() not in excluded_domains:
                            return {
                                "success": True,
                                "domain": domain,
                                "source": f"first_result_query_{i}",
                                "query_used": query,
                                "url": url_result,
                                "title": title
                            }
                    except:
                        pass
            
            # Small delay between queries
            if i < len(queries):
                print("Trying fallback query...")
                time.sleep(1)
                
        except Exception as e:
            print(f"Query {i} failed: {e}")
            continue
    
    return {
        "success": False,
        "error": "No quality website found in any query",
        "queries_tried": len(queries)
    }

def test_enhanced_search():
    """Test with both query approaches"""
    print("=" * 80)
    print("ENHANCED SIMPLE SEARCH TEST")
    print("=" * 80)
    
    # Test the problematic cases from before
    test_cases = [
        {"attorney": "Bennett Robbins", "state": "NJ"},
        {"attorney": "Daron Satterfield", "state": "NC"},
        {"attorney": "Alexander shunnarah", "state": "AL"},
        {"attorney": "Mark L karno", "state": "IL"},
    ]
    
    results = []
    
    for i, case in enumerate(test_cases, 1):
        print(f"\n--- Test {i}/{len(test_cases)} ---")
        print(f"Attorney: {case['attorney']}")
        print(f"State: {case['state']}")
        
        result = search_firm_website_enhanced(case['attorney'], case['state'])
        
        if result.get('success'):
            print(f"SUCCESS: {result['domain']}")
            print(f"  Source: {result['source']}")
            print(f"  Query Used: {result['query_used']}")
        else:
            print(f"FAILED: {result.get('error')}")
        
        results.append(result)
        
        # Rate limiting between tests
        if i < len(test_cases):
            print("Waiting 3 seconds...")
            time.sleep(3)
    
    # Summary
    print("\n" + "=" * 80)
    print("ENHANCED SEARCH RESULTS")
    print("=" * 80)
    
    successful = [r for r in results if r.get('success')]
    print(f"Successful: {len(successful)}/{len(test_cases)}")
    
    for result in successful:
        query_num = result['source'].split('_')[-1]
        print(f"  {result['domain']} (Query {query_num})")

if __name__ == "__main__":
    test_enhanced_search() 
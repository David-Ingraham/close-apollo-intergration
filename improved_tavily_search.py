import os
import requests
import json
import time
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def is_directory_site(domain):
    """Check if domain is a directory/listing site rather than actual law firm"""
    directory_domains = {
        'lawyer.com', 'lawyers.com', 'avvo.com', 'justia.com', 'findlaw.com',
        'martindale.com', 'superlawyers.com', 'law.com', 'hg.org',
        'rocketreach.co', 'law.usnews.com', 'yellowpages.com', 'yelp.com',
        'creators.spotify.com', 'linkedin.com', 'facebook.com', 'twitter.com',
        'wikipedia.org', 'google.com', 'bing.com'
    }
    return domain.lower() in directory_domains

def extract_domain_from_url(url):
    """Extract clean domain from URL"""
    try:
        domain = url.split('//')[1].split('/')[0]
        if domain.startswith('www.'):
            domain = domain[4:]
        return domain
    except:
        return None

def score_law_firm_result(url, title, content=""):
    """Score how likely this result is an actual law firm website"""
    domain = extract_domain_from_url(url)
    if not domain:
        return 0
    
    score = 0
    
    # Negative scoring for directory sites
    if is_directory_site(domain):
        return -10
    
    # Positive scoring for law firm indicators
    law_keywords = ['law', 'attorney', 'legal', 'injury', 'firm']
    
    # Check domain for law keywords
    domain_lower = domain.lower()
    for keyword in law_keywords:
        if keyword in domain_lower:
            score += 3
    
    # Check title for law firm indicators
    title_lower = title.lower()
    if 'law firm' in title_lower or 'attorney' in title_lower:
        score += 5
    if 'personal injury' in title_lower:
        score += 3
    if 'lawyer' in title_lower:
        score += 2
    
    # Bonus for shorter, cleaner domains (likely firm sites)
    if len(domain.split('.')) == 2 and not domain.startswith('www'):
        score += 2
    
    # Check if domain contains business-like terms
    business_indicators = ['law', 'attorney', 'legal', 'firm', 'group', 'associates']
    for indicator in business_indicators:
        if indicator in domain_lower:
            score += 1
    
    return score

def search_firm_website_improved(attorney_name, state_code="", lead_address=""):
    """
    Improved search for law firm website using Tavily API with better filtering
    """
    api_key = os.getenv('TAVILY_API_KEY')
    if not api_key:
        return {"error": "TAVILY_API_KEY not found in .env file"}
    
    # Build search query - try multiple approaches
    queries = []
    
    # Primary query
    base_query = f'"{attorney_name}" personal injury lawyer {state_code} website'
    queries.append(base_query)
    
    # Alternative query
    alt_query = f'"{attorney_name}" law firm {state_code} site'
    queries.append(alt_query)
    
    best_result = None
    best_score = -999
    
    for query in queries:
        print(f"Trying query: {query}")
        
        # Tavily API call
        url = "https://api.tavily.com/search"
        payload = {
            "api_key": api_key,
            "query": query,
            "search_depth": "basic",
            "include_answer": True,
            "include_raw_content": False,
            "max_results": 8,  # Get more results to filter through
            "include_domains": [],
            "exclude_domains": [
                "facebook.com", "linkedin.com", "twitter.com", "yelp.com", 
                "yellowpages.com", "avvo.com", "lawyer.com", "justia.com",
                "findlaw.com", "martindale.com", "law.usnews.com", "hg.org",
                "rocketreach.co", "creators.spotify.com"
            ]
        }
        
        try:
            response = requests.post(url, json=payload, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                results = data.get('results', [])
                
                for result in results:
                    url_result = result.get('url', '')
                    title = result.get('title', '')
                    content = result.get('content', '')
                    
                    domain = extract_domain_from_url(url_result)
                    if not domain:
                        continue
                    
                    # Score this result
                    score = score_law_firm_result(url_result, title, content)
                    
                    print(f"  {domain} - Score: {score} - {title[:50]}...")
                    
                    if score > best_score:
                        best_score = score
                        best_result = {
                            "success": True,
                            "domain": domain,
                            "url": url_result,
                            "title": title,
                            "score": score,
                            "query_used": query
                        }
            
            # Small delay between queries
            time.sleep(1)
            
        except Exception as e:
            print(f"Query failed: {e}")
            continue
    
    # Return best result if score is reasonable
    if best_result and best_score > 0:
        return best_result
    else:
        return {
            "success": False,
            "error": "No high-quality law firm websites found",
            "best_score": best_score,
            "best_result": best_result
        }

def test_improved_search():
    """Test the improved search on problematic cases"""
    print("=" * 80)
    print("IMPROVED TAVILY SEARCH TEST")
    print("=" * 80)
    
    # Test the problematic cases from previous run
    test_cases = [
        {"attorney": "Daron Satterfield", "state": "NC"},
        {"attorney": "Junnell and asst", "state": "MA"},
        {"attorney": "Alexander shunnarah", "state": "AL"},
        {"attorney": "Mark L karno", "state": "IL"},
        {"attorney": "Robert Desota", "state": "CA"},
        {"attorney": "Robert kinsman", "state": "CT"},
    ]
    
    results = []
    
    for i, case in enumerate(test_cases, 1):
        print(f"\n--- Test {i}/{len(test_cases)} ---")
        print(f"Attorney: {case['attorney']}")
        print(f"State: {case['state']}")
        
        result = search_firm_website_improved(case['attorney'], case['state'])
        
        if result.get('success'):
            print(f"SUCCESS: {result['domain']} (Score: {result['score']})")
            print(f"  URL: {result['url']}")
            print(f"  Title: {result['title']}")
            print(f"  Query: {result['query_used']}")
        else:
            print(f"FAILED: {result.get('error')}")
            if result.get('best_result'):
                print(f"  Best attempt: {result['best_result']['domain']} (Score: {result['best_score']})")
        
        results.append(result)
        
        # Rate limiting
        if i < len(test_cases):
            print("Waiting 3 seconds...")
            time.sleep(3)
    
    # Summary
    print("\n" + "=" * 80)
    print("IMPROVED SEARCH RESULTS")
    print("=" * 80)
    
    successful = [r for r in results if r.get('success')]
    print(f"Successful: {len(successful)}/{len(test_cases)}")
    
    for result in successful:
        print(f"  {result['domain']} (Score: {result['score']})")

if __name__ == "__main__":
    test_improved_search() 
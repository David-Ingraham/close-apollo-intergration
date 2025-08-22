import os
import requests
import json
import time
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def search_firm_website(attorney_name, state_code="", lead_address=""):
    """
    Search for law firm website using Tavily API
    Returns the best matching domain or None
    """
    api_key = os.getenv('TAVILY_API_KEY')
    if not api_key:
        return {"error": "TAVILY_API_KEY not found in .env file"}
    
    # Build search query
    query_parts = [attorney_name, "personal injury lawyer"]
    if state_code:
        query_parts.append(state_code)
    query_parts.append("website")
    
    search_query = " ".join(query_parts)
    
    # Tavily API endpoint
    url = "https://api.tavily.com/search"
    
    payload = {
        "api_key": api_key,
        "query": search_query,
        "search_depth": "basic",
        "include_answer": True,
        "include_raw_content": False,
        "max_results": 5,
        "include_domains": [],
        "exclude_domains": ["facebook.com", "linkedin.com", "twitter.com", "yelp.com", "yellowpages.com"]
    }
    
    try:
        response = requests.post(url, json=payload, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            results = data.get('results', [])
            
            # Look for law firm websites
            potential_websites = []
            
            for result in results:
                url_result = result.get('url', '')
                title = result.get('title', '')
                
                # Simple website filtering - look for law firm domains
                if any(keyword in url_result.lower() for keyword in ['law', 'attorney', 'legal']):
                    # Extract domain from URL
                    try:
                        domain = url_result.split('//')[1].split('/')[0]
                        if domain.startswith('www.'):
                            domain = domain[4:]
                        potential_websites.append({
                            'domain': domain,
                            'url': url_result,
                            'title': title
                        })
                    except:
                        pass
                elif attorney_name.lower().replace(' ', '') in url_result.lower():
                    # Attorney name appears in URL
                    try:
                        domain = url_result.split('//')[1].split('/')[0]
                        if domain.startswith('www.'):
                            domain = domain[4:]
                        potential_websites.append({
                            'domain': domain,
                            'url': url_result,
                            'title': title
                        })
                    except:
                        pass
            
            if potential_websites:
                return {
                    "success": True,
                    "domain": potential_websites[0]['domain'],
                    "url": potential_websites[0]['url'],
                    "title": potential_websites[0]['title'],
                    "all_results": potential_websites
                }
            else:
                return {
                    "success": False,
                    "error": "No law firm websites found",
                    "raw_results": len(results)
                }
                
        else:
            return {"error": f"API Error: {response.status_code}"}
            
    except Exception as e:
        return {"error": str(e)}

def test_with_real_data():
    """
    Test Tavily search with real lead data from lawyers_of_lead_poor.json
    """
    print("=" * 80)
    print("TAVILY SEARCH TEST WITH REAL LEAD DATA")
    print("=" * 80)
    
    # Load the real lead data
    try:
        with open('lawyers_of_lead_poor.json', 'r') as f:
            leads_data = json.load(f)
    except FileNotFoundError:
        print("Error: lawyers_of_lead_poor.json not found")
        return
    
    leads = leads_data.get('leads', [])
    
    # Filter to only test leads that have skip reasons (these need web search)
    skipped_leads = [
        lead for lead in leads 
        if lead.get('skip_reason') is not None 
        and lead.get('attorney_firm') not in ['N/A', '', 'n/a']
    ]
    
    print(f"Found {len(skipped_leads)} leads with skip reasons to test")
    print(f"Total leads in file: {len(leads)}")
    
    # Test results tracking
    successful_searches = 0
    failed_searches = 0
    results_summary = []
    
    # Test each skipped lead
    for i, lead in enumerate(skipped_leads, 1):
        attorney_name = lead.get('attorney_firm', '')
        state_code = lead.get('state_code', '')
        client_name = lead.get('client_name', '')
        lead_address = lead.get('lead_address', '')
        
        print(f"\n--- Test {i}/{len(skipped_leads)} ---")
        print(f"Client: {client_name}")
        print(f"Attorney: {attorney_name}")
        print(f"State: {state_code}")
        print(f"Original Skip Reason: {lead.get('skip_reason')}")
        
        # Search for website
        result = search_firm_website(attorney_name, state_code, lead_address)
        
        if result.get('success'):
            print(f"SUCCESS: Found domain: {result['domain']}")
            print(f"  URL: {result['url']}")
            print(f"  Title: {result['title']}")
            successful_searches += 1
            
            results_summary.append({
                'client': client_name,
                'attorney': attorney_name,
                'state': state_code,
                'found_domain': result['domain'],
                'found_url': result['url'],
                'status': 'SUCCESS'
            })
        else:
            print(f"FAILED: {result.get('error', 'Unknown error')}")
            failed_searches += 1
            
            results_summary.append({
                'client': client_name,
                'attorney': attorney_name,
                'state': state_code,
                'found_domain': None,
                'found_url': None,
                'status': 'FAILED',
                'error': result.get('error')
            })
        
        # Rate limiting - wait between requests
        if i < len(skipped_leads):
            print("Waiting 2 seconds...")
            time.sleep(2)
    
    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY RESULTS")
    print("=" * 80)
    print(f"Total Tested: {len(skipped_leads)}")
    print(f"Successful: {successful_searches}")
    print(f"Failed: {failed_searches}")
    if len(skipped_leads) > 0:
        success_rate = (successful_searches / len(skipped_leads)) * 100
        print(f"Success Rate: {success_rate:.1f}%")
    
    print(f"\nSUCCESSFUL RECOVERIES:")
    for result in results_summary:
        if result['status'] == 'SUCCESS':
            print(f"  {result['attorney']} ({result['state']}) -> {result['found_domain']}")
    
    print(f"\nFAILED SEARCHES:")
    for result in results_summary:
        if result['status'] == 'FAILED':
            print(f"  {result['attorney']} ({result['state']}) -> {result.get('error', 'Unknown')}")
    
    # Save detailed results
    output_file = 'tavily_test_results.json'
    with open(output_file, 'w') as f:
        json.dump({
            'summary': {
                'total_tested': len(skipped_leads),
                'successful': successful_searches,
                'failed': failed_searches,
                'success_rate': (successful_searches / len(skipped_leads)) * 100 if len(skipped_leads) > 0 else 0
            },
            'detailed_results': results_summary
        }, f, indent=2)
    
    print(f"\nDetailed results saved to: {output_file}")

if __name__ == "__main__":
    test_with_real_data() 
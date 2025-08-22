import os
import json
import time
import re
import requests
from typing import Dict, List, Optional
from dotenv import load_dotenv

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

def search_firm_website_tavily(attorney_name, lead_state="", lead_address=""):
    """
    Search for law firm website using Tavily API with multiple query approaches
    """
    api_key = os.getenv('TAVILY_API_KEY')
    if not api_key:
        return {"error": "TAVILY_API_KEY not found in .env file"}
    
    # Build multiple query strategies
    queries = []
    
    # Primary query
    primary_query = f"What is the website for {attorney_name} personal injury lawyer in {lead_state}?"
    queries.append(primary_query)
    
    # Fallback query with law office phrasing
    fallback_query = f"What is the website for {attorney_name} law office in {lead_state}?"
    queries.append(fallback_query)
    
    for i, query in enumerate(queries, 1):
        print(f"    Tavily Query {i}: {query}")
        
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
                
                # First, try to extract domain from AI answer
                ai_answer = data.get('answer', '')
                if ai_answer:
                    print(f"    AI Answer: {ai_answer}")
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
                print(f"    Trying fallback query...")
                time.sleep(1)
                
        except Exception as e:
            print(f"    Query {i} failed: {e}")
            continue
    
    return {
        "success": False,
        "error": "No quality website found in any query",
        "queries_tried": len(queries)
    }

def validate_domain_with_apollo(domain):
    """
    Quick Apollo validation to see if domain returns any organizations
    Returns True if Apollo finds organizations, False otherwise
    """
    api_key = os.getenv('APOLLO_API_KEY')
    if not api_key:
        print(f"    Apollo validation skipped: No APOLLO_API_KEY")
        return True  # Assume valid if we can't validate
    
    headers = {
        'Content-Type': 'application/json',
        'Cache-Control': 'no-cache',
        'X-Api-Key': api_key
    }
    
    # Quick domain search
    url = "https://api.apollo.io/v1/mixed_companies/search"
    payload = {
        "q_organization_name": domain,
        "page": 1,
        "per_page": 10  # Small limit for quick validation
    }
    
    try:
        print(f"    Validating {domain} with Apollo...")
        response = requests.post(url, headers=headers, json=payload, timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            organizations = data.get('organizations') or data.get('accounts', [])
            found_count = len(organizations)
            print(f"    Apollo validation: {found_count} organizations found")
            return found_count > 0
        else:
            print(f"    Apollo validation failed: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"    Apollo validation error: {e}")
        return False

def classify_attorney_name(attorney_name: str, attorney_email: str, lead_state: str, lead_address: str, groq_api_key: str, retry_count: int = 3) -> Optional[Dict]:
    """
    Use Tavily + Apollo validation to find law firm websites with retry logic
    """
    print(f"    Finding website for: {attorney_name} in {lead_state}")
    
    for attempt in range(retry_count):
        print(f"    Attempt {attempt + 1}/{retry_count}")
        
        # Tavily search for firm website
        tavily_result = search_firm_website_tavily(attorney_name, lead_state, lead_address)
        
        if not tavily_result.get('success'):
            print(f"    Tavily search failed: {tavily_result.get('error', 'Unknown error')}")
            if attempt < retry_count - 1:
                print(f"    Retrying Tavily search...")
                time.sleep(2)
                continue
            else:
                return {"error": "Tavily search failed after all attempts"}
        
        domain = tavily_result['domain']
        print(f"    Tavily found domain: {domain}")
        
        # Validate with Apollo
        if validate_domain_with_apollo(domain):
            print(f"    SUCCESS: Apollo validated {domain}")
            return {
                "CONFIDENCE": "8",  # High confidence since Apollo validated
                "WEBSITE": domain,
                "tavily_source": tavily_result.get('source'),
                "query_used": tavily_result.get('query_used'),
                "apollo_validated": True
            }
        else:
            print(f"    Apollo validation failed for {domain}")
            if attempt < retry_count - 1:
                print(f"    Retrying with different Tavily results...")
                time.sleep(3)  # Longer delay before retry
                continue
            else:
                print(f"    All attempts failed - no Apollo validation")
                return {
                    "error": "No Apollo-validated domains found",
                    "last_domain_tried": domain
                }
    
    return {"error": "Max retries exceeded"}

def process_ai_recovery(leads_data: Dict, min_confidence: int = 7) -> List[Dict]:
    """
    Process skipped leads through Tavily + Apollo validation and recover viable firms
    
    Args:
        leads_data: The leads package from get_lawyer_contacts
        min_confidence: Minimum confidence to accept a recovery (1-10)
    
    Returns:
        List of recovered leads ready for Apollo enrichment
    """
    print("\n" + "=" * 60)
    print(" TAVILY + APOLLO LEAD RECOVERY PROCESS")
    print("=" * 60)
    
    # Check API keys
    tavily_key = os.getenv('TAVILY_API_KEY')
    apollo_key = os.getenv('APOLLO_API_KEY')
    
    if not tavily_key:
        print(" No TAVILY_API_KEY found in .env file")
        print("Skipping web search recovery - no leads will be recovered")
        return []
    
    if not apollo_key:
        print(" No APOLLO_API_KEY found in .env file")
        print("Will search with Tavily but cannot validate with Apollo")
    
    # Extract skipped leads
    all_leads = leads_data.get('leads', [])
    skipped_leads = [
        lead for lead in all_leads 
        if lead.get('skip_reason') is not None 
        and lead.get('attorney_firm')  # Must have attorney name
        and lead.get('attorney_firm') not in ['N/A', '', 'n/a', 'N/a']
    ]
    
    print(f" Found {len(skipped_leads)} skipped leads with attorney names")
    
    if not skipped_leads:
        print("   No leads available for Tavily recovery")
        return []
    
    print(f"Web search starting (with Apollo validation)")
    print(f"   Using retry logic: up to 3 attempts per lead")
    
    recovered_leads = []
    processed_count = 0
    website_recoveries = 0
    validation_failures = 0
    search_failures = 0
    
    for lead in skipped_leads:
        processed_count += 1
        attorney_name = lead.get('attorney_firm', '')
        attorney_email = lead.get('attorney_email', '')
        lead_state = lead.get('state_code', '') or ''
        lead_address = lead.get('lead_address', '') or ''
        
        print(f"\n--- Processing Lead {processed_count}/{len(skipped_leads)} ---")
        print(f"   Client: {lead.get('client_name')}")
        print(f"   Attorney Name: '{attorney_name}'")
        print(f"   Attorney Email: {attorney_email}")
        print(f"   Lead State: {lead_state if lead_state else 'N/A'}")
        print(f"   Lead Address: {lead_address if lead_address else 'N/A'}")
        print(f"   Original Skip Reason: {lead.get('skip_reason')}")
        
        # Call Tavily + Apollo validation with retry
        recovery_result = classify_attorney_name(attorney_name, attorney_email, lead_state, lead_address, "dummy_key")
        
        if 'error' in recovery_result:
            print(f"    Recovery Failed: {recovery_result['error']}")
            if 'last_domain_tried' in recovery_result:
                validation_failures += 1
            else:
                search_failures += 1
            continue
        
        # Extract results
        confidence = recovery_result.get('CONFIDENCE', '0')
        website = recovery_result.get('WEBSITE', 'unknown')
        apollo_validated = recovery_result.get('apollo_validated', False)
        
        # Convert confidence to int
        try:
            confidence_score = int(confidence)
        except (ValueError, TypeError):
            confidence_score = 0
        
        print(f"    Tavily + Apollo Results:")
        print(f"      Website Found: {website}")
        print(f"      Confidence: {confidence_score}/10")
        print(f"      Apollo Validated: {apollo_validated}")
        
        # Accept recovery if confidence meets threshold
        if confidence_score >= min_confidence:
            print(f"    RECOVERING: High-confidence website found")
            
            # Create recovered lead
            recovered_lead = lead.copy()  # Start with original lead
            
            # Clear skip reason and enable enrichment
            recovered_lead['skip_reason'] = None
            recovered_lead['needs_apollo_enrichment'] = True
            
            # Add Tavily-found website
            recovered_lead['firm_website'] = website
            
            # Add recovery metadata
            recovered_lead['ai_recovery'] = {
                'original_skip_reason': lead.get('skip_reason'),
                'recovery_method': 'tavily_apollo_validation',
                'tavily_confidence': confidence_score,
                'apollo_validated': apollo_validated,
                'website_found': website,
                'query_used': recovery_result.get('query_used', 'unknown'),
                'tavily_source': recovery_result.get('tavily_source', 'unknown')
            }
            
            recovered_leads.append(recovered_lead)
            website_recoveries += 1
            
            print(f"   Recovery Details:")
            print(f"      Firm Name: {recovered_lead.get('attorney_firm')}")
            print(f"      Website Found: {website}")
            print(f"      Apollo Validated: {'Yes' if apollo_validated else 'No'}")
            print(f"      Will be sent to Apollo enrichment")
            
        else:
            print(f"     SKIPPING: Low confidence ({confidence_score} < {min_confidence})")
    
    # Summary
    print(f"\n" + "=" * 60)
    print(" TAVILY + APOLLO RECOVERY SUMMARY")
    print("=" * 60)
    print(f"   Total Processed: {processed_count}")
    print(f"    Websites Found & Validated: {website_recoveries}")
    print(f"    Search Failures: {search_failures}")
    print(f"    Validation Failures: {validation_failures}")
    
    if website_recoveries > 0:
        recovery_rate = (website_recoveries / processed_count) * 100
        print(f"    Recovery Rate: {recovery_rate:.1f}%")
        print(f"\n    {website_recoveries} leads will now proceed to Apollo enrichment")
    else:
        print(f"\n    No leads recovered - all failed search or validation")
    
    return recovered_leads

def merge_recovered_leads(original_leads_data: Dict, recovered_leads: List[Dict]) -> Dict:
    """
    Merge Tavily-recovered leads back into the main leads data structure
    
    Args:
        original_leads_data: Original leads package
        recovered_leads: List of recovered leads from Tavily processing
    
    Returns:
        Updated leads data with recovered leads merged in
    """
    if not recovered_leads:
        return original_leads_data
    
    print(f"\n Merging {len(recovered_leads)} recovered leads into main dataset...")
    
    # Create a map of lead_id to lead for easy lookup
    all_leads = original_leads_data.get('leads', [])
    lead_map = {lead['lead_id']: lead for lead in all_leads}
    
    # Update leads with recovered versions
    updated_count = 0
    for recovered_lead in recovered_leads:
        lead_id = recovered_lead['lead_id']
        if lead_id in lead_map:
            # Replace the original with the recovered version
            lead_map[lead_id] = recovered_lead
            updated_count += 1
            print(f"   Updated lead: {recovered_lead.get('client_name')} -> {recovered_lead.get('attorney_firm')}")
    
    # Rebuild the leads list
    updated_leads = list(lead_map.values())
    
    # Update counts
    enrichment_count = len([l for l in updated_leads if l.get('needs_apollo_enrichment', False)])
    
    # Create updated package
    updated_package = original_leads_data.copy()
    updated_package['leads'] = updated_leads
    updated_package['leads_needing_enrichment'] = enrichment_count
    updated_package['tavily_recovery_stats'] = {
        'recovered_leads': len(recovered_leads),
        'updated_leads': updated_count,
        'new_enrichment_total': enrichment_count
    }
    
    print(f"    Merge complete: {updated_count} leads updated")
    print(f"    New enrichment total: {enrichment_count} leads")
    
    return updated_package

if __name__ == "__main__":
    # Test with lawyers_of_lead_poor.json
    print(" Testing Tavily + Apollo Lead Recovery with lawyers_of_lead_poor.json")
    
    try:
        with open('lawyers_of_lead_poor.json', 'r') as f:
            test_data = json.load(f)
        
        # Test with first 3 skipped leads only
        all_leads = test_data.get('leads', [])
        skipped_sample = [lead for lead in all_leads if lead.get('skip_reason') is not None][:3]
        
        test_package = {
            'leads': skipped_sample,
            'timestamp': 'test_run'
        }
        
        recovered = process_ai_recovery(test_package, min_confidence=7)
        
        if recovered:
            merged = merge_recovered_leads(test_package, recovered)
            
            # Save test results
            with open('tavily_apollo_recovery_test_results.json', 'w') as f:
                json.dump(merged, f, indent=2)
            print(f"\nTest results saved to: tavily_apollo_recovery_test_results.json")
        
    except FileNotFoundError:
        print(" lawyers_of_lead_poor.json not found")
    except Exception as e:
        print(f" Test failed: {e}")

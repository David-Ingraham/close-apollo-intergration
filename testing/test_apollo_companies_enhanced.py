#!/usr/bin/env python3
"""
Enhanced Apollo Company Search Test Script
Tests new search strategies with real lead data and proper rate limiting
"""

import os
import requests
import json
import time
import re
from difflib import SequenceMatcher
from dotenv import load_dotenv

load_dotenv()

# Rate limiting settings
REQUEST_DELAY = 2  # 2 seconds between requests
RETRY_DELAY = 60   # 60 seconds when hitting 429

def safe_str(value):
    """Convert to string safely"""
    return str(value) if value is not None else ''

def safe_lower(text):
    """Convert to lowercase safely"""
    return safe_str(text).lower()

def is_public_domain(domain):
    """Check if domain is a public email provider"""
    public_domains = {'gmail.com', 'yahoo.com', 'hotmail.com', 'outlook.com', 'aol.com'}
    return safe_lower(domain) in public_domains

def extract_domain_root(domain):
    """Extract domain root (e.g., 'smithlaw' from 'smithlaw.com')"""
    if not domain:
        return ''
    parts = domain.split('.')
    return parts[0] if len(parts) > 1 else domain

def domain_name_similarity(domain_root, firm_name):
    """Check if domain root and firm name are similar"""
    if not domain_root or not firm_name:
        return False, 0.0
    
    domain_clean = safe_lower(domain_root)
    name_clean = safe_lower(firm_name)
    
    # Token overlap check
    name_tokens = [t for t in re.split(r'[^a-z0-9]+', name_clean) if len(t) > 2]
    
    # Check if any meaningful word from firm name appears in domain
    for token in name_tokens:
        if token in domain_clean:
            return True, 1.0
    
    # Fuzzy matching as backup
    similarity = SequenceMatcher(None, domain_clean, name_clean).ratio()
    return similarity > 0.6, similarity

def generate_name_variations(firm_name):
    """Generate conservative name variations"""
    if not firm_name:
        return []
    
    variations = []
    
    # Original name
    variations.append(firm_name)
    
    # & <-> and swapping
    if '&' in firm_name:
        variations.append(firm_name.replace('&', 'and'))
    elif ' and ' in firm_name.lower():
        variations.append(re.sub(r'\s+and\s+', ' & ', firm_name, flags=re.IGNORECASE))
    
    # Remove "The" prefix
    if firm_name.lower().startswith('the '):
        variations.append(firm_name[4:])
    
    # Remove legal suffixes
    legal_suffixes = r',?\s*(llp|llc|pc|pllc|ltd|inc|corp|corporation)\.?$'
    cleaned = re.sub(legal_suffixes, '', firm_name, flags=re.IGNORECASE).strip()
    if cleaned != firm_name:
        variations.append(cleaned)
    
    # Remove "Law Offices of" prefix
    prefixes = [r'^the\s+law\s+offices?\s+of\s+', r'^law\s+offices?\s+of\s+']
    for prefix in prefixes:
        cleaned = re.sub(prefix, '', firm_name, flags=re.IGNORECASE).strip()
        if cleaned != firm_name and len(cleaned.split()) >= 2:
            variations.append(cleaned)
    
    # Remove duplicates and empty strings
    return list(set([v.strip() for v in variations if v.strip()]))

def make_apollo_request(payload):
    """Make Apollo API request with rate limiting"""
    api_key = os.getenv('APOLLO_API_KEY')
    if not api_key:
        raise ValueError("APOLLO_API_KEY not found in environment variables")
    
    url = "https://api.apollo.io/v1/mixed_companies/search"
    headers = {
        'Content-Type': 'application/json',
        'Cache-Control': 'no-cache',
        'X-Api-Key': api_key
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload)
        
        # Handle rate limiting
        if response.status_code == 429:
            print(f"      RATE LIMIT: Waiting {RETRY_DELAY} seconds...")
            time.sleep(RETRY_DELAY)
            # Retry once
            response = requests.post(url, headers=headers, json=payload)
        
        response.raise_for_status()
        
        # Add delay between requests
        time.sleep(REQUEST_DELAY)
        
        return response.json()
        
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 429:
            print(f"      RATE LIMIT: Still hitting 429. Try again later.")
            return None
        else:
            print(f"      ERROR: HTTP {e.response.status_code}")
            return None
    except Exception as e:
        print(f"      ERROR: {e}")
        return None

def search_by_domain(domain):
    """Search Apollo by domain"""
    print(f"    DOMAIN SEARCH: {domain}")
    
    # Try organization_domains parameter
    payload = {
        "organization_domains": [domain],
        "page": 1,
        "per_page": 25
    }
    
    result = make_apollo_request(payload)
    if result and result.get('organizations'):
        orgs = result['organizations']
        print(f"      Found {len(orgs)} organizations")
        return orgs
    
    # Try q_organization_name with domain
    payload = {
        "q_organization_name": domain,
        "page": 1,
        "per_page": 25
    }
    
    result = make_apollo_request(payload)
    if result and result.get('organizations'):
        orgs = result['organizations']
        print(f"      Found {len(orgs)} organizations (name search)")
        return orgs
    
    print(f"      No results for domain search")
    return []

def search_by_name(firm_name):
    """Search Apollo by firm name with variations"""
    print(f"    NAME SEARCH: {firm_name}")
    
    variations = generate_name_variations(firm_name)
    print(f"      Testing {len(variations)} variations: {variations}")
    
    all_results = []
    
    for variation in variations:
        print(f"      Trying: '{variation}'")
        
        payload = {
            "q_organization_name": variation,
            "page": 1,
            "per_page": 25
        }
        
        result = make_apollo_request(payload)
        if result and result.get('organizations'):
            orgs = result['organizations']
            print(f"        Found {len(orgs)} organizations")
            all_results.extend(orgs)
        else:
            print(f"        No results")
    
    return all_results

def validate_results(organizations, original_domain, original_firm_name):
    """Validate search results against original data"""
    print(f"    VALIDATING {len(organizations)} results...")
    
    valid_results = []
    
    for org in organizations:
        org_name = org.get('name', '')
        org_domain = org.get('primary_domain', '')
        
        print(f"      Checking: {org_name} (domain: {org_domain})")
        
        # Domain validation (if we have original domain)
        domain_valid = True
        if original_domain and not is_public_domain(original_domain):
            if org_domain:
                orig_root = extract_domain_root(original_domain)
                org_root = extract_domain_root(org_domain)
                if safe_lower(orig_root) != safe_lower(org_root):
                    print(f"        REJECT: Domain mismatch ({org_root} vs {orig_root})")
                    domain_valid = False
            else:
                print(f"        WARN: No domain for organization")
        
        # Name similarity validation (if we have original firm name)
        name_valid = True
        if original_firm_name and domain_valid:
            is_similar, similarity = domain_name_similarity(
                extract_domain_root(org_domain) if org_domain else org_name,
                original_firm_name
            )
            if not is_similar:
                print(f"        REJECT: Name/domain similarity too low ({similarity:.2f})")
                name_valid = False
        
        if domain_valid and name_valid:
            print(f"        ACCEPT: Valid result")
            valid_results.append(org)
        
    return valid_results

def test_lead_search(lead):
    """Test search strategy for a single lead"""
    print(f"\n{'='*80}")
    print(f"TESTING LEAD: {lead['client_name']} -> {lead['attorney_firm']}")
    print(f"{'='*80}")
    
    firm_name = lead['attorney_firm']
    attorney_email = lead['attorney_email']
    firm_domain = lead['firm_domain']
    
    print(f"Firm Name: {firm_name}")
    print(f"Attorney Email: {attorney_email}")
    print(f"Firm Domain: {firm_domain}")
    
    # Determine search strategy
    has_business_domain = firm_domain and not is_public_domain(firm_domain)
    
    all_results = []
    
    if has_business_domain:
        print(f"\nSTRATEGY: Domain-first search (business email detected)")
        domain_results = search_by_domain(firm_domain)
        all_results.extend(domain_results)
        
        # If domain search didn't work well, try name search
        if len(domain_results) < 2:
            print(f"\nSTRATEGY: Name search (domain search insufficient)")
            name_results = search_by_name(firm_name)
            all_results.extend(name_results)
    else:
        print(f"\nSTRATEGY: Name-only search (personal email)")
        name_results = search_by_name(firm_name)
        all_results.extend(name_results)
    
    # Remove duplicates
    seen = set()
    unique_results = []
    for org in all_results:
        org_id = org.get('id')
        if org_id not in seen:
            seen.add(org_id)
            unique_results.append(org)
    
    print(f"\nTotal unique results found: {len(unique_results)}")
    
    # Validate results
    if unique_results:
        valid_results = validate_results(unique_results, firm_domain if has_business_domain else None, firm_name)
        
        print(f"\nFINAL RESULTS: {len(valid_results)} valid organizations")
        for i, org in enumerate(valid_results[:3], 1):
            print(f"  {i}. {org.get('name', 'No name')}")
            print(f"     Domain: {org.get('primary_domain', 'No domain')}")
            print(f"     Industry: {org.get('industry', 'No industry')}")
        
        return len(valid_results) > 0
    else:
        print(f"\nFINAL RESULTS: No organizations found")
        return False

def main():
    """Main test function"""
    print("Enhanced Apollo Company Search Test")
    print("=" * 80)
    
    # Load test data
    try:
        with open('json/lawyers_of_leads_20250810_171616.json', 'r') as f:
            data = json.load(f)
    except FileNotFoundError:
        print("ERROR: Could not find json/lawyers_of_leads_20250810_171616.json")
        return
    
    leads = data.get('leads', [])
    print(f"Testing {len(leads)} leads from file")
    
    # Test each lead
    successful_searches = 0
    total_tests = len(leads)
    
    for i, lead in enumerate(leads, 1):
        print(f"\n[{i}/{total_tests}] Testing lead...")
        success = test_lead_search(lead)
        if success:
            successful_searches += 1
        
        # Add delay between leads
        if i < total_tests:
            print(f"\nPausing {REQUEST_DELAY} seconds before next lead...")
            time.sleep(REQUEST_DELAY)
    
    # Summary
    print(f"\n{'='*80}")
    print(f"TEST SUMMARY")
    print(f"{'='*80}")
    print(f"Total leads tested: {total_tests}")
    print(f"Successful searches: {successful_searches}")
    print(f"Success rate: {successful_searches/total_tests*100:.1f}%")
    
    print(f"\nRate limiting settings:")
    print(f"  Request delay: {REQUEST_DELAY} seconds")
    print(f"  429 retry delay: {RETRY_DELAY} seconds")

if __name__ == "__main__":
    main()

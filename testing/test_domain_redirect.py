#!/usr/bin/env python3
"""
Test script for domain redirect functionality in apollo_enrich.py
Tests the new search_by_domain_redirect function with real examples
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from apollo_enrich import follow_domain_redirects, search_by_domain_redirect, validate_redirect_relationship

def test_domain_redirects():
    """Test the domain redirect functionality"""
    
    print("=== TESTING DOMAIN REDIRECT FUNCTIONALITY ===\n")
    
    # Test cases from your discovery
    test_cases = [
        {
            'name': 'sstrialattorneys redirect test',
            'email': 'devans@sstrialattorneys.com',
            'firm_name': 'Schuerger Shunnarah',
            'expected_redirect': 'warforyou.com'
        }
    ]
    
    for i, case in enumerate(test_cases, 1):
        print(f"TEST {i}: {case['name']}")
        print(f"Email: {case['email']}")
        print(f"Expected firm: {case['firm_name']}")
        print("-" * 50)
        
        # Extract domain from email
        domain = case['email'].split('@')[1]
        print(f"Testing domain: {domain}")
        
        # Test redirect following
        print(f"\n1. Testing redirect following...")
        redirect_result = follow_domain_redirects(domain)
        
        if redirect_result:
            print(f"   SUCCESS: {redirect_result['original_domain']} → {redirect_result['final_domain']}")
            if case['expected_redirect'] and case['expected_redirect'] in redirect_result['final_domain']:
                print(f"   EXPECTED REDIRECT FOUND: {case['expected_redirect']}")
            else:
                print(f"   UNEXPECTED REDIRECT: Expected {case['expected_redirect']}, got {redirect_result['final_domain']}")
        else:
            print(f"   NO REDIRECT: {domain} does not redirect")
        
        # Test full search functionality
        print(f"\n2. Testing full redirect search...")
        search_result = search_by_domain_redirect(case['email'], case['firm_name'])
        
        if search_result:
            orgs = search_result.get('organizations', [])
            print(f"   SUCCESS: Found {len(orgs)} organizations via redirect")
            
            for j, org in enumerate(orgs[:3], 1):  # Show first 3
                name = org.get('name', 'Unknown')
                domain = org.get('primary_domain', 'No domain')
                print(f"   Org {j}: {name} (domain: {domain})")
                
            redirect_info = search_result.get('redirect_info', {})
            if redirect_info:
                print(f"   Redirect chain: {redirect_info.get('original_domain')} → {redirect_info.get('final_domain')}")
        else:
            print(f"   FAILED: No organizations found via redirect search")
        
        print(f"\n{'='*60}\n")

def test_validation_logic():
    """Test the redirect relationship validation"""
    
    print("=== TESTING REDIRECT VALIDATION LOGIC ===\n")
    
    # Test validation function with mock data
    test_company = {
        'name': 'Schuerger Shunnarah',
        'primary_domain': 'warforyou.com',
        'website_url': 'https://warforyou.com'
    }
    
    test_cases = [
        ('sstrialattorneys.com', 'warforyou.com', True, 'Should validate - final domain matches'),
        ('randomdomain.com', 'warforyou.com', False, 'Should not validate - no relationship'),
        ('warforyou.com', 'warforyou.com', True, 'Should validate - exact match')
    ]
    
    for original, final, expected, description in test_cases:
        result = validate_redirect_relationship(test_company, original, final)
        status = "PASS" if result == expected else "FAIL"
        print(f"{status}: {description}")
        print(f"  Original: {original}, Final: {final}, Got: {result}, Expected: {expected}")
        print()

if __name__ == "__main__":
    try:
        test_domain_redirects()
        test_validation_logic()
        print("Domain redirect testing complete!")
        
    except Exception as e:
        print(f"Test failed with error: {e}")
        import traceback
        traceback.print_exc()

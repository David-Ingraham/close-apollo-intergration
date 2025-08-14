#!/usr/bin/env python3
"""
Test script to demonstrate how the AI website URL parsing logic works
"""

def parse_ai_website(ai_website):
    """
    Simulate the exact parsing logic from apollo_enrich.py
    """
    print(f"Original AI suggestion: '{ai_website}'")
    print()
    
    # Step 1: Remove https://, http://, www.
    clean_website = ai_website.replace('https://', '').replace('http://', '').replace('www.', '')
    print(f"After removing protocols/www: '{clean_website}'")
    
    # Step 2: Handle multiple URLs - take first one
    if ' or ' in clean_website:
        clean_website = clean_website.split(' or ')[0].strip()
        print(f"After splitting on ' or ': '{clean_website}'")
    
    # Step 3: Remove parenthetical explanations
    if ' (' in clean_website:
        clean_website = clean_website.split(' (')[0].strip()
        print(f"After removing parentheses: '{clean_website}'")
    
    # Step 4: Remove "likely" and similar text
    if ' likely' in clean_website.lower():
        clean_website = clean_website.split(' likely')[0].strip()
        print(f"After removing 'likely': '{clean_website}'")
    
    # Step 5: Remove trailing slash
    if clean_website.endswith('/'):
        clean_website = clean_website[:-1]
        print(f"After removing trailing slash: '{clean_website}'")
    
    # Step 6: Validate domain format
    is_valid = not (' ' in clean_website or len(clean_website.split('.')) < 2)
    print(f"Final cleaned website: '{clean_website}'")
    print(f"Valid domain format: {is_valid}")
    
    return clean_website if is_valid else None

# Test cases
test_cases = [
    "https://www.bailey-cowan.com or https://www.heckaman.com (likely related to Bailey Cowan Heckaman PLLC, a law firm)",
    "https://www.lexingtonlaw.com",
    "www.daggettschuler.com/",
    "marcdormanlaw.com",
    "unknown",
    "invalid url with spaces",
    "https://arnolditkin.com (personal injury law firm in Houston)"
]

for i, test_url in enumerate(test_cases, 1):
    print(f"=== TEST CASE {i} ===")
    result = parse_ai_website(test_url)
    print(f"RESULT: {'Will search Apollo' if result else 'Will skip'}")
    if result:
        print(f"Apollo search term: '{result}'")
    print()

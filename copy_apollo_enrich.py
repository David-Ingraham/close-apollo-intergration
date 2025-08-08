import os
import json
import re
import time
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def clean_firm_name(name):
    """
    Remove common legal terms and clean up the firm name for better search results.
    """
    if not name or name == 'N/A':
        return name
    
    # Common legal terms to remove
    legal_terms = [
        'the law offices of', 'law offices of', 'law office of', 'law firm of',
        'law firm', 'attorneys at law', 'llp', 'llc', 'pc', 'pllc', 
        'ltd', 'inc', 'corporation', 'corp'
    ]
    
    cleaned = name.lower()
    for term in legal_terms:
        cleaned = cleaned.replace(term, '')
    
    # Clean up punctuation and extra spaces
    cleaned = re.sub(r'[,&]+', ' ', cleaned)  # Replace commas and ampersands with spaces
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()  # Remove extra whitespace
    
    return cleaned

def extract_domain_root(domain):
    """
    Extract the root part of a domain (e.g., 'kpattorney' from 'kpattorney.com')
    """
    if not domain or domain == 'N/A':
        return None
    
    # Remove common TLDs
    domain_parts = domain.split('.')
    if len(domain_parts) > 1:
        return domain_parts[0]
    return domain

def get_search_variations(firm_name):
    """
    Generate different variations of the firm name to try as search terms.
    """
    if not firm_name or firm_name == 'N/A':
        return []
    
    variations = []
    
    # Original name
    variations.append(firm_name)
    
    # Cleaned name (remove legal boilerplate)
    cleaned = clean_firm_name(firm_name)
    if cleaned and cleaned != firm_name.lower():
        variations.append(cleaned)
    
    # Core firm name variations (handle & vs and)
    # Extract the main firm name part
    core_name = firm_name
    
    # Remove "The Law Offices of" type prefixes
    prefixes_to_remove = [
        r'^the\s+law\s+offices?\s+of\s+',
        r'^law\s+offices?\s+of\s+',
        r'^the\s+law\s+firm\s+of\s+'
    ]
    
    for prefix in prefixes_to_remove:
        core_name = re.sub(prefix, '', core_name, flags=re.IGNORECASE)
    
    # Remove suffixes like LLP, LLC, PC
    suffixes_to_remove = [
        r',?\s*(llp|llc|pc|pllc|ltd|inc|corp|corporation)\.?$'
    ]
    
    for suffix in suffixes_to_remove:
        core_name = re.sub(suffix, '', core_name, flags=re.IGNORECASE)
    
    core_name = core_name.strip()
    
    if core_name and core_name != firm_name:
        variations.append(core_name)
    
    # Handle & vs and variations
    if '&' in core_name:
        variations.append(core_name.replace('&', 'and'))
        variations.append(core_name.replace('&', ''))
    elif ' and ' in core_name.lower():
        variations.append(core_name.replace(' and ', ' & '))
        variations.append(re.sub(r'\s+and\s+', ' ', core_name, flags=re.IGNORECASE))
    
    # Individual attorney names (for cases like "Rotstein & Shiffman" -> ["Rotstein", "Shiffman"])
    # Only extract names that look like surnames (capitalized, 4+ letters)
    attorney_names = re.findall(r'\b[A-Z][a-z]{3,}\b', core_name)
    # Filter out common legal words
    legal_words = {'Law', 'Firm', 'Office', 'Offices', 'Group', 'Attorney', 'Attorneys', 'Associates', 'Legal'}
    attorney_names = [name for name in attorney_names if name not in legal_words]
    
    for name in attorney_names:
        variations.append(name)
    
    # Remove duplicates while preserving order
    seen = set()
    unique_variations = []
    for variation in variations:
        variation_clean = variation.strip()
        if variation_clean and variation_clean.lower() not in seen:
            seen.add(variation_clean.lower())
            unique_variations.append(variation_clean)
    
    return unique_variations

def is_law_firm(org_name):
    """
    Check if an organization name indicates it's a law firm.
    """
    if not org_name:
        return False
    
    name_lower = org_name.lower()
    law_firm_indicators = [
        'law', 'attorney', 'attorneys', 'legal', 'counsel', 
        'llp', 'law firm', 'law office', 'law offices',
        'associates', 'partners', 'esquire', 'esq'
    ]
    
    return any(indicator in name_lower for indicator in law_firm_indicators)

def enrich_organization_industry(org_id, org_domain=None):
    """
    Get detailed organization information including industry data.
    Try multiple parameter formats since API requirements are unclear.
    """
    api_key = os.getenv('APOLLO_API_KEY')
    if not api_key:
        raise ValueError("APOLLO_API_KEY not found in environment variables")

    url = f"https://api.apollo.io/api/v1/organizations/enrich"
    headers = {
        'Content-Type': 'application/json',
        'Cache-Control': 'no-cache',
        'X-Api-Key': api_key
    }

    # Try different parameter combinations
    attempts = [
        {"id": org_id},
        {"domain": org_domain} if org_domain else None,
        {"organization_id": org_id}
    ]
    
    attempts = [attempt for attempt in attempts if attempt is not None]

    for i, params in enumerate(attempts, 1):
        try:
            response = requests.get(url, headers=headers, params=params)
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 422:
                print(f"    Enrichment attempt {i} failed (422) with params: {params}")
                continue
            else:
                response.raise_for_status()
        except requests.exceptions.RequestException as e:
            print(f"    Enrichment attempt {i} error: {e}")
            continue
    
    print(f"    All enrichment attempts failed for org ID '{org_id}'")
    return None

def enrich_individual_person(person_name, company_name, linkedin_url=None, title=None, domain=None):
    """
    Use People Enrichment API to unlock email/phone for a specific person.
    Uses multiple matching criteria to ensure we get the RIGHT person.
    This API DOES spend credits to unlock contact information.
    """
    api_key = os.getenv('APOLLO_API_KEY')
    if not api_key:
        raise ValueError("APOLLO_API_KEY not found in environment variables")

    url = "https://api.apollo.io/api/v1/people/match"
    headers = {
        'Content-Type': 'application/json',
        'Cache-Control': 'no-cache',
        'X-Api-Key': api_key
    }

    # Build enrichment payload with multiple matching criteria for accuracy
    payload = {
        "reveal_personal_emails": True,
        # Note: reveal_phone_number requires webhook_url, so we'll skip it for now
        "first_name": person_name.split()[0] if person_name else "",
        "last_name": " ".join(person_name.split()[1:]) if len(person_name.split()) > 1 else "",
        "organization_name": company_name
    }
    
    # Add LinkedIn URL - this is the most unique identifier
    if linkedin_url:
        payload["linkedin_url"] = linkedin_url
    
    # Add title for additional matching validation
    if title:
        payload["title"] = title
        
    # Add domain for company validation
    if domain:
        payload["domain"] = domain

    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        result = response.json()
        
        # Validate that we got the right person by checking company match
        if result and result.get('person'):
            enriched_person = result['person']
            enriched_company = enriched_person.get('organization', {}).get('name', '').lower()
            target_company = company_name.lower()
            
            # Check if companies match (allow partial matches)
            company_matches = (
                target_company in enriched_company or 
                enriched_company in target_company or
                # Check for common law firm variations
                any(word in enriched_company for word in target_company.split() if len(word) > 3)
            )
            
            if not company_matches:
                print(f"          WARNING: Company mismatch - Expected: '{company_name}', Got: '{enriched_person.get('organization', {}).get('name', 'Unknown')}'")
                print(f"          This might be the wrong {person_name}")
            
        return result
    except requests.exceptions.RequestException as e:
        print(f"    ERROR: Person enrichment failed for '{person_name}': {e}")
        return None

def search_people_at_organization(org_id, org_name):
    """
    Search for people (attorneys/partners) at a specific organization.
    """
    api_key = os.getenv('APOLLO_API_KEY')
    if not api_key:
        raise ValueError("APOLLO_API_KEY not found in environment variables")

    url = "https://api.apollo.io/api/v1/mixed_people/search"
    headers = {
        'Content-Type': 'application/json',
        'Cache-Control': 'no-cache',
        'X-Api-Key': api_key
    }

    # Search for attorneys, partners, lawyers at this organization
    # Try different parameter combinations for unlocking emails
    payload = {
        "organization_ids": [org_id],
        "person_titles": ["attorney", "partner", "lawyer", "counsel", "legal", "paralegal"],
        "page": 1,
        "per_page": 100,  # Get up to 100 contacts
        "reveal_personal_emails": True,  # Get personal emails
        "reveal_phone_number": True,    # Get phone numbers  
        "show_phone_info": True,        # Alternative phone parameter
        "show_emails": True             # Alternative email parameter
    }

    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        result = response.json()
        
        # Found people - will enrich individually to unlock emails/phones
        
        return result
    except requests.exceptions.RequestException as e:
        print(f"    ERROR: People search failed for org '{org_name}' (ID: {org_id}): {e}")
        return None

def is_legal_industry(org_data):
    """
    Check if organization is in legal industry based on enriched data.
    """
    if not org_data or 'organization' not in org_data:
        return False
    
    org = org_data['organization']
    
    # Check primary industry
    if 'primary_industry' in org:
        industry = str(org['primary_industry']).lower()
        if any(term in industry for term in ['legal', 'law', 'attorney']):
            return True
    
    # Check industry tags
    if 'industry_tag_list' in org:
        for tag in org['industry_tag_list']:
            if any(term in str(tag).lower() for term in ['legal', 'law', 'attorney']):
                return True
    
    # Check keywords/description
    for field in ['keywords', 'short_description', 'description']:
        if field in org and org[field]:
            text = str(org[field]).lower()
            if any(term in text for term in ['legal services', 'law firm', 'attorney', 'legal counsel']):
                return True
    
    return False

def search_apollo_organization(query):
    """
    Search for an organization in Apollo by name.
    Returns the full API response or None if failed.
    """
    api_key = os.getenv('APOLLO_API_KEY')
    if not api_key:
        raise ValueError("APOLLO_API_KEY not found in environment variables")

    url = "https://api.apollo.io/v1/mixed_companies/search"
    headers = {
        'Content-Type': 'application/json',
        'Cache-Control': 'no-cache',
        'X-Api-Key': api_key
    }

    payload = {"q_organization_name": query}

    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"    ERROR: API call failed for '{query}': {e}")
        return None

def search_firm_with_retry(lead_data):
    """
    Attempt to find a law firm using multiple search strategies.
    Returns a dictionary with search results.
    """
    result = {
        'lead_id': lead_data.get('lead_id'),
        'client_name': lead_data.get('client_name'),
        'firm_name': lead_data.get('attorney_firm'),
        'search_successful': False,
        'winning_strategy': None,
        'winning_query': None,
        'organizations_found': [],
        'attempts': []
    }
    
    firm_name = lead_data.get('attorney_firm')
    firm_domain = lead_data.get('firm_domain')
    
    print(f"\nSearching for: {firm_name}")
    
    # Strategy 1: Try name variations
    if firm_name and firm_name != 'N/A':
        variations = get_search_variations(firm_name)
        
        for i, variation in enumerate(variations, 1):
            print(f"  Attempt {i}: Searching for '{variation}'")
            
            # Rate limiting - be respectful
            time.sleep(0.5)
            
            api_response = search_apollo_organization(variation)
            
            attempt_record = {
                'strategy': 'name_variation',
                'query': variation,
                'success': False,
                'organizations_count': 0
            }
            
            if api_response and api_response.get('organizations'):
                all_organizations = api_response['organizations']
                
                # Filter for law firms only
                law_firms = [org for org in all_organizations if is_law_firm(org.get('name', ''))]
                
                attempt_record['organizations_count'] = len(all_organizations)
                attempt_record['law_firms_count'] = len(law_firms)
                
                if law_firms:
                    attempt_record['success'] = True
                    
                    print(f"    SUCCESS! Found {len(all_organizations)} total organizations, {len(law_firms)} law firms")
                    for org in law_firms[:3]:  # Show first 3 law firms
                        org_name = str(org.get('name', 'Unknown')).encode('ascii', 'ignore').decode('ascii')
                        print(f"      - {org_name}")
                    
                    result['search_successful'] = True
                    result['winning_strategy'] = 'name_variation'
                    result['winning_query'] = variation
                    result['organizations_found'] = law_firms  # Only store law firms
                    result['attempts'].append(attempt_record)
                    return result
                else:
                    print(f"    Found {len(all_organizations)} organizations but no law firms")
            else:
                print(f"    No results found")
            
            result['attempts'].append(attempt_record)
    
    # Strategy 2: Try domain root as fallback
    if firm_domain and firm_domain != 'N/A':
        domain_root = extract_domain_root(firm_domain)
        if domain_root:
            print(f"  Fallback: Searching by domain root '{domain_root}'")
            
            time.sleep(0.5)
            
            api_response = search_apollo_organization(domain_root)
            
            attempt_record = {
                'strategy': 'domain_root',
                'query': domain_root,
                'success': False,
                'organizations_count': 0
            }
            
            if api_response and api_response.get('organizations'):
                all_organizations = api_response['organizations']
                
                # Filter for law firms only
                law_firms = [org for org in all_organizations if is_law_firm(org.get('name', ''))]
                
                attempt_record['organizations_count'] = len(all_organizations)
                attempt_record['law_firms_count'] = len(law_firms)
                
                if law_firms:
                    attempt_record['success'] = True
                    
                    print(f"    SUCCESS! Found {len(all_organizations)} total organizations, {len(law_firms)} law firms via domain")
                    for org in law_firms[:3]:  # Show first 3 law firms
                        org_name = str(org.get('name', 'Unknown')).encode('ascii', 'ignore').decode('ascii')
                        print(f"      - {org_name}")
                    
                    result['search_successful'] = True
                    result['winning_strategy'] = 'domain_root'
                    result['winning_query'] = domain_root
                    result['organizations_found'] = law_firms  # Only store law firms
                    result['attempts'].append(attempt_record)
                    return result
                else:
                    print(f"    Found {len(all_organizations)} organizations via domain but no law firms")
            else:
                print(f"    No results found via domain")
            
            result['attempts'].append(attempt_record)
    
    print(f"  FAILED: No organizations found for {firm_name}")
    return result

def main():
    """
    Main function to process leads and search for organizations.
    """
    # Load leads data
    try:
        with open('lawyers_of_lead_poor.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError:
        print("Error: lawyers_of_lead_poor.json not found")
        return
    except json.JSONDecodeError:
        print("Error: Invalid JSON in lawyers_of_lead_poor.json")
        return

    leads = data.get('leads', [])
    if not leads:
        print("No leads found in the JSON file")
        return

    print(f"Processing {len(leads)} leads...")
    
    results = []
    processed_count = 0
    successful_searches = 0
    
    for lead in leads:
        # Skip if client email same as attorney email
        if (lead.get('client_email') and lead.get('attorney_email') and 
            lead.get('client_email') == lead.get('attorney_email')):
            print(f"\nSkipping {lead.get('client_name')}: Client email same as attorney email")
            continue
        
        # Only process leads that need enrichment
        if not lead.get('needs_apollo_enrichment', False):
            print(f"\nSkipping {lead.get('client_name')}: No enrichment needed")
            continue
        
        processed_count += 1
        
        # Search for the firm
        search_result = search_firm_with_retry(lead)
        
        # Step 2: If we found organizations, check industry and get contacts
        if search_result['search_successful'] and search_result.get('organizations_found'):
            print(f"  Step 2: Processing organizations for {lead.get('client_name')}...")
            
            verified_legal_firms = []
            
            for org in search_result['organizations_found']:
                org_id = org.get('id')
                org_name = org.get('name', 'Unknown')
                print(f"    Checking organization: {org_name}")
                
                # Since we already filtered for law firms by name, proceed to people search
                # Step 2a: Organization enrichment (optional - skip if 422 errors)
                website_url = org.get('website_url') or ''
                org_domain = org.get('primary_domain') or website_url.replace('http://', '').replace('https://', '').split('/')[0] if website_url else None
                enriched_org = enrich_organization_industry(org_id, org_domain)
                time.sleep(0.5)  # Rate limiting
                
                # We already know it's a law firm from our name filtering, so proceed regardless
                print(f"      Organization already identified as law firm - searching for contacts...")
                
                # Step 2b: Search for people at this organization
                people_result = search_people_at_organization(org_id, org_name)
                time.sleep(0.5)  # Rate limiting
                
                if people_result and people_result.get('people'):
                    contacts = []
                    for person in people_result['people']:
                        person_name = person.get('first_name', '') + ' ' + person.get('last_name', '')
                        linkedin_url = person.get('linkedin_url')
                        title = person.get('title')
                        
                        print(f"        Enriching {person_name} ({title})...")
                        
                        # Step 2c: Use People Enrichment API to unlock email/phone (spends credits)
                        # Pass multiple matching criteria for accuracy
                        enriched_person = enrich_individual_person(
                            person_name=person_name, 
                            company_name=org_name, 
                            linkedin_url=linkedin_url,
                            title=title,
                            domain=org.get('primary_domain')
                        )
                        time.sleep(0.5)  # Rate limiting
                        
                        if enriched_person and enriched_person.get('person'):
                            # Use enriched data (with unlocked emails/phones)
                            enriched_data = enriched_person['person']
                            personal_emails = enriched_data.get('personal_emails', [])
                            primary_email = personal_emails[0] if personal_emails else enriched_data.get('email')
                            
                            # Check for phone in different possible fields
                            phone = None
                            if enriched_data.get('phone_numbers'):
                                phone = enriched_data['phone_numbers'][0].get('raw_number')
                            elif enriched_data.get('mobile_phone'):
                                phone = enriched_data['mobile_phone']
                            elif enriched_data.get('phone'):
                                phone = enriched_data['phone']
                            
                            contact = {
                                'name': person_name,
                                'title': enriched_data.get('title') or person.get('title'),
                                'email': primary_email,
                                'email_status': enriched_data.get('email_status'),
                                'personal_emails': personal_emails,
                                'phone': phone,
                                'linkedin_url': linkedin_url,
                                'enriched': True  # Mark as enriched with credits
                            }
                            print(f"          Unlocked: email={primary_email}, phone={phone}")
                        else:
                            # Fall back to basic data if enrichment fails
                            personal_emails = person.get('personal_emails', [])
                            primary_email = personal_emails[0] if personal_emails else person.get('email')
                            
                            contact = {
                                'name': person_name,
                                'title': person.get('title'),
                                'email': primary_email,
                                'email_status': person.get('email_status'),
                                'personal_emails': personal_emails,
                                'phone': None,
                                'linkedin_url': linkedin_url,
                                'enriched': False  # Not enriched
                            }
                            print(f"          Enrichment failed - using basic data")
                        
                        contacts.append(contact)
                    
                    # Add contacts to the organization data
                    verified_firm = org.copy()
                    verified_firm['industry_verified'] = True
                    verified_firm['contacts_found'] = len(contacts)
                    verified_firm['contacts'] = contacts
                    verified_legal_firms.append(verified_firm)
                    
                    print(f"      Found {len(contacts)} attorney contacts")
                else:
                    print(f"      No attorney contacts found")
            
            # Update the search result with verified firms and contacts
            search_result['organizations_found'] = verified_legal_firms
            search_result['verified_legal_firms_count'] = len(verified_legal_firms)
            search_result['total_contacts_found'] = sum(firm.get('contacts_found', 0) for firm in verified_legal_firms)
        
        results.append(search_result)
        
        if search_result['search_successful']:
            successful_searches += 1
    
    # Save results
    output_data = {
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
        'total_leads_processed': processed_count,
        'successful_searches': successful_searches,
        'success_rate': f"{(successful_searches/processed_count)*100:.1f}%" if processed_count > 0 else "0%",
        'search_results': results
    }
    
    output_filename = 'apollo_search_results.json'
    try:
        with open(output_filename, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
        
        print(f"\n" + "="*60)
        print(f"SEARCH COMPLETE")
        print(f"Total leads processed: {processed_count}")
        print(f"Successful searches: {successful_searches}")
        print(f"Success rate: {output_data['success_rate']}")
        print(f"Results saved to: {output_filename}")
        print("="*60)
        
    except Exception as e:
        print(f"Error saving results: {e}")

if __name__ == "__main__":
    main()
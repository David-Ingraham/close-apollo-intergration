import os
import json
import re
import time
import requests
import difflib
import sqlite3
from urllib.parse import urlparse
from dotenv import load_dotenv

load_dotenv()

# Defensive string helper functions to prevent NoneType errors
def safe_str(value):
    """Convert None to empty string, keep strings as-is"""
    return str(value) if value is not None else ''

def safe_lower(text):
    """Safely convert to lowercase, handles None"""
    return safe_str(text).lower()

# Database helper functions for caching
def connect_to_db():
    """Connect to the Apollo cache database"""
    try:
        conn = sqlite3.connect('apollo_cache.db')
        cursor = conn.cursor()
        return conn, cursor
    except Exception as e:
        print(f"Warning: Could not connect to cache database: {e}")
        return None, None

def find_company_in_cache_by_domain(cursor, domain):
    """Find a company in cache by domain (most reliable)"""
    if not cursor or not domain:
        return None
    
    try:
        cursor.execute("""
            SELECT organization_id, name, primary_domain, website_url, phone 
            FROM apollo_companies 
            WHERE LOWER(primary_domain) = LOWER(?)
        """, (domain,))
        result = cursor.fetchone()
        
        if result:
            return {
                'organization_id': result[0],
                'name': result[1],
                'primary_domain': result[2],
                'website_url': result[3],
                'phone': result[4]
            }
        
        return None
    except Exception as e:
        print(f"Error searching cache by domain '{domain}': {e}")
        return None

def find_company_in_cache_by_name(cursor, firm_name):
    """Find a company in cache by name with fuzzy matching"""
    if not cursor or not firm_name:
        return None
    
    try:
        # Try exact match first
        cursor.execute("""
            SELECT organization_id, name, primary_domain, website_url, phone 
            FROM apollo_companies 
            WHERE LOWER(name) = LOWER(?)
        """, (firm_name,))
        result = cursor.fetchone()
        
        if result:
            return {
                'organization_id': result[0],
                'name': result[1],
                'primary_domain': result[2],
                'website_url': result[3],
                'phone': result[4]
            }
        
        # Try containment matching: DB name contains input name
        cursor.execute("""
            SELECT organization_id, name, primary_domain, website_url, phone 
            FROM apollo_companies 
            WHERE LOWER(name) LIKE LOWER(?)
            ORDER BY LENGTH(name) ASC
            LIMIT 1
        """, (f'%{firm_name}%',))
        result = cursor.fetchone()
        
        if result:
            return {
                'organization_id': result[0],
                'name': result[1],
                'primary_domain': result[2],
                'website_url': result[3],
                'phone': result[4]
            }
        
        # Try reverse containment: input name contains DB name
        cursor.execute("""
            SELECT organization_id, name, primary_domain, website_url, phone 
            FROM apollo_companies 
            WHERE LOWER(?) LIKE LOWER('%' || name || '%')
            ORDER BY LENGTH(name) DESC
            LIMIT 1
        """, (firm_name,))
        result = cursor.fetchone()
        
        if result:
            return {
                'organization_id': result[0],
                'name': result[1],
                'primary_domain': result[2],
                'website_url': result[3],
                'phone': result[4]
            }
        
        return None
    except Exception as e:
        print(f"Error searching cache by name '{firm_name}': {e}")
        return None

def check_cache_for_company(cursor, firm_name, attorney_email):
    """Smart cache lookup: try domain first, then name matching"""
    if not cursor:
        return None
    
    # Extract domain from attorney email
    domain = None
    if attorney_email and '@' in attorney_email:
        domain = attorney_email.split('@')[1].lower()
    
    # Try domain-based lookup first (most reliable)
    if domain:
        print(f"  [DB CACHE] Checking cache by domain: {domain}")
        company = find_company_in_cache_by_domain(cursor, domain)
        if company:
            print(f"  [DB CACHE] Found company by domain: {company['name']}")
            return company
        else:
            print(f"  [DB CACHE] No company found for domain: {domain}")
    
    # Fallback to name-based lookup
    if firm_name:
        print(f"  [DB CACHE] Checking cache by name: {firm_name}")
        company = find_company_in_cache_by_name(cursor, firm_name)
        if company:
            print(f"  [DB CACHE] Found company by name: {company['name']}")
            return company
        else:
            print(f"  [DB CACHE] No company found for name: {firm_name}")
    
    return None

def find_people_in_cache(cursor, organization_id):
    """Find all people for a company in the cache database"""
    if not cursor or not organization_id:
        return []
    
    try:
        cursor.execute("""
            SELECT person_id, name, email, phone, title, organization_name
            FROM apollo_people 
            WHERE organization_id = ?
            ORDER BY 
                CASE WHEN phone IS NOT NULL AND phone != '' THEN 0 ELSE 1 END,
                title ASC
        """, (organization_id,))
        
        results = cursor.fetchall()
        people = []
        
        for row in results:
            person = {
                'person_id': row[0],
                'name': row[1],
                'email': row[2],
                'phone': row[3],
                'title': row[4],
                'organization_name': row[5]
            }
            people.append(person)
        
        return people
    except Exception as e:
        print(f"Error finding people for organization {organization_id}: {e}")
        return []

def save_enrichment_to_cache(cursor, conn, company_data, people_data):
    """Save enrichment results to the cache database"""
    if not cursor or not conn:
        return
    
    try:
        # Save company data
        if company_data and company_data.get('organization_id'):
            cursor.execute("""
                INSERT OR REPLACE INTO apollo_companies 
                (organization_id, name, primary_domain, website_url, phone, search_term, last_updated, source)
                VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, 'apollo_enrich_cache')
            """, (
                company_data.get('organization_id'),
                company_data.get('name'),
                company_data.get('primary_domain'),
                company_data.get('website_url'),
                company_data.get('phone'),
                company_data.get('search_term', '')
            ))
        
        # Save people data
        if people_data:
            for person in people_data:
                # Fix: Use 'id' instead of 'person_id' (Apollo uses 'id')
                person_id = person.get('id') or person.get('person_id')
                if person_id:
                    # Fix: Extract phone number properly from phone_numbers array or direct phone field
                    phone = None
                    if person.get('phone_numbers') and isinstance(person.get('phone_numbers'), list):
                        # Phone is in phone_numbers array
                        phone_nums = person['phone_numbers']
                        if phone_nums and len(phone_nums) > 0:
                            phone_obj = phone_nums[0]
                            if isinstance(phone_obj, dict):
                                phone = phone_obj.get('raw_number') or phone_obj.get('sanitized_number')
                            elif isinstance(phone_obj, str):
                                phone = phone_obj
                    elif person.get('phone'):
                        # Phone is directly available
                        phone = person.get('phone')
                    
                    # Build full name if needed
                    full_name = person.get('name')
                    if not full_name:
                        first = person.get('first_name', '').strip()
                        last = person.get('last_name', '').strip()
                        full_name = f"{first} {last}".strip()
                    
                    cursor.execute("""
                        INSERT OR REPLACE INTO apollo_people 
                        (person_id, name, email, phone, title, organization_id, organization_name, last_updated, source)
                        VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, 'apollo_enrich_cache')
                    """, (
                        person_id,
                        full_name,
                        person.get('email'),
                        phone,
                        person.get('title'),
                        person.get('organization_id'),
                        person.get('organization_name')
                    ))
        
        conn.commit()
        print(f"  [DB CACHE] Saved company and {len(people_data) if people_data else 0} contacts to cache")
        
    except Exception as e:
        print(f"Error saving to cache: {e}")

def analyze_cache_completeness(people):
    """Analyze cached people data and decide what to do"""
    if not people:
        return {'complete': False, 'people_with_phones': 0, 'total_people': 0, 'needs_phone_enrichment': False}
    
    # More robust phone number detection
    people_with_phones = []
    for p in people:
        phone = p.get('phone')
        if phone and phone.strip() and phone.strip().lower() != 'null':
            people_with_phones.append(p)
    
    # Debug output to help diagnose issues
    print(f"    [DB CACHE DEBUG] Total people: {len(people)}, People with phones: {len(people_with_phones)}")
    for p in people:
        phone = p.get('phone', 'None')
        name = p.get('name', 'Unknown')
        print(f"    [DB CACHE DEBUG] {name}: phone='{phone}'")
    
    result = {
        'complete': len(people_with_phones) >= 2,  # Complete if we have 2+ phones
        'people_with_phones': len(people_with_phones),
        'total_people': len(people),
        'needs_phone_enrichment': len(people_with_phones) < 2 and len(people) > 0  # Need phones if we have people but <2 phones
    }
    
    return result

def save_successful_result_to_cache(result, cursor, conn):
    """Save a successful Apollo search result to the cache"""
    if not cursor or not conn or not result.get('search_successful'):
        return
    
    try:
        # Extract company data from result - try different possible field names
        company_data = (result.get('firm_found') or 
                       result.get('selected_organization') or 
                       (result.get('organizations_found', [{}])[0] if result.get('organizations_found') else None))
        
        if company_data:
            # Add search term for reference
            company_data = dict(company_data)  # Make a copy
            company_data['search_term'] = result.get('firm_name', '')
        
        # Extract people data from result - try different possible field names
        people_data = (result.get('contacts_found') if isinstance(result.get('contacts_found'), list) else
                      result.get('contacts', []))
        
        # Save to cache
        save_enrichment_to_cache(cursor, conn, company_data, people_data)
        
    except Exception as e:
        print(f"  [DB CACHE] Error saving result to cache: {e}")

def safe_strip(text):
    """Safely strip whitespace, handles None"""
    return safe_str(text).strip()

def safe_split(text, delimiter):
    """Safely split string, handles None"""
    return safe_str(text).split(delimiter)

def safe_endswith(text, suffix):
    """Safely check if string ends with suffix, handles None"""
    return safe_str(text).endswith(suffix)

def safe_startswith(text, prefix):
    """Safely check if string starts with prefix, handles None"""
    return safe_str(text).startswith(prefix)

def safe_extract_domain(email):
    """Safely extract domain from email, handles None"""
    email_str = safe_str(email)
    if '@' not in email_str:
        return None
    return email_str.split('@')[1]

def is_domain_related_strict(contact_email, attorney_firm_domain):
    """
    Strict domain validation that rejects different TLD combinations.
    Same logic as update_close_leads.py
    """
    if not contact_email or not attorney_firm_domain:
        return True
    
    if '@' not in contact_email:
        return False
    
    contact_domain = safe_lower(safe_split(contact_email, '@')[1])
    attorney_domain = safe_lower(attorney_firm_domain)
    
    # ONLY exact domain match
    if contact_domain == attorney_domain:
        return True
    
    # Extract base domain and TLD for comparison
    def get_domain_parts(domain):
        """Split domain into base name and TLD parts"""
        parts = domain.split('.')
        if len(parts) < 2:
            return None, None
        
        # Handle common TLD patterns
        if len(parts) >= 3 and parts[-2] in ['co', 'com', 'org', 'net', 'gov', 'edu']:
            # e.g., domain.co.uk, domain.org.uk
            return '.'.join(parts[:-2]), '.'.join(parts[-2:])
        else:
            # e.g., domain.com, domain.org
            return '.'.join(parts[:-1]), parts[-1]
    
    contact_base, contact_tld = get_domain_parts(contact_domain)
    attorney_base, attorney_tld = get_domain_parts(attorney_domain)
    
    # Both domains must have the same base domain and TLD structure
    if not (contact_base and attorney_base and contact_tld and attorney_tld):
        return False
    
    if contact_tld != attorney_tld:
        return False  # Different TLD structures (e.g., .org vs .org.uk)
    
    if contact_base == attorney_base:
        return True  # Same base domain and TLD
    
    # Check for legitimate subdomain relationships
    # Valid: mail.smithlaw vs smithlaw (with same TLD)
    if contact_base.endswith('.' + attorney_base):
        subdomain = contact_base[:-len('.' + attorney_base)]
        # Only allow simple subdomains (not complex nested ones)
        if '.' not in subdomain and len(subdomain) <= 10:
            return True
    
    if attorney_base.endswith('.' + contact_base):
        subdomain = attorney_base[:-len('.' + contact_base)]
        if '.' not in subdomain and len(subdomain) <= 10:
            return True
    
    return False

# Correct endpoint (no /api)
APOLLO_SEARCH_URL = "https://api.apollo.io/v1/mixed_companies/search"

PUBLIC_DOMAINS = {
    "gmail.com","yahoo.com","outlook.com","hotmail.com","aol.com","icloud.com",
    "protonmail.com","yandex.com","msn.com","live.com","me.com"
}
def is_public_domain(d):
    return bool(d) and safe_lower(d) in PUBLIC_DOMAINS

def extract_domain_from_email(email):
    """Extract domain from email address"""
    if email and '@' in safe_str(email):
        return safe_split(email, '@')[1]
    return None

def validate_domain_match(org, attorney_email):
    """Validate that the organization domain matches the attorney email domain"""
    if not attorney_email or attorney_email == 'N/A' or not org.get('primary_domain'):
        return False
        
    attorney_domain = extract_domain_from_email(attorney_email)
    org_domain = safe_lower(org.get('primary_domain', ''))
    
    if not attorney_domain or is_public_domain(attorney_domain):
        return False
    
    # Exact domain match
    if safe_lower(attorney_domain) == org_domain:
        return True
    
    # Check if domains are similar (for abbreviations like rotstein-sh.com vs rotstein-shiffman.com)
    attorney_root = extract_domain_root(attorney_domain)
    org_root = extract_domain_root(org_domain)
    
    if attorney_root and org_root and len(attorney_root) >= 4 and len(org_root) >= 4:
        # Check if one domain contains the other or they share significant overlap
        if attorney_root in org_root or org_root in attorney_root:
            return True
        
        # Check similarity ratio
        similarity = difflib.SequenceMatcher(None, attorney_root, org_root).ratio()
        return similarity >= 0.7
    
    return False

def calculate_firm_match_score(org, firm_name, attorney_email=None):
    """Calculate a more strict matching score for law firms"""
    org_name = safe_lower(org.get("name", ""))
    search_name = safe_lower(firm_name)
    
    # Base score from name similarity
    base_score = difflib.SequenceMatcher(None, org_name, search_name).ratio()
    
    # Domain validation bonus
    domain_bonus = 0
    if validate_domain_match(org, attorney_email):
        domain_bonus = 0.3  # Significant bonus for domain match
    
    # Legal firm bonus (using industry data)
    if is_law_firm_by_industry(org):
        legal_bonus = 0.1
    else:
        legal_bonus = -0.1  # Smaller penalty for domain searches since domain match is strong signal
    
    # Geographic penalty for clearly foreign firms
    geo_penalty = 0
    domain = org.get('primary_domain', '')
    if safe_endswith(domain, ('.co.uk', '.ie', '.com.au', '.com.br', '.ca')):
        geo_penalty = -0.2
    
    final_score = base_score + domain_bonus + legal_bonus + geo_penalty
    return max(0, min(1, final_score))  # Clamp between 0 and 1

def prioritize_legal_professionals(people, return_all=False):
    """
    Sort and select legal professionals based on title priority
    Priority: 1. partner, 2. attorney/lawyer, 3. counsel, 4. case manager, 5. paralegal
    
    Args:
        people: List of people to prioritize
        return_all: If True, return all sorted people. If False, return top 2.
    """
    def get_title_priority(person):
        title = safe_lower(person.get('title', ''))
        
        # Partner gets highest priority
        if 'partner' in title:
            return 1
        # Attorney/Lawyer second priority  
        elif 'attorney' in title or 'lawyer' in title:
            return 2
        # Counsel third priority
        elif 'counsel' in title:
            return 3
        # Case Manager fourth priority
        elif 'case manager' in title or 'case_manager' in title:
            return 4
        # Paralegal lowest priority
        elif 'paralegal' in title:
            return 5
        # Unknown titles get medium priority
        else:
            return 3.5
    
    # Sort by priority (lower number = higher priority)
    sorted_people = sorted(people, key=get_title_priority)
    
    # Return all or top 2 based on parameter
    if return_all:
        return sorted_people
    else:
        return sorted_people[:2]

def clean_firm_name(name):
    if not name or name == 'N/A':
        return name
    legal_terms = [
        'the law offices of', 'law offices of', 'law office of', 'law firm of',
        'law firm', 'attorneys at law', 'llp', 'llc', 'pc', 'pllc',
        'ltd', 'inc', 'corporation', 'corp', 'group', 'associates'
    ]
    cleaned = safe_lower(name)
    for term in legal_terms:
        cleaned = cleaned.replace(term, '')
    cleaned = re.sub(r'[,&]+', ' ', cleaned)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned

def extract_domain_root(domain):
    if not domain or domain == 'N/A':
        return None
    parts = safe_lower(domain).strip().split('.')
    if len(parts) > 2 and parts[-2] in {"co"}:
        return parts[-3]
    return parts[0] if len(parts) > 1 else domain

def get_search_variations(firm_name):
    if not firm_name or firm_name == 'N/A':
        return []
    variations = []

    # Original and quoted exact - these are the most reliable
    variations += [firm_name, f'"{firm_name}"']

    # Cleaned version (remove legal terms)
    cleaned = clean_firm_name(firm_name)
    if cleaned and cleaned != safe_lower(firm_name) and len(cleaned.split()) >= 2:
        variations += [cleaned, f'"{cleaned}"']

    # Remove prefixes/suffixes but keep core firm name
    core = firm_name
    for prefix in [r'^the\s+law\s+offices?\s+of\s+', r'^law\s+offices?\s+of\s+', r'^the\s+law\s+firm\s+of\s+']:
        core = re.sub(prefix, '', core, flags=re.IGNORECASE)
    core = re.sub(r',?\s*(llp|llc|pc|pllc|ltd|inc|corp|corporation)\.?$', '', core, flags=re.IGNORECASE).strip()
    
    # Only add core variation if it still has multiple words (avoid single names)
    if core and core != firm_name and len(core.split()) >= 2:
        variations += [core, f'"{core}"']

    # & vs and variations - but only if we still have multiple meaningful words
    if '&' in core and len(core.split()) >= 2:
        and_version = core.replace('&', 'and')
        if len(and_version.split()) >= 2:
            variations.append(and_version)
    elif ' and ' in safe_lower(core) and len(core.split()) >= 2:
        variations.append(re.sub(r'\s+and\s+', ' & ', core, flags=re.IGNORECASE))

    # REMOVE THE INDIVIDUAL NAME FALLBACKS - these cause terrible matches
    # No more single surname searches like "Rice" or "Daniel"
    
    return list(set([v for v in variations if v.strip() and len(v.split()) >= 2]))

def is_law_firm(name):
    if not name:
        return False
    n = name.lower()
    indicators = ['law', 'attorney', 'attorneys', 'legal', 'counsel', 'llp', 'law firm', 'law office', 'law offices', 'associates', 'partners']
    return any(t in n for t in indicators)

def _post(headers, payload):
    """Make POST request with error handling and rate limiting"""
    import time
    try:
        resp = requests.post(APOLLO_SEARCH_URL, headers=headers, json=payload)
        
        # Handle rate limiting
        if resp.status_code == 429:
            print(f"      WARN: Rate limit hit (429). Waiting 60 seconds...")
            time.sleep(60)  # Wait 1 minute
            # Retry once
            resp = requests.post(APOLLO_SEARCH_URL, headers=headers, json=payload)
        
        resp.raise_for_status()
        
        # Add delay between all requests to prevent rate limiting
        time.sleep(2)  # 2 second delay between requests
        
        return resp.json()
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 429:
            print(f"      WARN: Rate limit exceeded. Try again in 60+ seconds")
        else:
            print(f"      WARN: search request error: {e}")
        return None
    except Exception as e:
        print(f"      WARN: search request error: {e}")
        return None

def search_apollo_organization(query, page=1, per_page=100, domains=None):
    api_key = os.getenv('APOLLO_API_KEY')
    if not api_key:
        raise ValueError("APOLLO_API_KEY not found in environment variables")
    headers = {'Content-Type': 'application/json', 'Cache-Control': 'no-cache', 'X-Api-Key': api_key}

    # Name search (primary)
    data = _post(headers, {"q_organization_name": query, "page": page, "per_page": per_page})
    if data:
        # Fix: Apollo returns 'accounts' not 'organizations'
        if data.get("accounts"):
            # Convert accounts to organizations format for compatibility
            data["organizations"] = data["accounts"]
        return data
    elif data.get("organizations"):
        return data
    # Domain search (exact) if provided - but this often returns irrelevant results
    if domains:
        print(f"    WARNING: Domain searches often return irrelevant results")
        for key in ("company_domains", "domains", "q_company_domains"):
            data = _post(headers, {key: domains, "page": 1, "per_page": 100})
            if data:
                # Fix: Apollo returns 'accounts' not 'organizations'  
                if data.get("accounts"):
                    data["organizations"] = data["accounts"]
                    return data
                elif data.get("organizations"):
                    return data
    return None

def _primary_domain(org):
    # First try primary_domain (for organizations format)
    d = org.get("primary_domain")
    if d:
        return safe_lower(d)
    
    # Then try website_url (for accounts format) 
    website = org.get("website_url") or ""
    if website:
        domain = safe_lower(website.replace("http://", "").replace("https://", "").split("/")[0])
        # Remove www. prefix
        if domain.startswith("www."):
            domain = domain[4:]
        return domain
    
    return None

def rank_and_dedupe_organizations(orgs, input_query, input_domain=None, top_k=5):
    deduped = {}
    for o in orgs:
        key = o.get("id") or _primary_domain(o) or o.get("name")
        if key and key not in deduped:
            deduped[key] = o
    orgs = list(deduped.values())

    def score(o):
        name = o.get("name") or ""
        domain = _primary_domain(o)
        s = 0.0
        s += difflib.SequenceMatcher(None, safe_lower(name), safe_lower(input_query)).ratio() * 60
        if safe_lower(input_query) in safe_lower(name):
            s += 10
        if is_law_firm_by_industry(o):
            s += 10
        if input_domain and domain and safe_lower(input_domain) in domain:
            s += 15
        if o.get("linkedin_url"):
            s += 2
        if o.get("phone") or o.get("primary_phone"):
            s += 1
        return s

    scored = sorted(orgs, key=lambda o: score(o), reverse=True)[:top_k]
    results = []
    for o in scored:
        results.append({
            "id": o.get("id"),
            "name": o.get("name"),
            "primary_domain": _primary_domain(o),
            "website_url": o.get("website_url"),
            "linkedin_url": o.get("linkedin_url"),
            "phone": o.get("phone") or (o.get("primary_phone") or {}).get("number"),
            "_score": round(difflib.SequenceMatcher(None, safe_lower(o.get('name') or ''), safe_lower(input_query)).ratio(), 3)
        })
    return results

def normalize_core(name: str):
    if not name:
        return ""
    n = name.lower()
    n = re.sub(r'(the\s+)?law\s+offices?\s+of\s+', '', n)
    n = re.sub(r',?\s*(llp|llc|pc|pllc|ltd|inc|corp|corporation|group)\.?$', '', n)
    n = n.replace('&', ' and ')
    n = re.sub(r'\bla\b', 'los angeles', n)
    n = re.sub(r'\s+', ' ', n).strip()
    return n

def acronym(s: str):
    toks = re.findall(r'[a-zA-Z]+', s or "")
    return ''.join(t[0] for t in toks if t)

LEGAL_HINTS = {'law','lawyer','lawyers','attorney','attorneys','legal','counsel','llp','law office','law offices'}

def name_has_legal_hint(name: str):
    n = safe_lower(name or "")
    return any(h in n for h in LEGAL_HINTS)

def is_law_firm_by_industry(org):
    """Check if organization is a law firm based on Apollo industry/keywords data"""
    if not org:
        return False
    
    # Check industries field (Apollo provides this in organizations format)
    industries = org.get('industries', [])
    if industries:
        industries_text = ' '.join(safe_lower(str(ind)) for ind in industries)
        if any(term in industries_text for term in ['law', 'legal', 'attorney', 'counsel']):
            return True
    
    # Check keywords field (Apollo provides this in organizations format)  
    keywords = org.get('keywords', [])
    if keywords:
        keywords_text = ' '.join(safe_lower(str(kw)) for kw in keywords)
        if any(term in keywords_text for term in ['law', 'legal', 'attorney', 'counsel', 'litigation', 'paralegal', "law firm", "law office", "law offices"]):
            return True
    
    # For accounts format, be more permissive since industry data is often missing
    # Check organization name (primary detection method for accounts format)
    org_name = org.get('name', '')
    if name_has_legal_hint(org_name):
        return True
    
    # Check if website/domain contains legal hints
    website = org.get('website_url', '')
    if any(term in safe_lower(website) for term in ['law', 'legal', 'attorney']):
        return True
    
    return False

def choose_best_org(lead_firm_name, firm_domain, candidates, attorney_email=None):
    if not candidates:
        return None, "no_candidates"
    
    # 1) Filter out clearly non-law firms first using industry data
    law_firms = [c for c in candidates if is_law_firm_by_industry(c)]
    if law_firms:
        candidates = law_firms
        print(f"    Filtered to {len(law_firms)} law firms (by industry/keywords)")
    
    # 2) Exact domain match (with email validation)
    if attorney_email and attorney_email != 'N/A':
        domain_matches = [c for c in candidates if validate_domain_match(c, attorney_email)]
        if domain_matches:
            # Sort by name similarity among domain matches
            domain_matches.sort(key=lambda c: calculate_firm_match_score(c, lead_firm_name, attorney_email), reverse=True)
            return domain_matches[0], "exact_domain_match"

    # 3) Score all candidates with strict criteria
    scored_candidates = []
    for c in candidates:
        score = calculate_firm_match_score(c, lead_firm_name, attorney_email)
        scored_candidates.append((c, score))
    
    # Sort by score
    scored_candidates.sort(key=lambda x: x[1], reverse=True)
    
    if not scored_candidates:
        return None, "no_valid_candidates"
    
    best_candidate, best_score = scored_candidates[0]
    
    # STRICTER CRITERIA: When no email domain available, require 95% similarity
    if not attorney_email or attorney_email == 'N/A':
        if best_score >= 0.95:  # 95% similarity required when no email validation possible
            return best_candidate, f"high_confidence_no_email:{best_score:.3f}"
        else:
            return None, f"insufficient_similarity_no_email:{best_score:.3f}_requires_0.95"
    
    # Standard criteria when we have email domain validation
    if best_score >= 0.75:  # Very high confidence required
        return best_candidate, f"high_confidence:{best_score:.3f}"
    elif best_score >= 0.60 and attorney_email and validate_domain_match(best_candidate, attorney_email):
        return best_candidate, f"domain_validated:{best_score:.3f}"
    else:
        return None, f"score_too_low:{best_score:.3f}"
        
        # Bonus for having any real domain vs "no-domain"
        if domain and domain != "no-domain": bonus += 0.05
        
        # Name token matching bonus (for cases like "KP" matching "KP Attorneys")
        query_words = set(safe_lower(lead_firm_name).split()) if lead_firm_name else set()
        name_words = set(name.split())
        word_matches = len(query_words & name_words)
        if word_matches > 0: bonus += word_matches * 0.05
        
        # LinkedIn presence
        if c.get("linkedin_url"): bonus += 0.02
        
        return sim*0.6 + core_cov*0.3 + bonus

    ranked = sorted(candidates, key=score, reverse=True)
    
    # Show all candidates found
    print(f"    Found {len(candidates)} organizations, showing top candidates:")
    for i, c in enumerate(ranked[:3], 1):
        s = score(c)
        domain = c.get("primary_domain") or "no-domain"
        name = c.get("name") or "Unknown"
        # Encode name safely for Windows console
        try:
            safe_name = name.encode('ascii', 'ignore').decode('ascii')
        except:
            safe_name = "Name with special chars"
        print(f"      {i}. {safe_name} (score: {s:.3f}, domain: {domain})")

    top, runner = ranked[0], ranked[1] if len(ranked) > 1 else None
    top_s = score(top)
    runner_s = score(runner) if runner else 0.0

    # Must be a law firm (using industry data)
    if not is_law_firm_by_industry(top):
        return None, f"not_law_firm:{top_s:.3f}"
    
    # Relaxed thresholds - accept closer matches
    gap = top_s - runner_s
    if top_s >= 0.35 and gap >= 0.02:
        return top, f"score_ok:{top_s:.3f}"
    
    # Accept tied scores or very close matches
    if gap <= 0.02 and top_s >= 0.35:
        return top, f"close_match:{top_s:.3f}"
    
    # For single token searches, be more permissive if it's clearly a law firm
    if len(core_tokens) == 1 and top_s >= 0.40:
        return top, f"single_token_match:{top_s:.3f}"
        
    return None, f"ambiguous:{top_s:.3f}/{runner_s:.3f}"

def search_people_at_organization(org_id, org_name, attorney_firm_domain=None):
    """Search for attorneys/partners at a specific organization and unlock their emails"""
    api_key = os.getenv('APOLLO_API_KEY')
    if not api_key:
        raise ValueError("APOLLO_API_KEY not found in environment variables")

    # Step 1: Get people list (without emails unlocked)
    search_url = "https://api.apollo.io/api/v1/mixed_people/search"
    headers = {
        'Content-Type': 'application/json',
        'Cache-Control': 'no-cache',
        'X-Api-Key': api_key
    }

    payload = {
        "organization_ids": [org_id],
        # Removed strict person_titles filter to get more people, then prioritize by title
        "page": 1,
        "per_page": 100  # Increased to get more candidates
    }

    try:
        response = requests.post(search_url, headers=headers, json=payload)
        response.raise_for_status()
        result = response.json()
        
        people = result.get("people", [])
        total_entries = result.get("pagination", {}).get("total_entries", 0)
        print(f"      Found {len(people)} people (total: {total_entries})")
        
        # FALLBACK: If organization_ids returns 0 people, try q_organization_name
        if total_entries == 0 and org_name:
            print(f"      No people found with organization_ids, trying q_organization_name fallback...")
            fallback_payload = {
                "q_organization_name": org_name,
                "page": 1,
                "per_page": 100  # Increased to get more candidates
            }
            
            try:
                fallback_response = requests.post(search_url, headers=headers, json=fallback_payload)
                if fallback_response.status_code == 200:
                    fallback_result = fallback_response.json()
                    fallback_people = fallback_result.get("people", [])
                    fallback_total = fallback_result.get("pagination", {}).get("total_entries", 0)
                    
                    if fallback_total > 0:
                        print(f"      FALLBACK SUCCESS: Found {len(fallback_people)} people (total: {fallback_total})")
                        people = fallback_people
                        total_entries = fallback_total
                    else:
                        print(f"      Fallback also returned 0 people")
                else:
                    print(f"      Fallback failed: {fallback_response.status_code}")
            except Exception as e:
                print(f"      Fallback error: {e}")
        
        if not people:
            return []
        
        # Apply priority filtering to get ALL legal professionals (not just top 2)
        all_legal_people = prioritize_legal_professionals(people, return_all=True)
        print(f"      Found {len(all_legal_people)} legal professionals to check for emails")
        
        # PRE-FLIGHT CHECK: Look at existing email domains before spending credits
        if attorney_firm_domain and not is_public_domain(attorney_firm_domain):
            promising_people = []
            for person in all_legal_people:
                existing_email = person.get('email')
                if existing_email and existing_email != 'email_not_unlocked@domain.com':
                    # Check if existing email domain matches attorney domain
                    if is_domain_related_strict(existing_email, attorney_firm_domain):
                        promising_people.append(person)
                        print(f"      PROMISING: {person.get('first_name')} {person.get('last_name')} - {existing_email}")
                    else:
                        contact_domain = safe_extract_domain(existing_email)
                        print(f"      SKIP: {person.get('first_name')} {person.get('last_name')} - Domain mismatch: {contact_domain} vs {attorney_firm_domain}")
                else:
                    # No existing email, might be worth trying to unlock
                    promising_people.append(person)
            
            if not promising_people:
                print(f"      No promising contacts found - all have domain mismatches vs {attorney_firm_domain}")
                print(f"      Skipping this organization to save credits")
                return []
            
            print(f"      Found {len(promising_people)} promising contacts (out of {len(all_legal_people)})")
            all_legal_people = promising_people
        
        # Step 2: Keep searching through people until we find enough WITH emails
        enrich_url = "https://api.apollo.io/api/v1/people/match"
        enriched_contacts = []
        target_contacts = 6  # We want to find 6 people with emails
        max_attempts = min(len(all_legal_people), 20)  # Don't try more than 20 people
        
        print(f"      Unlocking emails for up to {max_attempts} contacts...")
        
        consecutive_email_mismatches = 0
        
        for i, person in enumerate(all_legal_people[:max_attempts], 1):
            # Stop if we already found enough contacts with emails
            if len(enriched_contacts) >= target_contacts:
                print(f"      Found {target_contacts} contacts with emails, stopping search")
                break
            # Use person data to enrich and unlock email
            enrich_payload = {
                "first_name": person.get('first_name'),
                "last_name": person.get('last_name'),
                "organization_name": org_name,
                "reveal_personal_emails": True,
                "reveal_phone_number": False  # We'll do phones separately via webhook
            }
            
            try:
                enrich_response = requests.post(enrich_url, headers=headers, json=enrich_payload)
                if enrich_response.status_code == 200:
                    enriched_data = enrich_response.json()
                    enriched_person = enriched_data.get('person', {})
                    
                    # Check if we got a real email
                    email = enriched_person.get('email')
                    if email and email != 'email_not_unlocked@domain.com':
                        # Domain validation - only accept contacts whose email domain matches attorney firm domain
                        contact_domain_valid = True
                        if attorney_firm_domain and not is_public_domain(attorney_firm_domain):
                            # Use the same strict domain validation as update_close_leads.py
                            if not is_domain_related_strict(email, attorney_firm_domain):
                                contact_domain_valid = False
                                contact_email_domain = extract_domain_from_email(email)
                                consecutive_email_mismatches += 1
                                print(f"        [{i:2d}/{max_attempts}] {enriched_person.get('first_name')} {enriched_person.get('last_name')} - Domain mismatch: {contact_email_domain} vs {attorney_firm_domain}")
                                
                                # Early exit if we hit 3 consecutive email domain mismatches
                                if consecutive_email_mismatches >= 3:
                                    print(f"        EARLY EXIT: 3 consecutive email domain mismatches, stopping to save credits")
                                    break
                            else:
                                consecutive_email_mismatches = 0  # Reset counter on valid match
                        
                        if contact_domain_valid:
                            contact = {
                                'name': f"{enriched_person.get('first_name', '')} {enriched_person.get('last_name', '')}".strip(),
                                'title': enriched_person.get('title') or person.get('title'),
                                'email': email,
                                'linkedin_url': enriched_person.get('linkedin_url'),
                                'phone': None,
                                'organization_id': org_id,
                                'person_id': enriched_person.get('id')
                            }
                            enriched_contacts.append(contact)
                            print(f"        [{i:2d}/{len(people)}] [OK] {contact['name']} - {email}")
                    else:
                        print(f"        [{i:2d}/{len(people)}] [ERROR] {person.get('first_name')} {person.get('last_name')} - No email available")
                else:
                    print(f"        [{i:2d}/{len(people)}] ✗ {person.get('first_name')} {person.get('last_name')} - Enrichment failed ({enrich_response.status_code})")
                
                # Rate limiting to avoid Apollo API limits
                time.sleep(2)
                
            except Exception as e:
                print(f"        [{i:2d}/{len(people)}] ERROR enriching {person.get('first_name')}: {e}")
        
        print(f"      Successfully unlocked {len(enriched_contacts)}/{i} emails (target: {target_contacts})")
        if len(enriched_contacts) > 0:
            print(f"      CREDITS SAVED: Pre-flight check filtered out non-matching contacts")
        return enriched_contacts
        
    except requests.exceptions.RequestException as e:
        print(f"      ERROR: People search failed for '{org_name}': {e}")
        return []

def enrich_attorney_email_for_phone(attorney_email, webhook_url=None):
    """
    Enrich the original attorney's email to get their direct phone number.
    Uses email-only enrichment to avoid parsing messy name fields.
    """
    if not attorney_email or attorney_email == 'N/A':
        return None, "no_email_provided"
    
    api_key = os.getenv('APOLLO_API_KEY')
    if not api_key:
        raise ValueError("APOLLO_API_KEY not found in environment variables")
    
    url = "https://api.apollo.io/api/v1/people/match"
    headers = {
        'Content-Type': 'application/json',
        'Cache-Control': 'no-cache',
        'X-Api-Key': api_key
    }
    
    # Email-only enrichment payload
    payload = {
        "email": attorney_email,
        "reveal_personal_emails": True,
        "reveal_phone_number": True if webhook_url else False
    }
    
    # Add webhook URL if provided (for async phone enrichment)
    if webhook_url:
        payload["webhook_url"] = f"{webhook_url}/apollo-webhook"
    
    print(f"    Enriching attorney email: {attorney_email}")
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            person = result.get('person', {})
            
            if person and person.get('id'):
                # Build attorney contact info
                attorney_contact = {
                    'name': f"{person.get('first_name', '')} {person.get('last_name', '')}".strip(),
                    'title': person.get('title', 'Attorney'),
                    'email': attorney_email,
                    'linkedin_url': person.get('linkedin_url'),
                    'person_id': person.get('id'),
                    'organization_id': person.get('organization', {}).get('id'),
                    'organization_name': person.get('organization', {}).get('name'),
                    'phone': None  # Will be filled by webhook if webhook_url provided
                }
                
                # Try to get immediate phone number if not using webhook
                if not webhook_url:
                    phone_numbers = person.get('phone_numbers', [])
                    if phone_numbers:
                        attorney_contact['phone'] = phone_numbers[0].get('raw_number')
                
                print(f"    Successfully enriched: {attorney_contact['name']} at {attorney_contact.get('organization_name', 'Unknown Org')}")
                return attorney_contact, "success"
            else:
                print(f"    No person data found for email: {attorney_email}")
                return None, "no_person_data"
                
        elif response.status_code == 422:
            error_detail = response.json() if response.text else "Unknown validation error"
            print(f"    Validation error for {attorney_email}: {error_detail}")
            return None, f"validation_error:{error_detail}"
            
        else:
            print(f"    HTTP {response.status_code} error for {attorney_email}")
            try:
                error_detail = response.json()
                print(f"    Details: {error_detail}")
            except:
                print(f"    Response: {response.text[:100]}")
            return None, f"http_error:{response.status_code}"
            
    except requests.exceptions.Timeout:
        print(f"    Request timeout for {attorney_email}")
        return None, "timeout"
    except Exception as e:
        print(f"    Error enriching {attorney_email}: {e}")
        return None, f"error:{str(e)}"

def is_reasonable_domain_match(found_domain, target_domain):
    """Check if a found domain is a reasonable match for the target domain"""
    if not found_domain or not target_domain:
        return True  # If no domain info, allow it
    
    found_clean = found_domain.lower().replace('www.', '')
    target_clean = target_domain.lower().replace('www.', '')
    
    # Exact match
    if found_clean == target_clean:
        return True
    
    # Extract root domains
    found_root = found_clean.split('.')[0]
    target_root = target_clean.split('.')[0]
    
    # If roots are identical, check TLD similarity
    if found_root == target_root:
        # Same root with legal TLDs is good
        legal_tlds = ['.law', '.legal', '.com', '.net', '.org']
        found_tld = '.' + '.'.join(found_clean.split('.')[1:])
        target_tld = '.' + '.'.join(target_clean.split('.')[1:])
        
        if found_tld in legal_tlds and target_tld in legal_tlds:
            return True
    
    # Reject if one domain is clearly an extension of another with different business
    # e.g., getb.com vs getbee.com, getblock.io
    if len(found_root) > len(target_root) + 2:  # Significantly longer
        return False
    if len(target_root) > len(found_root) + 2:  # Significantly longer
        return False
    
    # Different TLD extensions that suggest different business types
    crypto_tlds = ['.io', '.crypto', '.blockchain']
    found_tld = '.' + '.'.join(found_clean.split('.')[1:]) if '.' in found_clean else ''
    target_tld = '.' + '.'.join(target_clean.split('.')[1:]) if '.' in target_clean else ''
    
    if found_tld in crypto_tlds and target_tld not in crypto_tlds:
        return False
    
    return True

def search_people_with_fallback(candidates, firm_name, attorney_firm_domain=None, attorney_email=None):
    """Try multiple organizations until we find people, with redirect fallback"""
    consecutive_domain_mismatches = 0
    failed_orgs_count = 0
    
    # Filter candidates upfront using domain validation
    if attorney_firm_domain:
        reasonable_candidates = []
        for org in candidates:
            org_domain = _primary_domain(org)
            if is_reasonable_domain_match(org_domain, attorney_firm_domain):
                reasonable_candidates.append(org)
            else:
                org_name = org.get('name', 'Unknown').encode('ascii', 'ignore').decode('ascii')
                print(f"    SKIPPED organization: {org_name} (domain {org_domain} not reasonable match for {attorney_firm_domain})")
        
        # Use filtered candidates if we found any reasonable ones
        if reasonable_candidates:
            candidates = reasonable_candidates
            print(f"    Filtered to {len(candidates)} reasonable domain matches")
    
    for i, org in enumerate(candidates):
        org_id = org.get('id')
        org_name = org.get('name', 'Unknown')
        org_domain = _primary_domain(org)
        safe_name = org_name.encode('ascii', 'ignore').decode('ascii')
        
        print(f"    Trying organization #{i+1}: {safe_name}")
        contacts = search_people_at_organization(org_id, safe_name, attorney_firm_domain)
        
        if contacts:
            print(f"      SUCCESS! Found {len(contacts)} people")
            return org, contacts, f"fallback_org_{i+1}"
        else:
            failed_orgs_count += 1
            
            # Check if this failure was due to domain mismatches
            if attorney_firm_domain and org_domain:
                if not is_reasonable_domain_match(org_domain, attorney_firm_domain):
                    consecutive_domain_mismatches += 1
                    print(f"      No people found (domain mismatch #{consecutive_domain_mismatches}), trying next organization...")
                    
                    # Early exit if we hit 3 consecutive domain mismatches
                    if consecutive_domain_mismatches >= 3:
                        print(f"      EARLY EXIT: 3 consecutive domain mismatches, stopping search to save credits")
                        break
                else:
                    consecutive_domain_mismatches = 0  # Reset counter on reasonable match
                    print(f"      No people found, trying next organization...")
            else:
                print(f"      No people found, trying next organization...")
            
            # REDIRECT FALLBACK: If we've tried 2+ organizations and they all failed with domain issues
            if (failed_orgs_count >= 2 and attorney_email and attorney_firm_domain and 
                not is_public_domain(attorney_firm_domain)):
                
                print(f"      REDIRECT FALLBACK: {failed_orgs_count} orgs failed, checking domain redirects...")
                redirect_result = try_redirect_recovery(attorney_email, firm_name, attorney_firm_domain)
                
                if redirect_result:
                    org, contacts, reason = redirect_result
                    print(f"      REDIRECT SUCCESS! Found {len(contacts)} people via redirect")
                    return org, contacts, f"redirect_recovery_{reason}"
    
    # If no org has people, return the first one anyway
    if candidates:
        org = candidates[0]
        return org, [], "no_people_found"
    
    return None, [], "no_candidates"

def try_redirect_recovery(attorney_email, firm_name, attorney_firm_domain):
    """Try to recover using domain redirects when regular searches fail"""
    if not attorney_email or '@' not in attorney_email:
        return None
        
    original_domain = extract_domain_from_email(attorney_email)
    if not original_domain or is_public_domain(original_domain):
        return None
    
    print(f"      Checking domain redirects for {original_domain}")
    
    # Follow redirects to find final domain
    redirect_result = follow_domain_redirects(original_domain)
    
    if not redirect_result:
        print(f"      No redirects found for {original_domain}")
        return None
        
    final_domain = redirect_result['final_domain']
    print(f"      Redirect found: {original_domain} → {final_domain}")
    
    # Search Apollo using the final domain - try both methods
    print(f"      Searching Apollo for final domain: {final_domain}")
    
    # Method 1: Domain-based search
    api_response = search_apollo_organization(final_domain, page=1, per_page=100)
    organizations = []
    
    if api_response and api_response.get('organizations'):
        organizations = api_response['organizations']
        print(f"      Domain search found {len(organizations)} organizations")
    else:
        print(f"      Domain search found 0 organizations")
    
    # Method 2: Name-based search (fallback) - extract domain root
    if not organizations:
        domain_root = final_domain.split('.')[0]  # "brownandcrouppen.com" -> "brownandcrouppen"
        print(f"      Trying name-based search with: {domain_root}")
        
        # Use the name-based search method
        api_key = os.getenv('APOLLO_API_KEY')
        headers = {
            'Content-Type': 'application/json',
            'Cache-Control': 'no-cache',
            'X-Api-Key': api_key
        }
        
        url = "https://api.apollo.io/api/v1/mixed_companies/search"
        payload = {
            "q_organization_name": domain_root,
            "page": 1,
            "per_page": 100
        }
        
        try:
            response = requests.post(url, headers=headers, json=payload)
            if response.status_code == 200:
                name_data = response.json()
                name_organizations = name_data.get('organizations', [])
                if name_organizations:
                    organizations = name_organizations
                    print(f"      Name search found {len(organizations)} organizations")
                else:
                    print(f"      Name search found 0 organizations")
            else:
                print(f"      Name search failed: {response.status_code}")
        except Exception as e:
            print(f"      Name search error: {e}")
    
    if not organizations:
        print(f"      No organizations found for final domain: {final_domain}")
        return None
    
    print(f"      Total organizations found: {len(organizations)}")
    
    # Use existing filtering and selection logic
    law_firms = [org for org in organizations if is_law_firm_by_industry(org)]
    
    # If no law firms found by industry, use all organizations (redirect is strong signal)
    if not law_firms and organizations:
        law_firms = organizations
        print(f"      Using all {len(organizations)} orgs (redirect is strong signal)")
    else:
        print(f"      Found {len(law_firms)} law firms by industry")
    
    if not law_firms:
        return None
    
    # Try the best redirect candidate
    ranked = rank_and_dedupe_organizations(law_firms, input_query=firm_name, input_domain=final_domain)
    best, reason = choose_best_org(firm_name, final_domain, ranked, attorney_email)
    
    if best:
        safe_name = best.get('name', 'Unknown').encode('ascii', 'ignore').decode('ascii')
        print(f"      Selected redirect candidate: {safe_name}")
        
        # Search for people at the redirect organization - skip domain validation (redirect is authentication)
        contacts = search_people_at_organization(best.get('id'), safe_name, None)
        
        if contacts:
            return best, contacts, reason
    
    return None

def follow_domain_redirects(original_domain):
    """
    Follow redirects from original domain to find final destination
    Returns: dict with redirect info or None if failed
    """
    if not original_domain:
        return None
        
    # Try both http and https
    for protocol in ['https', 'http']:
        url = f"{protocol}://{original_domain}"
        
        try:
            # Create session with redirect tracking
            session = requests.Session()
            session.max_redirects = 5
            
            # Make request with timeout
            response = session.get(url, timeout=10, allow_redirects=True)
            
            # Extract final domain from response URL
            final_url = response.url
            final_domain = urlparse(final_url).netloc.lower()
            
            # Clean up domain (remove www prefix)
            if final_domain.startswith('www.'):
                final_domain = final_domain[4:]
                
            # Skip if no redirect happened or same domain
            if final_domain == original_domain.lower():
                continue
                
            print(f"    Domain redirect found: {original_domain} → {final_domain}")
            
            return {
                'original_domain': original_domain,
                'final_domain': final_domain,
                'final_url': final_url,
                'success': True
            }
            
        except requests.RequestException as e:
            print(f"    Redirect check failed for {protocol}://{original_domain}: {str(e)}")
            continue
    
    return None

def search_by_domain_redirect(attorney_email, firm_name):
    """
    Backup search strategy using domain redirects
    Returns: dict with organizations list (same format as Apollo API) or None
    """
    if not attorney_email or '@' not in attorney_email:
        return None
        
    # Extract domain from attorney email
    original_domain = extract_domain_from_email(attorney_email)
    if not original_domain or is_public_domain(original_domain):
        return None
    
    print(f"  STRATEGY REDIRECT: Checking domain redirects for {original_domain}")
    
    # Follow redirects to find final domain
    redirect_result = follow_domain_redirects(original_domain)
    
    if not redirect_result:
        print(f"    No redirects found for {original_domain}")
        return None
        
    final_domain = redirect_result['final_domain']
    print(f"    Redirect found: {original_domain} → {final_domain}")
    
    # Search Apollo using the final domain
    print(f"    Searching Apollo for final domain: {final_domain}")
    api_response = search_apollo_organization(final_domain, page=1, per_page=100)
    
    if not api_response or not api_response.get('organizations'):
        print(f"    No organizations found for final domain: {final_domain}")
        return None
    
    organizations = api_response['organizations']
    print(f"    Found {len(organizations)} organizations for final domain")
    
    # Validate results - check if any companies have original domain in their email domains
    valid_companies = []
    for org in organizations:
        if validate_redirect_relationship(org, original_domain, final_domain):
            valid_companies.append(org)
    
    if valid_companies:
        print(f"    Found {len(valid_companies)} valid companies with domain relationship")
        return {
            'organizations': valid_companies,
            'search_method': 'domain_redirect',
            'redirect_info': redirect_result
        }
    else:
        print(f"    No companies found with valid domain relationship to {original_domain}")
        return None

def validate_redirect_relationship(company, original_domain, final_domain):
    """
    Check if company is legitimately related to original domain
    """
    if not company:
        return False
        
    # Check if company has original domain in their website or primary domain
    company_website = safe_lower(company.get('website_url', ''))
    company_primary = safe_lower(company.get('primary_domain', ''))
    
    # Check for original domain in website URL
    if original_domain.lower() in company_website:
        return True
        
    # Check for original domain in primary domain
    if original_domain.lower() == company_primary:
        return True
        
    # Check if final domain matches company domain
    if final_domain.lower() == company_primary:
        return True
        
    if final_domain.lower() in company_website:
        return True
    
    return False

def search_firm_with_retry(lead_data, webhook_url=None, cursor=None, conn=None):
    # Establish database connection if not provided
    db_connection_created = False
    if cursor is None or conn is None:
        conn, cursor = connect_to_db()
        db_connection_created = True  # Track if we created the connection
        if conn:
            print("  [DB CACHE] Connected to Apollo cache database")
        else:
            print("  [DB CACHE] Cache database not available - proceeding without cache")
            cursor = None
            conn = None
    
    def cleanup_and_return(result):
        """Helper function to clean up database connection and return result"""
        if db_connection_created and conn:
            conn.close()
            print("  [DB CACHE] Database connection closed")
        return result
    result = {
        'lead_id': lead_data.get('lead_id'),
        'client_name': lead_data.get('client_name'),
        'firm_name': lead_data.get('attorney_firm'),
        'attorney_email': lead_data.get('attorney_email'),
        'firm_domain': lead_data.get('firm_domain'),
        'search_successful': False,
        'winning_strategy': None,
        'winning_query': None,
        'organizations_found': [],
        'attempts': [],
        'attorney_contact': None,  # New field for original attorney
        'attorney_enrichment_status': None
    }

    firm_name = lead_data.get('attorney_firm')
    firm_domain = safe_lower(lead_data.get('firm_domain') or '')
    attorney_email = lead_data.get('attorney_email')
    ai_website = lead_data.get('firm_website')  # AI-suggested website
    ai_recovery = lead_data.get('ai_recovery')  # AI recovery metadata
    
    print(f"    Input data: firm_name='{firm_name}', attorney_email='{attorney_email}'")
    
    # DATABASE CACHE CHECK - Check if we already have this company
    cached_company = None
    cached_people = []
    cache_analysis = None
    
    if cursor:
        print(f"  [DB CACHE] Checking cache for '{firm_name}'...")
        cached_company = check_cache_for_company(cursor, firm_name, attorney_email)
        
        if cached_company:
            cached_people = find_people_in_cache(cursor, cached_company['organization_id'])
            cache_analysis = analyze_cache_completeness(cached_people)
            
            if cache_analysis['complete']:
                print(f"  [DB CACHE] COMPLETE DATA FOUND - {cache_analysis['total_people']} contacts with {cache_analysis['people_with_phones']} phone numbers")
                print(f"  [DB CACHE] Skipping all Apollo API calls - using cached data")
                
                # Format cached data into the expected result structure
                result.update({
                    'search_successful': True,
                    'winning_strategy': 'database_cache_complete',
                    'winning_query': f"Cache lookup: {cached_company['name']}",
                    'organizations_found': [cached_company],
                    'firm_found': cached_company,
                    'contacts_found': cached_people,
                    'attorney_contact': None,
                    'attorney_enrichment_status': 'skipped_cache_hit'
                })
                
                # Show the cached contacts in console
                print(f"  [DB CACHE] Contacts from cache:")
                for contact in cached_people:
                    phone_display = contact.get('phone', 'No phone')
                    print(f"    - {contact.get('name', 'Unknown')} ({contact.get('title', 'No title')}) - {contact.get('email', 'No email')} - {phone_display}")
                
                return cleanup_and_return(result)
            
            elif cache_analysis['needs_phone_enrichment']:
                print(f"  [DB CACHE] PARTIAL DATA FOUND - {cache_analysis['total_people']} contacts, {cache_analysis['people_with_phones']} with phones")
                print(f"  [DB CACHE] Will skip company search but still do phone enrichment")
            else:
                print(f"  [DB CACHE] Found company but no people - will proceed with full Apollo search")
        else:
            print(f"  [DB CACHE] No matching company found - proceeding with Apollo search")
    
    # Show AI recovery information if present
    if ai_recovery:
        print(f"     AI-RECOVERED LEAD:")
        print(f"       Original skip reason: {ai_recovery.get('original_skip_reason', 'unknown')}")
        print(f"       AI classification: {ai_recovery.get('ai_classification', 'unknown')}")
        print(f"       AI confidence: {ai_recovery.get('ai_confidence', 'unknown')}/10")
        if ai_website:
            print(f"       AI suggested website: {ai_website}")
        print(f"        This lead was rescued by AI and will now be enriched!")
    
    # NEW: Enrich the attorney's email to get their direct phone number
    print(f"\n  ATTORNEY ENRICHMENT: Getting direct contact info for {attorney_email}")
    if attorney_email and attorney_email != 'N/A':
        attorney_contact, attorney_status = enrich_attorney_email_for_phone(attorney_email, webhook_url)
        result['attorney_contact'] = attorney_contact
        result['attorney_enrichment_status'] = attorney_status
        
        if attorney_contact:
            print(f"    SUCCESS: Found {attorney_contact['name']} - {attorney_contact.get('title', 'Attorney')}")
        else:
            print(f"    FAILED: {attorney_status}")
    else:
        result['attorney_enrichment_status'] = "no_email_provided"
        print(f"    SKIPPED: No attorney email provided")
    
    print(f"\n  FIRM SEARCH: Finding law firm and other attorneys")
    
    # STRATEGY 1: Domain-First Search (when we have attorney email)  
    if attorney_email and '@' in attorney_email and not is_public_domain(extract_domain_from_email(attorney_email)):
        email_domain = extract_domain_from_email(attorney_email)
        domain_root = extract_domain_root(email_domain)
        
        print(f"  STRATEGY 1: Domain-first search")
        print(f"    Email domain: {email_domain}")
        print(f"    Domain root: {domain_root}")
        
        # Check if we can use cached company data for this domain
        if cached_company and cache_analysis and cache_analysis['needs_phone_enrichment']:
            print(f"  [DB CACHE] Using cached company data, skipping Apollo company search")
            print(f"  [DB CACHE] Proceeding directly to phone enrichment for {cache_analysis['total_people']} cached contacts")
            
            # Use cached data but still do phone enrichment
            result.update({
                'search_successful': True,
                'winning_strategy': 'database_cache_partial',
                'winning_query': f"Cache + phone enrichment: {cached_company['name']}",
                'organizations_found': [cached_company],
                'firm_found': cached_company,
                'contacts_found': cached_people,
                'firm_phone': cached_company.get('phone'),
                'attorney_contact': None,
                'attorney_enrichment_status': result.get('attorney_enrichment_status', 'unknown')
            })
            
            # TODO: Add phone enrichment logic here if needed
            print(f"  [DB CACHE] Using {len(cached_people)} cached contacts - phone enrichment not yet implemented")
            
            # Save any new data to cache (though minimal in this case)
            save_successful_result_to_cache(result, cursor, conn)
            
            return cleanup_and_return(result)
        
        # Search by exact domain
        print(f"  Attempt 1A: Domain search '{email_domain}'")
        api_response = search_apollo_organization(email_domain, page=1, per_page=100)
        attempt = {'strategy': 'domain_exact', 'query': email_domain, 'success': False, 'organizations_count': 0}
        
        if api_response and api_response.get('organizations'):
            orgs = api_response['organizations']
            attempt['organizations_count'] = len(orgs)
            contacts = []  # Initialize contacts
            # Only accept orgs with EXACT domain match
            exact_domain_matches = [org for org in orgs if _primary_domain(org) and email_domain and safe_lower(_primary_domain(org)) == safe_lower(email_domain)]
            # For exact domain matches, be less strict - domain match is strong signal
            law_firms = [org for org in exact_domain_matches if is_law_firm_by_industry(org)]
            
            # If no law firms found by industry, use all exact domain matches (domain is strong signal)
            if not law_firms and exact_domain_matches:
                law_firms = exact_domain_matches
                print(f"    Found {len(orgs)} total, {len(exact_domain_matches)} exact domain matches, using all (domain match is strong signal)")
            else:
                print(f"    Found {len(orgs)} total, {len(exact_domain_matches)} exact domain matches, {len(law_firms)} law firms by industry")
            
            # Initialize variables
            best, reason = None, "no_candidates"
            
            if law_firms:
                ranked = rank_and_dedupe_organizations(law_firms, input_query=domain_root, input_domain=domain_root)
                best, reason = choose_best_org(firm_name, email_domain, ranked, attorney_email)
                if best:
                    safe_name = best.get('name', 'Unknown').encode('ascii', 'ignore').decode('ascii')
                    print(f"    SUCCESS! Selected: {safe_name} ({reason}) - EXACT DOMAIN MATCH")
                    
                    org, contacts, selection_reason = search_people_with_fallback(ranked, firm_name, firm_domain)
                    if org:
                        safe_name = org.get('name', 'Unknown').encode('ascii', 'ignore').decode('ascii')
                        print(f"    FINAL SELECTION: {safe_name} ({selection_reason})")
                    
                    result.update({
                        'search_successful': True,
                        'winning_strategy': 'domain_exact',
                        'winning_query': email_domain,
                        'organizations_found': [best],
                        'selection_reason': reason,
                        'firm_phone': best.get('phone') if best else None,
                        'contacts_found': len(contacts),
                        'contacts': contacts
                    })
                    attempt['success'] = True
                    result['attempts'].append(attempt)
                    
                    # Save successful result to cache
                    save_successful_result_to_cache(result, cursor, conn)
                    
                    return cleanup_and_return(result)
        
        result['attempts'].append(attempt)
        
        # Search by domain root if exact domain didn't work
        if domain_root and domain_root != email_domain:
            print(f"  Attempt 1B: Domain root search '{domain_root}'")
            api_response = search_apollo_organization(domain_root, page=1, per_page=100)
            attempt = {'strategy': 'domain_root', 'query': domain_root, 'success': False, 'organizations_count': 0}
            
            if api_response and api_response.get('organizations'):
                orgs = api_response['organizations']
                attempt['organizations_count'] = len(orgs)
                contacts = []  # Initialize contacts
                # Prefer exact domain matches, but allow similar domains
                domain_matches = [org for org in orgs if email_domain and _primary_domain(org) and safe_lower(email_domain) in safe_lower(_primary_domain(org))]
                if not domain_matches:
                    domain_matches = [org for org in orgs if domain_root and _primary_domain(org) and safe_lower(domain_root) in safe_lower(_primary_domain(org))]
                law_firms = [org for org in domain_matches if is_law_firm_by_industry(org)]
                
                # If no law firms found by industry, use all domain matches (domain is strong signal)
                if not law_firms and domain_matches:
                    law_firms = domain_matches
                    print(f"    Found {len(orgs)} total, {len(domain_matches)} domain-related, using all (domain match is strong signal)")
                else:
                    print(f"    Found {len(orgs)} total, {len(domain_matches)} domain-related, {len(law_firms)} law firms by industry")
                
                # Initialize variables
                best, reason = None, "no_candidates"
                
                if law_firms:
                    ranked = rank_and_dedupe_organizations(law_firms, input_query=domain_root, input_domain=domain_root)
                    best, reason = choose_best_org(firm_name, email_domain, ranked, attorney_email)
                    if best:
                        safe_name = best.get('name', 'Unknown').encode('ascii', 'ignore').decode('ascii')
                        print(f"    SUCCESS! Selected: {safe_name} ({reason}) - DOMAIN ROOT MATCH")
                        
                        org, contacts, selection_reason = search_people_with_fallback(ranked, firm_name, firm_domain, attorney_email)
                        if org:
                            safe_name = org.get('name', 'Unknown').encode('ascii', 'ignore').decode('ascii')
                            print(f"    FINAL SELECTION: {safe_name} ({selection_reason})")
                        
                        result.update({
                            'search_successful': True,
                            'winning_strategy': 'domain_root',
                            'winning_query': domain_root,
                            'organizations_found': [best],
                            'selection_reason': reason,
                            'firm_phone': best.get('phone') if best else None,
                            'contacts_found': len(contacts),
                            'contacts': contacts
                        })
                        attempt['success'] = True
                        result['attempts'].append(attempt)
                        
                        # Save successful result to cache
                        save_successful_result_to_cache(result, cursor, conn)
                        
                        return cleanup_and_return(result)
            
            result['attempts'].append(attempt)
    
    # STRATEGY 1.5: AI Website Search (if AI suggested a website)
    if ai_website and ai_website.lower() != 'unknown':
        print(f"  STRATEGY 1.5: AI-suggested website search")
        print(f"    AI suggested website: {ai_website}")
        
        # Clean up the URL (remove https://, www., etc.)
        # Handle cases where AI gives multiple URLs or explanatory text
        clean_website = ai_website.replace('https://', '').replace('http://', '').replace('www.', '')
        
        # If AI gives multiple URLs, take the first one
        if ' or ' in clean_website:
            clean_website = clean_website.split(' or ')[0].strip()
        if ' (' in clean_website:
            clean_website = clean_website.split(' (')[0].strip()
        if ' likely' in clean_website.lower():
            clean_website = clean_website.split(' likely')[0].strip()
        
        # Remove trailing slash and any extra text
        if clean_website.endswith('/'):
            clean_website = clean_website[:-1]
        
        # Validate it looks like a domain
        if ' ' in clean_website or len(clean_website.split('.')) < 2:
            print(f"    WARNING: AI suggested invalid URL format: '{ai_website}'")
            print(f"    Skipping AI website search due to invalid format")
        else:
            print(f"    Cleaned website: '{clean_website}'")
            print(f"  Attempt 1.5A: AI website search '{clean_website}'")
            time.sleep(1)
            api_response = search_apollo_organization(clean_website, page=1, per_page=100)
            attempt = {'strategy': 'ai_website', 'query': clean_website, 'success': False, 'organizations_count': 0}
            
            if api_response and api_response.get('organizations'):
                orgs = api_response['organizations']
                attempt['organizations_count'] = len(orgs)
                contacts = []  # Initialize contacts
                law_firms = [org for org in orgs if is_law_firm_by_industry(org)]
                print(f"    Found {len(orgs)} total organizations, {len(law_firms)} law firms")
                
                # Initialize variables
                best, reason = None, "no_candidates"
                
                if law_firms:
                    # For AI suggestions, we're more trusting since AI analyzed the lead
                    firm_name = lead_data.get('attorney_firm')
                    attorney_email = lead_data.get('attorney_email')
                    best, reason = choose_best_org(firm_name, clean_website, law_firms, attorney_email)
                    
                    if best:
                        confidence = ai_recovery.get('ai_confidence', 'unknown') if ai_recovery else 'unknown'
                        print(f"    AI WEBSITE SUCCESS: {best.get('name')} (confidence: {confidence}/10)")
                        
                        # Get people for this organization
                        contacts = search_people_with_fallback([best], firm_name, clean_website)
                        
                        # Store result and return early
                        result.update({
                            'search_successful': True,
                            'winning_strategy': 'ai_website',
                            'winning_query': clean_website,
                            'selected_organization': best,
                            'contacts': contacts,
                            'firm_phone': best.get('phone'),  # Company main phone
                            'match_score': 'ai_suggested'
                        })
                        attempt['success'] = True
                        result['attempts'].append(attempt)
                        
                        # Save successful result to cache
                        save_successful_result_to_cache(result, cursor, conn)
                        
                        return cleanup_and_return(result)
                    else:
                        print(f"    No suitable law firms found with AI website: {reason}")
                else:
                    print(f"    No law firms found using AI suggested website")
            else:
                print(f"    No organizations found with AI suggested website")
            
            result['attempts'].append(attempt)
    
    # STRATEGY 2: Name-Based Search (treat "attorney_firm" as potential firm name)
    print(f"  STRATEGY 2: Name-based search (treating '{firm_name}' as firm name)")
    if firm_name and firm_name != 'N/A':
        variations = get_search_variations(firm_name)
        print(f"    Using {len(variations)} search variations")
        
        for i, variation in enumerate(variations, 1):
            print(f"  Attempt 2{chr(64+i)}: '{variation}'")
            time.sleep(1)
            api_response = search_apollo_organization(variation, page=1, per_page=100)
            attempt = {'strategy': 'name_variation', 'query': variation, 'success': False, 'organizations_count': 0}
            if api_response and api_response.get('organizations'):
                orgs = api_response['organizations']
                attempt['organizations_count'] = len(orgs)
                contacts = []  # Initialize contacts
                law_firms = [org for org in orgs if is_law_firm_by_industry(org)]
                print(f"    Found {len(orgs)} total organizations, {len(law_firms)} law firms")
                
                # Initialize variables
                best, reason = None, "no_candidates"
                
                if law_firms:
                    # Cross-validate with attorney email domain if available
                    if attorney_email and '@' in attorney_email:
                        email_domain = extract_domain_from_email(attorney_email)
                        print(f"    Cross-validating results with email domain: {email_domain}")
                        # Boost orgs that match the email domain
                        for org in law_firms:
                            org_domain = org.get('primary_domain', '')
                            if org_domain and email_domain and safe_lower(org_domain) == safe_lower(email_domain):
                                print(f"      ++ DOMAIN MATCH: {org.get('name')} ({org_domain})")
                    
                    ranked = rank_and_dedupe_organizations(
                        law_firms,
                        input_query=variation,
                        input_domain=None if is_public_domain(firm_domain) else extract_domain_root(firm_domain)
                    )
                    best, reason = choose_best_org(firm_name, firm_domain, ranked, attorney_email)
                    if best:
                        safe_name = best.get('name', 'Unknown').encode('ascii', 'ignore').decode('ascii')
                        print(f"    SUCCESS! Selected: {safe_name} ({reason})")
                        
                        org, contacts, selection_reason = search_people_with_fallback(ranked, firm_name, firm_domain, attorney_email)
                        if org:
                            safe_name = org.get('name', 'Unknown').encode('ascii', 'ignore').decode('ascii')
                            print(f"    FINAL SELECTION: {safe_name} ({selection_reason})")
                        
                    result.update({
                        'search_successful': True,
                        'winning_strategy': 'name_variation',
                        'winning_query': variation,
                            'organizations_found': [best],
                            'selection_reason': reason,
                            'firm_phone': best.get('phone') if best else None,
                            'contacts_found': len(contacts),
                            'contacts': contacts
                    })
                    attempt['success'] = True
                    result['attempts'].append(attempt)
                    
                    # Save successful result to cache
                    save_successful_result_to_cache(result, cursor, conn)
                    
                    return cleanup_and_return(result)
                else:
                    print(f"    No clear winner ({reason}); trying next variation...")
            else:
                print(f"    No law firms found")
        else:
            print(f"    No results found")
            result['attempts'].append(attempt)

    # Domain fallbacks only if not public email domains
    if firm_domain and not is_public_domain(firm_domain):
        domain_root = extract_domain_root(firm_domain)

        if domain_root:
            print(f"  Fallback by domain-root-as-name: '{domain_root}'")
            api_response = search_apollo_organization(domain_root, page=1, per_page=100)
            attempt = {'strategy': 'domain_root_as_name', 'query': domain_root, 'success': False, 'organizations_count': 0}
            if api_response and api_response.get('organizations'):
                orgs = api_response['organizations']
                attempt['organizations_count'] = len(orgs)
                contacts = []  # Initialize contacts
                law_firms = [org for org in orgs if is_law_firm_by_industry(org)]
                
                # If no law firms found by industry, use all orgs (domain search is strong signal)
                if not law_firms and orgs:
                    law_firms = orgs
                    print(f"    Found {len(orgs)} total organizations via domain, using all (domain search is strong signal)")
                else:
                    print(f"    Found {len(orgs)} total organizations, {len(law_firms)} law firms by industry via domain")
                
                # Initialize variables
                best, reason = None, "no_candidates"
                
                if law_firms:
                    ranked = rank_and_dedupe_organizations(law_firms, input_query=domain_root, input_domain=domain_root)
                    best, reason = choose_best_org(firm_name, firm_domain, ranked, attorney_email)
                    if best:
                        safe_name = best.get('name', 'Unknown').encode('ascii', 'ignore').decode('ascii')
                        print(f"    SUCCESS! Selected: {safe_name} ({reason})")
                        
                        # Try multiple organizations until we find people
                        org, contacts, selection_reason = search_people_with_fallback(ranked, firm_name, firm_domain, attorney_email)
                        if org:
                            safe_name = org.get('name', 'Unknown').encode('ascii', 'ignore').decode('ascii')
                            print(f"    FINAL SELECTION: {safe_name} ({selection_reason})")
                        
                    result.update({
                        'search_successful': True,
                        'winning_strategy': 'domain_root_as_name',
                        'winning_query': domain_root,
                            'organizations_found': [best],
                            'selection_reason': reason,
                            'firm_phone': best.get('phone') if best else None,
                            'contacts_found': len(contacts),
                            'contacts': contacts
                    })
                    attempt['success'] = True
                    result['attempts'].append(attempt)
                    
                    # Save successful result to cache
                    save_successful_result_to_cache(result, cursor, conn)
                    
                    return cleanup_and_return(result)
                else:
                    print(f"    No clear winner ({reason}); trying next fallback...")
            else:
                print(f"    No law firms found via domain")
        else:
            print(f"    No results found via domain")
            result['attempts'].append(attempt)

        print(f"  Fallback by exact domain: '{firm_domain}'")
        api_response = search_apollo_organization(query="", domains=[firm_domain])
        attempt = {'strategy': 'domain_exact', 'query': firm_domain, 'success': False, 'organizations_count': 0}
        if api_response and api_response.get('organizations'):
            orgs = api_response['organizations']
            attempt['organizations_count'] = len(orgs)
            contacts = []  # Initialize contacts
            law_firms = [org for org in orgs if is_law_firm_by_industry(org)]
            
            # If no law firms found by industry, use all orgs (exact domain search is very strong signal)
            if not law_firms and orgs:
                law_firms = orgs
                print(f"    Found {len(orgs)} total organizations via exact domain, using all (exact domain is very strong signal)")
            else:
                print(f"    Found {len(orgs)} total organizations, {len(law_firms)} law firms by industry via exact domain")
            
            # Initialize variables
            best, reason = None, "no_candidates"
            
            if law_firms:
                ranked = rank_and_dedupe_organizations(law_firms, input_query=firm_name or firm_domain, input_domain=domain_root)
                best, reason = choose_best_org(firm_name, firm_domain, ranked, attorney_email)
                if best:
                    safe_name = best.get('name', 'Unknown').encode('ascii', 'ignore').decode('ascii')
                    print(f"    SUCCESS! Selected: {safe_name} ({reason})")
                    
                    # Try multiple organizations until we find people
                    org, contacts, selection_reason = search_people_with_fallback(ranked, firm_name, firm_domain)
                    if org:
                        safe_name = org.get('name', 'Unknown').encode('ascii', 'ignore').decode('ascii')
                        print(f"    FINAL SELECTION: {safe_name} ({selection_reason})")
                    
                result.update({
                    'search_successful': True,
                    'winning_strategy': 'domain_exact',
                    'winning_query': firm_domain,
                    'organizations_found': [best],
                    'selection_reason': reason,
                    'firm_phone': best.get('phone') if best else None,
                    'contacts_found': len(contacts),
                    'contacts': contacts
                })
                attempt['success'] = True
                result['attempts'].append(attempt)
                
                # Save successful result to cache
                save_successful_result_to_cache(result, cursor, conn)
                
                return cleanup_and_return(result)
            else:
                print(f"    No clear winner ({reason}); no further fallbacks.")
        else:
            print(f"    No law firms found via exact domain")
        result['attempts'].append(attempt)
    else:
        print(f"    No results found via exact domain")
        result['attempts'].append(attempt)
    
    # Handle public domain fallback
    if not firm_domain or is_public_domain(firm_domain):
        if firm_domain:
            print(f"  Skipping domain fallback for public email domain: '{firm_domain}'")

    # FINAL FALLBACK: Domain redirect search
    if attorney_email and '@' in attorney_email and not is_public_domain(extract_domain_from_email(attorney_email)):
        print(f"  FINAL FALLBACK: Trying domain redirect search...")
        redirect_data = search_by_domain_redirect(attorney_email, firm_name)
        
        if redirect_data and redirect_data.get('organizations'):
            orgs = redirect_data['organizations']
            attempt = {
                'strategy': 'domain_redirect', 
                'query': f"{extract_domain_from_email(attorney_email)} → {redirect_data['redirect_info']['final_domain']}", 
                'success': False, 
                'organizations_count': len(orgs)
            }
            
            # Use existing filtering and selection logic
            law_firms = [org for org in orgs if is_law_firm_by_industry(org)]
            
            # If no law firms found by industry, use all organizations (redirect is strong signal)
            if not law_firms and orgs:
                law_firms = orgs
                print(f"    Found {len(orgs)} total orgs, using all (redirect is strong signal)")
            else:
                print(f"    Found {len(orgs)} total orgs, {len(law_firms)} law firms by industry")
            
            # Initialize variables
            best, reason = None, "no_candidates"
            contacts = []
            
            if law_firms:
                ranked = rank_and_dedupe_organizations(law_firms, input_query=firm_name, input_domain=firm_domain)
                best, reason = choose_best_org(firm_name, firm_domain, ranked, attorney_email)
                
                if best:
                    safe_name = best.get('name', 'Unknown').encode('ascii', 'ignore').decode('ascii')
                    print(f"    SUCCESS! Selected: {safe_name} ({reason}) - DOMAIN REDIRECT")
                    
                    org, contacts, selection_reason = search_people_with_fallback(ranked, firm_name, firm_domain)
                    if org:
                        safe_name = org.get('name', 'Unknown').encode('ascii', 'ignore').decode('ascii')
                        print(f"    FINAL SELECTION: {safe_name} ({selection_reason})")
                    
                    result.update({
                        'search_successful': True,
                        'winning_strategy': 'domain_redirect',
                        'winning_query': redirect_data['redirect_info']['final_domain'],
                        'organizations_found': [best],
                        'selection_reason': f"redirect_{reason}",
                        'firm_phone': best.get('phone') if best else None,
                        'contacts_found': len(contacts),
                        'contacts': contacts,
                        'redirect_info': redirect_data['redirect_info']
                    })
                    attempt['success'] = True
                    result['attempts'].append(attempt)
                    
                    # Save successful result to cache
                    save_successful_result_to_cache(result, cursor, conn)
                    
                    return cleanup_and_return(result)
            
            result['attempts'].append(attempt)

    print(f"  FAILED: No organizations found for {firm_name}")
    return cleanup_and_return(result)

# Removed dead function: enrich_people_at_organization (was unused)

def main():
    # Connect to cache database
    conn, cursor = connect_to_db()
    if conn:
        print("[DB CACHE] Connected to Apollo cache database")
    else:
        print("[DB CACHE] Cache database not available - proceeding without cache")
    
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

    print(f"Processing {len(leads)} leads (company lookup only)...")
    results, processed_count, successful_searches = [], 0, 0

    for lead in leads:
        if not lead.get('needs_apollo_enrichment', False):
            continue
        processed_count += 1
        # Use -> instead of unicode arrow for Windows compatibility
        print(f"\nSearching firm for: {lead.get('client_name')} -> {lead.get('attorney_firm')}")
        search_result = search_firm_with_retry(lead, cursor=cursor, conn=conn)
        results.append(search_result)
        if search_result['search_successful']:
            successful_searches += 1

    output = {
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
        'mode': 'companies_only',
        'total_leads_processed': processed_count,
        'successful_searches': successful_searches,
        'success_rate': f"{(successful_searches/processed_count)*100:.1f}%" if processed_count else "0%",
        'search_results': results
    }

    out_file = 'apollo_company_results.json'
    with open(out_file, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print("\n" + "="*60)
    print(f"COMPANY SEARCH COMPLETE -> {out_file}")
    print(f"Processed: {processed_count} | Success: {successful_searches} | Rate: {output['success_rate']}")
    print("="*60)
    
    # Close database connection
    if conn:
        conn.close()
        print("[DB CACHE] Database connection closed")

if __name__ == "__main__":
    main()
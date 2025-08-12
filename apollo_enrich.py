import os
import json
import re
import time
import requests
import difflib
from dotenv import load_dotenv

load_dotenv()

# Defensive string helper functions to prevent NoneType errors
def safe_str(value):
    """Convert None to empty string, keep strings as-is"""
    return str(value) if value is not None else ''

def safe_lower(text):
    """Safely convert to lowercase, handles None"""
    return safe_str(text).lower()

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

def prioritize_legal_professionals(people):
    """
    Sort and select top 2 legal professionals based on title priority
    Priority: 1. partner, 2. attorney/lawyer, 3. counsel, 4. paralegal
    """
    def get_title_priority(person):
        title = person.get('title', '').lower()
        
        # Partner gets highest priority
        if 'partner' in title:
            return 1
        # Attorney/Lawyer second priority  
        elif 'attorney' in title or 'lawyer' in title:
            return 2
        # Counsel third priority
        elif 'counsel' in title:
            return 3
        # Paralegal lowest priority
        elif 'paralegal' in title:
            return 4
        # Unknown titles get medium priority
        else:
            return 2.5
    
    # Sort by priority (lower number = higher priority)
    sorted_people = sorted(people, key=get_title_priority)
    
    # Return top 2
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
    elif ' and ' in core.lower() and len(core.split()) >= 2:
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
        industries_text = ' '.join(str(ind).lower() for ind in industries)
        if any(term in industries_text for term in ['law', 'legal', 'attorney', 'counsel']):
            return True
    
    # Check keywords field (Apollo provides this in organizations format)  
    keywords = org.get('keywords', [])
    if keywords:
        keywords_text = ' '.join(str(kw).lower() for kw in keywords)
        if any(term in keywords_text for term in ['law', 'legal', 'attorney', 'counsel', 'litigation', 'paralegal']):
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
        "per_page": 25
    }

    try:
        response = requests.post(search_url, headers=headers, json=payload)
        response.raise_for_status()
        result = response.json()
        
        people = result.get("people", [])
        print(f"      Found {len(people)} legal professionals")
        
        if not people:
            return []
        
        # Apply priority filtering to get top 2 candidates
        top_people = prioritize_legal_professionals(people)
        print(f"      Selected top {len(top_people)} candidates based on title priority")
        for person in top_people:
            title = person.get('title', 'N/A')
            name = f"{person.get('first_name', '')} {person.get('last_name', '')}".strip()
            print(f"        - {name} ({title})")
        
        print(f"      Unlocking emails for {len(top_people)} contacts...")
        
        # Step 2: Enrich each person to unlock their email
        enrich_url = "https://api.apollo.io/api/v1/people/match"
        enriched_contacts = []
        
        for i, person in enumerate(top_people, 1):
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
                            contact_email_domain = extract_domain_from_email(email)
                            if contact_email_domain:
                                # Check if domains are related (same root domain)
                                attorney_root = extract_domain_root(attorney_firm_domain)
                                contact_root = extract_domain_root(contact_email_domain)
                                
                                if attorney_root and contact_root:
                                    if safe_lower(attorney_root) != safe_lower(contact_root):
                                        contact_domain_valid = False
                                        print(f"        [{i:2d}/{len(people)}] {enriched_person.get('first_name')} {enriched_person.get('last_name')} - Domain mismatch: {contact_email_domain} vs {attorney_firm_domain}")
                        
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
                time.sleep(1)
                
            except Exception as e:
                print(f"        [{i:2d}/{len(people)}] ERROR enriching {person.get('first_name')}: {e}")
        
        print(f"      Successfully unlocked {len(enriched_contacts)}/{len(top_people)} emails")
        return enriched_contacts
        
    except requests.exceptions.RequestException as e:
        print(f"      ERROR: People search failed for '{org_name}': {e}")
        return []

def search_people_with_fallback(candidates, firm_name, attorney_firm_domain=None):
    """Try multiple organizations until we find people"""
    for i, org in enumerate(candidates):
        org_id = org.get('id')
        org_name = org.get('name', 'Unknown')
        safe_name = org_name.encode('ascii', 'ignore').decode('ascii')
        
        print(f"    Trying organization #{i+1}: {safe_name}")
        contacts = search_people_at_organization(org_id, safe_name, attorney_firm_domain)
        
        if contacts:
            print(f"      SUCCESS! Found {len(contacts)} people")
            return org, contacts, f"fallback_org_{i+1}"
        else:
            print(f"      No people found, trying next organization...")
    
    # If no org has people, return the first one anyway
    if candidates:
        org = candidates[0]
        return org, [], "no_people_found"
    
    return None, [], "no_candidates"

def search_firm_with_retry(lead_data):
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
        'attempts': []
    }

    firm_name = lead_data.get('attorney_firm')
    firm_domain = (lead_data.get('firm_domain') or '').lower()
    attorney_email = lead_data.get('attorney_email')
    
    print(f"    Input data: firm_name='{firm_name}', attorney_email='{attorney_email}'")
    
    # STRATEGY 1: Domain-First Search (when we have attorney email)
    if attorney_email and '@' in attorney_email and not is_public_domain(extract_domain_from_email(attorney_email)):
        email_domain = extract_domain_from_email(attorney_email)
        domain_root = extract_domain_root(email_domain)
        
        print(f"  STRATEGY 1: Domain-first search")
        print(f"    Email domain: {email_domain}")
        print(f"    Domain root: {domain_root}")
        
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
                        'contacts_found': len(contacts),
                        'contacts': contacts
                    })
                    attempt['success'] = True
                    result['attempts'].append(attempt)
                    return result
        
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
                        
                        org, contacts, selection_reason = search_people_with_fallback(ranked, firm_name, firm_domain)
                        if org:
                            safe_name = org.get('name', 'Unknown').encode('ascii', 'ignore').decode('ascii')
                            print(f"    FINAL SELECTION: {safe_name} ({selection_reason})")
                        
                        result.update({
                            'search_successful': True,
                            'winning_strategy': 'domain_root',
                            'winning_query': domain_root,
                            'organizations_found': [best],
                            'selection_reason': reason,
                            'contacts_found': len(contacts),
                            'contacts': contacts
                        })
                        attempt['success'] = True
                        result['attempts'].append(attempt)
                        return result
            
            result['attempts'].append(attempt)
    
    # STRATEGY 2: Name-Based Search (treat "attorney_firm" as potential firm name)
    print(f"  STRATEGY 2: Name-based search (treating '{firm_name}' as firm name)")
    if firm_name and firm_name != 'N/A':
        variations = get_search_variations(firm_name)
        print(f"    Using {len(variations)} search variations")
        
        for i, variation in enumerate(variations, 1):
            print(f"  Attempt 2{chr(64+i)}: '{variation}'")
            time.sleep(0.2)
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
                        
                        org, contacts, selection_reason = search_people_with_fallback(ranked, firm_name, firm_domain)
                        if org:
                            safe_name = org.get('name', 'Unknown').encode('ascii', 'ignore').decode('ascii')
                            print(f"    FINAL SELECTION: {safe_name} ({selection_reason})")
                        
                    result.update({
                        'search_successful': True,
                        'winning_strategy': 'name_variation',
                        'winning_query': variation,
                            'organizations_found': [best],
                            'selection_reason': reason,
                            'contacts_found': len(contacts),
                            'contacts': contacts
                    })
                    attempt['success'] = True
                    result['attempts'].append(attempt)
                    return result
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
                        org, contacts, selection_reason = search_people_with_fallback(ranked, firm_name, firm_domain)
                        if org:
                            safe_name = org.get('name', 'Unknown').encode('ascii', 'ignore').decode('ascii')
                            print(f"    FINAL SELECTION: {safe_name} ({selection_reason})")
                        
                    result.update({
                        'search_successful': True,
                        'winning_strategy': 'domain_root_as_name',
                        'winning_query': domain_root,
                            'organizations_found': [best],
                            'selection_reason': reason,
                            'contacts_found': len(contacts),
                            'contacts': contacts
                    })
                    attempt['success'] = True
                    result['attempts'].append(attempt)
                    return result
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
                            'contacts_found': len(contacts),
                            'contacts': contacts
                })
                attempt['success'] = True
                result['attempts'].append(attempt)
                return result
            else:
                print(f"    No clear winner ({reason}); no further fallbacks.")
        else:
            print(f"    No law firms found via exact domain")
    else:
        print(f"    No results found via exact domain")
    result['attempts'].append(attempt)
    
    # Handle public domain fallback
    if not firm_domain or is_public_domain(firm_domain):
        if firm_domain:
            print(f"  Skipping domain fallback for public email domain: '{firm_domain}'")

    print(f"  FAILED: No organizations found for {firm_name}")
    return result

def enrich_people_at_organization(org_id, org_name):
    """Get people from org, then enrich each one individually to unlock emails"""
    api_key = os.getenv('APOLLO_API_KEY')
    
    # Step 1: Get people list (no emails unlocked yet)
    search_url = "https://api.apollo.io/api/v1/mixed_people/search"
    headers = {
        'Content-Type': 'application/json',
        'Cache-Control': 'no-cache',
        'X-Api-Key': api_key
    }
    
    payload = {
        "organization_ids": [org_id],
        "person_titles": ["attorney", "partner", "lawyer", "counsel", "paralegal"],
        "page": 1,
        "per_page": 25
    }
    
    # Get people list
    response = requests.post(search_url, headers=headers, json=payload)
    people = response.json().get("people", [])
    print(f"      Found {len(people)} legal professionals")
    
    # Step 2: Enrich each person to unlock their email
    enriched_contacts = []
    enrich_url = "https://api.apollo.io/api/v1/people/match"
    
    for person in people:
        # Use person data to enrich and unlock email
        enrich_payload = {
            "first_name": person.get('first_name'),
            "last_name": person.get('last_name'),
            "organization_name": org_name,
            "reveal_personal_emails": True  # THIS is the correct parameter
        }
        
        try:
            enrich_response = requests.post(enrich_url, headers=headers, json=enrich_payload)
            if enrich_response.status_code == 200:
                enriched_person = enrich_response.json().get('person', {})
                
                contact = {
                    'name': f"{enriched_person.get('first_name', '')} {enriched_person.get('last_name', '')}".strip(),
                    'title': enriched_person.get('title'),
                    'email': enriched_person.get('email'),  # Real email now
                    'linkedin_url': enriched_person.get('linkedin_url'),
                    'phone': None,
                    'organization_id': org_id,
                    'person_id': enriched_person.get('id')
                }
                enriched_contacts.append(contact)
                print(f"        ✓ Enriched {contact['name']} - {contact['email']}")
            else:
                print(f"        ✗ Failed to enrich {person.get('first_name')} {person.get('last_name')}")
            
            time.sleep(0.5)  # Rate limiting
            
        except Exception as e:
            print(f"        ERROR enriching {person.get('first_name')}: {e}")
    
    return enriched_contacts

def main():
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
        search_result = search_firm_with_retry(lead)
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

if __name__ == "__main__":
    main()
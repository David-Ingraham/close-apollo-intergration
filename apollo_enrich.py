import os
import json
import re
import time
import requests
import difflib
from dotenv import load_dotenv

load_dotenv()

# Correct endpoint (no /api)
APOLLO_SEARCH_URL = "https://api.apollo.io/v1/mixed_companies/search"

PUBLIC_DOMAINS = {
    "gmail.com","yahoo.com","outlook.com","hotmail.com","aol.com","icloud.com",
    "protonmail.com","yandex.com","msn.com","live.com","me.com"
}
def is_public_domain(d):
    return bool(d) and d.lower() in PUBLIC_DOMAINS

def clean_firm_name(name):
    if not name or name == 'N/A':
        return name
    legal_terms = [
        'the law offices of', 'law offices of', 'law office of', 'law firm of',
        'law firm', 'attorneys at law', 'llp', 'llc', 'pc', 'pllc',
        'ltd', 'inc', 'corporation', 'corp', 'group', 'associates'
    ]
    cleaned = name.lower()
    for term in legal_terms:
        cleaned = cleaned.replace(term, '')
    cleaned = re.sub(r'[,&]+', ' ', cleaned)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned

def extract_domain_root(domain):
    if not domain or domain == 'N/A':
        return None
    parts = domain.lower().strip().split('.')
    if len(parts) > 2 and parts[-2] in {"co"}:
        return parts[-3]
    return parts[0] if len(parts) > 1 else domain

def get_search_variations(firm_name):
    if not firm_name or firm_name == 'N/A':
        return []
    variations = []

    # Original and quoted exact
    variations += [firm_name, f'"{firm_name}"']

    # Cleaned
    cleaned = clean_firm_name(firm_name)
    if cleaned and cleaned != firm_name.lower():
        variations += [cleaned, f'"{cleaned}"']

    # Remove prefixes/suffixes
    core = firm_name
    for prefix in [r'^the\s+law\s+offices?\s+of\s+', r'^law\s+offices?\s+of\s+', r'^the\s+law\s+firm\s+of\s+']:
        core = re.sub(prefix, '', core, flags=re.IGNORECASE)
    core = re.sub(r',?\s*(llp|llc|pc|pllc|ltd|inc|corp|corporation)\.?$', '', core, flags=re.IGNORECASE).strip()
    if core and core != firm_name:
        variations += [core, f'"{core}"']

    # & vs and
    if '&' in core:
        variations += [core.replace('&', 'and'), core.replace('&', '')]
    elif ' and ' in core.lower():
        variations += [re.sub(r'\s+and\s+', ' & ', core, flags=re.IGNORECASE),
                       re.sub(r'\s+and\s+', ' ', core, flags=re.IGNORECASE)]

    # Helpful normalizations (e.g., "Downtown LA Law")
    variations.append(re.sub(r'\bLA\b', 'Los Angeles', core, flags=re.IGNORECASE))
    variations.append(re.sub(r'\s+Group$', '', core, flags=re.IGNORECASE))
    # DTLA nickname
    if re.search(r'\bdowntown\s+la\b', core, flags=re.IGNORECASE):
        variations.append('DTLA Law Group')

    # Extract surnames to try as fallbacks (Rotstein, Shiffman)
    names = re.findall(r'\b[A-Z][a-z]{3,}\b', core)
    legal_words = {'Law','Firm','Office','Offices','Group','Attorney','Attorneys','Associates','Legal'}
    # Don't add single generic words as variations
    generic_words = {'downtown', 'law', 'group', 'office', 'firm', 'attorneys', 'legal'}
    for n in names:
        if n not in legal_words and n.lower() not in generic_words:
            variations.append(n)

    # Dedup preserving order
    seen, uniq = set(), []
    for v in variations:
        k = v.strip().lower()
        if k and k not in seen:
            seen.add(k)
            uniq.append(v.strip())
    return uniq

def is_law_firm(name):
    if not name:
        return False
    n = name.lower()
    indicators = ['law', 'attorney', 'attorneys', 'legal', 'counsel', 'llp', 'law firm', 'law office', 'law offices', 'associates', 'partners']
    return any(t in n for t in indicators)

def _post(headers, payload):
    try:
        resp = requests.post(APOLLO_SEARCH_URL, headers=headers, json=payload)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as e:
        print(f"      WARN: search request error: {e}")
        return None

def search_apollo_organization(query, page=1, per_page=100, domains=None):
    api_key = os.getenv('APOLLO_API_KEY')
    if not api_key:
        raise ValueError("APOLLO_API_KEY not found in environment variables")
    headers = {'Content-Type': 'application/json', 'Cache-Control': 'no-cache', 'X-Api-Key': api_key}

    # Name search (primary)
    data = _post(headers, {"q_organization_name": query, "page": page, "per_page": per_page})
    if data and data.get("organizations"):
        return data

    # Domain search (exact) if provided
    if domains:
        for key in ("company_domains", "domains", "q_company_domains"):
            data = _post(headers, {key: domains, "page": 1, "per_page": 100})
            if data and data.get("organizations"):
                return data
    return None

def _primary_domain(org):
    d = org.get("primary_domain")
    if d:
        return d.lower()
    website = org.get("website_url") or ""
    website = website.replace("http://", "").replace("https://", "").split("/")[0].lower()
    return website or None

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
        s += difflib.SequenceMatcher(None, name.lower(), input_query.lower()).ratio() * 60
        if input_query.lower() in name.lower():
            s += 10
        if is_law_firm(name):
            s += 10
        if input_domain and domain and input_domain.lower() in domain:
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
            "_score": round(difflib.SequenceMatcher(None, (o.get('name') or '').lower(), input_query.lower()).ratio(), 3)
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
    n = (name or "").lower()
    return any(h in n for h in LEGAL_HINTS)

def choose_best_org(lead_firm_name, firm_domain, candidates):
    if not candidates:
        return None, "no_candidates"
    
    core = normalize_core(lead_firm_name or "")
    core_tokens = set(core.split())
    acro = acronym(core)

    # 1) Exact domain match (non-public)
    if firm_domain and not is_public_domain(firm_domain):
        exact = [c for c in candidates if (c.get("primary_domain") or "").lower() == firm_domain.lower()]
        if exact:
            exact.sort(key=lambda c: difflib.SequenceMatcher(None, (c.get("name") or "").lower(), core).ratio(), reverse=True)
            return exact[0], "exact_domain"

    # 2) Score by name similarity + token coverage + hints + domain root
    dom_root = extract_domain_root(firm_domain) if firm_domain and not is_public_domain(firm_domain) else None

    def score(c):
        name = (c.get("name") or "").lower()
        domain = c.get("primary_domain") or ""
        tokens_in = len(core_tokens & set(name.split()))
        core_cov = tokens_in / max(1, len(core_tokens))
        sim = difflib.SequenceMatcher(None, name, core).ratio()
        bonus = 0.0
        
        # Legal firm bonus
        if name_has_legal_hint(name): bonus += 0.08
        
        # Acronym matching bonus
        if acro and acro in name.replace(' ', ''): bonus += 0.06
        
        # Domain matching bonuses (heavily weighted)
        if dom_root and domain:
            if dom_root in domain.lower(): bonus += 0.15  # Strong domain match
            # Check if query tokens appear in domain
            for token in core_tokens:
                if len(token) > 2 and token in domain.lower(): bonus += 0.10
        
        # Bonus for having any real domain vs "no-domain"
        if domain and domain != "no-domain": bonus += 0.05
        
        # Name token matching bonus (for cases like "KP" matching "KP Attorneys")
        query_words = set(lead_firm_name.lower().split()) if lead_firm_name else set()
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

    # Must be a law firm
    if not name_has_legal_hint(top.get("name", "")):
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

def search_people_at_organization(org_id, org_name):
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
        "person_titles": ["attorney", "partner", "lawyer", "counsel", "paralegal"],
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
        
        print(f"      Unlocking emails for {len(people)} contacts...")
        
        # Step 2: Enrich each person to unlock their email
        enrich_url = "https://api.apollo.io/api/v1/people/match"
        enriched_contacts = []
        
        for i, person in enumerate(people, 1):
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
                        print(f"        [{i:2d}/{len(people)}] ✓ {contact['name']} - {email}")
                    else:
                        print(f"        [{i:2d}/{len(people)}] ✗ {person.get('first_name')} {person.get('last_name')} - No email available")
                else:
                    print(f"        [{i:2d}/{len(people)}] ✗ {person.get('first_name')} {person.get('last_name')} - Enrichment failed ({enrich_response.status_code})")
                
                # Rate limiting to avoid Apollo API limits
                time.sleep(1)
                
            except Exception as e:
                print(f"        [{i:2d}/{len(people)}] ERROR enriching {person.get('first_name')}: {e}")
        
        print(f"      Successfully unlocked {len(enriched_contacts)}/{len(people)} emails")
        return enriched_contacts
        
    except requests.exceptions.RequestException as e:
        print(f"      ERROR: People search failed for '{org_name}': {e}")
        return []

def search_people_with_fallback(candidates, firm_name):
    """Try multiple organizations until we find people"""
    for i, org in enumerate(candidates):
        org_id = org.get('id')
        org_name = org.get('name', 'Unknown')
        safe_name = org_name.encode('ascii', 'ignore').decode('ascii')
        
        print(f"    Trying organization #{i+1}: {safe_name}")
        contacts = search_people_at_organization(org_id, safe_name)
        
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
        'search_successful': False,
        'winning_strategy': None,
        'winning_query': None,
        'organizations_found': [],
        'attempts': []
    }

    firm_name = lead_data.get('attorney_firm')
    firm_domain = (lead_data.get('firm_domain') or '').lower()

    # Name variations first
    if firm_name and firm_name != 'N/A':
        variations = get_search_variations(firm_name)
        for i, variation in enumerate(variations, 1):
            print(f"  Attempt {i}: '{variation}'")
            time.sleep(0.2)
            api_response = search_apollo_organization(variation, page=1, per_page=100)
            attempt = {'strategy': 'name_variation', 'query': variation, 'success': False, 'organizations_count': 0}
            if api_response and api_response.get('organizations'):
                orgs = api_response['organizations']
                attempt['organizations_count'] = len(orgs)
                # Filter for law firms
                law_firms = [org for org in orgs if is_law_firm(org.get('name', ''))]
                print(f"    Found {len(orgs)} total organizations, {len(law_firms)} law firms")
                
                if law_firms:
                    ranked = rank_and_dedupe_organizations(
                        law_firms,
                        input_query=variation,
                        input_domain=None if is_public_domain(firm_domain) else extract_domain_root(firm_domain)
                    )
                    best, reason = choose_best_org(firm_name, firm_domain, ranked)
                    if best:
                        safe_name = best.get('name', 'Unknown').encode('ascii', 'ignore').decode('ascii')
                        print(f"    SUCCESS! Selected: {safe_name} ({reason})")
                        
                        # Try multiple organizations until we find people
                        org, contacts, selection_reason = search_people_with_fallback(ranked, firm_name)
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
                law_firms = [org for org in orgs if is_law_firm(org.get('name', ''))]
                print(f"    Found {len(orgs)} total organizations, {len(law_firms)} law firms via domain")
                
                if law_firms:
                    ranked = rank_and_dedupe_organizations(law_firms, input_query=domain_root, input_domain=domain_root)
                    best, reason = choose_best_org(firm_name, firm_domain, ranked)
                    if best:
                        safe_name = best.get('name', 'Unknown').encode('ascii', 'ignore').decode('ascii')
                        print(f"    SUCCESS! Selected: {safe_name} ({reason})")
                        
                        # Try multiple organizations until we find people
                        org, contacts, selection_reason = search_people_with_fallback(ranked, firm_name)
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
            law_firms = [org for org in orgs if is_law_firm(org.get('name', ''))]
            print(f"    Found {len(orgs)} total organizations, {len(law_firms)} law firms via exact domain")
            
            if law_firms:
                ranked = rank_and_dedupe_organizations(law_firms, input_query=firm_name or firm_domain, input_domain=domain_root)
                best, reason = choose_best_org(firm_name, firm_domain, ranked)
                if best:
                    safe_name = best.get('name', 'Unknown').encode('ascii', 'ignore').decode('ascii')
                    print(f"    SUCCESS! Selected: {safe_name} ({reason})")
                    
                    # Try multiple organizations until we find people
                    org, contacts, selection_reason = search_people_with_fallback(ranked, firm_name)
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
    else:
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
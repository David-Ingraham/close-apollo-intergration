import os
import json
import time
import requests
import difflib
import re
from base64 import b64encode
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

class ApolloClosePipeline:
    def __init__(self):
        self.close_api_key = os.getenv('CLOSE_API_KEY')
        self.apollo_api_key = os.getenv('APOLLO_API_KEY')
        self.ngrok_url = os.getenv('NGROK_URL')
        
        if not all([self.close_api_key, self.apollo_api_key, self.ngrok_url]):
            raise ValueError("Missing required environment variables")
        
        self.leads_data = []
        self.enriched_data = []
        self.phone_requests = []
        self.webhook_responses = []
        
        # Apollo search configuration
        self.PUBLIC_DOMAINS = {
            "gmail.com","yahoo.com","outlook.com","hotmail.com","aol.com","icloud.com",
            "protonmail.com","yandex.com","msn.com","live.com","me.com"
        }
        
    def print_header(self, title):
        """Print a formatted header"""
        print("\n" + "=" * 60)
        print(f" {title}")
        print("=" * 60)
    
    def get_close_auth_header(self):
        """Get Close CRM authentication header"""
        encoded_key = b64encode(f"{self.close_api_key}:".encode('utf-8')).decode('utf-8')
        return f'Basic {encoded_key}'
    
    def extract_domain_from_email(self, email):
        """Extract domain from email address"""
        if email and '@' in email:
            return email.split('@')[1]
        return None
    
    def is_public_domain(self, domain):
        """Check if domain is a public email provider"""
        return bool(domain) and domain.lower() in self.PUBLIC_DOMAINS
    
    def extract_domain_root(self, domain):
        """Extract root domain name (before .com, .org, etc.)"""
        if not domain:
            return None
        parts = domain.split('.')
        return parts[0] if parts else None
    
    def clean_firm_name(self, name):
        """Clean firm name for searching"""
        if not name or name == 'N/A':
            return name
        
        name = re.sub(r'\b(the\s+)?law\s+(offices?\s+of\s+|firm\s+of\s+)?', '', name, flags=re.IGNORECASE)
        name = re.sub(r',?\s*(llp|llc|pc|pllc|ltd|inc|corp|corporation|group|pllc)\.?$', '', name, flags=re.IGNORECASE)
        name = re.sub(r'\s+', ' ', name).strip()
        return name
    
    def is_law_firm(self, name):
        """Check if organization name indicates a law firm"""
        if not name:
            return False
        
        name_lower = name.lower()
        legal_indicators = [
            'law', 'attorney', 'lawyer', 'legal', 'counsel', 'advocacy',
            'litigation', 'firm', 'associates', 'partner'
        ]
        
        return any(indicator in name_lower for indicator in legal_indicators)
    
    def step1_get_todays_leads(self):
        """Step 1: Get today's leads from Close CRM"""
        self.print_header("STEP 1: GETTING TODAY'S LEADS FROM CLOSE CRM")
        
        todays_leads_view_id = "save_ebxRoBR5KEXJz0jTSCfn1xyaXMQYBHmskqU6iCOoZd9"
        url = 'https://api.close.com/api/v1/data/search/'
        
        headers = {
            'Authorization': self.get_close_auth_header(),
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        
        payload = {
            "query": {
                "type": "saved_search",
                "saved_search_id": todays_leads_view_id
            },
            "_fields": {
                "lead": ["id", "display_name", "status_id", "name", "contacts", "custom"]
            },
            "results_limit": 100
        }
        
        try:
            response = requests.post(url, headers=headers, json=payload)
            response.raise_for_status()
            
            leads = response.json()
            self.leads_data = self.process_leads_data(leads.get('data', []))
            
            print(f"Retrieved {len(self.leads_data)} leads")
            enrichable = len([l for l in self.leads_data if l.get('needs_apollo_enrichment')])
            print(f"{enrichable} leads need Apollo enrichment")
            
            return len(self.leads_data) > 0
            
        except Exception as e:
            print(f"ERROR: Failed to get leads from Close CRM: {e}")
            return False
    
    def process_leads_data(self, leads):
        """Process raw leads data from Close CRM"""
        processed_leads = []
        
        for lead in leads:
            if not lead.get('contacts') or len(lead['contacts']) == 0:
                continue
                
            # Get client info from first contact
            client_contact = lead['contacts'][0]
            client_name = client_contact.get('name', client_contact.get('display_name', 'N/A'))
            client_email = 'N/A'
            
            if client_contact.get('emails') and len(client_contact['emails']) > 0:
                client_email = client_contact['emails'][0].get('email', 'N/A')
            
            # Extract attorney/firm info from custom fields
            firm_name = client_contact.get('custom.cf_bB8dqX4BWGbISOehyNVVaZhJpfV9OZNOqs5WfYjaRYv', 'N/A')
            attorney_email = client_contact.get('custom.cf_vq0cl2Sj1h0QaSePdnTdf3NyAjx3w4QcgmlhgJrWrZE', 'N/A')
            
            # Try alternate firm name field if first is empty
            if firm_name == 'N/A':
                firm_name = client_contact.get('custom.cf_lQKyH0EhHsNDLZn8KqfFSb0342doHgTNfWdTcfWCljw', 'N/A')
            
            # Determine if this lead needs enrichment
            firm_domain = self.extract_domain_from_email(attorney_email) if attorney_email != 'N/A' else None
            needs_enrichment = True
            skip_reason = None
            
            # Skip if no firm name
            if firm_name == 'N/A' or not firm_name:
                needs_enrichment = False
                skip_reason = 'no_firm_name'
            
            # Skip if personal email domain only
            elif attorney_email != 'N/A' and self.is_public_domain(firm_domain):
                # Only skip if firm name looks like a person's name (not a firm)
                if not self.is_law_firm(firm_name):
                    needs_enrichment = False
                    skip_reason = 'personal_email_and_person_name'
            
            processed_lead = {
                'lead_id': lead.get('id'),
                'client_name': client_name,
                'client_email': client_email,
                'attorney_firm': firm_name,
                'attorney_email': attorney_email,
                'firm_domain': firm_domain,
                'needs_apollo_enrichment': needs_enrichment,
                'skip_reason': skip_reason
            }
            
            processed_leads.append(processed_lead)
        
        return processed_leads
    
    def step2_apollo_enrichment(self):
        """Step 2: Enrich leads with Apollo company and people data"""
        self.print_header("STEP 2: APOLLO COMPANY & PEOPLE ENRICHMENT")
        
        leads_to_process = [l for l in self.leads_data if l.get('needs_apollo_enrichment')]
        print(f"Processing {len(leads_to_process)} leads for Apollo enrichment...")
        
        enriched_results = []
        successful_searches = 0
        
        for lead in leads_to_process:
            print(f"\nSearching firm for: {lead.get('client_name')} -> {lead.get('attorney_firm')}")
            
            # Search for the firm
            firm_result = self.search_firm_with_apollo(lead)
            
            if firm_result.get('search_successful'):
                # Get people from the firm
                org_id = firm_result['organization']['id']
                org_name = firm_result['organization']['name']
                contacts = self.get_people_from_organization(org_id, org_name)
                
                firm_result['contacts'] = contacts
                successful_searches += 1
                print(f"    SUCCESS! Found {len(contacts)} contacts")
            else:
                firm_result['contacts'] = []
                print(f"    FAILED: No firm found")
            
            enriched_results.append(firm_result)
        
        self.enriched_data = enriched_results
        print(f"\nEnrichment complete: {successful_searches}/{len(leads_to_process)} successful")
        
        return successful_searches > 0
    
    def search_firm_with_apollo(self, lead_data):
        """Search for a firm using Apollo API"""
        result = {
            'lead_id': lead_data.get('lead_id'),
            'client_name': lead_data.get('client_name'),
            'firm_name': lead_data.get('attorney_firm'),
            'search_successful': False,
            'organization': None,
            'winning_strategy': None
        }
        
        firm_name = lead_data.get('attorney_firm')
        attorney_email = lead_data.get('attorney_email')
        
        # Strategy 1: Domain-first search (if we have attorney email)
        if attorney_email and '@' in attorney_email and not self.is_public_domain(self.extract_domain_from_email(attorney_email)):
            email_domain = self.extract_domain_from_email(attorney_email)
            print(f"    Trying domain-first search: {email_domain}")
            
            org = self.search_apollo_by_domain(email_domain)
            if org:
                result.update({
                    'search_successful': True,
                    'organization': org,
                    'winning_strategy': 'domain_search'
                })
                return result
        
        # Strategy 2: Name-based search
        print(f"    Trying name-based search: {firm_name}")
        org = self.search_apollo_by_name(firm_name)
        if org:
            result.update({
                'search_successful': True,
                'organization': org,
                'winning_strategy': 'name_search'
            })
        
        return result
    
    def search_apollo_by_domain(self, domain):
        """Search Apollo by domain"""
        url = "https://api.apollo.io/v1/mixed_companies/search"
        headers = {
            'Content-Type': 'application/json',
            'Cache-Control': 'no-cache',
            'X-Api-Key': self.apollo_api_key
        }
        
        payload = {
            "q_organization_domain": domain,
            "page": 1,
            "per_page": 10
        }
        
        try:
            response = requests.post(url, headers=headers, json=payload)
            if response.status_code == 200:
                data = response.json()
                orgs = data.get('organizations', [])
                
                # Look for exact domain match and law firm
                for org in orgs:
                    if (org.get('primary_domain', '').lower() == domain.lower() and 
                        self.is_law_firm(org.get('name', ''))):
                        return org
        except Exception as e:
            print(f"        Domain search error: {e}")
        
        return None
    
    def search_apollo_by_name(self, firm_name):
        """Search Apollo by firm name"""
        url = "https://api.apollo.io/v1/mixed_companies/search"
        headers = {
            'Content-Type': 'application/json',
            'Cache-Control': 'no-cache',
            'X-Api-Key': self.apollo_api_key
        }
        
        # Try exact name first, then cleaned name
        search_terms = [firm_name, self.clean_firm_name(firm_name)]
        
        for term in search_terms:
            if not term:
                continue
                
            payload = {
                "q_organization_name": term,
                "page": 1,
                "per_page": 20
            }
            
            try:
                response = requests.post(url, headers=headers, json=payload)
                if response.status_code == 200:
                    data = response.json()
                    orgs = data.get('organizations', [])
                    
                    # Look for law firms and score them
                    law_firms = [org for org in orgs if self.is_law_firm(org.get('name', ''))]
                    if law_firms:
                        # Simple scoring - prefer exact name match
                        for org in law_firms:
                            if org.get('name', '').lower() == term.lower():
                                return org
                        # If no exact match, return first law firm
                        return law_firms[0]
                        
            except Exception as e:
                print(f"        Name search error: {e}")
        
        return None
    
    def get_people_from_organization(self, org_id, org_name):
        """Get people from an organization and unlock their emails"""
        url = "https://api.apollo.io/api/v1/mixed_people/search"
        headers = {
            'Content-Type': 'application/json',
            'Cache-Control': 'no-cache',
            'X-Api-Key': self.apollo_api_key
        }
        
        payload = {
            "organization_ids": [org_id],
            "person_titles": ["attorney", "partner", "lawyer", "counsel", "paralegal"],
            "page": 1,
            "per_page": 25
        }
        
        try:
            response = requests.post(url, headers=headers, json=payload)
            if response.status_code == 200:
                data = response.json()
                people = data.get('people', [])
                
                # Enrich each person to unlock email
                enriched_contacts = []
                for person in people[:5]:  # Limit to top 5 to save credits
                    enriched = self.enrich_person_email(person, org_name)
                    if enriched:
                        enriched_contacts.append(enriched)
                
                return enriched_contacts
                
        except Exception as e:
            print(f"        People search error: {e}")
        
        return []
    
    def enrich_person_email(self, person, org_name):
        """Enrich a person to unlock their email"""
        url = "https://api.apollo.io/api/v1/people/match"
        headers = {
            'Content-Type': 'application/json',
            'Cache-Control': 'no-cache',
            'X-Api-Key': self.apollo_api_key
        }
        
        payload = {
            "first_name": person.get('first_name'),
            "last_name": person.get('last_name'),
            "organization_name": org_name,
            "reveal_personal_emails": True
        }
        
        try:
            response = requests.post(url, headers=headers, json=payload)
            if response.status_code == 200:
                result = response.json()
                enriched_person = result.get('person', {})
                
                email = enriched_person.get('email')
                if email and email != 'email_not_unlocked@domain.com':
                    return {
                        'name': f"{enriched_person.get('first_name', '')} {enriched_person.get('last_name', '')}".strip(),
                        'title': enriched_person.get('title') or person.get('title'),
                        'email': email,
                        'linkedin_url': enriched_person.get('linkedin_url'),
                        'person_id': enriched_person.get('id'),
                        'phone': None  # Will be filled by webhook
                    }
        except Exception as e:
            print(f"        Email enrichment error: {e}")
        
        return None
    
    def step3_send_phone_requests(self):
        """Step 3: Send phone number enrichment requests to Apollo"""
        self.print_header("STEP 3: SENDING PHONE NUMBER REQUESTS")
        
        # Collect all contacts that need phone enrichment
        phone_targets = []
        for result in self.enriched_data:
            if result.get('search_successful') and result.get('contacts'):
                for contact in result['contacts']:
                    if contact.get('person_id'):
                        phone_targets.append({
                            'lead_id': result['lead_id'],
                            'firm_name': result['firm_name'],
                            'contact': contact
                        })
        
        print(f"Sending phone requests for {len(phone_targets)} contacts...")
        
        successful_requests = 0
        for i, target in enumerate(phone_targets, 1):
            contact = target['contact']
            success = self.send_phone_enrichment_request(contact, i, len(phone_targets))
            if success:
                successful_requests += 1
                self.phone_requests.append(target)
        
        print(f"\nPhone requests complete: {successful_requests}/{len(phone_targets)} successful")
        return successful_requests > 0
    
    def send_phone_enrichment_request(self, contact, index, total):
        """Send individual phone enrichment request"""
        url = "https://api.apollo.io/api/v1/people/match"
        headers = {
            'Content-Type': 'application/json',
            'Cache-Control': 'no-cache',
            'X-Api-Key': self.apollo_api_key
        }
        
        payload = {
            "person_id": contact['person_id'],
            "reveal_phone_number": True,
            "webhook_url": f"{self.ngrok_url}/apollo-webhook"
        }
        
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                person = result.get('person', {})
                
                if person and person.get('id'):
                    print(f"   [{index:2d}/{total}] ✓ {contact['name']} - Phone request sent")
                    return True
                else:
                    print(f"   [{index:2d}/{total}] ✗ {contact['name']} - No person data")
                    return False
            else:
                print(f"   [{index:2d}/{total}] ✗ {contact['name']} - HTTP {response.status_code}")
                return False
                
        except Exception as e:
            print(f"   [{index:2d}/{total}] ✗ {contact['name']} - Error: {e}")
            return False
    
    def step4_update_close_with_emails(self):
        """Step 4: Update Close CRM with email contacts"""
        self.print_header("STEP 4: UPDATING CLOSE CRM WITH EMAIL CONTACTS")
        
        total_contacts = 0
        for result in self.enriched_data:
            if result.get('search_successful') and result.get('contacts'):
                lead_id = result['lead_id']
                firm_name = result['firm_name']
                contacts = result['contacts']
                
                print(f"\n{result['client_name']} -> {firm_name} ({len(contacts)} contacts)")
                print(f"Lead ID: {lead_id}")
                
                for contact in contacts:
                    success = self.add_contact_to_close_lead(lead_id, firm_name, contact)
                    if success:
                        total_contacts += 1
        
        print(f"\nClose CRM update complete: {total_contacts} contacts added")
        return total_contacts > 0
    
    def add_contact_to_close_lead(self, lead_id, firm_name, contact):
        """Add a single contact to a Close lead"""
        url = "https://api.close.com/api/v1/contact/"
        headers = {
            'Authorization': self.get_close_auth_header(),
            'Content-Type': 'application/json'
        }
        
        contact_data = {
            "lead_id": lead_id,
            "name": contact['name'],
            "title": contact.get('title', ''),
            "emails": [{"email": contact['email'], "type": "office"}] if contact.get('email') else [],
            "phones": [],  # Will be updated when webhook data arrives
            "custom": {
                "cf_firm_name": firm_name,
                "cf_source": "Apollo.io enrichment"
            }
        }
        
        try:
            response = requests.post(url, headers=headers, json=contact_data)
            if response.status_code == 201:
                print(f"    ✓ Created contact: {contact['name']} | Email: {contact.get('email', 'N/A')}")
                return True
            else:
                print(f"    ✗ Failed to create contact: {contact['name']} - HTTP {response.status_code}")
                return False
                
        except Exception as e:
            print(f"    ✗ Error creating contact {contact['name']}: {e}")
            return False
    
    def step5_wait_for_webhooks(self, timeout_minutes=30):
        """Step 5: Wait for webhook responses and update with phone numbers"""
        self.print_header("STEP 5: WAITING FOR APOLLO WEBHOOK RESPONSES")
        
        if not self.phone_requests:
            print("No phone requests were sent, skipping webhook wait")
            return True
        
        print(f"Waiting up to {timeout_minutes} minutes for phone data...")
        print(f"Expecting responses for {len(self.phone_requests)} contacts")
        print("Monitor your webhook server console for incoming data")
        
        start_time = time.time()
        timeout_seconds = timeout_minutes * 60
        last_count = 0
        
        while time.time() - start_time < timeout_seconds:
            # Check for webhook data
            webhook_data = self.check_webhook_data()
            
            if webhook_data and len(webhook_data) > last_count:
                new_responses = len(webhook_data) - last_count
                print(f"\n✓ Received {new_responses} new webhook responses!")
                self.webhook_responses = webhook_data
                
                # Update Close CRM with phone numbers
                self.update_close_with_phone_data()
                last_count = len(webhook_data)
                
                # Check if we have all expected responses
                if len(webhook_data) >= len(self.phone_requests):
                    print("✓ All webhook responses received!")
                    break
            
            elapsed = int((time.time() - start_time) / 60)
            print(f"⏳ Still waiting... ({elapsed} min elapsed, {len(self.webhook_responses)} responses received)")
            time.sleep(30)  # Check every 30 seconds
        
        if len(self.webhook_responses) == 0:
            print(f"\n⚠ Timeout reached with no webhook responses")
            print("You can manually check webhook_data.json later and run update manually")
        else:
            print(f"\n✓ Completed with {len(self.webhook_responses)} webhook responses")
        
        return True
    
    def check_webhook_data(self):
        """Check for webhook data file"""
        try:
            if os.path.exists('webhook_data.json'):
                with open('webhook_data.json', 'r') as f:
                    data = json.load(f)
                    return data if isinstance(data, list) else []
        except Exception:
            pass
        return []
    
    def update_close_with_phone_data(self):
        """Update Close CRM contacts with phone numbers from webhook data"""
        if not self.webhook_responses:
            return
        
        print("\n--- Updating Close CRM with phone numbers ---")
        
        # Create mapping of person_id to phone numbers
        phone_map = {}
        for webhook_response in self.webhook_responses:
            data = webhook_response.get('data', {})
            if data.get('person', {}).get('id'):
                person_id = data['person']['id']
                phone_numbers = data['person'].get('phone_numbers', [])
                if phone_numbers:
                    phone_map[person_id] = phone_numbers
        
        # Update contacts in Close CRM
        updated_count = 0
        for request in self.phone_requests:
            contact = request['contact']
            person_id = contact.get('person_id')
            
            if person_id in phone_map:
                phone_numbers = phone_map[person_id]
                success = self.add_phone_to_contact(contact['name'], phone_numbers)
                if success:
                    updated_count += 1
        
        print(f"Phone updates complete: {updated_count} contacts updated")
    
    def add_phone_to_contact(self, contact_name, phone_numbers):
        """Add phone numbers to an existing contact in Close CRM"""
        # For simplicity, we'll search for the contact by name and update it
        # In a production system, you'd want to store contact IDs during creation
        
        search_url = "https://api.close.com/api/v1/contact/"
        headers = {
            'Authorization': self.get_close_auth_header(),
            'Content-Type': 'application/json'
        }
        
        # Search for contact by name
        search_params = {"name": contact_name, "_limit": 1}
        
        try:
            response = requests.get(search_url, headers=headers, params=search_params)
            if response.status_code == 200:
                contacts = response.json().get('data', [])
                if contacts:
                    contact_id = contacts[0]['id']
                    
                    # Prepare phone data
                    phones = []
                    for phone in phone_numbers:
                        phones.append({
                            "phone": phone.get('sanitized_number', phone.get('raw_number')),
                            "type": phone.get('type_cd', 'other')
                        })
                    
                    # Update contact with phones
                    update_url = f"https://api.close.com/api/v1/contact/{contact_id}/"
                    update_data = {"phones": phones}
                    
                    update_response = requests.put(update_url, headers=headers, json=update_data)
                    if update_response.status_code == 200:
                        print(f"    ✓ Updated {contact_name} with {len(phones)} phone numbers")
                        return True
                    else:
                        print(f"    ✗ Failed to update {contact_name} with phones")
                        return False
        except Exception as e:
            print(f"    ✗ Error updating {contact_name} with phones: {e}")
        
        return False
    
    def run_complete_pipeline(self):
        """Run the complete pipeline"""
        print("APOLLO-CLOSE INTEGRATION PIPELINE")
        print("=" * 60)
        
        try:
            # Check webhook server is running
            webhook_check = self.check_webhook_server()
            if not webhook_check:
                print("⚠ WARNING: Webhook server may not be running")
                proceed = input("Continue anyway? (y/n): ").lower()
                if proceed != 'y':
                    return
            
            # Step 1: Get leads from Close
            if not self.step1_get_todays_leads():
                print("❌ Failed to get leads from Close CRM")
                return
            
            # Step 2: Apollo enrichment
            if not self.step2_apollo_enrichment():
                print("❌ Failed to enrich any leads with Apollo")
                return
            
            # Step 3: Send phone requests
            if not self.step3_send_phone_requests():
                print("❌ Failed to send phone enrichment requests")
                return
            
            # Step 4: Update Close with emails
            if not self.step4_update_close_with_emails():
                print("❌ Failed to update Close CRM with emails")
                return
            
            # Step 5: Wait for webhooks and update phones
            self.step5_wait_for_webhooks()
            
            print("\n" + "=" * 60)
            print("PIPELINE COMPLETE!")
            print("✓ Leads retrieved from Close CRM")
            print("✓ Apollo enrichment completed")
            print("✓ Email contacts added to Close CRM")
            print("✓ Phone enrichment requests sent")
            if self.webhook_responses:
                print("✓ Phone numbers added to Close CRM")
            else:
                print("⚠ Phone numbers pending (check webhook_data.json later)")
            print("=" * 60)
            
        except KeyboardInterrupt:
            print("\n\n❌ Pipeline interrupted by user")
        except Exception as e:
            print(f"\n❌ Pipeline failed: {e}")
            raise
    
    def check_webhook_server(self):
        """Check if webhook server is running"""
        try:
            response = requests.get(f"{self.ngrok_url}/webhook-health", timeout=5)
            return response.status_code == 200
        except:
            return False

def main():
    try:
        pipeline = ApolloClosePipeline()
        pipeline.run_complete_pipeline()
    except Exception as e:
        print(f"ERROR: {e}")
        return 1
    return 0

if __name__ == "__main__":
    exit(main())

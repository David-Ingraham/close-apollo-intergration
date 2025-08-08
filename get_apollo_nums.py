import requests
import os
import json
import time
from dotenv import load_dotenv

load_dotenv()

def check_prerequisites():
    """Check that all required files and environment variables exist"""
    errors = []
    
    # Check for company results file
    if not os.path.exists('apollo_company_results.json'):
        errors.append("apollo_company_results.json not found. Run apollo_enrich.py first.")
    
    # Check for API key
    if not os.getenv('APOLLO_API_KEY'):
        errors.append("APOLLO_API_KEY not found in environment variables")
    
    # Check for ngrok URL
    if not os.getenv('NGROK_URL'):
        errors.append("NGROK_URL not found in environment variables")
    
    if errors:
        print("ERROR: Missing prerequisites:")
        for error in errors:
            print(f"  - {error}")
        return False
    
    return True

def load_company_results():
    """Load and parse the apollo_company_results.json file"""
    try:
        with open('apollo_company_results.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"ERROR loading apollo_company_results.json: {e}")
        return None

def show_company_results_summary(data):
    """Display summary of company results and available contacts"""
    print("COMPANY RESULTS SUMMARY")
    print("=" * 60)
    print(f"Total leads processed: {data['total_leads_processed']}")
    print(f"Successful searches: {data['successful_searches']}")
    print(f"Success rate: {data['success_rate']}")
    print(f"Timestamp: {data['timestamp']}")
    
    total_contacts = 0
    successful_firms = []
    
    for result in data['search_results']:
        if result.get('search_successful'):
            contacts = result.get('contacts', [])
            total_contacts += len(contacts)
            successful_firms.append({
                'client': result['client_name'],
                'firm': result['firm_name'], 
                'contacts': len(contacts)
            })
            
            print(f"\n✓ {result['client_name']} -> {result['firm_name']}")
            print(f"    Contacts found: {len(contacts)}")
            for contact in contacts[:3]:  # Show first 3
                title = contact.get('title', 'No title')
                email = contact.get('email', 'No email')
                print(f"      - {contact['name']} ({title}) - {email}")
            if len(contacts) > 3:
                print(f"      ... and {len(contacts)-3} more")
        else:
            print(f"\n✗ {result['client_name']} -> {result['firm_name']} (search failed)")
    
    print(f"\nSUMMARY:")
    print(f"  Successful firms: {len(successful_firms)}")
    print(f"  Total contacts available: {total_contacts}")
    print(f"  Contacts with emails: {sum(1 for firm in data['search_results'] if firm.get('search_successful') for contact in firm.get('contacts', []) if contact.get('email'))}")
    print("=" * 60)
    
    return total_contacts

def test_webhook_server(ngrok_url):
    """Test webhook server connectivity"""
    print("TESTING WEBHOOK SERVER")
    print("=" * 40)
    
    try:
        # Health check
        print("1. Health check...")
        response = requests.get(f"{ngrok_url}/webhook-health", timeout=10)
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            print(f"   Response: {response.json()}")
            print("   ✓ Webhook server is healthy")
        else:
            print("   ✗ Webhook server returned error")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"   ✗ Cannot connect to webhook server: {e}")
        print("   Make sure webhook_server.py is running and ngrok tunnel is active")
        return False
    
    try:
        # Test mock webhook
        print("\n2. Mock webhook test...")
        response = requests.post(f"{ngrok_url}/test-webhook", timeout=10)
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            print("   ✓ Mock webhook successful")
            return True
        else:
            print("   ✗ Mock webhook failed")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"   ✗ Mock webhook failed: {e}")
        return False

def extract_contacts_for_enrichment(data):
    """Extract all contacts that can be enriched with phone numbers"""
    enrichment_targets = []
    
    for result in data['search_results']:
        if not result.get('search_successful'):
            continue
            
        lead_id = result['lead_id']
        client_name = result['client_name']
        firm_name = result['firm_name']
        contacts = result.get('contacts', [])
        
        for i, contact in enumerate(contacts):
            # Only process contacts with email and person_id
            if contact.get('email') and contact.get('person_id'):
                enrichment_targets.append({
                    'lead_id': lead_id,
                    'client_name': client_name,
                    'firm_name': firm_name,
                    'contact': contact,
                    'request_id': f"{lead_id}_{i+1}"
                })
    
    return enrichment_targets

def send_phone_enrichment_request(target, webhook_url):
    """Send phone number enrichment request to Apollo"""
    api_key = os.getenv('APOLLO_API_KEY')
    contact = target['contact']
    
    url = "https://api.apollo.io/api/v1/people/match"
    headers = {
        'Content-Type': 'application/json',
        'Cache-Control': 'no-cache',
        'X-Api-Key': api_key
    }
    
    # Use person_id for exact match
    payload = {
        "person_id": contact['person_id'],
        "reveal_phone_number": True,
        "webhook_url": f"{webhook_url}/apollo-webhook"
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            person = result.get('person', {})
            status = person.get('status', 'unknown')
            
            if status == 'success':
                print(f"   ✓ {contact['name']} - Enrichment queued successfully")
                return True
            else:
                print(f"   ⚠ {contact['name']} - Status: {status}")
                return False
                
        elif response.status_code == 422:
            error_detail = response.json() if response.text else "Unknown validation error"
            print(f"   ✗ {contact['name']} - Validation error: {error_detail}")
            return False
            
        else:
            print(f"   ✗ {contact['name']} - HTTP {response.status_code}")
            try:
                error_detail = response.json()
                print(f"       Details: {error_detail}")
            except:
                print(f"       Response: {response.text[:100]}")
            return False
            
    except requests.exceptions.Timeout:
        print(f"   ✗ {contact['name']} - Request timeout")
        return False
    except Exception as e:
        print(f"   ✗ {contact['name']} - Error: {e}")
        return False

def process_all_enrichments(data, webhook_url):
    """Process all contacts for phone number enrichment"""
    print("PROCESSING PHONE NUMBER ENRICHMENTS")
    print("=" * 60)
    
    # Extract contacts that can be enriched
    targets = extract_contacts_for_enrichment(data)
    
    if not targets:
        print("No contacts found that can be enriched (need email + person_id)")
        return 0
    
    print(f"Found {len(targets)} contacts ready for phone enrichment")
    print("\nSending enrichment requests:")
    print("-" * 40)
    
    success_count = 0
    
    # Group by firm for better logging
    current_firm = None
    
    for i, target in enumerate(targets, 1):
        firm = target['firm_name']
        
        # Print firm header when we switch firms
        if firm != current_firm:
            if current_firm is not None:
                print()  # Space between firms
            print(f"\n{firm}:")
            current_firm = firm
        
        print(f"   [{i:2d}/{len(targets)}] ", end="")
        
        if send_phone_enrichment_request(target, webhook_url):
            success_count += 1
        
        # Rate limiting - Apollo recommends 1 request per second
        if i < len(targets):  # Don't sleep after the last request
            time.sleep(1)
    
    print("\n" + "=" * 60)
    print("ENRICHMENT REQUESTS COMPLETE")
    print(f"Successfully sent: {success_count}/{len(targets)} requests")
    print(f"Failed: {len(targets) - success_count}/{len(targets)} requests")
    
    if success_count > 0:
        print("\nNext steps:")
        print("- Apollo will process phone lookups (typically 5-30 minutes)")
        print("- Phone data will be sent to your webhook server")
        print("- Monitor webhook_server.py console for incoming data")
        print("- Check webhook_data.json for collected responses")
    
    print("=" * 60)
    
    return success_count

def main():
    """Main execution function"""
    print("APOLLO PHONE NUMBER ENRICHMENT")
    print("=" * 60)
    
    # Check prerequisites
    if not check_prerequisites():
        return
    
    # Load company results
    data = load_company_results()
    if not data:
        return
    
    # Show summary of available data
    total_contacts = show_company_results_summary(data)
    
    if total_contacts == 0:
        print("\nNo contacts found for enrichment. Run apollo_enrich.py to get company data first.")
        return
    
    # Get webhook URL
    ngrok_url = os.getenv('NGROK_URL')
    print(f"\nUsing webhook URL: {ngrok_url}")
    
    # Interactive menu
    print("\nOptions:")
    print("1. Test webhook server only")
    print("2. Process all contacts for phone enrichment")
    print("3. Test webhook AND process contacts (recommended)")
    print("4. Show detailed contact list")
    
    while True:
        choice = input("\nEnter choice (1-4): ").strip()
        if choice in ['1', '2', '3', '4']:
            break
        print("Please enter 1, 2, 3, or 4")
    
    if choice == '4':
        # Show detailed contact list
        print("\nDETAILED CONTACT LIST")
        print("=" * 60)
        for result in data['search_results']:
            if result.get('search_successful'):
                print(f"\n{result['client_name']} -> {result['firm_name']}")
                for i, contact in enumerate(result.get('contacts', []), 1):
                    email = contact.get('email', 'No email')
                    person_id = contact.get('person_id', 'No ID')
                    enrichable = "yes" if email and person_id else "no"
                    print(f"  {i:2d}. {enrichable} {contact['name']} ({contact.get('title', 'No title')})")
                    print(f"       Email: {email}")
                    if not person_id:
                        print(f"       Missing person_id - cannot enrich")
        return
    
    webhook_ok = True
    
    if choice in ['1', '3']:
        print("\n" + "=" * 60)
        webhook_ok = test_webhook_server(ngrok_url)
        
        if not webhook_ok:
            print("\n⚠ WARNING: Webhook test failed!")
            print("Make sure:")
            print("- webhook_server.py is running (python webhook_server.py)")
            print("- ngrok tunnel is active (ngrok http 5000)")
            print("- NGROK_URL in .env matches your current ngrok URL")
            
            if choice == '3':
                proceed = input("\nProceed with enrichment anyway? (y/n): ").lower()
                if proceed != 'y':
                    print("Aborted.")
                    return
    
    if choice in ['2', '3']:
        print("\n" + "=" * 60)
        success_count = process_all_enrichments(data, ngrok_url)
        
        if success_count == 0:
            print("\n⚠ No enrichment requests were sent successfully")
        elif not webhook_ok:
            print(f"\n⚠ WARNING: {success_count} requests sent but webhook may not be working")
            print("You might miss the Apollo responses!")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nScript interrupted by user")
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        raise
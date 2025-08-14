import os
import subprocess
import time
import json
import requests
from datetime import datetime

# Import the individual script functions
import get_lawyer_contacts
import apollo_enrich
import update_close_leads
import ai_lead_recovery

def print_header(title):
    """Print a formatted header"""
    print("\n" + "=" * 60)
    print(f" {title}")
    print("=" * 60)

def get_timestamp():
    """Get current timestamp for file naming"""
    return datetime.now().strftime("%Y%m%d_%H%M%S")

def save_debug_file(data, filename, debug_mode=False):
    """Save intermediate data to file if debug mode is enabled"""
    if debug_mode and data:
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            print(f"    [DEBUG] Saved intermediate data to {filename}")
        except Exception as e:
            print(f"    [DEBUG] Failed to save {filename}: {e}")

def check_prerequisites():
    """Check that all required files and services are ready"""
    print_header("CHECKING PREREQUISITES")
    
    issues = []
    
    # Check required files
    required_files = [
        'get_lawyer_contacts.py',
        'apollo_enrich.py',
        'get_apollo_nums.py', 
        'update_close_leads.py',
        'webhook_server.py',
        '.env'
    ]
    
    for file in required_files:
        if os.path.exists(file):
            print(f" {file} found")
        else:
            print(f" {file} missing")
            issues.append(f"Missing file: {file}")
    
    # Check environment variables
    from dotenv import load_dotenv
    load_dotenv()
    
    required_env = ['CLOSE_API_KEY', 'APOLLO_API_KEY', 'NGROK_URL', 'GROQ_API_KEY']
    for env_var in required_env:
        if os.getenv(env_var):
            print(f" {env_var} set")
        else:
            print(f" {env_var} missing")
            issues.append(f"Missing environment variable: {env_var}")
    
    # Check if webhook server is running
    ngrok_url = os.getenv('NGROK_URL')
    if ngrok_url:
        try:
            response = requests.get(f"{ngrok_url}/webhook-health", timeout=5)
            if response.status_code == 200:
                print(f" Webhook server responding at {ngrok_url}")
            else:
                print(f" Webhook server not responding (status: {response.status_code})")
                issues.append("Webhook server not responding")
        except:
            print(f" Cannot reach webhook server at {ngrok_url}")
            issues.append("Cannot reach webhook server - make sure webhook_server.py and ngrok are running")
    
    return issues

def get_leads_data():
    """Get leads data from Close CRM"""
    print_header("STEP 1: GET LEADS & IDENTIFY LAW FIRMS")
    print("Getting new leads from Close CRM and extracting lawyer/firm information...")
    
    try:
        # Call the function directly instead of running as subprocess
        leads_data = get_lawyer_contacts.get_todays_leads()
        if not leads_data:
            print(" Failed to retrieve leads data")
            return None
        
        # Prompt user for lead limit
        total_available = len(leads_data.get('data', []))
        print(f"\nHow many leads would you like to process?")
        print(f"Available: {total_available} leads")
        print("Options:")
        print("  'a' or 'all' - Process all leads")
        print("  1-20 - Process specific number of leads")
        
        while True:
            choice = input("Enter choice: ").lower().strip()
            
            if choice in ['a', 'all']:
                limit = None
                print("Processing all leads")
                break
            elif choice.isdigit():
                num = int(choice)
                if 1 <= num <= 20:
                    limit = num
                    print(f"Processing first {num} leads")
                    break
                else:
                    print("Please enter a number between 1-20")
            else:
                print("Please enter 'a', 'all', or a number between 1-20")
            
        processed_leads = get_lawyer_contacts.process_leads_data(leads_data, limit)
        if not processed_leads:
            print(" No processed leads data")
            return None
            
        # Package the data
        leads_package = {
            "timestamp": leads_data.get('timestamp', datetime.now().isoformat()),
            "total_leads": len(processed_leads),
            "leads_needing_enrichment": len([l for l in processed_leads if l.get('needs_apollo_enrichment', False)]),
            "leads": processed_leads
        }
        
        print(f" Successfully processed {leads_package['total_leads']} leads")
        print(f" Leads needing enrichment: {leads_package['leads_needing_enrichment']}")
        
        return leads_package
        
    except Exception as e:
        print(f" Error getting leads data: {e}")
        return None

def enrich_companies_and_people(leads_data, webhook_url=None):
    """Enrich companies and people data using Apollo"""
    print_header("STEP 2: COMPANY & PEOPLE ENRICHMENT") 
    print("Running Apollo enrichment to get company and people data...")
    print("NEW: Also enriching original attorney emails for direct phone numbers...")
    
    if not leads_data or not leads_data.get('leads'):
        print(" No leads data to process")
        return None
        
    try:
        # Get webhook URL from environment if not provided
        if not webhook_url:
            webhook_url = os.getenv('WEBHOOK_URL')
            if webhook_url:
                print(f"Using webhook URL from environment: {webhook_url}")
            else:
                print("No webhook URL provided - phone requests will be immediate (not async)")
        
        # Process leads that need enrichment
        leads_to_process = [lead for lead in leads_data['leads'] if lead.get('needs_apollo_enrichment', False)]
        print(f"Processing {len(leads_to_process)} leads (company + attorney enrichment)...")
        
        results = []
        processed_count = 0
        successful_searches = 0
        attorney_enrichments = 0
        
        for lead in leads_to_process:
            processed_count += 1
            print(f"\nProcessing lead: {lead.get('client_name')} -> {lead.get('attorney_firm')}")
            
            # Call apollo_enrich function with webhook URL for attorney enrichment
            search_result = apollo_enrich.search_firm_with_retry(lead, webhook_url)
            results.append(search_result)
            
            if search_result.get('search_successful'):
                successful_searches += 1
            
            if search_result.get('attorney_contact'):
                attorney_enrichments += 1
        
        # Package the enriched data
        enriched_package = {
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'mode': 'companies_and_attorneys',
            'total_leads_processed': processed_count,
            'successful_searches': successful_searches,
            'attorney_enrichments': attorney_enrichments,
            'success_rate': f"{(successful_searches/processed_count)*100:.1f}%" if processed_count else "0%",
            'attorney_success_rate': f"{(attorney_enrichments/processed_count)*100:.1f}%" if processed_count else "0%",
            'search_results': results
        }
        
        print(f"\nEnrichment complete:")
        print(f"Processed: {processed_count} | Firm Success: {successful_searches} | Attorney Success: {attorney_enrichments}")
        print(f"Firm Rate: {enriched_package['success_rate']} | Attorney Rate: {enriched_package['attorney_success_rate']}")
        
        return enriched_package
        
    except Exception as e:
        print(f" Error during enrichment: {e}")
        return None

def send_phone_requests(enriched_data):
    """Send phone enrichment requests to Apollo"""
    print_header("STEP 3: SEND PHONE ENRICHMENT REQUESTS")
    print("Sending phone number requests to Apollo...")
    
    # For now, we'll still call the script since it has complex webhook logic
    # TODO: Refactor get_apollo_nums.py to accept data directly
    if not enriched_data:
        print(" No enriched data to process")
        return False
        
    try:
        # Save enriched data directly to the file get_apollo_nums.py expects
        with open('apollo_company_results.json', 'w', encoding='utf-8') as f:
            json.dump(enriched_data, f, indent=2, ensure_ascii=False)
        
        # Run the phone enrichment script
        result = subprocess.run(['python', 'get_apollo_nums.py'], 
                              input="3\n", text=True, capture_output=True)
            
        if result.returncode == 0:
            print(" Phone enrichment requests sent successfully")
            return True
        else:
            print(f" Phone enrichment failed (return code: {result.returncode})")
            print(f" STDOUT: {result.stdout}")
            print(f" STDERR: {result.stderr}")
            return False
            
    except Exception as e:
        print(f" Error sending phone requests: {e}")
        return False

def update_close_with_emails(enriched_data):
    """Update Close CRM with lawyer contacts (emails only)"""
    print_header("STEP 4: UPDATE CLOSE CRM WITH EMAILS")
    print("Adding lawyer contacts with emails to Close CRM...")
    
    if not enriched_data:
        print(" No enriched data to process")
        return False
        
    try:
        # Save enriched data directly to the file update_close_leads.py expects
        with open('apollo_company_results.json', 'w', encoding='utf-8') as f:
            json.dump(enriched_data, f, indent=2, ensure_ascii=False)
        
        # Run the update script (emails only)
        result = subprocess.run(['python', 'update_close_leads.py'], 
                              input="n\n", text=True, capture_output=True)
            
        if result.returncode == 0:
            print(" Successfully added lawyer contacts with emails")
            return True
        else:
            print(f" Failed to update Close CRM with emails (return code: {result.returncode})")
            print(f" STDOUT: {result.stdout}")
            print(f" STDERR: {result.stderr}")
            return False
            
    except Exception as e:
        print(f" Error updating Close with emails: {e}")
        return False

def wait_for_webhook_data(timeout_minutes=30):
    """Wait for webhook data to arrive"""
    print_header("STEP 5: WAITING FOR APOLLO WEBHOOK RESPONSES")
    print(f"Waiting up to {timeout_minutes} minutes for phone data...")
    print("You can monitor webhook_server.py console for incoming data")
    
    start_time = time.time()
    timeout_seconds = timeout_minutes * 60
    
    while time.time() - start_time < timeout_seconds:
        if os.path.exists('webhook_data.json'):
            try:
                with open('webhook_data.json', 'r') as f:
                    data = json.load(f)
                    
                if data:  # Check if we have any webhook responses
                    phone_count = 0
                    for response in data:
                        response_data = response.get('data', {})
                        people = response_data.get('people', [])
                        for person in people:
                            if person.get('phone_numbers'):
                                phone_count += len(person.get('phone_numbers', []))
                    
                    if phone_count > 0:
                        print(f" Webhook data received! Found {phone_count} phone numbers")
                        return data
                        
            except Exception as e:
                print(f"Error checking webhook data: {e}")
        
        print(f"Still waiting... ({int((time.time() - start_time) / 60)} min elapsed)")
        time.sleep(30)  # Check every 30 seconds
    
    print(f" Timeout reached ({timeout_minutes} minutes)")
    print("You can still run the final update later when webhook data arrives")
    return None

def update_close_with_phones(enriched_data, webhook_data):
    """Update Close CRM with phone numbers"""
    print_header("STEP 6: UPDATE CLOSE CRM WITH PHONE NUMBERS")
    print("Adding phone numbers to existing lawyer contacts...")
    
    if not enriched_data or not webhook_data:
        print(" Missing data for phone update")
        return False
        
    try:
        # Create the files that update_close_leads.py expects
        # Don't clean them up - leave them for future manual runs
        
        with open('apollo_company_results.json', 'w', encoding='utf-8') as f:
            json.dump(enriched_data, f, indent=2, ensure_ascii=False)
        with open('webhook_data.json', 'w', encoding='utf-8') as f:
            json.dump(webhook_data, f, indent=2, ensure_ascii=False)
        
        # Run the update script (with phones)
        result = subprocess.run(['python', 'update_close_leads.py'], 
                              input="y\n", text=True, capture_output=True)
        
        print(f" STDOUT: {result.stdout}")
        if result.stderr:
            print(f" STDERR: {result.stderr}")
                
        if result.returncode == 0:
            print(" Successfully updated contacts with phone numbers")
            return True
        else:
            print(f" Phone number update failed (return code: {result.returncode})")
            return False
            
    except Exception as e:
        print(f" Error updating Close with phones: {e}")
        return False

def save_comprehensive_results(leads_data, enriched_data, webhook_data, timestamp, mode="testing"):
    """Save comprehensive results in readable format"""
    print_header("SAVING RESULTS")
    
    try:
        # Create comprehensive results
        results = {
            'session_info': {
                'session_id': timestamp,
                'timestamp': datetime.now().isoformat(),
                'mode': mode,
                'pipeline_version': 'v2.0'
            },
            'summary': {
                'total_leads_processed': enriched_data.get('total_leads_processed', 0) if enriched_data else 0,
                'successful_firm_matches': enriched_data.get('successful_searches', 0) if enriched_data else 0,
                'attorney_enrichments': enriched_data.get('attorney_enrichments', 0) if enriched_data else 0,
                'firm_success_rate': enriched_data.get('success_rate', '0%') if enriched_data else '0%',
                'attorney_success_rate': enriched_data.get('attorney_success_rate', '0%') if enriched_data else '0%',
                'phone_requests_sent': 0,
                'phone_responses_received': len(webhook_data) if webhook_data else 0,
                'total_phone_numbers_found': sum(
                    len(person.get('phone_numbers', []))
                    for response in (webhook_data or [])
                    for person in response.get('data', {}).get('people', [])
                ) if webhook_data else 0
            },
            'detailed_results': []
        }
        
        # Process each lead's results
        if enriched_data and enriched_data.get('search_results'):
            phone_map = {}
            if webhook_data:
                # Create phone mapping by person_id
                for response in webhook_data:
                    response_data = response.get('data', {})
                    people = response_data.get('people', [])
                    for person in people:
                        person_id = person.get('id')
                        if person_id:
                            phone_map[person_id] = person.get('phone_numbers', [])
            
            for result in enriched_data['search_results']:
                lead_result = {
                    'client_info': {
                        'client_name': result.get('client_name'),
                        'lead_id': result.get('lead_id')
                    },
                    'original_attorney_info': {
                        'attorney_firm': result.get('firm_name'),
                        'attorney_email': result.get('attorney_email'),
                        'firm_domain': result.get('firm_domain')
                    },
                    'attorney_enrichment': {
                        'enrichment_successful': result.get('attorney_contact') is not None,
                        'enrichment_status': result.get('attorney_enrichment_status', 'not_attempted'),
                        'attorney_contact': result.get('attorney_contact')
                    },
                    'apollo_search': {
                        'search_successful': result.get('search_successful', False),
                        'strategy_used': result.get('strategy', 'unknown'),
                        'firm_found': None,
                        'contacts_found': [],
                        'validation_notes': []
                    }
                }
                
                if result.get('search_successful'):
                    # Add firm information
                    if result.get('selected_organization'):
                        org = result['selected_organization']
                        lead_result['apollo_search']['firm_found'] = {
                            'name': org.get('name'),
                            'domain': org.get('primary_domain'),
                            'industry': org.get('industry'),
                            'apollo_id': org.get('id'),
                            'match_score': result.get('match_score', 'unknown')
                        }
                    
                    # Add contacts information
                    contacts = result.get('contacts', [])
                    for contact in contacts:
                        contact_info = {
                            'name': contact.get('name'),
                            'title': contact.get('title'),
                            'email': contact.get('email'),
                            'person_id': contact.get('person_id'),
                            'phone_numbers': [],
                            'phone_status': 'no_request'
                        }
                        
                        # Check for phone numbers
                        person_id = contact.get('person_id')
                        if person_id:
                            results['summary']['phone_requests_sent'] += 1
                            if person_id in phone_map:
                                contact_info['phone_numbers'] = phone_map[person_id]
                                contact_info['phone_status'] = 'received'
                            else:
                                contact_info['phone_status'] = 'pending'
                        
                        lead_result['apollo_search']['contacts_found'].append(contact_info)
                
                results['detailed_results'].append(lead_result)
        
        # Save main results file
        filename = f"enrichment_results_{mode}_{timestamp}.json"
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        
        print(f" Results saved to: {filename}")
        
        # Also save raw data files for reference
        if enriched_data:
            raw_filename = f"raw_apollo_results_{timestamp}.json"
            with open(raw_filename, 'w', encoding='utf-8') as f:
                json.dump(enriched_data, f, indent=2, ensure_ascii=False)
            print(f" Raw Apollo data saved to: {raw_filename}")
        
        if webhook_data:
            webhook_filename = f"raw_webhook_data_{timestamp}.json"
            with open(webhook_filename, 'w', encoding='utf-8') as f:
                json.dump(webhook_data, f, indent=2, ensure_ascii=False)
            print(f" Raw webhook data saved to: {webhook_filename}")
        
        return filename, results['summary']
        
    except Exception as e:
        print(f" Error saving results: {e}")
        return None, None

def main():
    """Run the complete Apollo-Close integration pipeline"""
    print_header("APOLLO-CLOSE INTEGRATION PIPELINE")
    print("This script will run the complete enrichment and update process")
    print("NEW: Includes AI-powered lead recovery using Groq LLM")
    print("Make sure webhook_server.py and ngrok are running before starting!")
    
    # Check prerequisites
    issues = check_prerequisites()
    if issues:
        print("\n PREREQUISITES NOT MET:")
        for issue in issues:
            print(f"  - {issue}")
        print("\nPlease fix these issues and try again.")
        return
    
    print("\n All prerequisites met!")
    
    # Ask user for mode selection
    print("\nSelect mode:")
    print("1. Testing Mode - Run pipeline and save results for review (no Close CRM updates)")
    print("2. Production Mode - Run full pipeline + save results + update Close CRM")
    
    while True:
        mode_choice = input("\nEnter choice (1 or 2): ").strip()
        if mode_choice == '1':
            mode = "testing"
            update_close = False
            print("Selected: Testing Mode")
            break
        elif mode_choice == '2':
            mode = "production"
            update_close = True
            print("Selected: Production Mode")
            break
        else:
            print("Please enter 1 or 2")
    
    # Show what will happen
    print(f"\nThis will:")
    print("1. Get new leads from Close CRM and find law firms")
    print("1.5. AI Recovery: Use LLM to recover skipped leads with firm names")
    print("2. Enrich companies and people data from Apollo")
    print("3. Save comprehensive results to timestamped file")
    if update_close:
        print("4. Send phone enrichment requests to Apollo")
        print("5. Update Close CRM with lawyer emails")
        print("6. Wait for Apollo webhook responses")
        print("7. Update Close CRM with phone numbers")
    else:
        print("4. STOP - Review results before sending phone requests (no Apollo credits used)")
    
    choice = input(f"\nProceed with {mode} mode? (y/n): ").lower().strip()
    if choice not in ['y', 'yes']:
        print("Pipeline cancelled by user")
        return
    
    pipeline_start = datetime.now()
    timestamp = get_timestamp()
    
    print(f"\nStarting {mode} pipeline session: {timestamp}")
    
    # Initialize data containers
    leads_data = None
    enriched_data = None
    webhook_data = None
    
    try:
        # Step 1: Get leads data
        leads_data = get_leads_data()
        if not leads_data:
            print(" Pipeline failed: Could not get leads data")
            return
        
        # Step 1.5: AI Lead Recovery (recover skipped leads using LLM)
        ai_recovered_leads = ai_lead_recovery.process_ai_recovery(leads_data, min_confidence=7)
        if ai_recovered_leads:
            leads_data = ai_lead_recovery.merge_recovered_leads(leads_data, ai_recovered_leads)
            print(f" AI Recovery complete: {len(ai_recovered_leads)} leads recovered for enrichment")
        else:
            print("ℹ  AI Recovery: No additional leads recovered")
        
        # Step 2: Enrich companies and people (including attorney email enrichment)
        webhook_url = os.getenv('WEBHOOK_URL')  # Get webhook URL for attorney phone requests
        enriched_data = enrich_companies_and_people(leads_data, webhook_url)
        if not enriched_data:
            print(" Pipeline failed: Could not enrich data")
            return
        
        # SAVE RESULTS AND CHECK MODE
        results_file, summary = save_comprehensive_results(leads_data, enriched_data, None, timestamp, mode)
        
        if mode == "testing":
            # TESTING MODE: Stop here before sending phone requests
            print_header("TESTING MODE COMPLETE")
            print("Pipeline stopped before phone requests for review.")
            print(f"Results saved to: {results_file}")
            print("\nSUMMARY:")
            if summary:
                for key, value in summary.items():
                    print(f"  {key.replace('_', ' ').title()}: {value}")
            
            print("\nREVIEW INSTRUCTIONS:")
            print("1. Open the results file to review what Apollo found")
            print("2. Check firm matches and contact quality")
            print("3. Verify domain validations look correct")
            print("4. When satisfied, run Production Mode to send phone requests & update Close CRM")
            print("\nNO phone requests sent - no Apollo credits consumed in testing mode")
            return
        
        # PRODUCTION MODE: Continue with phone requests and Close CRM updates
        print_header("PRODUCTION MODE: SENDING PHONE REQUESTS")
        
        # Step 3: Send phone requests
        phone_request_success = send_phone_requests(enriched_data)
        
        # PRODUCTION MODE: Continue with Close CRM updates
        print_header("PRODUCTION MODE: UPDATING CLOSE CRM")
        
        # Step 4: Update Close with emails
        email_update_success = update_close_with_emails(enriched_data)
        if not email_update_success:
            print(" Pipeline failed: Could not update Close with emails")
            return
        
        # Step 5: Wait for webhook data
        webhook_data = wait_for_webhook_data(timeout_minutes=30)
        
        # Step 6: Update Close with phones (if we got webhook data)
        phone_update_success = False
        if webhook_data:
            phone_update_success = update_close_with_phones(enriched_data, webhook_data)
        
        # Save final results with webhook data
        final_file, final_summary = save_comprehensive_results(leads_data, enriched_data, webhook_data, timestamp, mode)
        
        # Summary
        pipeline_end = datetime.now()
        duration = pipeline_end - pipeline_start
        
        print_header("PRODUCTION PIPELINE SUMMARY")
        print(f"Session ID: {timestamp}")
        print(f"Started: {pipeline_start.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Ended: {pipeline_end.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Duration: {duration}")
        
        if final_file:
            print(f"Final Results: {final_file}")
        
        if final_summary:
            print("\nFINAL SUMMARY:")
            for key, value in final_summary.items():
                print(f"  {key.replace('_', ' ').title()}: {value}")
        
        if phone_update_success:
            print("\nStatus: COMPLETE (emails + phones pushed to Close CRM)")
        else:
            print("\nStatus: PARTIAL (emails pushed, phones pending)")
        
        print("\nNext steps:")
        print("- Check Close CRM to verify lawyer contacts were added")
        if not phone_update_success:
            print("- Monitor webhook_server.py for additional phone data")
            print("- Re-run production mode if more webhook data arrives")
            
    except Exception as e:
        print(f"\n Pipeline failed with error: {e}")
        # Still try to save what we have
        if leads_data or enriched_data or webhook_data:
            save_comprehensive_results(leads_data, enriched_data, webhook_data, timestamp, mode)
        raise

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n Pipeline interrupted by user")
    except Exception as e:
        print(f"\n\n Pipeline failed with error: {e}")
        raise

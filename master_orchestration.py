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
    
    required_env = ['CLOSE_API_KEY', 'APOLLO_API_KEY', 'NGROK_URL']
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
            
        processed_leads = get_lawyer_contacts.process_leads_data(leads_data)
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

def enrich_companies_and_people(leads_data):
    """Enrich companies and people data using Apollo"""
    print_header("STEP 2: COMPANY & PEOPLE ENRICHMENT") 
    print("Running Apollo enrichment to get company and people data...")
    
    if not leads_data or not leads_data.get('leads'):
        print(" No leads data to process")
        return None
        
    try:
        # Process leads that need enrichment
        leads_to_process = [lead for lead in leads_data['leads'] if lead.get('needs_apollo_enrichment', False)]
        print(f"Processing {len(leads_to_process)} leads (company lookup only)...")
        
        results = []
        processed_count = 0
        successful_searches = 0
        
        for lead in leads_to_process:
            processed_count += 1
            print(f"\nSearching firm for: {lead.get('client_name')} -> {lead.get('attorney_firm')}")
            
            # Call apollo_enrich function directly
            search_result = apollo_enrich.search_firm_with_retry(lead)
            results.append(search_result)
            
            if search_result.get('search_successful'):
                successful_searches += 1
        
        # Package the enriched data
        enriched_package = {
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'mode': 'companies_only',
            'total_leads_processed': processed_count,
            'successful_searches': successful_searches,
            'success_rate': f"{(successful_searches/processed_count)*100:.1f}%" if processed_count else "0%",
            'search_results': results
        }
        
        print(f"\nCompany enrichment complete:")
        print(f"Processed: {processed_count} | Success: {successful_searches} | Rate: {enriched_package['success_rate']}")
        
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
        # Temporarily save the enriched data for get_apollo_nums.py
        temp_file = 'temp_apollo_company_results.json'
        with open(temp_file, 'w', encoding='utf-8') as f:
            json.dump(enriched_data, f, indent=2, ensure_ascii=False)
        
        # Create symlink for compatibility
        if os.path.exists('apollo_company_results.json'):
            os.remove('apollo_company_results.json')
        os.symlink(temp_file, 'apollo_company_results.json')
        
        # Run the phone enrichment script
        result = subprocess.run(['python', 'get_apollo_nums.py'], 
                              input="3\n", text=True, capture_output=True)
        
        # Clean up temporary files
        if os.path.islink('apollo_company_results.json'):
            os.unlink('apollo_company_results.json')
        if os.path.exists(temp_file):
            os.remove(temp_file)
            
        if result.returncode == 0:
            print(" Phone enrichment requests sent successfully")
            return True
        else:
            print(f" Phone enrichment may have failed, but continuing...")
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
        # Call update function directly with emails only
        # TODO: Refactor update_close_leads.py to accept data directly
        # For now, use temporary file approach
        temp_file = 'temp_apollo_results_for_emails.json'
        with open(temp_file, 'w', encoding='utf-8') as f:
            json.dump(enriched_data, f, indent=2, ensure_ascii=False)
        
        # Create symlink for compatibility
        if os.path.exists('apollo_company_results.json'):
            os.remove('apollo_company_results.json')
        os.symlink(temp_file, 'apollo_company_results.json')
        
        # Run the update script (emails only)
        result = subprocess.run(['python', 'update_close_leads.py'], 
                              input="n\n", text=True, capture_output=True)
        
        # Clean up
        if os.path.islink('apollo_company_results.json'):
            os.unlink('apollo_company_results.json')
        if os.path.exists(temp_file):
            os.remove(temp_file)
            
        if result.returncode == 0:
            print(" Successfully added lawyer contacts with emails")
            return True
        else:
            print(f" Failed to update Close CRM with emails")
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
        
        print(f"⏳ Still waiting... ({int((time.time() - start_time) / 60)} min elapsed)")
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
        # Temporarily save both datasets for the update script
        temp_enriched = 'temp_apollo_results_for_phones.json'
        temp_webhook = 'temp_webhook_data.json'
        
        with open(temp_enriched, 'w', encoding='utf-8') as f:
            json.dump(enriched_data, f, indent=2, ensure_ascii=False)
        with open(temp_webhook, 'w', encoding='utf-8') as f:
            json.dump(webhook_data, f, indent=2, ensure_ascii=False)
        
        # Create symlinks for compatibility
        if os.path.exists('apollo_company_results.json'):
            os.remove('apollo_company_results.json')
        if os.path.exists('webhook_data.json'):
            os.remove('webhook_data.json')
        os.symlink(temp_enriched, 'apollo_company_results.json')
        os.symlink(temp_webhook, 'webhook_data.json')
        
        # Run the update script (with phones)
        result = subprocess.run(['python', 'update_close_leads.py'], 
                              input="y\n", text=True, capture_output=True)
        
        # Clean up temporary files
        cleanup_files = [
            'apollo_company_results.json', 'webhook_data.json', 
            temp_enriched, temp_webhook
        ]
        for file in cleanup_files:
            if os.path.islink(file):
                os.unlink(file)
            elif os.path.exists(file):
                os.remove(file)
                
        if result.returncode == 0:
            print(" Successfully updated contacts with phone numbers")
            return True
        else:
            print(" Phone number update failed")
            return False
            
    except Exception as e:
        print(f" Error updating Close with phones: {e}")
        return False

def save_final_results(leads_data, enriched_data, webhook_data, timestamp, debug_mode=False):
    """Save final results and audit trail"""
    print_header("SAVING FINAL RESULTS")
    
    try:
        # Save final enriched results
        final_results = {
            'session_id': timestamp,
            'timestamp': datetime.now().isoformat(),
            'pipeline_summary': {
                'total_leads_processed': enriched_data.get('total_leads_processed', 0) if enriched_data else 0,
                'successful_enrichments': enriched_data.get('successful_searches', 0) if enriched_data else 0,
                'phone_data_received': bool(webhook_data),
                'phone_numbers_found': sum(
                    len(person.get('phone_numbers', []))
                    for response in (webhook_data or [])
                    for person in response.get('data', {}).get('people', [])
                ) if webhook_data else 0
            },
            'enriched_results': enriched_data,
            'webhook_responses': webhook_data
        }
        
        final_filename = f"final_enrichment_results_{timestamp}.json"
        with open(final_filename, 'w', encoding='utf-8') as f:
            json.dump(final_results, f, indent=2, ensure_ascii=False)
        
        print(f" Final results saved to: {final_filename}")
        
        # Save debug files if requested
        if debug_mode:
            save_debug_file(leads_data, f"debug_leads_{timestamp}.json", True)
            save_debug_file(enriched_data, f"debug_enriched_{timestamp}.json", True)
            save_debug_file(webhook_data, f"debug_webhook_{timestamp}.json", True)
        
        return final_filename
        
    except Exception as e:
        print(f" Error saving final results: {e}")
        return None

def main():
    """Run the complete Apollo-Close integration pipeline"""
    print_header("APOLLO-CLOSE INTEGRATION PIPELINE")
    print("This script will run the complete enrichment and update process")
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
    
    # Ask user for configuration
    print("\nThis will:")
    print("1. Get new leads from Close CRM and find law firms")
    print("2. Enrich companies and people data from Apollo")
    print("3. Send phone enrichment requests to Apollo")
    print("4. Update Close CRM with lawyer emails immediately")
    print("5. Wait for Apollo webhook responses")
    print("6. Update Close CRM with phone numbers")
    
    choice = input("\nProceed with full pipeline? (y/n): ").lower().strip()
    if choice not in ['y', 'yes']:
        print("Pipeline cancelled by user")
        return
    
    debug_choice = input("Enable debug mode (saves intermediate files)? (y/n): ").lower().strip()
    debug_mode = debug_choice in ['y', 'yes']
    
    pipeline_start = datetime.now()
    timestamp = get_timestamp()
    
    print(f"\nStarting pipeline session: {timestamp}")
    if debug_mode:
        print("Debug mode enabled - intermediate files will be saved")
    
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
        save_debug_file(leads_data, f"debug_leads_{timestamp}.json", debug_mode)
        
        # Step 2: Enrich companies and people
        enriched_data = enrich_companies_and_people(leads_data)
        if not enriched_data:
            print(" Pipeline failed: Could not enrich data")
            return
        save_debug_file(enriched_data, f"debug_enriched_{timestamp}.json", debug_mode)
        
        # Step 3: Send phone requests
        phone_request_success = send_phone_requests(enriched_data)
        
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
            save_debug_file(webhook_data, f"debug_webhook_{timestamp}.json", debug_mode)
            phone_update_success = update_close_with_phones(enriched_data, webhook_data)
        
        # Save final results
        final_file = save_final_results(leads_data, enriched_data, webhook_data, timestamp, debug_mode)
        
        # Summary
        pipeline_end = datetime.now()
        duration = pipeline_end - pipeline_start
        
        print_header("PIPELINE SUMMARY")
        print(f"Session ID: {timestamp}")
        print(f"Started: {pipeline_start.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Ended: {pipeline_end.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Duration: {duration}")
        
        if final_file:
            print(f"Final Results: {final_file}")
        
        if phone_update_success:
            print("Status: COMPLETE (emails + phones)")
        else:
            print("Status: PARTIAL (emails only, phones pending)")
        
        print("\nNext steps:")
        print("- Check Close CRM to verify lawyer contacts were added")
        if not phone_update_success:
            print("- Monitor webhook_server.py for additional phone data")
            print("- Re-run pipeline if more webhook data arrives")
            
    except Exception as e:
        print(f"\n Pipeline failed with error: {e}")
        # Still try to save what we have
        if leads_data or enriched_data or webhook_data:
            save_final_results(leads_data, enriched_data, webhook_data, timestamp, debug_mode)
        raise

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n Pipeline interrupted by user")
    except Exception as e:
        print(f"\n\n Pipeline failed with error: {e}")
        raise

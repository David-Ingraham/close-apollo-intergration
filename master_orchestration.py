import os
import subprocess
import time
import json
import requests
from datetime import datetime

def print_header(title):
    """Print a formatted header"""
    print("\n" + "=" * 60)
    print(f" {title}")
    print("=" * 60)

def check_prerequisites():
    """Check that all required files and services are ready"""
    print_header("CHECKING PREREQUISITES")
    
    issues = []
    
    # Check required files
    required_files = [
        'apollo_enrich.py',
        'get_apollo_nums.py', 
        'update_close_leads.py',
        'webhook_server.py',
        '.env'
    ]
    
    for file in required_files:
        if os.path.exists(file):
            print(f"✓ {file} found")
        else:
            print(f"✗ {file} missing")
            issues.append(f"Missing file: {file}")
    
    # Check environment variables
    from dotenv import load_dotenv
    load_dotenv()
    
    required_env = ['CLOSE_API_KEY', 'APOLLO_API_KEY', 'NGROK_URL']
    for env_var in required_env:
        if os.getenv(env_var):
            print(f"✓ {env_var} set")
        else:
            print(f"✗ {env_var} missing")
            issues.append(f"Missing environment variable: {env_var}")
    
    # Check if webhook server is running
    ngrok_url = os.getenv('NGROK_URL')
    if ngrok_url:
        try:
            response = requests.get(f"{ngrok_url}/webhook-health", timeout=5)
            if response.status_code == 200:
                print(f"✓ Webhook server responding at {ngrok_url}")
            else:
                print(f"✗ Webhook server not responding (status: {response.status_code})")
                issues.append("Webhook server not responding")
        except:
            print(f"✗ Cannot reach webhook server at {ngrok_url}")
            issues.append("Cannot reach webhook server - make sure webhook_server.py and ngrok are running")
    
    return issues

def run_script(script_name, description, auto_input=None):
    """Run a Python script with optional automatic input"""
    print_header(f"RUNNING: {description}")
    print(f"Command: python {script_name}")
    
    try:
        if auto_input:
            # Run with automatic input
            process = subprocess.Popen(
                ['python', script_name],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
            
            output, _ = process.communicate(input=auto_input)
            print(output)
            
            if process.returncode == 0:
                print(f"✓ {script_name} completed successfully")
                return True
            else:
                print(f"✗ {script_name} failed with return code {process.returncode}")
                return False
        else:
            # Run interactively
            result = subprocess.run(['python', script_name], check=True)
            print(f"✓ {script_name} completed successfully")
            return True
            
    except subprocess.CalledProcessError as e:
        print(f"✗ {script_name} failed: {e}")
        return False
    except KeyboardInterrupt:
        print(f"⚠ {script_name} interrupted by user")
        return False
    except Exception as e:
        print(f"✗ Error running {script_name}: {e}")
        return False

def wait_for_webhook_data(timeout_minutes=30):
    """Wait for webhook data to arrive"""
    print_header("WAITING FOR APOLLO WEBHOOK RESPONSES")
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
                        print(f"✓ Webhook data received! Found {phone_count} phone numbers")
                        return True
                        
            except Exception as e:
                print(f"Error checking webhook data: {e}")
        
        print(f"⏳ Still waiting... ({int((time.time() - start_time) / 60)} min elapsed)")
        time.sleep(30)  # Check every 30 seconds
    
    print(f"⚠ Timeout reached ({timeout_minutes} minutes)")
    print("You can still run the final update later when webhook data arrives")
    return False

def main():
    """Run the complete Apollo-Close integration pipeline"""
    print_header("APOLLO-CLOSE INTEGRATION PIPELINE")
    print("This script will run the complete enrichment and update process")
    print("Make sure webhook_server.py and ngrok are running before starting!")
    
    # Check prerequisites
    issues = check_prerequisites()
    if issues:
        print("\n❌ PREREQUISITES NOT MET:")
        for issue in issues:
            print(f"  - {issue}")
        print("\nPlease fix these issues and try again.")
        return
    
    print("\n✅ All prerequisites met!")
    
    # Ask user for confirmation
    print("\nThis will:")
    print("1. Get leads from Close CRM and find law firms")
    print("2. Send phone enrichment requests to Apollo")
    print("3. Update Close CRM with lawyer emails immediately")
    print("4. Wait for Apollo webhook responses")
    print("5. Update Close CRM with phone numbers")
    
    choice = input("\nProceed with full pipeline? (y/n): ").lower().strip()
    if choice not in ['y', 'yes']:
        print("Pipeline cancelled by user")
        return
    
    pipeline_start = datetime.now()
    
    # Step 1: Get leads and enrich companies/people
    print_header("STEP 1: COMPANY & PEOPLE ENRICHMENT")
    if not os.path.exists('apollo_company_results.json'):
        print("Running apollo_enrich.py to get company and people data...")
        if not run_script('apollo_enrich.py', 'Company & People Enrichment'):
            print("❌ Pipeline failed at step 1")
            return
    else:
        print("✓ apollo_company_results.json already exists, skipping company enrichment")
    
    # Step 2: Send phone enrichment requests
    print_header("STEP 2: SEND PHONE ENRICHMENT REQUESTS")
    print("Sending phone number requests to Apollo...")
    # Auto-answer the get_apollo_nums.py prompts (option 3: test webhook AND process contacts)
    if not run_script('get_apollo_nums.py', 'Phone Enrichment Requests', auto_input="3\n"):
        print("⚠ Phone enrichment requests may have failed, but continuing...")
    
    # Step 3: Update Close with emails (no phones yet)
    print_header("STEP 3: UPDATE CLOSE CRM WITH EMAILS")
    print("Adding lawyer contacts with emails to Close CRM...")
    # Auto-answer 'n' to phone number prompt since webhooks haven't responded yet
    if not run_script('update_close_leads.py', 'Close CRM Update (Emails)', auto_input="n\n"):
        print("❌ Pipeline failed at step 3")
        return
    
    # Step 4: Wait for webhook responses
    webhook_success = wait_for_webhook_data(timeout_minutes=30)
    
    # Step 5: Update Close with phone numbers (if we got webhook data)
    if webhook_success:
        print_header("STEP 5: UPDATE CLOSE CRM WITH PHONE NUMBERS")
        print("Adding phone numbers to existing lawyer contacts...")
        # Auto-answer 'y' to phone number prompt since we have webhook data
        if not run_script('update_close_leads.py', 'Close CRM Update (Phones)', auto_input="y\n"):
            print("⚠ Phone number update failed")
        else:
            print("✅ Pipeline completed successfully with phone numbers!")
    else:
        print_header("STEP 5: WEBHOOK TIMEOUT")
        print("Phone data not received within timeout period")
        print("You can run this command later to add phone numbers:")
        print("    python update_close_leads.py")
        print("✅ Pipeline completed successfully (emails only)")
    
    # Summary
    pipeline_end = datetime.now()
    duration = pipeline_end - pipeline_start
    
    print_header("PIPELINE SUMMARY")
    print(f"Started: {pipeline_start.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Ended: {pipeline_end.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Duration: {duration}")
    
    if webhook_success:
        print("Status: ✅ COMPLETE (emails + phones)")
    else:
        print("Status: ✅ PARTIAL (emails only, phones pending)")
    
    print("\nNext steps:")
    print("- Check Close CRM to verify lawyer contacts were added")
    print("- Monitor webhook_server.py for any additional phone data")
    print("- Run update_close_leads.py again if more webhook data arrives")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠ Pipeline interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Pipeline failed with error: {e}")
        raise

import os
import json
import time
from typing import Dict, List, Optional
import requests
from dotenv import load_dotenv

load_dotenv()

def classify_attorney_name(attorney_name: str, attorney_email: str, groq_api_key: str, retry_count: int = 3) -> Optional[Dict]:
    """
    Use Groq to classify if an attorney name is a person or firm
    Includes rate limiting and retries
    """
    # Add delay between requests to avoid rate limits
    time.sleep(2)  # 2 second delay between requests
    
    headers = {
        "Authorization": f"Bearer {groq_api_key}",
        "Content-Type": "application/json"
    }
    
    prompt = f"""
    Analyze this attorney name field: "{attorney_name}"
    Attorney email: "{attorney_email}"
    
    Determine:
    1. Is this a PERSON name, LAW FIRM name, or JUNK data?
    2. Confidence level (1-10)
    3. If it's a firm, suggest a likely website URL.
    4. If it's a person, suggest what their firm might be called and what their url might be
    5. If the attorney_email field is present, use it to find the firm's domain.
    6. If we have the attorney email, use the root domain to suggest a url for the firm.
    
    Respond in this exact format:
    TYPE: [PERSON/FIRM/JUNK]
    CONFIDENCE: [1-10]
    WEBSITE: [suggested URL or "unknown"]
    """
    
    payload = {
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "model": "llama-3.3-70b-versatile",
        "max_tokens": 150
    }
    
    for attempt in range(retry_count):
        try:
            response = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                content = result['choices'][0]['message']['content']
                
                # Parse the response into a structured format
                lines = content.strip().split('\n')
                parsed = {}
                for line in lines:
                    if ': ' in line:
                        key, value = line.split(': ', 1)
                        parsed[key] = value.strip('[]')
                
                return parsed
                
            elif response.status_code == 429:  # Rate limit
                if attempt < retry_count - 1:  # If not the last attempt
                    print(f"    Rate limit hit, waiting {5 * (attempt + 1)} seconds...")
                    time.sleep(5 * (attempt + 1))  # Exponential backoff
                    continue
                return {"error": "Rate limit exceeded"}
            else:
                return {"error": f"API Error: {response.status_code}"}
                
        except Exception as e:
            if attempt < retry_count - 1:  # If not the last attempt
                print(f"    API error, retrying in {5 * (attempt + 1)} seconds...")
                time.sleep(5 * (attempt + 1))  # Exponential backoff
                continue
            return {"error": str(e)}
    
    return {"error": "Max retries exceeded"}

def process_ai_recovery(leads_data: Dict, min_confidence: int = 7) -> List[Dict]:
    """
    Process skipped leads through AI classification and recover viable firms
    
    Args:
        leads_data: The leads package from get_lawyer_contacts
        min_confidence: Minimum AI confidence to accept a recovery (1-10)
    
    Returns:
        List of recovered leads ready for Apollo enrichment
    """
    print("\n" + "=" * 60)
    print(" AI LEAD RECOVERY PROCESS")
    print("=" * 60)
    
    api_key = os.getenv('GROQ_API_KEY')
    if not api_key:
        print(" No GROQ_API_KEY found in .env file")
        print("Skipping AI recovery - no leads will be recovered")
        return []
    
    # Extract skipped leads
    all_leads = leads_data.get('leads', [])
    skipped_leads = [
        lead for lead in all_leads 
        if lead.get('skip_reason') is not None 
        and lead.get('attorney_firm')  # Must have attorney name
        and lead.get('attorney_firm') not in ['N/A', '', 'n/a', 'N/a']
    ]
    
    print(f" Found {len(skipped_leads)} skipped leads with attorney names")
    
    if not skipped_leads:
        print("   No leads available for AI recovery")
        return []
    
    print(f"🤖 Starting AI classification (min confidence: {min_confidence}/10)")
    print(f"   Using rate limiting: 2s delay between requests")
    
    recovered_leads = []
    processed_count = 0
    firm_recoveries = 0
    person_skips = 0
    junk_skips = 0
    low_confidence_skips = 0
    errors = 0
    
    for lead in skipped_leads:
        processed_count += 1
        attorney_name = lead.get('attorney_firm', '')
        attorney_email = lead.get('attorney_email', '')
        
        print(f"\n--- AI Processing Lead {processed_count}/{len(skipped_leads)} ---")
        print(f"   Client: {lead.get('client_name')}")
        print(f"   Attorney Name: '{attorney_name}'")
        print(f"   Attorney Email: {attorney_email}")
        print(f"   Original Skip Reason: {lead.get('skip_reason')}")
        
        # Call AI classification
        ai_result = classify_attorney_name(attorney_name, attorney_email, api_key)
        
        if 'error' in ai_result:
            print(f"    AI Classification Error: {ai_result['error']}")
            errors += 1
            continue
        
        # Extract AI results
        ai_type = ai_result.get('TYPE', 'unknown').upper()
        ai_confidence = ai_result.get('CONFIDENCE', '0')
        ai_website = ai_result.get('WEBSITE', 'unknown')
        
        # Convert confidence to int
        try:
            confidence_score = int(ai_confidence)
        except (ValueError, TypeError):
            confidence_score = 0
        
        print(f"    AI Classification:")
        print(f"      Type: {ai_type}")
        print(f"      Confidence: {confidence_score}/10")
        print(f"      Suggested Website: {ai_website}")
        
        # Determine action based on AI results
        if ai_type == 'PERSON':
            print(f"     SKIPPING: Classified as person name")
            person_skips += 1
            
        elif ai_type == 'JUNK':
            print(f"     SKIPPING: Classified as junk data")
            junk_skips += 1
            
        elif ai_type == 'FIRM':
            if confidence_score >= min_confidence:
                print(f"    RECOVERING: High-confidence firm classification")
                
                # Create recovered lead
                recovered_lead = lead.copy()  # Start with original lead
                
                # Clear skip reason and enable enrichment
                recovered_lead['skip_reason'] = None
                recovered_lead['needs_apollo_enrichment'] = True
                
                # Add AI-suggested website if available
                if ai_website and ai_website.lower() != 'unknown':
                    recovered_lead['firm_website'] = ai_website
                
                # Add AI recovery metadata
                recovered_lead['ai_recovery'] = {
                    'original_skip_reason': lead.get('skip_reason'),
                    'ai_classification': ai_type,
                    'ai_confidence': confidence_score,
                    'ai_suggested_website': ai_website,
                    'recovery_method': 'ai_classification'
                }
                
                recovered_leads.append(recovered_lead)
                firm_recoveries += 1
                
                print(f"   Recovery Details:")
                print(f"      Firm Name: {recovered_lead.get('attorney_firm')}")
                if 'firm_website' in recovered_lead:
                    print(f"      Suggested URL: {recovered_lead['firm_website']}")
                print(f"      Will be sent to Apollo enrichment")
                
            else:
                print(f"     SKIPPING: Firm classification but low confidence ({confidence_score} < {min_confidence})")
                low_confidence_skips += 1
                
        else:
            print(f"     SKIPPING: Unknown classification type '{ai_type}'")
            errors += 1
    
    # Summary
    print(f"\n" + "=" * 60)
    print(" AI RECOVERY SUMMARY")
    print("=" * 60)
    print(f"   Total Processed: {processed_count}")
    print(f"    Firms Recovered: {firm_recoveries}")
    print(f"    Person Skips: {person_skips}")
    print(f"    Junk Skips: {junk_skips}")
    print(f"    Low Confidence Skips: {low_confidence_skips}")
    print(f"    Errors: {errors}")
    
    if firm_recoveries > 0:
        recovery_rate = (firm_recoveries / processed_count) * 100
        print(f"    Recovery Rate: {recovery_rate:.1f}%")
        print(f"\n    {firm_recoveries} leads will now proceed to Apollo enrichment")
    else:
        print(f"\n    No leads recovered - all skipped or failed classification")
    
    return recovered_leads

def merge_recovered_leads(original_leads_data: Dict, recovered_leads: List[Dict]) -> Dict:
    """
    Merge AI-recovered leads back into the main leads data structure
    
    Args:
        original_leads_data: Original leads package
        recovered_leads: List of recovered leads from AI processing
    
    Returns:
        Updated leads data with recovered leads merged in
    """
    if not recovered_leads:
        return original_leads_data
    
    print(f"\n Merging {len(recovered_leads)} recovered leads into main dataset...")
    
    # Create a map of lead_id to lead for easy lookup
    all_leads = original_leads_data.get('leads', [])
    lead_map = {lead['lead_id']: lead for lead in all_leads}
    
    # Update leads with recovered versions
    updated_count = 0
    for recovered_lead in recovered_leads:
        lead_id = recovered_lead['lead_id']
        if lead_id in lead_map:
            # Replace the original with the recovered version
            lead_map[lead_id] = recovered_lead
            updated_count += 1
            print(f"   Updated lead: {recovered_lead.get('client_name')} -> {recovered_lead.get('attorney_firm')}")
    
    # Rebuild the leads list
    updated_leads = list(lead_map.values())
    
    # Update counts
    enrichment_count = len([l for l in updated_leads if l.get('needs_apollo_enrichment', False)])
    
    # Create updated package
    updated_package = original_leads_data.copy()
    updated_package['leads'] = updated_leads
    updated_package['leads_needing_enrichment'] = enrichment_count
    updated_package['ai_recovery_stats'] = {
        'recovered_leads': len(recovered_leads),
        'updated_leads': updated_count,
        'new_enrichment_total': enrichment_count
    }
    
    print(f"    Merge complete: {updated_count} leads updated")
    print(f"    New enrichment total: {enrichment_count} leads")
    
    return updated_package

if __name__ == "__main__":
    # Test with lawyers_of_lead_poor.json
    print(" Testing AI Lead Recovery with lawyers_of_lead_poor.json")
    
    try:
        with open('lawyers_of_lead_poor.json', 'r') as f:
            test_data = json.load(f)
        
        # Test with first 5 skipped leads only
        all_leads = test_data.get('leads', [])
        skipped_sample = [lead for lead in all_leads if lead.get('skip_reason') is not None][:5]
        
        test_package = {
            'leads': skipped_sample,
            'timestamp': 'test_run'
        }
        
        recovered = process_ai_recovery(test_package, min_confidence=7)
        
        if recovered:
            merged = merge_recovered_leads(test_package, recovered)
            
            # Save test results
            with open('ai_recovery_test_results.json', 'w') as f:
                json.dump(merged, f, indent=2)
            print(f"\nTest results saved to: ai_recovery_test_results.json")
        
    except FileNotFoundError:
        print(" lawyers_of_lead_poor.json not found")
    except Exception as e:
        print(f" Test failed: {e}")

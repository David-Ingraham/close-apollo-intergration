import os
import json
import requests
from dotenv import load_dotenv

load_dotenv()

import time
from typing import Dict, Optional

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
    
    Determine:
    1. Is this a PERSON name, LAW FIRM name, or JUNK data?
    2. Confidence level (1-10)
    3. If it's a firm, suggest a likely website URL.
    4. If it's a person, suggest what their firm might be called.and what theier url might be
    5. If the attorney_email field is present, use it to find the firm's domain.
    6.If we have the attorney email, use the root domain to suggest a url for the firm.
    
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
                    time.sleep(5 * (attempt + 1))  # Exponential backoff
                    continue
                return {"error": "Rate limit exceeded"}
            else:
                return {"error": f"API Error: {response.status_code}"}
                
        except Exception as e:
            if attempt < retry_count - 1:  # If not the last attempt
                time.sleep(5 * (attempt + 1))  # Exponential backoff
                continue
            return {"error": str(e)}
    
    return {"error": "Max retries exceeded"}



def test_with_skipped_leads():
    """
    Test with actual skipped leads from lawyers_of_lead_poor.json
    """
    try:
        with open('lawyers_of_lead_poor.json', 'r') as f:
            data = json.load(f)
            
        # Filter leads that were skipped (have a skip_reason)
        skipped_leads =[lead for lead in data["leads"] if lead["skip_reason"]is not None]
        
        api_key = os.getenv('GROQ_API_KEY')
        if not api_key:
            print(" No GROQ_API_KEY found in .env file")
            return
        
        print(f" Found {len(skipped_leads)} skipped leads\n")
        
        # Test first 5 leads
        for i, lead in enumerate(skipped_leads):
            attorney_name = lead.get('attorney_firm', 'N/A')
            attorney_email = lead.get('attorney_email', 'N/A')
            
            print(f"--- Lead {i} ---")
            print(f"Attorney Name: {attorney_name}")
            print(f"Attorney Email: {attorney_email}")
            
            if attorney_name and attorney_name != 'N/A':
                result = classify_attorney_name(attorney_name, attorney_email, api_key)
                print(f"AI Classification:\n{result}")
            else:
                print("Skipping - no attorney name")
            print("-" * 50)
            
    except FileNotFoundError:
        print(" lawyers_of_lead_poor.json not found")
        print("Run test_with_sample_data() instead")

if __name__ == "__main__":
    print(" Choose test mode:")
    print("1. Sample data test")
    print("2. Real skipped leads test")
    
    test_with_skipped_leads()


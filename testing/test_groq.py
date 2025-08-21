import os
import requests
from dotenv import load_dotenv

load_dotenv()

def test_groq():
    """Simple test of Groq API connectivity"""
    api_key = os.getenv('GROQ_API_KEY')
    if not api_key:
        print(" No GROQ_API_KEY found in .env file")
        print("Get a free API key from: https://console.groq.com/")
        return False
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    # Test with a simple prompt
    payload = {
        "messages": [
            {"role": "user", "content": "Is 'Smith & Associates' a law firm name or a person name? Answer in one sentence."}
        ],
        "model": "llama-3.3-70b-versatile",
        "max_tokens": 50
    }
    
    try:
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            message = result['choices'][0]['message']['content']
            print(f" Groq test successful!")
            print(f"Response: {message}")
            return True
        else:
            print(f" API call failed: {response.status_code}")
            print(f"Error: {response.text}")
            
    except Exception as e:
        print(f" Error: {e}")
    
    return False

if __name__ == "__main__":
    print(" Testing Groq API connection...")
    test_groq()

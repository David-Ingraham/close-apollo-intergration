#!/usr/bin/env python3
"""
Test script to verify LLM connectivity from Python
Tests multiple free LLM options to find what works
"""

import os
import json
import requests
from dotenv import load_dotenv

load_dotenv()

def test_ollama_local():
    """
    Test Ollama running locally (completely free)
    First install Ollama: https://ollama.ai/
    Then run: ollama pull llama2 (or another model)
    """
    print("=== TESTING OLLAMA (LOCAL) ===")
    
    try:
        # Check if Ollama is running
        response = requests.get("http://localhost:11434/api/tags", timeout=5)
        
        if response.status_code == 200:
            models = response.json().get('models', [])
            print(f"✅ Ollama is running with {len(models)} models:")
            for model in models:
                print(f"   - {model['name']}")
            
            # Test a simple chat completion
            if models:
                model_name = models[0]['name']
                print(f"\n🧪 Testing chat with {model_name}...")
                
                chat_payload = {
                    "model": model_name,
                    "messages": [{"role": "user", "content": "Say hello in exactly 5 words"}],
                    "stream": False
                }
                
                chat_response = requests.post(
                    "http://localhost:11434/api/chat", 
                    json=chat_payload, 
                    timeout=30
                )
                
                if chat_response.status_code == 200:
                    result = chat_response.json()
                    print(f"✅ Chat success: {result['message']['content']}")
                    return True
                else:
                    print(f"❌ Chat failed: {chat_response.status_code}")
            
        else:
            print(f"❌ Ollama responded but with error: {response.status_code}")
            
    except requests.exceptions.ConnectionError:
        print("❌ Ollama not running. Install from https://ollama.ai/")
        print("   Then run: ollama pull llama2")
    except Exception as e:
        print(f"❌ Ollama error: {e}")
    
    return False

def test_groq_api():
    """
    Test Groq API (free tier available)
    Get API key from: https://console.groq.com/
    """
    print("\n=== TESTING GROQ API ===")
    
    api_key = os.getenv('GROQ_API_KEY')
    if not api_key:
        print("❌ No GROQ_API_KEY in .env file")
        print("   Get free API key from: https://console.groq.com/")
        return False
    
    try:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "messages": [
                {"role": "user", "content": "Say hello in exactly 5 words"}
            ],
            "model": "llama3-8b-8192",  # Free model
            "max_tokens": 50
        }
        
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            message = result['choices'][0]['message']['content']
            print(f"✅ Groq success: {message}")
            return True
        else:
            print(f"❌ Groq failed: {response.status_code} - {response.text}")
            
    except Exception as e:
        print(f"❌ Groq error: {e}")
    
    return False

def test_openai_api():
    """
    Test OpenAI API (has free tier)
    Get API key from: https://platform.openai.com/
    """
    print("\n=== TESTING OPENAI API ===")
    
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        print("❌ No OPENAI_API_KEY in .env file")
        print("   Get API key from: https://platform.openai.com/")
        return False
    
    try:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": "gpt-3.5-turbo",  # Cheapest model
            "messages": [
                {"role": "user", "content": "Say hello in exactly 5 words"}
            ],
            "max_tokens": 50
        }
        
        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            message = result['choices'][0]['message']['content']
            print(f"✅ OpenAI success: {message}")
            return True
        else:
            print(f"❌ OpenAI failed: {response.status_code} - {response.text}")
            
    except Exception as e:
        print(f"❌ OpenAI error: {e}")
    
    return False

def test_attorney_classification(llm_function):
    """
    Test attorney name classification with working LLM
    """
    print(f"\n=== TESTING ATTORNEY CLASSIFICATION ===")
    
    test_cases = [
        "Constantine Bardis",
        "Smith & Associates", 
        "Michelle",
        "Do not have one",
        "Krause and Kinsman"
    ]
    
    prompt = """
    Analyze these attorney name fields and classify each one:
    
    Names to analyze:
    1. "Constantine Bardis"
    2. "Smith & Associates" 
    3. "Michelle"
    4. "Do not have one"
    5. "Krause and Kinsman"
    
    For each name, determine:
    - Is it a PERSON name or LAW FIRM name or JUNK data?
    - What's your confidence level (1-10)?
    - If it's a person, can you guess their likely law firm name?
    - If it's a firm, what might their website be?
    
    Respond in a simple numbered list format.
    """
    
    # This is a placeholder - we'll implement the actual LLM call
    # based on which service works
    print("🧪 Testing attorney name classification...")
    print("Sample prompt:", prompt[:200] + "...")
    print("✅ Classification test ready (implement with working LLM)")

def main():
    """
    Test all LLM connectivity options
    """
    print("🔍 Testing LLM Connectivity Options...\n")
    
    working_llms = []
    
    # Test each option
    if test_ollama_local():
        working_llms.append("Ollama (Local)")
    
    if test_groq_api():
        working_llms.append("Groq API")
        
    if test_openai_api():
        working_llms.append("OpenAI API")
    
    # Summary
    print(f"\n{'='*50}")
    print("🎯 CONNECTIVITY TEST RESULTS:")
    print(f"{'='*50}")
    
    if working_llms:
        print(f"✅ Working LLMs: {', '.join(working_llms)}")
        
        # Run attorney classification test
        test_attorney_classification(None)
        
        print(f"\n📋 NEXT STEPS:")
        print("1. Pick your preferred LLM from the working options")
        print("2. Implement attorney name classification function")
        print("3. Test with real skipped leads from lawyers_of_lead_poor.json")
        
    else:
        print("❌ No LLMs working. Setup options:")
        print("\nOPTION 1 - Ollama (Recommended for testing)")
        print("  1. Install: https://ollama.ai/download")
        print("  2. Run: ollama pull llama3.2")
        print("  3. Test: ollama run llama3.2")
        
        print("\nOPTION 2 - Groq API (Good free tier)")
        print("  1. Sign up: https://console.groq.com/")
        print("  2. Get API key")
        print("  3. Add GROQ_API_KEY=your_key to .env file")
        
        print("\nOPTION 3 - OpenAI API (Paid but reliable)")
        print("  1. Sign up: https://platform.openai.com/")
        print("  2. Add $5+ credits")
        print("  3. Add OPENAI_API_KEY=your_key to .env file")

if __name__ == "__main__":
    main()

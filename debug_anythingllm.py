#!/usr/bin/env python3
"""
Direct test of AnythingLLM API to debug the empty response issue
"""

import requests
import json
import yaml

def test_direct_api():
    """Test AnythingLLM API directly using the working chatbot format"""
    
    # Load config
    with open("backend/anythingllm_config.yaml", "r") as file:
        config = yaml.safe_load(file)
    
    api_key = config["api_key"]
    base_url = config["model_server_base_url"]
    workspace_slug = config["workspace_slug"]
    
    # Test URL
    url = f"{base_url}/workspace/{workspace_slug}/chat"
    
    headers = {
        "accept": "application/json",
        "Content-Type": "application/json",
        "Authorization": "Bearer " + api_key
    }
    
    # Simple test message
    data = {
        "message": "Hello, can you help me extract questions from exam text?",
        "mode": "chat",
        "sessionId": "test-session-123",
        "attachments": []
    }
    
    print(f"Testing URL: {url}")
    print(f"Headers: {headers}")
    print(f"Data: {json.dumps(data, indent=2)}")
    print("-" * 50)
    
    try:
        response = requests.post(url, headers=headers, json=data, timeout=30)
        
        print(f"Status Code: {response.status_code}")
        print(f"Response Headers: {dict(response.headers)}")
        print(f"Raw Response: {repr(response.text)}")
        
        if response.text:
            try:
                json_response = response.json()
                print(f"JSON Response: {json.dumps(json_response, indent=2)}")
            except json.JSONDecodeError as e:
                print(f"JSON decode error: {e}")
        else:
            print("Empty response body!")
            
        print("-" * 50)
        
        if response.status_code == 200:
            print("✅ API call successful!")
        else:
            print(f"❌ API call failed with status {response.status_code}")
            
    except Exception as e:
        print(f"❌ Request failed: {e}")

if __name__ == "__main__":
    test_direct_api()
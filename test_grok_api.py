"""Simple test script to debug Grok API issues."""

import os
from dotenv import load_dotenv
import httpx
import json

# Load environment variables
load_dotenv()

api_key = os.getenv("XAI_API_KEY")
if not api_key:
    print("❌ XAI_API_KEY not found in environment")
    exit(1)

print(f"✅ API Key found: {api_key[:20]}...")

# Test 1: Simple text completion (no images)
print("\n" + "="*60)
print("Test 1: Simple text chat completion (no images)")
print("="*60)

base_url = "https://api.x.ai/v1"
headers = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json"
}

payload = {
    "model": "grok-2-1212",  # Try without -vision first
    "messages": [
        {
            "role": "user",
            "content": "Hello, can you see this message?"
        }
    ],
    "temperature": 0.7
}

print(f"Endpoint: {base_url}/chat/completions")
print(f"Payload: {json.dumps(payload, indent=2)}")

try:
    with httpx.Client(timeout=30.0) as client:
        response = client.post(
            f"{base_url}/chat/completions",
            headers=headers,
            json=payload
        )
        print(f"\nStatus Code: {response.status_code}")
        print(f"Response Headers: {dict(response.headers)}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Success!")
            print(f"Response: {json.dumps(result, indent=2)}")
        else:
            print(f"❌ Error!")
            print(f"Response: {response.text}")
except Exception as e:
    print(f"❌ Exception: {e}")

# Test 2: Try with vision model
print("\n" + "="*60)
print("Test 2: Vision model text-only test")
print("="*60)

payload2 = {
    "model": "grok-2-vision-1212",
    "messages": [
        {
            "role": "user",
            "content": "Hello, can you see this message?"
        }
    ],
    "temperature": 0.7
}

print(f"Payload: {json.dumps(payload2, indent=2)}")

try:
    with httpx.Client(timeout=30.0) as client:
        response = client.post(
            f"{base_url}/chat/completions",
            headers=headers,
            json=payload2
        )
        print(f"\nStatus Code: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Success!")
            print(f"Response: {json.dumps(result, indent=2)}")
        else:
            print(f"❌ Error!")
            print(f"Response: {response.text}")
except Exception as e:
    print(f"❌ Exception: {e}")

# Test 3: List available models (if endpoint exists)
print("\n" + "="*60)
print("Test 3: List available models")
print("="*60)

try:
    with httpx.Client(timeout=30.0) as client:
        response = client.get(
            f"{base_url}/models",
            headers=headers
        )
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Available models:")
            print(json.dumps(result, indent=2))
        else:
            print(f"Response: {response.text}")
except Exception as e:
    print(f"Note: {e}")

print("\n" + "="*60)
print("Testing complete")
print("="*60)

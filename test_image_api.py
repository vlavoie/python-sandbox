"""
Test if Grok has image generation capabilities and find the correct endpoint/model.
"""

import os
from dotenv import load_dotenv
import httpx
import json

load_dotenv()

api_key = os.getenv("XAI_API_KEY")
base_url = "https://api.x.ai/v1"
headers = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json"
}

print("=" * 60)
print("Testing Grok Image Generation API")
print("=" * 60)

# Test 1: Try the /images/generations endpoint
print("\nTest 1: Checking /images/generations endpoint...")
try:
    with httpx.Client(timeout=30.0) as client:
        response = client.post(
            f"{base_url}/images/generations",
            headers=headers,
            json={
                "prompt": "A simple test image",
                "n": 1
            }
        )
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            print("✅ Image generation endpoint works!")
            result = response.json()
            print(json.dumps(result, indent=2))
        else:
            print(f"Response: {response.text}")
except Exception as e:
    print(f"Error: {e}")

# Test 2: Check if there's a specific image model in the models list
print("\n" + "=" * 60)
print("Test 2: Looking for image generation models...")
print("=" * 60)

try:
    with httpx.Client(timeout=30.0) as client:
        response = client.get(
            f"{base_url}/models",
            headers=headers
        )
        if response.status_code == 200:
            models = response.json()
            print("Searching for image-related models...")
            found_image_model = False
            
            if "data" in models:
                for model in models.get("data", []):
                    if isinstance(model, dict):
                        model_id = model.get("id", "")
                        # Look for image-related keywords
                        if any(keyword in model_id.lower() for keyword in ["image", "vision", "imagine", "dall", "aurora", "draw", "paint"]):
                            print(f"  ✓ Found: {model_id}")
                            found_image_model = True
                
                if not found_image_model:
                    print("  ℹ No dedicated image generation models found")
                    print("  ℹ Grok might use the chat API with vision for image generation")
except Exception as e:
    print(f"Error: {e}")

print("\n" + "=" * 60)
print("CONCLUSION:")
print("=" * 60)
print("""
It appears Grok may not have a separate image generation API endpoint
like OpenAI's DALL-E. 

Grok's image generation might work differently:
1. It might be integrated into the chat API with special prompting
2. It might require a different API endpoint entirely
3. It might be available through a different service (Aurora, Grok Imagine on X.com)

Check the official documentation at https://docs.x.ai/docs
for the latest information on image generation capabilities.
""")

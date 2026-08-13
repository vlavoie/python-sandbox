"""
Script to list available Grok API models.
Run this to find the correct model names for your API key.
"""

import os
from dotenv import load_dotenv
from pasokon.grok_client import GrokClient
import json

load_dotenv()

print("=" * 60)
print("Grok API - List Available Models")
print("=" * 60)

try:
    client = GrokClient()
    print(f"\n✅ API Key configured")
    print(f"Base URL: {client.base_url}")
    
    print("\nFetching available models...")
    models = client.list_models()
    
    print("\n" + "=" * 60)
    print("AVAILABLE MODELS:")
    print("=" * 60)
    print(json.dumps(models, indent=2))
    
    # Try to extract model IDs if they're in the response
    if "data" in models:
        print("\n" + "=" * 60)
        print("MODEL IDs (use these in your .env file):")
        print("=" * 60)
        for model in models.get("data", []):
            if isinstance(model, dict) and "id" in model:
                print(f"  - {model['id']}")
    
    print("\n" + "=" * 60)
    print("UPDATE YOUR .env FILE:")
    print("=" * 60)
    print("Add one of the model names above to your .env file:")
    print("")
    print("XAI_CHAT_MODEL=grok-beta")
    print("XAI_IMAGE_MODEL=grok-beta")
    print("")
    print("(Replace 'grok-beta' with the correct model name from the list above)")
    print("=" * 60)

except Exception as e:
    print(f"\n❌ Error: {e}")
    print("\nTroubleshooting:")
    print("1. Make sure your XAI_API_KEY is set in .env")
    print("2. Check that your API key is valid")
    print("3. The /models endpoint might not be available")
    print("4. Check https://docs.x.ai/docs for model names")

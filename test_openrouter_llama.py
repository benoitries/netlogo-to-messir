#!/usr/bin/env python3
"""Test OpenRouter API call with Llama model to diagnose 404 error."""

import os
import sys
from pathlib import Path

# Add the current directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from utils_api_key import load_env_files, get_api_key_for_model
from utils_openai_client import normalize_openrouter_model_name
from litellm import completion as litellm_completion
import litellm

# Load environment files
load_env_files()

# Test model
model_in = "llama-3.3-70b-instruct"
normalized = normalize_openrouter_model_name(model_in)

print("=" * 80)
print("TESTING OPENROUTER API CALL WITH LLAMA MODEL")
print("=" * 80)
print(f"Input model: '{model_in}'")
print(f"Normalized:  '{normalized}'")
print()

# Get API key
try:
    api_key = get_api_key_for_model(model_in)
    print(f"✓ API key retrieved (length: {len(api_key)})")
except Exception as e:
    print(f"✗ Failed to get API key: {e}")
    sys.exit(1)

# Configure LiteLLM
litellm.drop_params = True

# Prepare test call
messages = [
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "Say 'Hello' in one word."}
]

litellm_kwargs = {
    "model": normalized,
    "messages": messages,
    "api_key": api_key,
    "api_base": os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
    "headers": {
        "HTTP-Referer": os.getenv("OPENROUTER_HTTP_REFERER", "https://github.com/research-publi-reverse-engineering"),
        "X-Title": os.getenv("OPENROUTER_X_TITLE", "NetLogo to LUCIM Converter"),
    },
    "max_tokens": 10,
}

print("Making API call with:")
print(f"  model: {litellm_kwargs['model']}")
print(f"  api_base: {litellm_kwargs['api_base']}")
print(f"  headers: {litellm_kwargs['headers']}")
print()

try:
    print("Calling LiteLLM completion...")
    response = litellm_completion(**litellm_kwargs)
    print("✓ SUCCESS!")
    print(f"Response type: {type(response)}")
    if hasattr(response, 'choices') and response.choices:
        content = response.choices[0].message.content
        print(f"Response content: {content}")
    else:
        print(f"Response: {response}")
except Exception as e:
    print("✗ ERROR:")
    print(f"  Type: {type(e).__name__}")
    print(f"  Message: {str(e)}")
    
    # Try to extract HTTP status if available
    if hasattr(e, 'status_code'):
        print(f"  HTTP Status: {e.status_code}")
    if hasattr(e, 'response'):
        try:
            error_body = e.response.text if hasattr(e.response, 'text') else str(e.response)
            print(f"  Response body: {error_body[:200]}")
        except:
            pass
    
    print()
    print("Trying alternative model names...")
    
    # Test alternative model names
    alternatives = [
        "meta-llama/llama-3.1-70b-instruct",
        "meta-llama/llama-3.1-8b-instruct",
        "meta-llama/llama-3-70b-instruct",
    ]
    
    for alt_model in alternatives:
        print(f"\n  Testing: {alt_model}")
        try:
            test_kwargs = litellm_kwargs.copy()
            test_kwargs["model"] = alt_model
            response = litellm_completion(**test_kwargs)
            print(f"    ✓ SUCCESS with {alt_model}!")
            break
        except Exception as alt_e:
            print(f"    ✗ Failed: {type(alt_e).__name__}: {str(alt_e)[:100]}")

print("=" * 80)


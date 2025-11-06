#!/usr/bin/env python3
"""Quick diagnostic script to check OpenRouter configuration."""

import os
import sys
from pathlib import Path

# Add the current directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from utils_api_key import load_env_files, get_api_key_for_model
from utils_openai_client import normalize_openrouter_model_name

# Load environment files
load_env_files()

# Test model normalization
model_in = "llama-3.3-70b-instruct"
print("=" * 80)
print("OPENROUTER CONFIGURATION DIAGNOSTIC")
print("=" * 80)
print(f"\n1. Model Name Normalization:")
print(f"   Input model: '{model_in}'")
normalized = normalize_openrouter_model_name(model_in)
print(f"   Normalized:  '{normalized}'")
print(f"   ✓ Mapping active: {'YES' if normalized == 'meta-llama/llama-3.3-70b-instruct' else 'NO'}")

# Check API keys
print(f"\n2. API Key Configuration:")
candidates = ["ROUTER_API_KEY", "ROUTER_KEY", "ROUTER", "OPENROUTER_API_KEY"]
found_key = False
for var_name in candidates:
    val = os.getenv(var_name)
    if val:
        masked = val[:10] + "..." if len(val) > 10 else "***"
        print(f"   ✓ {var_name}: Found (length: {len(val)}, preview: {masked})")
        found_key = True
    else:
        print(f"   ✗ {var_name}: Not set")

if not found_key:
    print("   ⚠ WARNING: No OpenRouter API key found in environment!")

# Check API key retrieval function
print(f"\n3. API Key Retrieval Function:")
try:
    api_key = get_api_key_for_model(model_in)
    print(f"   ✓ get_api_key_for_model('{model_in}'): SUCCESS")
    print(f"     Key length: {len(api_key)}")
    print(f"     Key preview: {api_key[:10]}...")
except Exception as e:
    print(f"   ✗ get_api_key_for_model('{model_in}'): ERROR")
    print(f"     {type(e).__name__}: {e}")

# Check base URL
print(f"\n4. Base URL Configuration:")
base_url = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
print(f"   OPENROUTER_BASE_URL: {base_url}")
if base_url == "https://openrouter.ai/api/v1":
    print("   ✓ Using default (correct)")
else:
    print(f"   ⚠ Using custom URL: {base_url}")

# Check headers
print(f"\n5. Header Configuration:")
http_referer = os.getenv("OPENROUTER_HTTP_REFERER", "https://github.com/research-publi-reverse-engineering")
x_title = os.getenv("OPENROUTER_X_TITLE", "NetLogo to LUCIM Converter")
print(f"   HTTP-Referer: {http_referer}")
print(f"   X-Title: {x_title}")
print("   ✓ Headers will be set (using defaults if not in env)")

# Summary
print(f"\n" + "=" * 80)
print("SUMMARY")
print("=" * 80)
all_ok = found_key and normalized == "meta-llama/llama-3.3-70b-instruct"
if all_ok:
    print("✓ Configuration looks good! OpenRouter should work with Llama models.")
else:
    print("⚠ Issues detected:")
    if not found_key:
        print("  - Missing OpenRouter API key")
    if normalized != "meta-llama/llama-3.3-70b-instruct":
        print(f"  - Model normalization issue: got '{normalized}' instead of 'meta-llama/llama-3.3-70b-instruct'")
print("=" * 80)


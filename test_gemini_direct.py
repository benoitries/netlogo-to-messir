#!/usr/bin/env python3
"""
Simple test script to verify direct Gemini API calls.

This script tests the Gemini SDK directly to diagnose 503 UNAVAILABLE errors.
"""

import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
from utils_api_key import get_gemini_api_key, get_provider_for_model
from utils_openai_client import get_openai_client_for_model, GEMINI_AVAILABLE

# Load environment variables
load_dotenv()
load_dotenv(project_root / '.env')
load_dotenv(project_root.parent / '.env')

def test_gemini_direct():
    """Test direct Gemini API call using Google SDK."""
    print("=" * 80)
    print("GEMINI DIRECT API TEST")
    print("=" * 80)
    
    # Check if Gemini SDK is available
    if not GEMINI_AVAILABLE:
        print("❌ ERROR: google-genai package is not installed")
        print("   Install with: pip install google-genai")
        return False
    
    print("✓ google-genai package is available")
    
    # Test model name
    model_name = "gemini-2.5-flash"
    print(f"\n📋 Testing model: {model_name}")
    
    # Check provider detection
    provider = get_provider_for_model(model_name)
    print(f"✓ Provider detected: {provider}")
    
    if provider != "gemini":
        print(f"❌ ERROR: Expected provider 'gemini', got '{provider}'")
        return False
    
    # Get API key
    try:
        api_key = get_gemini_api_key()
        print(f"✓ API key found: {api_key[:8]}...{api_key[-4:] if len(api_key) > 12 else '***'}")
    except Exception as e:
        print(f"❌ ERROR: Failed to get API key: {e}")
        return False
    
    # Test 1: Direct Google SDK call
    print("\n" + "=" * 80)
    print("TEST 1: Direct Google SDK call (bypassing wrapper)")
    print("=" * 80)
    try:
        from google import genai
        
        client = genai.Client(api_key=api_key)
        print(f"✓ Created genai.Client")
        
        # Simple test prompt
        test_prompt = "Say 'Hello, world!' in one sentence."
        print(f"📝 Test prompt: {test_prompt}")
        
        print("🔄 Calling client.models.generate_content()...")
        response = client.models.generate_content(
            model=model_name,
            contents=test_prompt
        )
        
        print("✓ API call successful!")
        
        # Extract text from response
        text = ""
        try:
            if hasattr(response, 'candidates') and isinstance(response.candidates, list) and len(response.candidates) > 0:
                candidate = response.candidates[0]
                if hasattr(candidate, 'content'):
                    content = candidate.content
                    if hasattr(content, 'parts') and isinstance(content.parts, list):
                        for part in content.parts:
                            if hasattr(part, 'text') and isinstance(part.text, str):
                                text += part.text
                    elif hasattr(content, 'text'):
                        text = content.text
            elif hasattr(response, 'text'):
                text = response.text
        except Exception as e:
            print(f"⚠️  Warning: Could not extract text from response: {e}")
        
        if text:
            print(f"📄 Response: {text[:200]}{'...' if len(text) > 200 else ''}")
        else:
            print("⚠️  Warning: No text found in response")
            print(f"   Response type: {type(response)}")
            print(f"   Response attributes: {dir(response)}")
        
        print("\n✅ TEST 1 PASSED: Direct SDK call works")
        
    except Exception as e:
        error_type = type(e).__name__
        error_msg = str(e)
        error_repr = repr(e)
        
        print(f"\n❌ TEST 1 FAILED: {error_type}")
        print(f"   Error message: {error_msg}")
        print(f"   Error repr: {error_repr}")
        
        # Check for specific error types
        if "503" in error_msg or "UNAVAILABLE" in error_msg or "overloaded" in error_msg:
            print("\n🔍 DIAGNOSIS: 503 UNAVAILABLE error detected")
            print("   This indicates the Gemini API is temporarily overloaded.")
            print("   The error is real and comes from Google's servers.")
            print("   Recommendation: Wait a few minutes and retry.")
        elif "401" in error_msg or "403" in error_msg or "authentication" in error_msg.lower():
            print("\n🔍 DIAGNOSIS: Authentication error")
            print("   Check your GEMINI_API_KEY in .env file")
        elif "404" in error_msg or "not found" in error_msg.lower():
            print("\n🔍 DIAGNOSIS: Model not found")
            print(f"   Check if model name '{model_name}' is correct")
        
        return False
    
    # Test 2: Using our wrapper
    print("\n" + "=" * 80)
    print("TEST 2: Using GeminiClientWrapper (our wrapper)")
    print("=" * 80)
    try:
        client = get_openai_client_for_model(model_name)
        print(f"✓ Created GeminiClientWrapper")
        print(f"   Client type: {type(client).__name__}")
        
        # Test with wrapper's responses interface
        api_config = {
            "model": model_name,
            "instructions": "You are a helpful assistant.",
            "input": [{
                "role": "user",
                "content": [{"type": "input_text", "text": "Say 'Hello from wrapper!' in one sentence."}]
            }]
        }
        
        print(f"📝 Test prompt: {api_config['input'][0]['content'][0]['text']}")
        print("🔄 Calling client.responses.create()...")
        
        response = client.responses.create(**api_config)
        print("✓ API call successful!")
        
        # Extract text from wrapper response
        text = ""
        try:
            if hasattr(response, 'output') and isinstance(response.output, list):
                for item in response.output:
                    content = item.get('content') if isinstance(item, dict) else getattr(item, 'content', None)
                    if isinstance(content, list):
                        for part in content:
                            if isinstance(part, dict) and 'text' in part:
                                text += part['text']
                            elif hasattr(part, 'text'):
                                text += part.text
        except Exception as e:
            print(f"⚠️  Warning: Could not extract text from wrapper response: {e}")
        
        if text:
            print(f"📄 Response: {text[:200]}{'...' if len(text) > 200 else ''}")
        else:
            print("⚠️  Warning: No text found in wrapper response")
        
        print("\n✅ TEST 2 PASSED: Wrapper call works")
        return True
        
    except Exception as e:
        error_type = type(e).__name__
        error_msg = str(e)
        error_repr = repr(e)
        
        print(f"\n❌ TEST 2 FAILED: {error_type}")
        print(f"   Error message: {error_msg}")
        print(f"   Error repr: {error_repr}")
        
        if "503" in error_msg or "UNAVAILABLE" in error_msg or "overloaded" in error_msg:
            print("\n🔍 DIAGNOSIS: 503 UNAVAILABLE error detected")
            print("   This indicates the Gemini API is temporarily overloaded.")
            print("   The error is real and comes from Google's servers.")
            print("   Recommendation: Wait a few minutes and retry.")
        
        return False


if __name__ == "__main__":
    success = test_gemini_direct()
    print("\n" + "=" * 80)
    if success:
        print("✅ ALL TESTS PASSED")
    else:
        print("❌ SOME TESTS FAILED")
        print("=" * 80)
        sys.exit(1)
    print("=" * 80)


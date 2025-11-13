#!/usr/bin/env python3
"""
Test script to verify that native tokenizers are working correctly.
"""

import sys
from pathlib import Path

# Add the parent directory to the path
sys.path.insert(0, str(Path(__file__).parent))

from utils_openai_client import count_tokens_with_native_tokenizer

def test_tokenizers():
    """Test tokenizers for different models."""
    test_text = "Hello, this is a test sentence to verify token counting."
    
    models_to_test = [
        "mistralai/mistral-small-3.2-24b-instruct",
        "mistralai/codestral-2508",
        "meta-llama/llama-3.3-70b-instruct",
        "gpt-4",
    ]
    
    print("Testing native tokenizers...")
    print("=" * 60)
    
    for model in models_to_test:
        try:
            token_count = count_tokens_with_native_tokenizer(test_text, model)
            print(f"✓ {model:50} → {token_count} tokens")
        except Exception as e:
            print(f"✗ {model:50} → ERROR: {e}")
    
    print("=" * 60)
    print("\nNote: If transformers is not installed, all models will use tiktoken fallback.")
    print("Install with: pip install transformers sentencepiece")

if __name__ == "__main__":
    test_tokenizers()


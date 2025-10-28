"""
OpenAI client utilities for the NetLogo to LUCIM/UCI conversion pipeline.

This module provides unified functions for interacting with OpenAI's API,
handling both legacy chat completions and the new Responses API.
"""

import json
import time
import os
from typing import Any, Dict, Optional, Iterable, Tuple
from utils_openai_error import with_retries

try:
    # Typed import for editors; at runtime we only rely on attributes used.
    from openai import OpenAI  # type: ignore
except Exception:  # pragma: no cover - allow module import even if SDK missing at analysis time
    OpenAI = object  # type: ignore


def validate_openai_key() -> bool:
    """Validate OpenAI API key by making a simple test call.
    
    This function should be called at the very beginning of orchestration
    before any user interaction to ensure the API key is valid.
    
    Returns:
        bool: True if key is valid and API is accessible, False otherwise
        
    Raises:
        SystemExit: If OPENAI_API_KEY environment variable is not set
    """
    # Import centralized key from config
    from utils_config_constants import OPENAI_API_KEY
    
    # Check if API key is set
    if not OPENAI_API_KEY:
        print("ERROR: OPENAI_API_KEY environment variable is not set")
        print("Please set your OpenAI API key:")
        print("  export OPENAI_API_KEY='your-api-key-here'")
        raise SystemExit(1)
    
    # Test the key with a simple API call
    try:
        client = OpenAI(api_key=OPENAI_API_KEY)
        
        # Make a minimal test call to validate the key
        # Using a simple completion request that should work with any valid key
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": "test"}],
            max_tokens=1
        )
        
        # If we get here, the key is valid
        print("✓ OpenAI API key validation successful")
        return True
        
    except Exception as e:
        print(f"ERROR: OpenAI API key validation failed: {e}")
        print("Please check your API key and try again")
        return False


def create_and_wait(
    client: "OpenAI",
    api_config: Dict[str, Any],
    poll_interval_seconds: float = 1.0,
    timeout_seconds: Optional[float] = None,
) -> Any:
    """Create a responses job then poll until completion or failure.

    Returns the final response object. Raises RuntimeError on failure/timeout.
    """
    response = with_retries(lambda: client.responses.create(**api_config))

    start_time = time.time()
    while getattr(response, "status", None) not in ("completed", "failed", "cancelled"):
        time.sleep(poll_interval_seconds)
        response = with_retries(lambda: client.responses.retrieve(response.id))

        if timeout_seconds is not None and (time.time() - start_time) > timeout_seconds:
            raise RuntimeError("OpenAI response polling timed out")

    status = getattr(response, "status", None)
    if status != "completed":
        raise RuntimeError(f"OpenAI response ended with status: {status}")

    return response


# Streaming helpers were removed as the project no longer persists streaming artifacts.


def get_output_text(response: Any) -> str:
    """Return best-effort plain text from a responses object.

    Prefers the SDK helper `response.output_text` when available, with
    a safe fallback to traverse `response.output` content parts.
    """
    # Preferred helper in 2.x SDK
    text_attr = getattr(response, "output_text", None)
    if isinstance(text_attr, str) and text_attr:
        return text_attr

    # Fallback: traverse structured output
    text_chunks: list[str] = []
    output = getattr(response, "output", None)
    if isinstance(output, list):
        for item in output:
            # Typical shape: item.type == "message" with item.content parts
            content = getattr(item, "content", None)
            if isinstance(content, list):
                for part in content:
                    if getattr(part, "type", None) == "output_text":
                        value = getattr(part, "text", None)
                        if isinstance(value, str):
                            text_chunks.append(value)
                    # Some SDKs use generic text parts
                    if getattr(part, "type", None) == "text":
                        value = getattr(part, "text", None)
                        if isinstance(value, str):
                            text_chunks.append(value)

    return "".join(text_chunks).strip()


def get_reasoning_summary(response: Any) -> str:
    """Extract reasoning summary if present; else empty string.

    This function is intentionally tolerant to schema variations across SDK/model versions.
    It inspects several likely locations and shapes:
    - response.reasoning.summary (string)
    - content parts of type "reasoning" with either .text or .summary (list of items with .text)
    - content parts of type "reasoning_summary" with .text
    """
    # 1) Root-level reasoning dict with a "summary" string
    summary = getattr(response, "reasoning", None)
    if isinstance(summary, dict):
        value = summary.get("summary")
        if isinstance(value, str) and value.strip():
            return value.strip()

    # 2) Traverse output to find summaries in multiple shapes
    output = getattr(response, "output", None)
    # 2.a) New requirement: concatenate all elements of the array output.summary.text
    # Handle when output is an object-like with a "summary" list of items each having "text"
    try:
        output_summary = getattr(output, "summary", None) if output is not None else None
        # Also support dict-like
        if output_summary is None and isinstance(output, dict):
            output_summary = output.get("summary")
        if isinstance(output_summary, list) and output_summary:
            chunks0: list[str] = []
            for s in output_summary:
                # Support object attributes or dicts with key "text"
                s_text = getattr(s, "text", None)
                if s_text is None and isinstance(s, dict):
                    s_text = s.get("text")
                if isinstance(s_text, str) and s_text.strip():
                    chunks0.append(s_text.strip())
            if chunks0:
                return "\n".join(chunks0)
    except Exception:
        pass

    # 2.b) When output is a list of items, inspect both per-item content and per-item summary
    if isinstance(output, list):
        for item in output:
            # Prefer item.summary (array of {text}) if present
            item_summary = getattr(item, "summary", None)
            if item_summary is None and isinstance(item, dict):
                item_summary = item.get("summary")
            if isinstance(item_summary, list) and item_summary:
                chunksx: list[str] = []
                for s in item_summary:
                    s_text = getattr(s, "text", None)
                    if s_text is None and isinstance(s, dict):
                        s_text = s.get("text")
                    if isinstance(s_text, str) and s_text.strip():
                        chunksx.append(s_text.strip())
                if chunksx:
                    return "\n".join(chunksx)

            content = getattr(item, "content", None)
            if not isinstance(content, list):
                continue
            for part in content:
                part_type = getattr(part, "type", None)
                # a) Explicit reasoning summary in text form
                if part_type in ("reasoning_summary",):
                    text_value = getattr(part, "text", None)
                    if isinstance(text_value, str) and text_value.strip():
                        return text_value.strip()
                # b) Reasoning block which may contain nested summary items
                if part_type == "reasoning":
                    # Prefer direct text if provided
                    text_value = getattr(part, "text", None)
                    if isinstance(text_value, str) and text_value.strip():
                        return text_value.strip()
                    # Otherwise, aggregate from part.summary list
                    summary_items = getattr(part, "summary", None)
                    if isinstance(summary_items, list) and summary_items:
                        chunks: list[str] = []
                        for s in summary_items:
                            s_text = getattr(s, "text", None)
                            if isinstance(s_text, str) and s_text.strip():
                                chunks.append(s_text.strip())
                        if chunks:
                            return "\n".join(chunks)

    # 3) Some SDKs attach reasoning at the item level (not per-part)
    if isinstance(output, list):
        for item in output:
            item_reasoning = getattr(item, "reasoning", None)
            if isinstance(item_reasoning, dict):
                # Accept either a string summary or list of items with .text
                summ = item_reasoning.get("summary")
                if isinstance(summ, str) and summ.strip():
                    return summ.strip()
                if isinstance(summ, list) and summ:
                    chunks2: list[str] = []
                    for s in summ:
                        s_text = getattr(s, "text", None)
                        if isinstance(s_text, str) and s_text.strip():
                            chunks2.append(s_text.strip())
                    if chunks2:
                        return "\n".join(chunks2)

    # 4) Final fallback: if usage indicates reasoning tokens, but no explicit summary was found
    usage = getattr(response, "usage", None)
    if usage is not None:
        # Try common attributes
        reasoning_tokens = getattr(getattr(usage, "output_tokens_details", None), "reasoning_tokens", None)
        if isinstance(reasoning_tokens, int) and reasoning_tokens > 0:
            # There was reasoning activity, but no explicit summary structure was found.
            # Return empty string so downstream writers can decide how to represent absence.
            return ""

    # Nothing found
    return ""


def get_usage_tokens(response: Any, exact_input_tokens: Optional[int] = None) -> Dict[str, int]:
    """Return usage tokens as a dict using the canonical OpenAI 2.x schema.

    Canonical fields (prefer exact API fields when present):
    - input_tokens: response.usage.input_tokens
    - output_tokens: response.usage.output_tokens  ← standardized source of truth
    - total_tokens: response.usage.total_tokens
    - reasoning_tokens: response.usage.output_tokens_details.reasoning_tokens

    Fallbacks (conservative):
    - If input_tokens is missing but an exact_input_tokens value is provided by caller,
      use exact_input_tokens and infer output_tokens = max(total_tokens - input_tokens, 0).
    - reasoning_tokens defaults to 0 when output_tokens_details is missing.
    """
    tokens_used = 0
    input_tokens = 0
    output_tokens = 0
    reasoning_tokens = 0

    usage = getattr(response, "usage", None)
    if usage is None:
        return {
            "total_tokens": tokens_used,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "reasoning_tokens": reasoning_tokens,
        }

    # Canonical fields
    tokens_used = getattr(usage, "total_tokens", 0) or 0
    api_input_tokens = getattr(usage, "input_tokens", 0) or 0
    api_output_tokens = getattr(usage, "output_tokens", 0) or 0

    # Canonical reasoning location only (no legacy fallbacks)
    output_tokens_details = getattr(usage, "output_tokens_details", None)
    if output_tokens_details is not None:
        rt = getattr(output_tokens_details, "reasoning_tokens", 0)
        if isinstance(rt, int) and rt >= 0:
            reasoning_tokens = rt

    if api_input_tokens > 0:
        input_tokens = api_input_tokens
        output_tokens = api_output_tokens
    else:
        # Use exact input tokens if provided by the caller; infer output tokens from total
        if isinstance(exact_input_tokens, int) and exact_input_tokens >= 0:
            input_tokens = exact_input_tokens
            if tokens_used >= exact_input_tokens:
                output_tokens = tokens_used - exact_input_tokens
            else:
                output_tokens = 0
        else:
            # Nothing better to do; leave zeros if API did not provide values
            input_tokens = 0
            output_tokens = 0

    return {
        "total_tokens": tokens_used,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "reasoning_tokens": reasoning_tokens,
    }


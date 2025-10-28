"""
OpenAI client utilities for the NetLogo to LUCIM/UCI conversion pipeline.

This module provides unified functions for interacting with OpenAI's API,
handling both legacy chat completions and the new Responses API.
"""

import json
import time
from typing import Any, Dict, Optional, Union
from openai import OpenAI
from utils_openai_error import with_retries, classify_error
from utils_config_constants import get_reasoning_config
from utils_api_key import create_openai_client, validate_openai_key


def validate_openai_setup() -> bool:
    """Validate OpenAI API setup before any operations.
    
    This function should be called at the beginning of any script
    that uses OpenAI API to ensure proper configuration.
    
    Returns:
        bool: True if setup is valid, False otherwise
    """
    print("🔍 Validating OpenAI API setup...")
    return validate_openai_key()


def get_openai_client() -> OpenAI:
    """Get a configured OpenAI client with automatic API key loading.
    
    Returns:
        OpenAI: Configured OpenAI client
        
    Raises:
        ValueError: If API key is not found or invalid
    """
    return create_openai_client()


def format_prompt_for_responses_api(prompt_text: str) -> str:
    """Format prompt text for OpenAI Responses API.
    
    Args:
        prompt_text: The prompt text as a string
        
    Returns:
        The prompt text directly (as it worked on Oct 9)
    """
    return prompt_text


def create_and_wait(
    client: "OpenAI",
    api_config: Dict[str, Any],
    poll_interval_seconds: float = 1.0,
    timeout_seconds: Optional[float] = None,
) -> Any:
    """Create a response and wait for completion using OpenAI Responses API.
    
    Args:
        client: OpenAI client instance
        api_config: Configuration dictionary for the API call
        poll_interval_seconds: Interval between polling attempts
        timeout_seconds: Maximum time to wait (None for no timeout)
        
    Returns:
        Completed response object
        
    Raises:
        Exception: If the response fails or times out
    """
    try:
        # Create the response
        response = with_retries(lambda: client.responses.create(**api_config))
        
        # Wait for completion
        start_time = time.time()
        while response.status != "completed":
            if timeout_seconds and (time.time() - start_time) > timeout_seconds:
                raise TimeoutError(f"Response timed out after {timeout_seconds} seconds")
            
            time.sleep(poll_interval_seconds)
            response = client.responses.retrieve(response.id)
            
            if response.status == "failed":
                error_msg = getattr(response, "error", "Unknown error")
                raise Exception(f"Response failed: {error_msg}")
        
        return response
        
    except Exception as e:
        # Log the error category for debugging
        error_category = classify_error(e)
        print(f"OpenAI API error (category: {error_category}): {e}")
        raise


# Streaming helpers were removed as the project no longer persists streaming artifacts.


def get_output_text(response: Any) -> str:
    """Extract plain text output from OpenAI Responses API response.
    
    Args:
        response: OpenAI Responses API response object
        
    Returns:
        Plain text content from the response
    """
    try:
        # For Responses API: response.output[1].content[0].text
        if hasattr(response, 'output') and isinstance(response.output, list):
            for output_item in response.output:
                if hasattr(output_item, 'content') and isinstance(output_item.content, list):
                    for content_item in output_item.content:
                        if hasattr(content_item, 'text') and content_item.text:
                            return content_item.text
        
        # Fallback for legacy chat completions API
        if hasattr(response, 'choices') and response.choices:
            return response.choices[0].message.content or ""
        
        return ""
    except (AttributeError, IndexError, KeyError):
        return ""


def get_reasoning_summary(response: Any) -> str:
    """Extract reasoning summary from OpenAI Responses API response.
    
    Args:
        response: OpenAI Responses API response object
        
    Returns:
        Reasoning summary text if available, empty string otherwise
    """
    try:
        # For Responses API: look for reasoning blocks in output
        if hasattr(response, 'output') and isinstance(response.output, list):
            for output_item in response.output:
                if hasattr(output_item, 'summary') and isinstance(output_item.summary, list):
                    chunks = []
                    for summary_item in output_item.summary:
                        if hasattr(summary_item, 'text') and summary_item.text:
                            chunks.append(summary_item.text.strip())
                    if chunks:
                        return "\n".join(chunks)
        
        # Fallback for legacy chat completions API
        return ""
    except (AttributeError, IndexError, KeyError):
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
            # Conservative fallback: assume all tokens are output tokens
            output_tokens = tokens_used

    return {
        "total_tokens": tokens_used,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "reasoning_tokens": reasoning_tokens,
    }


def parse_json_response(text: str) -> Dict[str, Any]:
    """Parse JSON response text, handling common formatting issues.
    
    Args:
        text: Raw text response that should contain JSON
        
    Returns:
        Parsed JSON as dictionary
        
    Raises:
        ValueError: If JSON parsing fails
    """
    if not text.strip():
        raise ValueError("Empty response text")
    
    # Try to parse as-is first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    
    # Try to extract JSON from markdown code blocks
    if "```json" in text:
        start = text.find("```json") + 7
        end = text.find("```", start)
        if end > start:
            json_text = text[start:end].strip()
            try:
                return json.loads(json_text)
            except json.JSONDecodeError:
                pass
    
    # Try to extract JSON from code blocks without language
    if "```" in text:
        start = text.find("```") + 3
        end = text.find("```", start)
        if end > start:
            json_text = text[start:end].strip()
            try:
                return json.loads(json_text)
            except json.JSONDecodeError:
                pass
    
    # Last resort: try to find JSON-like content
    lines = text.split('\n')
    json_lines = []
    in_json = False
    
    for line in lines:
        stripped = line.strip()
        if stripped.startswith('{') and not in_json:
            in_json = True
            json_lines.append(line)
        elif in_json:
            json_lines.append(line)
            if stripped.endswith('}') and stripped.count('{') <= stripped.count('}'):
                break
    
    if json_lines:
        json_text = '\n'.join(json_lines)
        try:
            return json.loads(json_text)
        except json.JSONDecodeError:
            pass
    
    raise ValueError(f"Could not parse JSON from response: {text[:200]}...")


def validate_openai_key() -> bool:
    """Validate that OpenAI API key is properly configured.
    
    Returns:
        True if API key is valid, False otherwise
    """
    try:
        from openai import OpenAI
        client = OpenAI()
        # Try a simple API call to validate the key
        client.models.list()
        return True
    except Exception:
        return False


def create_response_summary(
    agent_type: str,
    model: str,
    timestamp: str,
    base_name: str,
    step_number: str,
    reasoning_summary: str,
    data: Optional[Dict[str, Any]],
    errors: list[str],
    tokens_used: int,
    input_tokens: int,
    visible_output_tokens: int,
    reasoning_tokens: int,
    total_output_tokens: int,
    raw_response: Optional[Any] = None,
) -> Dict[str, Any]:
    """Create a standardized response summary.
    
    Args:
        agent_type: Type of agent that processed the request
        model: Model used for the request
        timestamp: Timestamp of the request
        base_name: Base name of the input file
        step_number: Step number in the pipeline
        reasoning_summary: Summary of the reasoning process
        data: Parsed data from the response
        errors: List of error messages
        tokens_used: Total tokens used
        input_tokens: Input tokens used
        visible_output_tokens: Visible output tokens
        reasoning_tokens: Reasoning tokens used
        total_output_tokens: Total output tokens
        raw_response: Raw response object
        
    Returns:
        Standardized response summary dictionary
    """
    return {
        "agent_type": agent_type,
        "model": model,
        "timestamp": timestamp,
        "base_name": base_name,
        "step_number": step_number,
        "reasoning_summary": reasoning_summary,
        "data": data,
        "errors": errors,
        "tokens_used": tokens_used,
        "input_tokens": input_tokens,
        "visible_output_tokens": visible_output_tokens,
        "reasoning_tokens": reasoning_tokens,
        "total_output_tokens": total_output_tokens,
        "raw_response": raw_response,
    }
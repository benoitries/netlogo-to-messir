#!/usr/bin/env python3
"""
OpenAI Responses API error handling utilities
Provides retry wrappers, error classification, and a create-and-wait helper
for the OpenAI 2.x Responses API.
"""

from typing import Callable, Optional, Dict, Any
import time
import logging

# Always use our own exception classes to avoid OpenAI 2.x APIError requiring 'request' argument
# This ensures consistent behavior regardless of whether OpenAI is installed
class APIError(Exception):
    """Custom APIError that doesn't require 'request' argument like OpenAI 2.x exceptions."""
    def __init__(self, message: str = "", request=None):
        super().__init__(message)
        self.message = message
        self.request = request

class APIConnectionError(APIError):
    """Connection-related API error."""
    pass

class RateLimitError(APIError):
    """Rate limit API error."""
    pass

class BadRequestError(APIError):
    """Bad request API error."""
    pass

class AuthenticationError(APIError):
    """Authentication API error."""
    pass

class PermissionDeniedError(APIError):
    """Permission denied API error."""
    pass


RETRYABLE_EXCEPTIONS = (APIConnectionError, RateLimitError, APIError, BadRequestError)


def classify_error(error: Exception) -> str:
    """Return a stable error category string for logging/metrics."""
    if isinstance(error, RateLimitError):
        return "rate_limit"
    if isinstance(error, APIConnectionError):
        return "connection"
    if isinstance(error, BadRequestError):
        return "bad_request"
    if isinstance(error, AuthenticationError):
        return "auth"
    if isinstance(error, PermissionDeniedError):
        return "permission"
    if isinstance(error, APIError):
        return "server"
    return "unknown"


def with_retries(function_call: Callable[[], Any], *, max_retries: int = 3, backoff_factor: float = 1.5, logger: Optional[logging.Logger] = None, provider: Optional[str] = None) -> Any:
    """
    Execute a function with exponential backoff on retryable OpenAI errors.
    
    Args:
        function_call: Function to execute with retries
        max_retries: Maximum number of retry attempts
        backoff_factor: Exponential backoff multiplier
        logger: Optional logger instance
        provider: Optional provider name ("openai", "gemini", "router") for better error messages
    """
    attempt = 0
    # Special policy: for LiteLLM transient errors we wait 60s and retry up to 2 times
    max_special_retries = 2
    special_attempts = 0
    while True:
        try:
            return function_call()
        except RETRYABLE_EXCEPTIONS as error:
            attempt += 1
            err_name = type(error).__name__
            category = classify_error(error)
            is_litellm_like_timeout = ("Timeout" in err_name)
            is_litellm_like_apierr = ("APIError" in err_name)
            is_litellm_like_badreq = ("BadRequestError" in err_name) or (category == "bad_request")

            # Auto-detect provider from error message if not provided
            detected_provider = provider
            if not detected_provider:
                error_msg = str(error).lower()
                if "gemini api error" in error_msg or "gemini" in error_msg:
                    detected_provider = "gemini"
                elif "litellm" in error_msg or "openrouter" in error_msg:
                    detected_provider = "router"
                else:
                    detected_provider = "openai"  # Default assumption

            if (is_litellm_like_timeout or is_litellm_like_apierr or is_litellm_like_badreq) and special_attempts < max_special_retries:
                special_attempts += 1
                # Write explicitly into logs for orchestrator visibility
                if logger:
                    logger.info(f"[Retry] Model error detected ({err_name}). Waiting 60s before retry #{special_attempts} with same setup.")
                else:
                    logging.getLogger(__name__).info(f"[Retry] Model error detected ({err_name}). Waiting 60s before retry #{special_attempts} with same setup.")
                time.sleep(60)
                continue

            # Use provider-specific error message
            if detected_provider == "gemini":
                error_prefix = "Gemini API call failed"
            elif detected_provider == "router":
                error_prefix = "OpenRouter/LiteLLM call failed"
            else:
                error_prefix = "OpenAI API call failed"
            
            if logger:
                logger.warning(f"{error_prefix} (attempt {attempt}): category={category} error={error}")
            if attempt > max_retries:
                if logger:
                    logger.error(f"{error_prefix} exhausted retries: error={error}")
                raise
            sleep_seconds = backoff_factor ** attempt
            time.sleep(sleep_seconds)


def create_and_wait(client, api_config: Dict[str, Any], *, poll_interval: float = 1.0, max_wait_seconds: int = 300, logger: Optional[logging.Logger] = None, provider: Optional[str] = None):
    """
    Create a Responses API job and poll until completion or failure.

    Returns the final response object when status == "completed".
    Raises on failure/cancelled or timeout.
    
    Args:
        client: API client (OpenAI, Gemini wrapper, etc.)
        api_config: API configuration dictionary
        poll_interval: Polling interval in seconds
        max_wait_seconds: Maximum wait time
        logger: Optional logger instance
        provider: Optional provider name for better error messages
    """
    start_time = time.time()
    response = with_retries(lambda: client.responses.create(**api_config), logger=logger, provider=provider)
    if logger:
        logger.info(f"Responses.create submitted: id={getattr(response, 'id', 'N/A')} status={getattr(response, 'status', 'unknown')}")

    while getattr(response, "status", None) not in ("completed", "failed", "cancelled"):
        if time.time() - start_time > max_wait_seconds:
            raise TimeoutError(f"OpenAI response timed out after {max_wait_seconds}s, id={getattr(response, 'id', 'N/A')}")
        time.sleep(poll_interval)
        response = with_retries(lambda: client.responses.retrieve(response.id), logger=logger, provider=provider)

    if getattr(response, "status", None) != "completed":
        raise APIError(f"OpenAI response did not complete successfully: status={response.status} id={getattr(response, 'id', 'N/A')}")

    return response


def get_output_text(response: Any) -> str:
    """
    Best-effort plain text extraction from a Responses API object.
    Prefer response.output_text when available; fallback to traversing output items.
    """
    # Prefer SDK convenience if present
    text = getattr(response, "output_text", None)
    if isinstance(text, str) and text.strip():
        return text

    # Fallback walk
    try:
        if getattr(response, "output", None):
            # If reasoning present, content often at index 1
            items = list(response.output)
            for item in items:
                content = getattr(item, "content", None)
                if content and isinstance(content, list):
                    first = content[0]
                    maybe_text = getattr(first, "text", None)
                    if isinstance(maybe_text, str) and maybe_text.strip():
                        return maybe_text
    except Exception:
        pass
    return ""



#!/usr/bin/env python3
"""
OpenAI Responses API error handling utilities
Provides retry wrappers, error classification, and a create-and-wait helper
for the OpenAI 2.x Responses API.
"""

from typing import Callable, Optional, Dict, Any
import time
import logging

try:
    # OpenAI 2.x exceptions
    from openai import (
        APIError,
        APIConnectionError,
        RateLimitError,
        BadRequestError,
        AuthenticationError,
        PermissionDeniedError,
    )
except Exception:  # pragma: no cover - allow import before openai is installed
    # Define fallbacks to avoid import errors in environments without openai
    class APIError(Exception):
        pass

    class APIConnectionError(APIError):
        pass

    class RateLimitError(APIError):
        pass

    class BadRequestError(APIError):
        pass

    class AuthenticationError(APIError):
        pass

    class PermissionDeniedError(APIError):
        pass


RETRYABLE_EXCEPTIONS = (APIConnectionError, RateLimitError, APIError)


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


def with_retries(function_call: Callable[[], Any], *, max_retries: int = 3, backoff_factor: float = 1.5, logger: Optional[logging.Logger] = None) -> Any:
    """
    Execute a function with exponential backoff on retryable OpenAI errors.
    """
    attempt = 0
    while True:
        try:
            return function_call()
        except RETRYABLE_EXCEPTIONS as error:
            attempt += 1
            if logger:
                logger.warning(f"OpenAI call failed (attempt {attempt}): category={classify_error(error)} error={error}")
            if attempt > max_retries:
                if logger:
                    logger.error(f"OpenAI call exhausted retries: error={error}")
                raise
            sleep_seconds = backoff_factor ** attempt
            time.sleep(sleep_seconds)


def create_and_wait(client, api_config: Dict[str, Any], *, poll_interval: float = 1.0, max_wait_seconds: int = 300, logger: Optional[logging.Logger] = None):
    """
    Create a Responses API job and poll until completion or failure.

    Returns the final response object when status == "completed".
    Raises on failure/cancelled or timeout.
    """
    start_time = time.time()
    response = with_retries(lambda: client.responses.create(**api_config), logger=logger)
    if logger:
        logger.info(f"Responses.create submitted: id={getattr(response, 'id', 'N/A')} status={getattr(response, 'status', 'unknown')}")

    while getattr(response, "status", None) not in ("completed", "failed", "cancelled"):
        if time.time() - start_time > max_wait_seconds:
            raise TimeoutError(f"OpenAI response timed out after {max_wait_seconds}s, id={getattr(response, 'id', 'N/A')}")
        time.sleep(poll_interval)
        response = with_retries(lambda: client.responses.retrieve(response.id), logger=logger)

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



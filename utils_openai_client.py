"""
OpenAI client utilities for the NetLogo to LUCIM/UCI conversion pipeline.

This module provides unified functions for interacting with OpenAI's API,
handling both legacy chat completions and the new Responses API.
Also supports Google Gemini and OpenRouter models.
"""

import json
import logging
import time
from typing import Any, Dict, Optional, Union
from openai import OpenAI
from utils_openai_error import with_retries, classify_error
from utils_config_constants import get_reasoning_config
from utils_api_key import get_openai_api_key, get_api_key_for_model, get_provider_for_model

# Logger for this module
logger = logging.getLogger(__name__)


def _mask_api_key(value: Any) -> Any:
    """Mask API keys in logged parameters for security.
    
    Args:
        value: Value to mask (string or other type)
    
    Returns:
        Masked value if it looks like an API key, original value otherwise
    """
    if isinstance(value, str) and len(value) > 10:
        # Common API key patterns: starts with sk-, sk-proj-, etc.
        if value.startswith(("sk-", "sk-proj-", "xoxb-", "xoxp-")) or "api" in value.lower():
            return f"{value[:8]}...{value[-4:]}" if len(value) > 12 else "***MASKED***"
    return value


def _log_completion_params(api_config: Dict[str, Any], litellm_kwargs: Dict[str, Any]) -> None:
    """Log all parameters used for AI model chat completions.
    
    Args:
        api_config: Original API configuration dictionary
        litellm_kwargs: Final kwargs passed to litellm.completion
    """
    # Log original api_config (masking sensitive values)
    safe_api_config = {k: _mask_api_key(v) for k, v in api_config.items()}
    logger.info("=" * 80)
    logger.info("AI MODEL CHAT COMPLETION - API CONFIG PARAMETERS:")
    logger.info(f"  Original api_config: {json.dumps(safe_api_config, indent=2, ensure_ascii=False)}")
    
    # Log final litellm_kwargs (masking sensitive values)
    safe_litellm_kwargs = {k: _mask_api_key(v) for k, v in litellm_kwargs.items()}
    logger.info("AI MODEL CHAT COMPLETION - LITELLM CALL PARAMETERS:")
    logger.info(f"  Model: {litellm_kwargs.get('model', 'N/A')}")
    logger.info(f"  Messages count: {len(litellm_kwargs.get('messages', []))}")
    
    # Log message structure (truncate long content)
    messages = litellm_kwargs.get('messages', [])
    for idx, msg in enumerate(messages):
        role = msg.get('role', 'unknown') if isinstance(msg, dict) else getattr(msg, 'role', 'unknown')
        content = msg.get('content', '') if isinstance(msg, dict) else getattr(msg, 'content', '')
        content_preview = content[:200] + "..." if len(content) > 200 else content
        logger.info(f"    Message {idx + 1} [{role}]: {content_preview}")
    
    # Log other parameters
    for key, value in safe_litellm_kwargs.items():
        if key not in ('model', 'messages', 'api_key'):
            logger.info(f"  {key}: {value}")
    
    if 'api_key' in litellm_kwargs:
        logger.info(f"  api_key: {_mask_api_key(litellm_kwargs['api_key'])}")
    if 'api_base' in litellm_kwargs:
        logger.info(f"  api_base: {litellm_kwargs['api_base']}")
    
    logger.info(f"  litellm.drop_params: {litellm.drop_params}")
    logger.info("=" * 80)


def _log_responses_api_params(api_config: Dict[str, Any]) -> None:
    """Log all parameters used for OpenAI Responses API calls.
    
    Args:
        api_config: Configuration dict passed to client.responses.create
    """
    safe_api_config = {k: _mask_api_key(v) for k, v in api_config.items()}
    logger.info("=" * 80)
    logger.info("AI MODEL RESPONSES API - PARAMETERS:")
    logger.info(f"  responses.create payload: {json.dumps(safe_api_config, indent=2, ensure_ascii=False)}")
    logger.info("=" * 80)


def _log_openrouter_response(response: Any, error: Optional[Exception] = None) -> None:
    """Log complete OpenRouter API response details for debugging.
    
    Logs all available information from OpenRouter responses including:
    - HTTP status code
    - Response headers
    - Response body
    - Error details if present
    - Model information
    - Usage/token information
    
    Args:
        response: LiteLLM response object or exception
        error: Exception if the call failed
    """
    logger.info("=" * 80)
    logger.info("OPENROUTER API RESPONSE - COMPLETE DETAILS:")
    
    if error:
        logger.error(f"  ERROR OCCURRED: {type(error).__name__}")
        logger.error(f"  Error message: {str(error)}")
        
        # Try to extract HTTP details from exception
        if hasattr(error, 'status_code'):
            logger.error(f"  HTTP Status Code: {error.status_code}")
        if hasattr(error, 'code'):
            logger.error(f"  Error Code: {error.code}")
        
        # LiteLLM/OpenRouter specific error attributes
        if hasattr(error, 'response'):
            resp = error.response
            if hasattr(resp, 'status_code'):
                logger.error(f"  HTTP Status Code: {resp.status_code}")
            if hasattr(resp, 'status'):
                logger.error(f"  HTTP Status: {resp.status}")
            if hasattr(resp, 'headers'):
                try:
                    headers_dict = dict(resp.headers) if hasattr(resp.headers, '__iter__') and not isinstance(resp.headers, str) else resp.headers
                    logger.error(f"  Response Headers: {json.dumps(headers_dict, indent=2, default=str)}")
                except Exception:
                    logger.error(f"  Response Headers: {resp.headers}")
            if hasattr(resp, 'text'):
                logger.error(f"  Response Body (text): {resp.text}")
            elif hasattr(resp, 'content'):
                logger.error(f"  Response Body (content): {resp.content}")
            if hasattr(resp, 'json'):
                try:
                    body_json = resp.json() if callable(resp.json) else resp.json
                    logger.error(f"  Response Body (JSON): {json.dumps(body_json, indent=2, default=str)}")
                except Exception as e:
                    logger.debug(f"  Could not parse response as JSON: {e}")
        
        # Additional error attributes
        if hasattr(error, 'body'):
            body = error.body
            if isinstance(body, dict):
                logger.error(f"  Error Body (dict): {json.dumps(body, indent=2, default=str)}")
            else:
                logger.error(f"  Error Body: {body}")
        if hasattr(error, 'message'):
            logger.error(f"  Error Message: {error.message}")
        if hasattr(error, 'headers'):
            try:
                headers_dict = dict(error.headers) if hasattr(error.headers, '__iter__') and not isinstance(error.headers, str) else error.headers
                logger.error(f"  Error Headers: {json.dumps(headers_dict, indent=2, default=str)}")
            except Exception:
                logger.error(f"  Error Headers: {error.headers}")
        
        # Log full exception attributes for debugging
        try:
            error_attrs = {}
            for attr in dir(error):
                if not attr.startswith('__') and not callable(getattr(error, attr, None)):
                    try:
                        value = getattr(error, attr)
                        if not callable(value):
                            # Truncate very long values
                            str_value = str(value)
                            if len(str_value) > 500:
                                str_value = str_value[:500] + "..."
                            error_attrs[attr] = str_value
                    except Exception:
                        pass
            if error_attrs:
                logger.debug(f"  Full error attributes: {json.dumps(error_attrs, indent=2, default=str)}")
        except Exception as e:
            logger.debug(f"  Could not serialize error attributes: {e}")
    
    if response and not error:
        # Log successful response details
        logger.info("  Response Status: SUCCESS")
        
        # Log model information
        if hasattr(response, 'model'):
            logger.info(f"  Model: {response.model}")
        if hasattr(response, '_hidden_params'):
            model_info = getattr(response, '_hidden_params', {}).get('model', 'N/A')
            logger.info(f"  Model (from hidden params): {model_info}")
        
        # Log usage/token information
        if hasattr(response, 'usage'):
            usage = response.usage
            logger.info("  Token Usage:")
            if hasattr(usage, 'prompt_tokens'):
                logger.info(f"    Prompt tokens: {usage.prompt_tokens}")
            if hasattr(usage, 'completion_tokens'):
                logger.info(f"    Completion tokens: {usage.completion_tokens}")
            if hasattr(usage, 'total_tokens'):
                logger.info(f"    Total tokens: {usage.total_tokens}")
            # Log full usage object
            try:
                usage_dict = usage.__dict__ if hasattr(usage, '__dict__') else {}
                if usage_dict:
                    logger.info(f"    Full usage object: {json.dumps(usage_dict, indent=4, default=str)}")
            except Exception:
                pass
        
        # Log response metadata
        if hasattr(response, 'id'):
            logger.info(f"  Response ID: {response.id}")
        if hasattr(response, 'created'):
            logger.info(f"  Created: {response.created}")
        if hasattr(response, 'object'):
            logger.info(f"  Object type: {response.object}")
        
        # Log response headers if available
        if hasattr(response, '_response_ms'):
            logger.info(f"  Response time (ms): {response._response_ms}")
        if hasattr(response, '_headers'):
            logger.info(f"  Response headers: {response._headers}")
        
        # Log choices/content
        if hasattr(response, 'choices'):
            logger.info(f"  Choices count: {len(response.choices) if isinstance(response.choices, list) else 'N/A'}")
            if isinstance(response.choices, list) and response.choices:
                first_choice = response.choices[0]
                if hasattr(first_choice, 'message'):
                    msg = first_choice.message
                    if hasattr(msg, 'content'):
                        content_preview = str(msg.content)[:500] + "..." if len(str(msg.content)) > 500 else str(msg.content)
                        logger.info(f"  First choice content preview: {content_preview}")
        
        # Log full response object structure (for debugging)
        try:
            response_dict = {}
            for attr in dir(response):
                if not attr.startswith('_') and not callable(getattr(response, attr, None)):
                    try:
                        value = getattr(response, attr)
                        if not callable(value):
                            response_dict[attr] = str(value)[:200]  # Truncate long values
                    except Exception:
                        pass
            if response_dict:
                logger.info(f"  Response attributes: {json.dumps(response_dict, indent=2, default=str)}")
        except Exception as e:
            logger.debug(f"  Could not serialize response attributes: {e}")
    
    logger.info("=" * 80)


# Try to import Google genai SDK (optional for Gemini support)
try:
    from google import genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    genai = None


# Require LiteLLM for unified provider routing (no fallbacks)
from litellm import completion as litellm_completion  # type: ignore
import litellm  # type: ignore
import os


def validate_openai_setup() -> bool:
    """Validate OpenAI API setup before any operations.
    
    This function should be called at the beginning of any script
    that uses OpenAI API to ensure proper configuration.
    
    Returns:
        bool: True if setup is valid, False otherwise
    """
    print("🔍 Validating OpenAI API setup...")
    try:
        _ = get_openai_api_key()
        return True
    except Exception:
        return False


def get_openai_client() -> OpenAI:
    """Get a configured OpenAI client with automatic API key loading.
    
    Returns:
        OpenAI: Configured OpenAI client
        
    Raises:
        ValueError: If API key is not found or invalid
    """
    api_key = get_openai_api_key()
    return OpenAI(api_key=api_key)


class GeminiClientWrapper:
    """Wrapper for Google Gemini client to provide OpenAI-compatible interface.
    
    This wrapper adapts Google's genai SDK to work with the existing agent code
    that expects OpenAI client interface.
    """
    
    def __init__(self, api_key: str, model_name: str):
        """Initialize Gemini client wrapper.
        
        Args:
            api_key: Gemini API key
            model_name: Model name (e.g., "gemini-2.5-flash")
        """
        if not GEMINI_AVAILABLE:
            raise ImportError(
                "google-genai package is required for Gemini support. "
                "Install with: pip install google-genai"
            )
        self.client = genai.Client(api_key=api_key)
        self.model_name = model_name
        self.provider = "gemini"
        
        # Store the last response for retrieval
        self._last_response = None
        self._last_response_id = None
    
    class Responses:
        """Mock responses object to match OpenAI client.responses interface."""
        
        def __init__(self, parent: "GeminiClientWrapper"):
            self.parent = parent
        
        def create(self, **kwargs) -> Any:
            """Create a response using Gemini API.
            
            Args:
                model: Model name (required)
                instructions: System instructions (optional)
                input: Input messages (optional)
                **kwargs: Other OpenAI API config (ignored for Gemini)
            
            Returns:
                Response object with OpenAI-like structure
            """
            # Enforce Gemini model: prefer wrapper's configured model_name
            requested_model = kwargs.get("model")
            model = self.parent.model_name
            try:
                if isinstance(requested_model, str) and "gemini" in requested_model.lower():
                    model = requested_model
            except Exception:
                pass
            instructions = kwargs.get("instructions", "")
            input_messages = kwargs.get("input", [])
            
            # Build prompt from instructions and input
            prompt_parts = []
            if instructions:
                prompt_parts.append(instructions)
            
            # Extract content from input messages
            for msg in input_messages:
                if isinstance(msg, dict):
                    content = msg.get("content", "")
                    if isinstance(content, str):
                        prompt_parts.append(content)
                    elif isinstance(content, list):
                        for item in content:
                            if isinstance(item, dict) and "text" in item:
                                prompt_parts.append(item["text"])
            
            # Combine all parts
            full_prompt = "\n\n".join(prompt_parts)
            
            # Call Gemini API
            # Note: model name is used exactly as provided (e.g., "gemini-2.5-flash")
            # No transformation or sanitization is applied to the model name
            try:
                response = self.parent.client.models.generate_content(
                    model=model,
                    contents=full_prompt
                )
                
                # Convert to OpenAI-like response structure
                response_id = f"gemini_{int(time.time() * 1000)}"
                self.parent._last_response_id = response_id
                
                # Create OpenAI-like response object
                wrapped_response = GeminiResponseWrapper(response, response_id, full_prompt)
                self.parent._last_response = wrapped_response
                
                return wrapped_response
            except Exception as e:
                # Convert Gemini errors to retryable OpenAI exceptions
                # Import exceptions from utils_openai_error to use fallback versions
                # that don't require 'request' argument (unlike OpenAI 2.x real exceptions)
                from utils_openai_error import APIError, RateLimitError, APIConnectionError
                
                error_str = str(e).lower()
                error_repr = repr(e)
                
                # Check for 503 Service Unavailable (overloaded model)
                if "503" in error_str or "unavailable" in error_str or "overloaded" in error_str:
                    # Use Exception with message to create APIError-like exception
                    # The fallback APIError from utils_openai_error doesn't require 'request'
                    raise APIError(f"Gemini API error: 503 UNAVAILABLE. {error_repr}")
                
                # Check for rate limit errors (429)
                if "429" in error_str or "rate limit" in error_str or "quota" in error_str:
                    raise RateLimitError(f"Gemini API error: 429 RATE_LIMIT. {error_repr}")
                
                # Check for connection errors
                if "connection" in error_str or "timeout" in error_str or "network" in error_str:
                    raise APIConnectionError(f"Gemini API error: CONNECTION. {error_repr}")
                
                # For other errors, raise as APIError (retryable) if they look like server errors
                # Non-retryable errors (400, 401, 403) will be raised as generic Exception
                if any(code in error_str for code in ["400", "401", "403", "404"]):
                    raise Exception(f"Gemini API error: {error_repr}")
                else:
                    # Server errors (500, 502, 504, etc.) should be retryable
                    raise APIError(f"Gemini API error: {error_repr}")
        
        def retrieve(self, response_id: str) -> Any:
            """Retrieve a response (for Gemini, returns immediately as it's synchronous).
            
            Args:
                response_id: Response ID (ignored for Gemini)
            
            Returns:
                Same response object (Gemini is synchronous)
            """
            if self.parent._last_response:
                return self.parent._last_response
            
            # Create a completed response wrapper
            class CompletedResponse:
                def __init__(self):
                    self.status = "completed"
                    self.id = response_id
                    self.output = []
                    self.usage = None
            
            return CompletedResponse()
    
    @property
    def responses(self):
        """Access responses interface like OpenAI client.responses."""
        return self.Responses(self)


class GeminiResponseWrapper:
    """Wrapper for Gemini response to match OpenAI response structure."""
    
    def __init__(self, gemini_response: Any, response_id: str, prompt: str):
        """Initialize Gemini response wrapper.
        
        Args:
            gemini_response: Original Gemini response object
            response_id: Generated response ID
            prompt: Original prompt (for token counting estimation)
        """
        self._gemini_response = gemini_response
        self.id = response_id
        self.status = "completed"
        self.prompt = prompt
        
        # Extract text from Gemini response
        # Gemini response structure: candidates[0].content.parts[0].text
        self._text = ""
        try:
            # Try direct text attribute first (for compatibility)
            if hasattr(gemini_response, 'text'):
                self._text = gemini_response.text
            # Try candidates structure (standard Gemini format)
            elif hasattr(gemini_response, 'candidates') and isinstance(gemini_response.candidates, list) and len(gemini_response.candidates) > 0:
                candidate = gemini_response.candidates[0]
                if hasattr(candidate, 'content'):
                    content = candidate.content
                    if hasattr(content, 'parts') and isinstance(content.parts, list):
                        for part in content.parts:
                            if hasattr(part, 'text') and isinstance(part.text, str):
                                self._text += part.text
                    elif hasattr(content, 'text'):
                        self._text = content.text
            # Fallback: try content attribute directly
            elif hasattr(gemini_response, 'content'):
                # Handle different response formats
                if isinstance(gemini_response.content, str):
                    self._text = gemini_response.content
                elif isinstance(gemini_response.content, list):
                    for item in gemini_response.content:
                        if hasattr(item, 'text'):
                            self._text += item.text
        except Exception as e:
            logger.warning(f"Failed to extract text from Gemini response: {e}")
            self._text = ""
        
        # Create OpenAI-like output structure
        self.output = [{
            "content": [{"text": self._text}],
            "summary": []
        }]
        
        # Estimate usage (Gemini doesn't provide detailed token counts in basic response)
        # We'll estimate based on prompt and response length
        prompt_tokens = len(prompt.split()) * 1.3  # Rough estimate
        response_tokens = len(self._text.split()) * 1.3  # Rough estimate
        
        class Usage:
            def __init__(self):
                self.input_tokens = int(prompt_tokens)
                self.output_tokens = int(response_tokens)
                self.total_tokens = int(prompt_tokens + response_tokens)
                self.output_tokens_details = None
        
        self.usage = Usage()

def get_openai_client_for_model(model_name: str) -> OpenAI:
    """Get a configured client for a specific model with automatic provider detection.
    
    This function automatically detects the provider (OpenAI, OpenRouter) based on the model name
    and configures the client accordingly with the correct API key and base URL.
    
    For OpenRouter models (including Gemini, Mistral, Llama, etc.), it also sets up the required headers (HTTP-Referer and X-Title).
    
    Args:
        model_name: The model name (e.g., "gpt-5-mini-2025-08-07", "gemini-2.5-flash", "mistral-reasoning-latest")
    
    Returns:
        OpenAI: Configured client with appropriate API key and base URL
        - OpenAI client for OpenAI models
        - OpenAI client with OpenRouter base_url and headers for OpenRouter models (Gemini, Mistral, Llama, etc.)
        
    Raises:
        ValueError: If API key is not found or invalid
    """
    provider = get_provider_for_model(model_name)
    api_key = get_api_key_for_model(model_name)
    
    # For Gemini models, return Gemini wrapper (direct SDK)
    if provider == "gemini":
        api_key = get_api_key_for_model(model_name)
        return GeminiClientWrapper(api_key=api_key, model_name=model_name)
    
    # For OpenRouter models (Mistral, Llama, etc.), use OpenRouter's base URL and headers
    if provider == "router":
        # OpenRouter requires HTTP-Referer and X-Title headers
        # Note: We'll pass these headers in each API call via extra_headers parameter
        # Create client with OpenRouter base URL
        import os
        
        # Create client with OpenRouter base URL
        # Headers will be passed in each API call (see create_and_wait function)
        client = OpenAI(
            api_key=api_key,
            base_url="https://openrouter.ai/api/v1"
        )
        
        # Store headers as attributes for later use in API calls
        http_referer = os.getenv("OPENROUTER_HTTP_REFERER", "https://github.com/research-publi-reverse-engineering")
        x_title = os.getenv("OPENROUTER_X_TITLE", "NetLogo to LUCIM Converter")
        client._openrouter_headers = {
            "HTTP-Referer": http_referer,
            "X-Title": x_title,
        }
        
        return client
    
    # For OpenAI models, use default OpenAI client
    elif provider == "openai":
        return OpenAI(api_key=api_key)
    
    # Fallback: treat as OpenAI (backward compatibility)
    else:
        return OpenAI(api_key=api_key)


def format_prompt_for_responses_api(prompt_text: str) -> str:
    """Format prompt text for OpenAI Responses API.
    
    Args:
        prompt_text: The prompt text as a string
        
    Returns:
        The prompt text directly (as it worked on Oct 9)
    """
    return prompt_text


def normalize_openrouter_model_name(model_name: str) -> str:
    """Normalize OpenRouter model name for LiteLLM compatibility.
    
    When using OpenRouter via LiteLLM with api_base configured, the model name
    should NOT include the 'openrouter/' prefix. OpenRouter expects the format:
    '<provider>/<model>' (e.g., 'mistralai/mistral-small-latest').
    
    This function:
    1. Removes the 'openrouter/' prefix if present
    2. Maps simplified model names (from AVAILABLE_MODELS) to full OpenRouter format
    3. Returns the normalized name in '<provider>/<model>' format
    
    Args:
        model_name: Original model name (e.g., "openrouter/mistralai/mistral-small-latest", 
                   "mistralai/mistral-small-latest", "mistral-medium", or "gemini-2.5-flash")
        
    Returns:
        Normalized model name without 'openrouter/' prefix (e.g., "mistralai/mistral-medium" or "google/gemini-2.5-flash")
    """
    if not model_name:
        return model_name
    
    # Remove 'openrouter/' prefix if present (since we configure api_base for OpenRouter)
    trimmed = model_name.strip()
    if trimmed.startswith("openrouter/"):
        trimmed = trimmed[len("openrouter/"):]
    
    # Map simplified model names (from AVAILABLE_MODELS) to full OpenRouter format
    # This allows using simplified names like "mistral-medium" instead of "mistralai/mistral-medium"
    model_mapping = {
        # Mistral
        "mistral-medium": "mistralai/mistral-medium",
        "mistral-medium-3.1": "mistralai/mistral-medium",
        # Llama
        "llama-3.3-70b-instruct": "meta-llama/llama-3.3-70b-instruct",
        # Gemini (routed through OpenRouter)
        "gemini-2.5-flash": "google/gemini-2.5-flash",
        "gemini-2.5-pro": "google/gemini-2.5-pro",
    }
    
    # If the model name is in our simplified format, map it to the full OpenRouter format
    if trimmed in model_mapping:
        return model_mapping[trimmed]
    
    # If it already contains a '/', assume it's already in the correct format
    if '/' in trimmed:
        return trimmed
    
    # Fallback: return as-is (might be a model name we don't recognize)
    return trimmed


def create_and_wait(
    client: "OpenAI",
    api_config: Dict[str, Any],
    poll_interval_seconds: float = 1.0,
    timeout_seconds: Optional[float] = None,
) -> Any:
    """Create a model response using SDKs for OpenAI, Gemini, and OpenRouter for others.

    Routing policy:
    - OpenAI models (gpt-*, gpt-5*): OpenAI Responses API (SDK)
    - Gemini: Google SDK via GeminiClientWrapper (OpenAI-like interface)
    - All others (e.g., Mistral, Llama): OpenRouter via LiteLLM
    """
    # Build messages from api_config (instructions + first input content)
    model_name = (api_config.get("model") or "").strip()
    system_text = api_config.get("instructions", "") or ""
    user_text = ""
    input_payload = api_config.get("input")
    if isinstance(input_payload, list) and len(input_payload) > 0:
        first = input_payload[0]
        if isinstance(first, dict):
            cnt = first.get("content", "")
            if isinstance(cnt, str):
                user_text = cnt
            elif isinstance(cnt, list):
                for item in cnt:
                    if isinstance(item, dict) and "text" in item and isinstance(item["text"], str):
                        user_text = item["text"]
                        break
    if not user_text:
        user_text = system_text

    messages = []
    if system_text:
        messages.append({"role": "system", "content": system_text})
    messages.append({"role": "user", "content": user_text})

    # Decide provider
    provider = get_provider_for_model(model_name)

    # 1) OpenAI → Responses API (SDK)
    if provider == "openai":
        # Ensure we have a proper OpenAI client
        if not hasattr(client, 'responses'):
            client = get_openai_client()
        # Log request payload
        _log_responses_api_params(api_config)
        # Create and poll until completion
        response = with_retries(lambda: client.responses.create(**api_config))
        start_time = time.time()
        while getattr(response, "status", None) not in ("completed", "failed", "cancelled"):
            if timeout_seconds and (time.time() - start_time) > timeout_seconds:
                raise TimeoutError(f"Response timed out after {timeout_seconds} seconds")
            time.sleep(poll_interval_seconds)
            response = client.responses.retrieve(response.id)
        if getattr(response, "status", None) != "completed":
            raise RuntimeError(f"OpenAI response ended with status: {getattr(response, 'status', None)}")
        return response
    
    # 1.b) Gemini → direct Google SDK via GeminiClientWrapper (OpenAI-like interface)
    if provider == "gemini":
        # Ensure we have a Gemini wrapper client bound to the model
        if not hasattr(client, 'responses') or client.__class__.__name__ != "GeminiClientWrapper":
            client = get_openai_client_for_model(model_name)
        _log_responses_api_params(api_config)
        response = with_retries(lambda: client.responses.create(**api_config))
        start_time = time.time()
        while getattr(response, "status", None) not in ("completed", "failed", "cancelled"):
            if timeout_seconds and (time.time() - start_time) > timeout_seconds:
                raise TimeoutError(f"Response timed out after {timeout_seconds} seconds")
            time.sleep(poll_interval_seconds)
            response = client.responses.retrieve(getattr(response, "id", ""))
        if getattr(response, "status", None) != "completed":
            raise RuntimeError(f"Gemini response ended with status: {getattr(response, 'status', None)}")
        return response

    # 2) OpenRouter models (Mistral, Llama, etc.) → OpenRouter via LiteLLM
    # Relax parameter strictness to avoid provider-specific UnsupportedParamsError
    litellm.drop_params = True

    # Normalize OpenRouter model name for LiteLLM compatibility
    # When api_base is configured for OpenRouter, the model name should be '<provider>/<model>'
    # (e.g., 'mistralai/mistral-small-latest') without the 'openrouter/' prefix
    normalized_model_name = normalize_openrouter_model_name(model_name)
    # LiteLLM prefers explicit OpenRouter provider prefix
    if not normalized_model_name.startswith("openrouter/"):
        normalized_model_name = f"openrouter/{normalized_model_name}"

    litellm_kwargs: Dict[str, Any] = {
        "model": normalized_model_name,
        "messages": messages,
    }

    if "temperature" in api_config and api_config.get("temperature") is not None:
        litellm_kwargs["temperature"] = api_config.get("temperature")
    if "max_tokens" in api_config and api_config.get("max_tokens") is not None:
        litellm_kwargs["max_tokens"] = api_config.get("max_tokens")

    # OpenRouter credentials
    if isinstance(model_name, str):
        # Use get_api_key_for_model to handle all OpenRouter API key variants
        api_key = get_api_key_for_model(model_name)
        if not api_key or not str(api_key).strip():
            raise ValueError("OpenRouter API key is required and must not be empty for OpenRouter models. Please set ROUTER_API_KEY, ROUTER_KEY, ROUTER, or OPENROUTER_API_KEY in your .env file.")
        litellm_kwargs["api_key"] = api_key
        litellm_kwargs["api_base"] = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
        # Required OpenRouter headers
        # Note: OpenRouter expects "HTTP-Referer" (not "Referer") and "X-Title" headers
        http_referer = os.getenv("OPENROUTER_HTTP_REFERER", "https://github.com/research-publi-reverse-engineering")
        x_title = os.getenv("OPENROUTER_X_TITLE", "NetLogo to LUCIM Converter")
        litellm_kwargs["headers"] = {
            "HTTP-Referer": http_referer,
            "X-Title": x_title,
        }

    _log_completion_params(api_config, litellm_kwargs)
    
    # Log OpenRouter-specific request details
    logger.info("=" * 80)
    logger.info("OPENROUTER API REQUEST - DETAILED PARAMETERS:")
    logger.info(f"  Original model name: {model_name}")
    logger.info(f"  Normalized model name: {normalized_model_name}")
    logger.info(f"  API Base URL: {litellm_kwargs.get('api_base', 'N/A')}")
    logger.info(f"  Headers: {json.dumps(litellm_kwargs.get('headers', {}), indent=2)}")
    logger.info(f"  Messages count: {len(messages)}")
    logger.info(f"  Temperature: {litellm_kwargs.get('temperature', 'N/A')}")
    logger.info(f"  Max tokens: {litellm_kwargs.get('max_tokens', 'N/A')}")
    logger.info("=" * 80)
    
    # Execute OpenRouter call with detailed error logging
    try:
        response = with_retries(lambda: litellm_completion(**litellm_kwargs))
        # Log successful response details
        _log_openrouter_response(response)
        return response
    except Exception as e:
        # Log detailed error information
        _log_openrouter_response(None, error=e)
        raise


# Streaming helpers were removed as the project no longer persists streaming artifacts.


def get_output_text(response: Any) -> str:
    """Extract plain text output from LiteLLM/OpenAI-style chat completion.
    
    Args:
        response: LiteLLM completion response object
    
    Returns:
        Plain text content from the response
    """
    try:
        if hasattr(response, 'choices') and isinstance(response.choices, list) and response.choices:
            first_choice = response.choices[0]
            # dict-like
            if isinstance(first_choice, dict):
                msg = first_choice.get('message', {})
                if isinstance(msg, dict):
                    content_val = msg.get('content')
                    if isinstance(content_val, str):
                        return content_val
            # object-like
            msg_obj = getattr(first_choice, 'message', None)
            if msg_obj is not None:
                content_val = getattr(msg_obj, 'content', None)
                if isinstance(content_val, str):
                    return content_val
        
        text_attr = getattr(response, 'output_text', None)
        if isinstance(text_attr, str) and text_attr:
            return text_attr

        # Traverse Responses-style structured output (and Gemini wrapper)
        output = getattr(response, 'output', None)
        if isinstance(output, list):
            text_chunks: list[str] = []
            for item in output:
                content = item.get('content') if isinstance(item, dict) else getattr(item, 'content', None)
                if isinstance(content, list):
                    for part in content:
                        # Accept typed and untyped parts carrying 'text'
                        if isinstance(part, dict):
                            part_type = part.get('type')
                            if part_type in ("output_text", "text") and isinstance(part.get('text'), str):
                                text_chunks.append(part['text'])
                            elif 'text' in part and isinstance(part['text'], str):
                                text_chunks.append(part['text'])
                        else:
                            part_type = getattr(part, 'type', None)
                            val = getattr(part, 'text', None)
                            if (part_type in ("output_text", "text") and isinstance(val, str)):
                                text_chunks.append(val)
                elif isinstance(content, str):
                    text_chunks.append(content)
            if text_chunks:
                return "".join(text_chunks).strip()

        return ""
    except (AttributeError, IndexError, KeyError, TypeError):
        return ""


def get_reasoning_summary(response: Any) -> str:
    """Extract reasoning summary from API response (OpenAI, Gemini, or OpenRouter).
    
    Args:
        response: API response object (OpenAI Responses API, Gemini wrapper, or legacy OpenAI)
    
    Returns:
        Reasoning summary text if available, empty string otherwise
        Note: Gemini models don't provide reasoning summaries, so returns empty string
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


def build_error_raw_payload(exc: Exception) -> Dict[str, Any]:
    """Return a structured error payload suitable for output-raw_response.json.

    Attempts to capture HTTP status/body when present, otherwise includes
    exception type and message for faster diagnostics.
    """
    payload: Dict[str, Any] = {
        "error_type": type(exc).__name__,
        "message": str(exc),
    }
    # Best-effort extraction of HTTP info
    try:
        status = getattr(exc, "status_code", None) or getattr(exc, "status", None)
        if status is not None:
            payload["http_status"] = int(status) if isinstance(status, (int,)) else status
        resp = getattr(exc, "response", None)
        if resp is not None:
            # Some clients expose .text or .content, others .json()
            body_text = getattr(resp, "text", None)
            if body_text:
                payload["http_body"] = body_text
            else:
                try:
                    payload["http_body_json"] = resp.json()
                except Exception:
                    pass
    except Exception:
        # Ignore extraction errors; keep minimal payload
        pass
    return payload

def get_usage_tokens(response: Any, exact_input_tokens: Optional[int] = None) -> Dict[str, int]:
    """Return usage tokens as a dict using the canonical OpenAI 2.x schema.
    
    Supports OpenAI, Gemini, and OpenRouter responses.

    Canonical fields (prefer exact API fields when present):
    - input_tokens: response.usage.input_tokens
    - output_tokens: response.usage.output_tokens  ← standardized source of truth
    - total_tokens: response.usage.total_tokens
    - reasoning_tokens: response.usage.output_tokens_details.reasoning_tokens

    Fallbacks (conservative):
    - If input_tokens is missing but an exact_input_tokens value is provided by caller,
      use exact_input_tokens and infer output_tokens = max(total_tokens - input_tokens, 0).
    - reasoning_tokens defaults to 0 when output_tokens_details is missing.
    - For Gemini: uses estimated tokens from GeminiResponseWrapper
    """
    tokens_used = 0
    input_tokens = 0
    output_tokens = 0
    reasoning_tokens = 0

    usage = getattr(response, "usage", None)
    if usage is None:
        # No usage info available
        return {
            "total_tokens": tokens_used,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "reasoning_tokens": reasoning_tokens,
        }

    # Canonical fields (works for OpenAI, OpenRouter, and Gemini wrapper)
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
    """Minimal check: ensure an API key is present in environment or .env."""
    try:
        _ = get_openai_api_key()
        return True
    except Exception:
        return False


def validate_model_name_and_connectivity(model_name: str, verbose: bool = True) -> tuple[bool, str, str]:
    """Preflight check for model/provider usability with a minimal call.

    Args:
        model_name: Target model name (e.g., "gpt-5-mini-2025-08-07", "gemini-2.5-flash", "llama-3.3-70b-instruct")
        verbose: Print compact diagnostics when True

    Returns:
        (ok, provider, message)
    """
    from utils_api_key import get_api_key_for_model, get_provider_for_model

    provider = get_provider_for_model(model_name)
    diag_prefix = f"[{provider}] {model_name}: "

    # Check API key
    try:
        api_key = get_api_key_for_model(model_name)
    except Exception as e:
        msg = f"API key error: {e}"
        if verbose:
            print(diag_prefix + msg)
        return False, provider, msg

    try:
        if provider == "openai":
            client = OpenAI(api_key=api_key)
            # Use current OpenAI Responses schema: content type must be 'input_text'
            payload = {
                "model": model_name,
                "input": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "input_text", "text": "ping"}
                        ],
                    }
                ],
                "max_output_tokens": 1,
            }
            _log_responses_api_params(payload)
            _ = client.responses.create(**payload)
            if verbose:
                print(diag_prefix + "OK")
            return True, provider, "OK"

        # OpenRouter via LiteLLM (includes Gemini, Mistral, Llama, etc.)
        litellm.drop_params = True
        normalized = normalize_openrouter_model_name(model_name)
        # LiteLLM expects explicit provider for OpenRouter; prefix the model
        litellm_model = (
            normalized if normalized.startswith("openrouter/") else f"openrouter/{normalized}"
        )
        kwargs = {
            "model": litellm_model,
            "messages": [
                {"role": "system", "content": "preflight"},
                {"role": "user", "content": "ping"},
            ],
            "api_key": api_key,
            "api_base": os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
            "headers": {
                "HTTP-Referer": os.getenv("OPENROUTER_HTTP_REFERER", "https://github.com/research-publi-reverse-engineering"),
                "X-Title": os.getenv("OPENROUTER_X_TITLE", "NetLogo to LUCIM Converter"),
            },
            "max_tokens": 1,
        }
        try:
            _ = litellm_completion(**kwargs)
            if verbose:
                print(diag_prefix + "OK")
            return True, provider, "OK"
        except Exception as e:
            # If model id invalid, hint the normalized suggestion we used
            err_type = type(e).__name__
            msg = f"{err_type}: {str(e)[:200]} | tried model='{litellm_model}'"
            if verbose:
                print(diag_prefix + msg)
            return False, provider, msg

    except Exception as e:
        err_type = type(e).__name__
        msg = f"{err_type}: {str(e)[:200]}"
        if verbose:
            print(diag_prefix + msg)
        return False, provider, msg


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
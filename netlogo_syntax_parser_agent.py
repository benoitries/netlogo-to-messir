#!/usr/bin/env python3
"""
NetLogo AST Agent using OpenAI models
Parses NetLogo source code into structured AST using OpenAI models.
"""

import os
import json
import datetime
import pathlib
import tiktoken
from typing import Dict, Any
from google.adk.agents import LlmAgent
from openai import OpenAI

from config import (
    PERSONA_SYNTAX_PARSER, OUTPUT_DIR, 
    AGENT_VERSION_SYNTAX_PARSER, get_reasoning_config, get_reasoning_suffix,
    validate_agent_response
)

# Configuration
PERSONA_FILE = PERSONA_SYNTAX_PARSER
WRITE_FILES = True

# Load persona
persona = PERSONA_FILE.read_text(encoding="utf-8")

# Get agent version from config
AGENT_VERSION = AGENT_VERSION_SYNTAX_PARSER

def sanitize_model_name(model_name: str) -> str:
    """Sanitize model name by replacing hyphens with underscores for valid identifier."""
    return model_name.replace("-", "_")

class NetLogoSyntaxParserAgent(LlmAgent):
    model: str = "gpt-5"
    timestamp: str = ""
    name: str = "NetLogo Syntax Parser"
    max_tokens: int = 16000
    client: OpenAI = None
    reasoning_effort: str = "low"
    reasoning_summary: str = "auto"
    
    def __init__(self, model_name: str = "gpt-5", external_timestamp: str = None, max_tokens: int = 16000):
        sanitized_name = sanitize_model_name(model_name)
        super().__init__(
            name=f"netlogo_ast_agent_{sanitized_name}",
            description="AST-based agent for parsing NetLogo code structure"
        )
        self.model = model_name
        # Pydantic will handle max_tokens field assignment automatically
        # Use external timestamp if provided, otherwise generate new one
        if external_timestamp:
            self.timestamp = external_timestamp
        else:
            # Format: YYYYMMDD_HHMM for better readability
            self.timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M")
        
        # Configure OpenAI client
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise SystemExit("ERROR: OPENAI_API_KEY environment variable required")
        self.client = OpenAI(api_key=api_key)
    
    def update_reasoning_config(self, reasoning_effort: str, reasoning_summary: str):
        """
        Update reasoning configuration for this agent.
        
        Args:
            reasoning_effort: "low", "medium", or "high"
            reasoning_summary: "auto" or "manual"
        """
        self.reasoning_effort = reasoning_effort
        self.reasoning_summary = reasoning_summary
    
    def count_input_tokens(self, instructions: str, input_text: str) -> int:
        """
        Count input tokens exactly using tiktoken for the given model.
        
        Args:
            instructions: The persona/instructions text
            input_text: The actual input text (filename + code)
            
        Returns:
            Exact token count for the input
        """
        try:
            # Get the appropriate encoding for the model
            if "gpt-4" in self.model or "gpt-3.5" in self.model:
                encoding = tiktoken.encoding_for_model(self.model)
            else:
                # For other models, use cl100k_base which is used by GPT-4 and GPT-3.5
                encoding = tiktoken.get_encoding("cl100k_base")
            
            # Combine instructions and input text (this is what gets sent to the model)
            full_input = f"{instructions}\n\n{input_text}"
            
            # Count tokens
            token_count = len(encoding.encode(full_input))
            return token_count
            
        except Exception as e:
            print(f"[WARNING] Failed to count input tokens with tiktoken: {e}")
            # Fallback to character-based estimation
            full_input = f"{instructions}\n\n{input_text}"
            estimated_tokens = len(full_input) // 4  # Rough estimate: 4 chars per token
            return estimated_tokens
        
    def parse_netlogo_code(self, code: str, filename: str = "input.nlogo") -> Dict[str, Any]:
        instructions = f"{persona}"
        
        input_text = f"""
Filename: {filename}
Code:
```
{code}
```
"""
        
        # Count input tokens exactly
        exact_input_tokens = self.count_input_tokens(instructions, input_text)
        
        try:
            # Use the configured max_tokens value
            max_completion_tokens = self.max_tokens
            
            # Create response using OpenAI Responses API
            api_config = get_reasoning_config("syntax_parser")
            # Update reasoning configuration with agent's settings
            if "reasoning" in api_config:
                api_config["reasoning"]["effort"] = self.reasoning_effort
                api_config["reasoning"]["summary"] = self.reasoning_summary
            api_config.update({
                "instructions": instructions,
                "input": input_text
            })
            
            response = self.client.responses.create(**api_config)
            
            # Poll for completion
            while response.status not in ("completed", "failed", "cancelled"):
                import time
                time.sleep(1)
                response = self.client.responses.retrieve(response.id)
            
            if response.status != "completed":
                return {
                    "reasoning_summary": f"Response failed with status: {response.status}",
                    "data": None,
                    "errors": [f"Response failed with status: {response.status}"],
                    "tokens_used": 0,
                    "input_tokens": 0,
                    "output_tokens": 0
                }
            
            # Extract content from response - use the correct path
            content = ""
            reasoning_summary = ""
            
            if response.output:
                if len(response.output) > 1:
                    # Model supports reasoning: reasoning is in first output item, content in second
                    reasoning_item = response.output[0]
                    if hasattr(reasoning_item, 'summary') and reasoning_item.summary:
                        for summary_item in reasoning_item.summary:
                            if hasattr(summary_item, 'text'):
                                reasoning_summary += summary_item.text + "\n"
                    
                    # The actual content is in the second output item (index 1)
                    message_item = response.output[1]
                    if hasattr(message_item, 'content') and message_item.content:
                        content_item = message_item.content[0]
                        if hasattr(content_item, 'text'):
                            content = content_item.text
                else:
                    # Fallback: content is in the first (and only) output item
                    message_item = response.output[0]
                    if hasattr(message_item, 'content') and message_item.content:
                        content_item = message_item.content[0]
                        if hasattr(content_item, 'text'):
                            content = content_item.text
                    
                    # Set a default reasoning summary for unexpected response structure
                    reasoning_summary = "Unexpected response structure - no reasoning summary available."
            
            # Check if response is empty
            if not content or content.strip() == "":
                return {
                    "reasoning_summary": "Received empty response from API",
                    "data": None,
                    "errors": ["Empty response from API - this may indicate a model issue or token limit problem"],
                    "tokens_used": 0,
                    "input_tokens": 0,
                    "output_tokens": 0
                }
            
            # Parse JSON response
            try:
                # Debug: Log the raw response for troubleshooting
                # Note: These debug prints are kept as they provide useful debugging information
                print(f"[DEBUG] Raw response length: {len(content)}")
                print(f"[DEBUG] Raw response preview: {content[:500]}...")
                
                # Clean up the content
                content_clean = content.strip()
                if content_clean.startswith("```json"):
                    content_clean = content_clean.replace("```json", "").replace("```", "").strip()
                elif content_clean.startswith("```"):
                    content_clean = content_clean.replace("```", "").strip()
                
                # Parse the response as JSON
                response_data = json.loads(content_clean)
                print(f"[DEBUG] Successfully parsed response as JSON")
                
                # Extract and normalize fields from JSON response.
                # Always save under 'data': if no 'data' key present, wrap top-level object.
                ast = {}
                if isinstance(response_data, dict):
                    if "data" in response_data and isinstance(response_data["data"], dict):
                        ast = response_data["data"]
                    else:
                        ast = response_data
                errors = response_data.get("errors", []) if isinstance(response_data, dict) else []

                # Extract token usage from response
                tokens_used = 0
                input_tokens = 0
                output_tokens = 0
                reasoning_tokens = 0
                
                # Get token usage from OpenAI Responses API
                usage_dict = None
                if hasattr(response, 'usage') and response.usage:
                    tokens_used = getattr(response.usage, 'total_tokens', 0)
                    api_input_tokens = getattr(response.usage, 'input_tokens', 0)
                    api_output_tokens = getattr(response.usage, 'output_tokens', 0)
                    # Try to read reasoning tokens from output_tokens_details if available
                    reasoning_details = getattr(response.usage, 'output_tokens_details', None)
                    if reasoning_details is not None:
                        reasoning_tokens = getattr(reasoning_details, 'reasoning_tokens', 0)
                    else:
                        reasoning_tokens = getattr(response.usage, 'reasoning_tokens', 0)
                    
                    # Use exact input token count only if API doesn't provide it
                    if api_input_tokens and api_input_tokens > 0:
                        input_tokens = api_input_tokens
                        output_tokens = api_output_tokens
                    else:
                        input_tokens = exact_input_tokens
                        output_tokens = tokens_used - exact_input_tokens if tokens_used > exact_input_tokens else 0
                    
                    usage_dict = {
                        "total_tokens": tokens_used,
                        "input_tokens": input_tokens,
                        "output_tokens": output_tokens,
                        "reasoning_tokens": reasoning_tokens
                    }
                    # Debug: Print usage details
                    print(f"# Usage details")
                    print(f"response.usage: {response.usage}")
                    print(f"Exact input tokens: {exact_input_tokens}")
                    print(f"API input tokens: {api_input_tokens}")
                    print(f"Final input tokens: {input_tokens}")
                    print(f"Output tokens: {output_tokens}")
                    print(f"Total tokens: {tokens_used}")
                else:
                    print(f"[WARNING] No usage data available in response")

                return {
                    "reasoning_summary": reasoning_summary,
                    "data": ast,
                    "errors": [],
                    "tokens_used": tokens_used,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "raw_usage": usage_dict,
                    "reasoning_tokens": reasoning_tokens
                }
            except json.JSONDecodeError as e:
                return {
                    "reasoning_summary": reasoning_summary,
                    "data": None,
                    "errors": [f"Failed to parse AST JSON: {e}", f"Raw response: {content[:200]}..."],
                    "tokens_used": 0,
                    "input_tokens": 0,
                    "output_tokens": 0
                }
                
        except Exception as e:
            return {
                "reasoning_summary": f"Error during model inference: {e}",
                "data": None,
                "errors": [f"Model inference error: {e}", f"Model used: {self.model}", f"Token limit: {max_completion_tokens}"],
                "tokens_used": 0,
                "input_tokens": 0,
                "output_tokens": 0
            }
    

    
    def save_results(self, results: Dict[str, Any], base_name: str, model_name: str, step_number = None):
        """Save parsing results to a single JSON file."""
        if not WRITE_FILES:
            return
            
        # New format: base-name_timestamp_AI-model_step_agent-name_version_reasoning-suffix_rest
        agent_name = "syntax_parser"
        # Use the agent's current reasoning level instead of global config
        reasoning_suffix = f"reasoning-{self.reasoning_effort}-{self.reasoning_summary}"
        
        if step_number is not None:
            prefix = f"{base_name}_{self.timestamp}_{model_name}_{step_number}_{agent_name}_{AGENT_VERSION}_{reasoning_suffix}_"
        else:
            prefix = f"{base_name}_{self.timestamp}_{model_name}_{agent_name}_{AGENT_VERSION}_{reasoning_suffix}_"
        
        # Save complete response as single JSON file
        json_file = OUTPUT_DIR / f"{prefix}response.json"
        
        # Create complete response structure
        complete_response = {
            "agent_type": "syntax_parser",
            "model": self.model,
            "timestamp": self.timestamp,
            "base_name": base_name,
            "step_number": step_number,
            "reasoning_summary": results.get("reasoning_summary", "").replace("\\n", "\n"),
            "data": results.get("data", ""),
            "errors": results.get("errors", []),
            "tokens_used": results.get("tokens_used", 0),
            "input_tokens": results.get("input_tokens", 0),
            "output_tokens": results.get("output_tokens", 0),
            "reasoning_tokens": results.get("reasoning_tokens", 0)
        }
        
        # Validate response before saving
        validation_errors = validate_agent_response("syntax_parser", complete_response)
        if validation_errors:
            print(f"[WARNING] Validation errors in syntax parser response: {validation_errors}")
        
        # Save complete response as JSON file
        json_file.write_text(json.dumps(complete_response, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"OK: {base_name} -> {prefix}response.json")
        
        # Save reasoning summary as markdown file
        reasoning_file = OUTPUT_DIR / f"{prefix}reasoning.md"
        reasoning_content = f"""# Reasoning Summary - {agent_name.title().replace('_', ' ')}

**Base Name:** {base_name}
**Model:** {self.model}
**Timestamp:** {self.timestamp}
**Step Number:** {step_number if step_number else 'N/A'}
**Reasoning Level:** {self.reasoning_effort}
**Reasoning Summary:** {self.reasoning_summary}

## Token Usage

- **Total Tokens:** {results.get("tokens_used", 0):,}
- **Input Tokens:** {results.get("input_tokens", 0):,}
- **Output Tokens:** {results.get("output_tokens", 0):,}
 - **Reasoning Tokens:** {results.get("reasoning_tokens", 0):,}

## Reasoning Summary

{results.get("reasoning_summary", "No reasoning summary available")}

## Errors

{chr(10).join(f"- {error}" for error in results.get("errors", [])) if results.get("errors") else "No errors"}
"""
        reasoning_file.write_text(reasoning_content, encoding="utf-8")
        print(f"OK: {base_name} -> {prefix}reasoning.md")
        
        # Save data field as separate file
        data_file = OUTPUT_DIR / f"{prefix}data.json"
        if results.get("data"):
            data_file.write_text(json.dumps(results["data"], indent=2, ensure_ascii=False), encoding="utf-8")
            print(f"OK: {base_name} -> {prefix}data.json")
        else:
            print(f"WARNING: No data to save for {base_name}")


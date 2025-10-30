#!/usr/bin/env python3
"""
NetLogo Interface Image Analyzer using OpenAI models
Analyzes NetLogo interface images to extract widget information and produce structured JSON output.
"""

import os
import json
import datetime
import pathlib
import tiktoken
import base64
from typing import Dict, Any, List, Optional
from utils_config_constants import (
    OUTPUT_DIR, 
    get_reasoning_config, validate_agent_response, DEFAULT_MODEL
)

from google.adk.agents import LlmAgent
from openai import OpenAI
from utils_openai_client import create_and_wait, get_output_text, get_reasoning_summary, get_usage_tokens, format_prompt_for_responses_api
from utils_response_dump import serialize_response_to_dict, verify_exact_keys, write_minimal_artifacts, write_input_instructions_before_api, write_all_output_files
from utils_config_constants import expected_keys_for_agent
from utils_logging import write_reasoning_md_from_payload
from utils_task_loader import load_task_instruction

# Configuration
WRITE_FILES = True

# Widget types allowed in output
ALLOWED_WIDGET_TYPES = {
    "Button", "Slider", "Switch", "Chooser", "Input", 
    "Monitor", "Plot", "Output", "Note"
}

def sanitize_model_name(model_name: str) -> str:
    """Sanitize model name by replacing hyphens with underscores for valid identifier."""
    return model_name.replace("-", "_")

class NetLogoInterfaceImageAnalyzerAgent(LlmAgent):
    model: str = DEFAULT_MODEL
    timestamp: str = ""
    name: str = "NetLogo Interface Image Analyzer"
    
    client: OpenAI = None
    reasoning_effort: str = "medium"
    reasoning_summary: str = "auto"
    text_verbosity: str = "medium"
    # Persona path and content
    persona_path: Optional[str] = None
    persona_text: str = ""
    
    def __init__(self, model_name: str = DEFAULT_MODEL, external_timestamp: str = None):
        sanitized_name = sanitize_model_name(model_name)
        super().__init__(
            name=f"netlogo_interface_image_analyzer_agent_{sanitized_name}",
            description="Interface image analyzer extracting widget information from NetLogo UI screenshots"
        )
        self.model = model_name
        
        # Use external timestamp if provided, otherwise generate new one
        if external_timestamp:
            self.timestamp = external_timestamp
        else:
            # Format: YYYYMMDD_HHMM for better readability
            self.timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M")
        
        # Configure OpenAI client (assumes key already validated by orchestrator)
        from utils_config_constants import OPENAI_API_KEY
        self.client = OpenAI(api_key=OPENAI_API_KEY)
    
    def update_reasoning_config(self, reasoning_effort: str, reasoning_summary: str):
        """
        Update reasoning configuration for this agent.
        
        Args:
            reasoning_effort: "low", "medium", or "high"
            reasoning_summary: "auto" or "manual"
        """
        self.reasoning_effort = reasoning_effort
        self.reasoning_summary = reasoning_summary
    
    def update_text_config(self, text_verbosity: str):
        """Update text verbosity configuration for this agent."""
        self.text_verbosity = text_verbosity

    def apply_config(self, config: Dict[str, Any]) -> None:
        """Apply a unified configuration bundle to this agent.

        Supported keys (optional): "reasoning_effort", "reasoning_summary", "text_verbosity".
        Unknown keys are ignored.
        """
        if not isinstance(config, dict):
            return
        for key in ("reasoning_effort", "reasoning_summary", "text_verbosity"):
            value = config.get(key)
            if value is not None:
                setattr(self, key, value)

    def update_persona_path(self, persona_path: Optional[str]) -> None:
        """Update the persona file path and reload its content."""
        if not persona_path:
            return
        self.persona_path = persona_path
        try:
            self.persona_text = pathlib.Path(persona_path).read_text(encoding="utf-8")
        except Exception as e:
            print(f"[WARNING] Failed to load persona file: {persona_path} ({e})")
            self.persona_text = ""

    def analyze_interface_images(self, ui_image_paths: List[str], output_dir: str = None) -> Dict[str, Any]:
        """
        Analyze NetLogo interface images to extract widget information.
        
        Args:
            ui_image_paths: List of image file paths (initial and simulation interfaces)
            output_dir: Output directory (per-agent if provided)
            
        Returns:
            Dictionary with analysis results and metadata
        """
        # Resolve base output directory (per-agent if provided)
        if output_dir is None:
            output_dir = OUTPUT_DIR
        
        # Load task instruction
        task_instruction = load_task_instruction(2, "interface_image_analyzer")
        
        # Build canonical instruction blocks (task → persona → specific guidance)
        rules_block_sections: List[str] = []
        if task_instruction:
            rules_block_sections.append(task_instruction)
        if self.persona_text:
            rules_block_sections.append(self.persona_text)
        # Note: Do not add additional guidance blocks to keep the prompt minimal
        instructions = "\n\n".join(rules_block_sections).rstrip()

        # Build tagged input text
        ui_entries: List[str] = []
        for p in ui_image_paths[:2]:
            try:
                pp = pathlib.Path(p)
                size_info = f"{pp.stat().st_size} bytes" if pp.exists() else "not found"
                ui_entries.append(f"- {pp.name} — abs: {pp.resolve()} — size: {size_info}")
            except Exception:
                ui_entries.append(f"- {p} — abs: (unresolved) — size: (unknown)")
        ui_images_text = "\n".join(ui_entries) if ui_entries else "- (none provided)"

        input_text = f"""
<NETLOGO-INTERFACE-IMAGES>
{ui_images_text}
</NETLOGO-INTERFACE-IMAGES>
""".rstrip()

        # Create single system_prompt variable for both API call and file generation
        system_prompt = f"{instructions}\n\n{input_text}"

        # Write input-instructions.md BEFORE API call for debugging
        if WRITE_FILES:
            write_input_instructions_before_api(output_dir, system_prompt)
        
        # Load and encode images for API
        encoded_images = self._load_and_encode_images(ui_image_paths)
        
        # Build API input message with images
        user_content = [{"type": "input_text", "text": system_prompt}]
        
        # Add images to the message content
        for img_base64 in encoded_images:
            user_content.append({
                "type": "input_image",
                "image_url": f"data:image/png;base64,{img_base64}"
            })
        
        # Get reasoning configuration (by agent name)
        api_config = get_reasoning_config("netlogo_interface_image_analyzer")
        api_config.update({
            "instructions": format_prompt_for_responses_api(system_prompt),
            "input": [{"role": "user", "content": user_content}],
        })
        
        # Make API call
        try:
            response = create_and_wait(self.client, api_config)
            
            # Extract response components
            output_text = get_output_text(response)
            reasoning_summary = get_reasoning_summary(response)
            usage_tokens = get_usage_tokens(response)
            
            # Parse and validate JSON output
            widget_data = self._parse_and_validate_widget_json(output_text)
            
            # Prepare response data
            response_data = {
                "widgets": widget_data,
                "image_paths": ui_image_paths,
                "analysis_timestamp": self.timestamp,
                "model_used": self.model
            }
            
            # Serialize response for artifacts
            serialized_response = serialize_response_to_dict(response)
            
            # Prepare unified results payload for generic writer
            total_output_tokens = max(0, usage_tokens.get("output_tokens", 0) + usage_tokens.get("reasoning_tokens", 0))
            unified_results = {
                "reasoning_summary": reasoning_summary,
                "data": widget_data,
                "errors": [],
                "tokens_used": usage_tokens.get("total_tokens", 0),
                "input_tokens": usage_tokens.get("input_tokens", 0),
                "total_output_tokens": total_output_tokens,
                "reasoning_tokens": usage_tokens.get("reasoning_tokens", 0),
                "raw_usage": usage_tokens,
                "raw_response": serialized_response,
            }
            
            # Write artifacts using generic utility (standard filenames)
            if WRITE_FILES:
                from pathlib import Path as _P
                write_all_output_files(
                    output_dir=_P(output_dir),
                    results=unified_results,
                    agent_type="netlogo_interface_image_analyzer",
                    base_name="input",
                    model=self.model,
                    timestamp=self.timestamp,
                    reasoning_effort=self.reasoning_effort,
                    step_number=2,
                )
            
            return response_data
            
        except Exception as e:
            error_msg = f"Interface image analysis failed: {e}"
            print(f"[ERROR] {error_msg}")
            
            # Write standardized error artifacts
            if WRITE_FILES:
                from pathlib import Path as _P
                error_results = {
                    "reasoning_summary": "Interface image analysis failed",
                    "data": None,
                    "errors": [error_msg],
                    "tokens_used": 0,
                    "input_tokens": 0,
                    "total_output_tokens": 0,
                    "reasoning_tokens": 0,
                    "raw_response": {"error": error_msg},
                }
                write_all_output_files(
                    output_dir=_P(output_dir),
                    results=error_results,
                    agent_type="netlogo_interface_image_analyzer",
                    base_name="input",
                    model=self.model,
                    timestamp=self.timestamp,
                    reasoning_effort=self.reasoning_effort,
                    step_number=2,
                )
            
            return {
                "widgets": [],
                "image_paths": ui_image_paths,
                "error": error_msg,
                "analysis_timestamp": self.timestamp
            }

    def _load_and_encode_images(self, ui_image_paths: List[str]) -> List[str]:
        """Load and base64-encode images from file paths."""
        encoded_images = []
        for image_path in ui_image_paths[:2]:  # Limit to first 2 images
            try:
                img_path = pathlib.Path(image_path)
                if img_path.exists():
                    with open(img_path, "rb") as img_file:
                        encoded_string = base64.b64encode(img_file.read()).decode('utf-8')
                        encoded_images.append(encoded_string)
                        print(f"[INFO] Successfully loaded and encoded image: {img_path.name}")
                else:
                    print(f"[WARNING] Image file not found: {image_path}")
            except Exception as e:
                print(f"[WARNING] Could not read or encode image {image_path}: {e}")
        return encoded_images


    def _parse_and_validate_widget_json(self, output_text: str) -> List[Dict[str, str]]:
        """Parse and validate the widget JSON output."""
        try:
            # Clean output text (remove markdown fences if present)
            cleaned_text = output_text.strip()
            if cleaned_text.startswith("```json"):
                cleaned_text = cleaned_text[7:]
            if cleaned_text.startswith("```"):
                cleaned_text = cleaned_text[3:]
            if cleaned_text.endswith("```"):
                cleaned_text = cleaned_text[:-3]
            cleaned_text = cleaned_text.strip()
            
            # Parse JSON
            widget_data = json.loads(cleaned_text)
            
            # Validate structure
            if not isinstance(widget_data, list):
                raise ValueError("Output must be a JSON array")
            
            # Validate each widget
            validated_widgets = []
            for i, widget in enumerate(widget_data):
                if not isinstance(widget, dict):
                    print(f"[WARNING] Widget {i} is not an object, skipping")
                    continue
                
                # Check required fields
                if not all(field in widget for field in ["type", "name", "description"]):
                    print(f"[WARNING] Widget {i} missing required fields, skipping")
                    continue
                
                # Validate widget type
                widget_type = widget.get("type")
                if widget_type not in ALLOWED_WIDGET_TYPES:
                    print(f"[WARNING] Widget {i} has invalid type '{widget_type}', skipping")
                    continue
                
                # Check non-empty values
                if not all(widget.get(field, "").strip() for field in ["type", "name", "description"]):
                    print(f"[WARNING] Widget {i} has empty required fields, skipping")
                    continue
                
                validated_widgets.append({
                    "type": widget["type"],
                    "name": widget["name"].strip(),
                    "description": widget["description"].strip()
                })
            
            return validated_widgets
            
        except json.JSONDecodeError as e:
            print(f"[ERROR] Failed to parse JSON: {e}")
            return []
        except Exception as e:
            print(f"[ERROR] Widget validation failed: {e}")
            return []


def main():
    """CLI for testing the interface image analyzer."""
    import sys
    
    if len(sys.argv) < 3:
        print("Usage: python agent_2a_netlogo_interface_image_analyzer.py <image1> <image2> [output_dir]")
        sys.exit(1)
    
    image_paths = sys.argv[1:3]
    output_dir = sys.argv[3] if len(sys.argv) > 3 else "output"
    
    # Create agent
    agent = NetLogoInterfaceImageAnalyzerAgent()
    
    # Analyze images
    result = agent.analyze_interface_images(image_paths, output_dir)
    
    print("Analysis complete!")
    print(f"Detected {len(result.get('widgets', []))} widgets")
    if result.get('error'):
        print(f"Error: {result['error']}")
    else:
        print("Widgets:")
        for widget in result.get('widgets', []):
            print(f"  - {widget['type']}: {widget['name']} - {widget['description']}")

if __name__ == "__main__":
    main()

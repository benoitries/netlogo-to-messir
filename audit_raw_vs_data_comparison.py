#!/usr/bin/env python3
"""
Deep audit script to compare output-response-raw.json with output-data.json
across all runs in a directory.

This script identifies if and how output-data.json is modified compared to
the raw_response from the LLM.
"""

import json
import pathlib
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional
from collections import defaultdict
import sys


def load_json_file(filepath: Path) -> Optional[Any]:
    """Load JSON file, return None if file doesn't exist or is invalid."""
    try:
        if not filepath.exists():
            return None
        content = filepath.read_text(encoding='utf-8')
        return json.loads(content)
    except Exception as e:
        print(f"ERROR loading {filepath}: {e}")
        return None


def extract_data_from_raw(raw_response: Any) -> Optional[Any]:
    """Extract the 'data' field from raw_response structure.
    
    Handles multiple response formats:
    - Gemini: _gemini_response.candidates[0].content.parts[0].text (JSON string)
    - OpenAI/OpenRouter: output[1].content[0].text or choices[0].message.content (JSON string)
    - Direct: raw_response['data']
    """
    if raw_response is None:
        return None
    
    if not isinstance(raw_response, dict):
        return None
    
    # 1) Direct data field
    if 'data' in raw_response and not isinstance(raw_response['data'], str):
        return raw_response['data']
    
    # 2) Gemini structure: _gemini_response.candidates[0].content.parts[0].text
    if '_gemini_response' in raw_response:
        gemini_resp = raw_response['_gemini_response']
        if isinstance(gemini_resp, dict) and 'candidates' in gemini_resp:
            candidates = gemini_resp['candidates']
            if isinstance(candidates, list) and len(candidates) > 0:
                candidate = candidates[0]
                if isinstance(candidate, dict) and 'content' in candidate:
                    content = candidate['content']
                    if isinstance(content, dict) and 'parts' in content:
                        parts = content['parts']
                        if isinstance(parts, list) and len(parts) > 0:
                            part = parts[0]
                            if isinstance(part, dict) and 'text' in part:
                                text = part['text']
                                if isinstance(text, str):
                                    return _parse_json_text_for_data(text)
    
    # 3) OpenAI Responses API structure: output[1].content[0].text
    if 'output' in raw_response:
        output = raw_response['output']
        if isinstance(output, list) and len(output) > 1:
            # Usually output[1] is the message (output[0] might be reasoning)
            for output_item in output:
                if isinstance(output_item, dict):
                    content_list = output_item.get('content', [])
                    if isinstance(content_list, list) and len(content_list) > 0:
                        content_item = content_list[0]
                        if isinstance(content_item, dict) and 'text' in content_item:
                            text = content_item['text']
                            if isinstance(text, str):
                                result = _parse_json_text_for_data(text)
                                if result is not None:
                                    return result
    
    # 4) OpenAI ChatCompletion structure: choices[0].message.content
    if 'choices' in raw_response and isinstance(raw_response['choices'], list) and len(raw_response['choices']) > 0:
        choice = raw_response['choices'][0]
        if isinstance(choice, dict) and 'message' in choice:
            message = choice['message']
            if isinstance(message, dict) and 'content' in message:
                content = message['content']
                if isinstance(content, str):
                    result = _parse_json_text_for_data(content)
                    if result is not None:
                        return result
                elif isinstance(content, dict) and 'data' in content:
                    return content['data']
    
    # 5) Check nested structures
    for key in ['response', 'result', 'body']:
        if key in raw_response:
            nested = extract_data_from_raw(raw_response[key])
            if nested is not None:
                return nested
    
    return None


def _parse_json_text_for_data(text: str) -> Optional[Any]:
    """Parse JSON from text string and extract 'data' field."""
    if not isinstance(text, str):
        return None
    
    # Clean up markdown code fences
    text_clean = text.strip()
    if text_clean.startswith("```json"):
        text_clean = text_clean.replace("```json", "").replace("```", "").strip()
    elif text_clean.startswith("```"):
        text_clean = text_clean.replace("```", "").strip()
    
    # Try to parse as JSON
    try:
        parsed = json.loads(text_clean)
        if isinstance(parsed, dict):
            # Return 'data' field if present, otherwise return the whole parsed object
            if 'data' in parsed:
                return parsed['data']
            # If no 'data' field, return the whole object (might be the data itself)
            return parsed
        return parsed
    except (json.JSONDecodeError, ValueError):
        # Not valid JSON, return None
        return None


def deep_compare(obj1: Any, obj2: Any, path: str = "") -> List[str]:
    """Deep comparison of two objects, return list of differences."""
    differences = []
    
    if type(obj1) != type(obj2):
        differences.append(f"{path}: Type mismatch - {type(obj1).__name__} vs {type(obj2).__name__}")
        return differences
    
    if isinstance(obj1, dict):
        all_keys = set(obj1.keys()) | set(obj2.keys())
        for key in all_keys:
            new_path = f"{path}.{key}" if path else key
            if key not in obj1:
                differences.append(f"{new_path}: Missing in raw_response (present in output-data)")
            elif key not in obj2:
                differences.append(f"{new_path}: Missing in output-data (present in raw_response)")
            else:
                differences.extend(deep_compare(obj1[key], obj2[key], new_path))
    elif isinstance(obj1, list):
        len1, len2 = len(obj1), len(obj2)
        if len1 != len2:
            differences.append(f"{path}: Length mismatch - {len1} vs {len2}")
        for i in range(min(len1, len2)):
            differences.extend(deep_compare(obj1[i], obj2[i], f"{path}[{i}]"))
    else:
        if obj1 != obj2:
            differences.append(f"{path}: Value mismatch - {repr(obj1)[:100]} vs {repr(obj2)[:100]}")
    
    return differences


def analyze_file_pair(raw_path: Path, data_path: Path) -> Dict[str, Any]:
    """Analyze a pair of raw_response and output-data files."""
    result = {
        "raw_path": str(raw_path),
        "data_path": str(data_path),
        "raw_exists": raw_path.exists(),
        "data_exists": data_path.exists(),
        "raw_content": None,
        "data_content": None,
        "extracted_data": None,
        "is_identical": False,
        "differences": [],
        "modification_type": "unknown"
    }
    
    if not raw_path.exists():
        result["modification_type"] = "raw_missing"
        return result
    
    if not data_path.exists():
        result["modification_type"] = "data_missing"
        return result
    
    # Load both files
    raw_content = load_json_file(raw_path)
    data_content = load_json_file(data_path)
    
    result["raw_content"] = raw_content
    result["data_content"] = data_content
    
    if raw_content is None or data_content is None:
        result["modification_type"] = "load_error"
        return result
    
    # Extract data from raw_response
    extracted_data = extract_data_from_raw(raw_content)
    result["extracted_data"] = extracted_data
    
    if extracted_data is None:
        result["modification_type"] = "no_data_in_raw"
        return result
    
    # Compare extracted data with output-data
    differences = deep_compare(extracted_data, data_content)
    result["differences"] = differences
    result["is_identical"] = len(differences) == 0
    
    if result["is_identical"]:
        result["modification_type"] = "identical"
    else:
        # Categorize modification type
        if len(differences) > 0:
            result["modification_type"] = "modified"
        else:
            result["modification_type"] = "unknown"
    
    return result


def find_all_pairs(base_dir: Path) -> List[Tuple[Path, Path]]:
    """Find all pairs of output-response-raw.json and output-data.json files."""
    pairs = []
    
    for raw_file in base_dir.rglob("output-response-raw.json"):
        # Find corresponding output-data.json in same directory
        data_file = raw_file.parent / "output-data.json"
        if data_file.exists():
            pairs.append((raw_file, data_file))
    
    return pairs


def generate_summary(analyses: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Generate summary statistics from analyses."""
    summary = {
        "total_pairs": len(analyses),
        "identical": 0,
        "modified": 0,
        "raw_missing": 0,
        "data_missing": 0,
        "load_error": 0,
        "no_data_in_raw": 0,
        "modification_patterns": defaultdict(list),
        "common_differences": defaultdict(int)
    }
    
    for analysis in analyses:
        mod_type = analysis["modification_type"]
        summary[mod_type] = summary.get(mod_type, 0) + 1
        
        if mod_type == "modified":
            # Track modification patterns
            path_parts = Path(analysis["raw_path"]).parts
            # Extract model, stage, iteration, agent type
            model = None
            stage = None
            iteration = None
            agent = None
            
            for part in path_parts:
                if "my-ecosys-" in part:
                    model = part.replace("my-ecosys-", "").split("/")[0]
                elif "_lucim_" in part:
                    stage = part
                elif part.startswith("iter-"):
                    iteration = part
                elif part in ["1-generator", "2-auditor"]:
                    agent = part
            
            pattern_key = f"{model}/{stage}/{iteration}/{agent}"
            summary["modification_patterns"][pattern_key].append(analysis)
            
            # Track common differences
            for diff in analysis["differences"]:
                # Extract the field path
                if ":" in diff:
                    field_path = diff.split(":")[0].strip()
                    summary["common_differences"][field_path] += 1
    
    return summary


def main():
    if len(sys.argv) < 2:
        print("Usage: python audit_raw_vs_data_comparison.py <run_directory>")
        print("Example: python audit_raw_vs_data_comparison.py output/runs/2025-11-06/1726-persona-v3-limited-agents-v3-adk")
        sys.exit(1)
    
    base_dir = Path(sys.argv[1])
    if not base_dir.exists():
        print(f"ERROR: Directory does not exist: {base_dir}")
        sys.exit(1)
    
    print(f"🔍 Scanning directory: {base_dir}")
    print("=" * 80)
    
    # Find all pairs
    pairs = find_all_pairs(base_dir)
    print(f"Found {len(pairs)} file pairs to analyze\n")
    
    if len(pairs) == 0:
        print("No file pairs found. Exiting.")
        return
    
    # Analyze each pair
    analyses = []
    for raw_path, data_path in pairs:
        print(f"Analyzing: {raw_path.relative_to(base_dir)}")
        analysis = analyze_file_pair(raw_path, data_path)
        analyses.append(analysis)
        
        if analysis["modification_type"] == "identical":
            print("  ✅ IDENTICAL")
        elif analysis["modification_type"] == "modified":
            print(f"  ⚠️  MODIFIED ({len(analysis['differences'])} differences)")
        else:
            print(f"  ❌ {analysis['modification_type'].upper()}")
    
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    
    # Generate summary
    summary = generate_summary(analyses)
    
    print(f"\nTotal pairs analyzed: {summary['total_pairs']}")
    print(f"  ✅ Identical: {summary['identical']}")
    print(f"  ⚠️  Modified: {summary['modified']}")
    print(f"  ❌ Raw missing: {summary['raw_missing']}")
    print(f"  ❌ Data missing: {summary['data_missing']}")
    print(f"  ❌ Load error: {summary['load_error']}")
    print(f"  ❌ No data in raw: {summary['no_data_in_raw']}")
    
    # Show detailed differences for modified files
    if summary['modified'] > 0:
        print("\n" + "=" * 80)
        print("DETAILED MODIFICATIONS")
        print("=" * 80)
        
        for analysis in analyses:
            if analysis["modification_type"] == "modified":
                rel_path = Path(analysis["raw_path"]).relative_to(base_dir)
                print(f"\n📄 {rel_path}")
                print(f"   Differences ({len(analysis['differences'])}):")
                for diff in analysis['differences'][:10]:  # Show first 10
                    print(f"     - {diff}")
                if len(analysis['differences']) > 10:
                    print(f"     ... and {len(analysis['differences']) - 10} more")
        
        # Show common difference patterns
        if summary['common_differences']:
            print("\n" + "=" * 80)
            print("COMMON DIFFERENCE PATTERNS")
            print("=" * 80)
            sorted_patterns = sorted(summary['common_differences'].items(), 
                                   key=lambda x: x[1], reverse=True)
            for field_path, count in sorted_patterns[:20]:  # Top 20
                print(f"  {field_path}: {count} occurrences")
    
    # Save detailed report
    report_path = base_dir / "audit_raw_vs_data_report.json"
    report_data = {
        "summary": summary,
        "analyses": analyses
    }
    report_path.write_text(json.dumps(report_data, indent=2, ensure_ascii=False), encoding='utf-8')
    print(f"\n📊 Detailed report saved to: {report_path}")


if __name__ == "__main__":
    main()


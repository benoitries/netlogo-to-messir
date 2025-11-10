#!/usr/bin/env python3
"""
PlantUML Utilities for Post-Processing
Provides functions to clean escape characters from PlantUML diagram files and generate SVG files.
"""

import re
import pathlib
import subprocess
import os
import sys
import urllib.request
import urllib.error
from typing import Optional, List, Tuple


def clean_plantuml_escapes(content: str) -> str:
    """
    Clean escape characters from PlantUML content.
    
    Args:
        content: Raw PlantUML content with potential escape characters
        
    Returns:
        Cleaned PlantUML content with proper syntax
    """
    if not content:
        return content
    
    # Make a copy to avoid modifying the original
    cleaned = content
    
    # 1. Fix escaped quotes in participant declarations
    # Pattern: participant \"name:Type\" -> participant "name:Type"
    cleaned = re.sub(
        r'participant\s+\\"([^"]+)\\"\s+as\s+(\w+)',
        r'participant "\1" as \2',
        cleaned
    )
    
    # 2. Fix escaped quotes in JSON parameters within messages
    # Pattern: {\"key\":\"value\"} -> {"key":"value"}
    # Handle multiple levels of escaping
    cleaned = re.sub(
        r'\\\\\\"([^"]*)\\\\\\"',
        r'"\1"',
        cleaned
    )
    cleaned = re.sub(
        r'\\"([^"]*)\\"',
        r'"\1"',
        cleaned
    )
    
    # Preserve activation color codes (no removal). Colors like #RRGGBB are valid and must be kept.
    
    # 4. Clean any remaining escaped quotes in message parameters
    # Pattern: message(\\"param\\") -> message("param")
    cleaned = re.sub(
        r'\(\\"([^"]*)\\"\)',
        r'("\1")',
        cleaned
    )
    
    # 5. Fix common @enduml typos
    # Pattern: e@enduml -> @enduml (common LLM error)
    cleaned = re.sub(
        r'^e@enduml$',
        r'@enduml',
        cleaned,
        flags=re.MULTILINE
    )
    
    # Pattern: @enduml with extra characters -> @enduml (preserve content before @enduml)
    cleaned = re.sub(
        r'^([^@]*?)@enduml.*$',
        r'\1@enduml',
        cleaned,
        flags=re.MULTILINE
    )
    
    return cleaned


def validate_plantuml_syntax(content: str) -> Tuple[bool, List[str]]:
    """
    Validate PlantUML syntax and return issues found.
    
    Args:
        content: PlantUML content to validate
        
    Returns:
        Tuple of (is_valid, list_of_issues)
    """
    issues = []
    
    if not content:
        return False, ["Empty content"]
    
    # Check for basic PlantUML structure
    if "@startuml" not in content:
        issues.append("Missing @startuml directive")
    
    if "@enduml" not in content:
        issues.append("Missing @enduml directive")
    
    # Check for common @enduml typos
    if "e@enduml" in content:
        issues.append("Found 'e@enduml' instead of '@enduml' - common LLM error")
    
    # Check for @enduml with extra characters
    if re.search(r'^.*@enduml.*$', content, re.MULTILINE) and not re.search(r'^@enduml$', content, re.MULTILINE):
        issues.append("Found @enduml with extra characters - should be just '@enduml'")
    
    # Check for escaped quotes (should be cleaned)
    # Only flag if there are excessive escaped quotes that suggest cleaning issues
    escaped_quote_count = content.count('\\"')
    if escaped_quote_count > 5:  # Allow some escaped quotes but flag excessive amounts
        issues.append(f"Contains {escaped_quote_count} escaped quotes that should be cleaned")
    
    # Do not treat activation color codes as invalid; they are allowed and expected
    
    # Check for basic participant syntax
    participant_lines = [line for line in content.split('\n') if 'participant' in line]
    for line in participant_lines:
        if '\\"' in line:
            issues.append(f"Participant line with escaped quotes: {line.strip()}")
    
    return len(issues) == 0, issues


def clean_plantuml_file(file_path: pathlib.Path) -> Tuple[bool, List[str]]:
    """
    Clean a PlantUML file and return success status and changes made.
    
    Args:
        file_path: Path to the PlantUML file to clean
        
    Returns:
        Tuple of (success, list_of_changes_made)
    """
    try:
        # Read the file
        original_content = file_path.read_text(encoding="utf-8")
        
        # Clean the content
        cleaned_content = clean_plantuml_escapes(original_content)
        
        # Check if changes were made
        changes_made = []
        if original_content != cleaned_content:
            # Write back the cleaned content
            file_path.write_text(cleaned_content, encoding="utf-8")
            
            # Log what changes were made
            if '\\"' in original_content and '\\"' not in cleaned_content:
                changes_made.append("Removed escaped quotes from participant declarations")
                        
            if re.search(r'\\"', original_content):
                changes_made.append("Cleaned escaped quotes in JSON parameters")
        
        return True, changes_made
        
    except Exception as e:
        return False, [f"Error cleaning file: {str(e)}"]


def log_cleaning_operation(file_path: pathlib.Path, changes_made: List[str]) -> None:
    """
    Log the cleaning operation for audit purposes.
    
    Args:
        file_path: Path to the file that was cleaned
        changes_made: List of changes that were made
    """
    if changes_made:
        print(f"🧹 Cleaned PlantUML file: {file_path.name}")
        for change in changes_made:
            print(f"   ✓ {change}")
    else:
        print(f"✅ PlantUML file already clean: {file_path.name}")


def process_plantuml_file(file_path: pathlib.Path) -> bool:
    """
    Complete processing of a PlantUML file: clean and validate.
    
    Args:
        file_path: Path to the PlantUML file to process
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Clean the file
        success, changes_made = clean_plantuml_file(file_path)
        
        if not success:
            print(f"❌ Failed to clean PlantUML file: {file_path}")
            return False
        
        # Log the operation
        log_cleaning_operation(file_path, changes_made)
        
        # Validate the result
        content = file_path.read_text(encoding="utf-8")
        is_valid, issues = validate_plantuml_syntax(content)
        
        if not is_valid:
            print(f"⚠️  PlantUML validation issues in {file_path.name}: {issues}")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ Error processing PlantUML file {file_path}: {str(e)}")
        return False


def main():
    """Main function for testing the utilities."""
    import argparse
    
    parser = argparse.ArgumentParser(description="PlantUML Utilities")
    parser.add_argument("file", help="PlantUML file to clean")
    parser.add_argument("--validate-only", action="store_true", help="Only validate, don't clean")
    
    args = parser.parse_args()
    
    file_path = pathlib.Path(args.file)
    
    if not file_path.exists():
        print(f"❌ File not found: {file_path}")
        return 1
    
    if args.validate_only:
        content = file_path.read_text(encoding="utf-8")
        is_valid, issues = validate_plantuml_syntax(content)
        
        if is_valid:
            print("✅ PlantUML syntax is valid")
        else:
            print("❌ PlantUML syntax issues:")
            for issue in issues:
                print(f"   - {issue}")
        
        return 0 if is_valid else 1
    else:
        success = process_plantuml_file(file_path)
        return 0 if success else 1


# PlantUML JAR configuration for SVG generation
PLANTUML_MAVEN_BASE = "https://repo1.maven.org/maven2/net/sourceforge/plantuml/plantuml"
PLANTUML_VERSION = "1.2024.3"  # Stable version
PLANTUML_JAR_URL = f"{PLANTUML_MAVEN_BASE}/{PLANTUML_VERSION}/plantuml-{PLANTUML_VERSION}.jar"
PLANTUML_ALL_JAR_URL = f"{PLANTUML_MAVEN_BASE}/{PLANTUML_VERSION}/plantuml-{PLANTUML_VERSION}-all.jar"
PLANTUML_JAR_NAME = "plantuml.jar"

# Cache directory for downloaded JAR
CACHE_DIR = pathlib.Path.home() / ".cache" / "plantuml"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
CACHE_JAR_PATH = CACHE_DIR / PLANTUML_JAR_NAME


def _download_plantuml_jar(jar_path: pathlib.Path, use_all_version: bool = True) -> bool:
    """
    Download PlantUML JAR file from Maven Central.
    
    Args:
        jar_path: Path where to save the JAR file
        use_all_version: If True, download "all" version with dependencies
        
    Returns:
        True if download successful, False otherwise
    """
    url = PLANTUML_ALL_JAR_URL if use_all_version else PLANTUML_JAR_URL
    version_type = "all (with dependencies)" if use_all_version else "standard"
    
    try:
        jar_path.parent.mkdir(parents=True, exist_ok=True)
        
        def show_progress(block_num, block_size, total_size):
            if total_size > 0:
                percent = min(100, (block_num * block_size * 100) // total_size)
                sys.stdout.write(f"\rDownloading PlantUML JAR: {percent}%")
                sys.stdout.flush()
        
        urllib.request.urlretrieve(url, jar_path, show_progress)
        sys.stdout.write("\n")
        return True
        
    except urllib.error.HTTPError as e:
        if e.code == 404 and use_all_version:
            return _download_plantuml_jar(jar_path, use_all_version=False)
        return False
    except Exception:
        return False


def _find_plantuml_jar() -> Optional[pathlib.Path]:
    """
    Find or download PlantUML JAR file.
    
    Checks in order:
    1. Environment variable PLANTUML_JAR
    2. Cache directory (~/.cache/plantuml/plantuml.jar)
    3. Download to cache if not found
    
    Returns:
        Path to plantuml.jar if found/available, None otherwise
    """
    # Check environment variable
    env_jar = os.environ.get("PLANTUML_JAR")
    if env_jar:
        env_path = pathlib.Path(env_jar)
        if env_path.exists():
            return env_path
    
    # Check cache directory
    if CACHE_JAR_PATH.exists():
        return CACHE_JAR_PATH
    
    # Try to download to cache
    if _download_plantuml_jar(CACHE_JAR_PATH):
        return CACHE_JAR_PATH
    
    return None


def generate_svg_from_puml(puml_file: pathlib.Path, output_dir: pathlib.Path) -> Optional[pathlib.Path]:
    """
    Generate SVG file from PlantUML file using PlantUML JAR.
    
    Args:
        puml_file: Path to input .puml file
        output_dir: Directory where SVG will be generated (same name as .puml file)
        
    Returns:
        Path to generated SVG file, or None on failure
    """
    try:
        if not puml_file.exists():
            print(f"[WARNING] PlantUML file not found: {puml_file}")
            return None
        
        # Find PlantUML JAR
        jar_path = _find_plantuml_jar()
        if not jar_path:
            print(f"[WARNING] PlantUML JAR not found. Cannot generate SVG. Set PLANTUML_JAR environment variable or install PlantUML.")
            return None
        
        # Ensure output directory exists
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate SVG using PlantUML JAR
        cmd = [
            "java",
            "-jar",
            str(jar_path),
            "-tsvg",
            "-o",
            str(output_dir),
            str(puml_file)
        ]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60
        )
        
        if result.returncode != 0:
            error_msg = result.stderr.strip() or result.stdout.strip() or "Unknown error"
            print(f"[WARNING] SVG generation failed: {error_msg}")
            return None
        
        # Find generated SVG file (PlantUML generates with same base name)
        expected_svg = output_dir / f"{puml_file.stem}.svg"
        if expected_svg.exists():
            return expected_svg
        else:
            print(f"[WARNING] SVG file not created: {expected_svg}")
            return None
            
    except subprocess.TimeoutExpired:
        print(f"[WARNING] SVG generation timed out for {puml_file}")
        return None
    except Exception as e:
        print(f"[WARNING] Error generating SVG from {puml_file}: {e}")
        return None


if __name__ == "__main__":
    exit(main())

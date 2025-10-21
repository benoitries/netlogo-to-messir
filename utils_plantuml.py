#!/usr/bin/env python3
"""
PlantUML Utilities for Post-Processing
Provides functions to clean escape characters from PlantUML diagram files.
"""

import re
import pathlib
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
    cleaned = re.sub(
        r'\\"([^"]*)\\"',
        r'"\1"',
        cleaned
    )
    
    # 3. Remove invalid color codes from activate commands
    # Pattern: activate participant #invalidcolor -> activate participant
    cleaned = re.sub(
        r'activate\s+(\w+)\s+#[0-9A-Fa-f]{6}',
        r'activate \1',
        cleaned
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
    
    # Check for escaped quotes (should be cleaned)
    if '\\"' in content:
        issues.append("Contains escaped quotes that should be cleaned")
    
    # Check for invalid color codes in activate commands
    invalid_colors = re.findall(r'activate\s+\w+\s+#[0-9A-Fa-f]{6}', content)
    if invalid_colors:
        issues.append(f"Invalid color codes in activate commands: {invalid_colors}")
    
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
            
            if re.search(r'activate\s+\w+\s+#[0-9A-Fa-f]{6}', original_content):
                changes_made.append("Removed invalid color codes from activate commands")
            
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


if __name__ == "__main__":
    exit(main())

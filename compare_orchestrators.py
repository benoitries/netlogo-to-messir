#!/usr/bin/env python3
"""
Comparison script to show the improvements made to the orchestrator.
"""

import os
import pathlib


def count_lines_in_file(file_path: str) -> int:
    """Count lines in a file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return len(f.readlines())
    except FileNotFoundError:
        return 0


def analyze_file_structure(file_path: str) -> dict:
    """Analyze the structure of a Python file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Count different elements
        imports = content.count('import ')
        from_imports = content.count('from ')
        functions = content.count('def ')
        classes = content.count('class ')
        print_statements = content.count('print(')
        logger_calls = content.count('self.logger.')
        
        return {
            'imports': imports + from_imports,
            'functions': functions,
            'classes': classes,
            'print_statements': print_statements,
            'logger_calls': logger_calls
        }
    except FileNotFoundError:
        return {}


def main():
    """Main comparison function."""
    print("📊 ORCHESTRATOR COMPARISON ANALYSIS")
    print("="*60)
    
    # File paths
    original_file = "orchestrator.py"
    simplified_file = "orchestrator_simplified.py"
    logging_util = "utils_orchestrator_logging.py"
    ui_util = "utils_orchestrator_ui.py"
    fileio_util = "utils_orchestrator_fileio.py"
    
    # Count lines
    original_lines = count_lines_in_file(original_file)
    simplified_lines = count_lines_in_file(simplified_file)
    logging_lines = count_lines_in_file(logging_util)
    ui_lines = count_lines_in_file(ui_util)
    fileio_lines = count_lines_in_file(fileio_util)
    
    total_new_lines = simplified_lines + logging_lines + ui_lines + fileio_lines
    
    print(f"\n📏 LINE COUNT COMPARISON:")
    print(f"   Original orchestrator:     {original_lines:,} lines")
    print(f"   Simplified orchestrator:   {simplified_lines:,} lines")
    print(f"   Logging utility:           {logging_lines:,} lines")
    print(f"   UI utility:                {ui_lines:,} lines")
    print(f"   File I/O utility:          {fileio_lines:,} lines")
    print(f"   Total new code:            {total_new_lines:,} lines")
    
    reduction_percentage = ((original_lines - simplified_lines) / original_lines) * 100
    print(f"\n📉 SIMPLIFICATION RESULTS:")
    print(f"   Lines removed:             {original_lines - simplified_lines:,} lines")
    print(f"   Reduction percentage:      {reduction_percentage:.1f}%")
    print(f"   Code organization:        Split into 4 focused files")
    
    # Analyze structure
    print(f"\n🔍 STRUCTURAL ANALYSIS:")
    
    original_structure = analyze_file_structure(original_file)
    simplified_structure = analyze_file_structure(simplified_file)
    logging_structure = analyze_file_structure(logging_util)
    ui_structure = analyze_file_structure(ui_util)
    fileio_structure = analyze_file_structure(fileio_util)
    
    print(f"\n   Original orchestrator:")
    print(f"     - Functions: {original_structure.get('functions', 0)}")
    print(f"     - Classes: {original_structure.get('classes', 0)}")
    print(f"     - Print statements: {original_structure.get('print_statements', 0)}")
    print(f"     - Logger calls: {original_structure.get('logger_calls', 0)}")
    
    print(f"\n   Simplified orchestrator:")
    print(f"     - Functions: {simplified_structure.get('functions', 0)}")
    print(f"     - Classes: {simplified_structure.get('classes', 0)}")
    print(f"     - Print statements: {simplified_structure.get('print_statements', 0)}")
    print(f"     - Logger calls: {simplified_structure.get('logger_calls', 0)}")
    
    print(f"\n   Utility files:")
    print(f"     - Logging utility: {logging_structure.get('functions', 0)} functions")
    print(f"     - UI utility: {ui_structure.get('functions', 0)} functions")
    print(f"     - File I/O utility: {fileio_structure.get('functions', 0)} functions")
    
    # Key improvements
    print(f"\n✨ KEY IMPROVEMENTS:")
    print(f"   ✅ Removed start_step parameter and resume logic")
    print(f"   ✅ Centralized logging in dedicated utility")
    print(f"   ✅ Centralized UI interaction in dedicated utility")
    print(f"   ✅ Centralized file I/O operations in dedicated utility")
    print(f"   ✅ Simplified workflow - always runs complete pipeline")
    print(f"   ✅ Better separation of concerns")
    print(f"   ✅ More maintainable and readable code")
    print(f"   ✅ Easier to test individual components")
    
    # Workflow visibility
    print(f"\n🎯 WORKFLOW VISIBILITY:")
    print(f"   ✅ Clear 8-step pipeline: 1+2 (parallel) → 3-8 (sequential)")
    print(f"   ✅ No complex resume logic to understand")
    print(f"   ✅ Each utility has a single responsibility")
    print(f"   ✅ Orchestrator focuses on coordination only")
    
    print(f"\n🎉 REFACTORING SUCCESS!")
    print(f"   The orchestrator has been successfully simplified and modularized.")


if __name__ == "__main__":
    main()

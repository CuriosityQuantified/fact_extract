#!/usr/bin/env python
"""
Fix import paths in all test files.
This script updates the sys.path.insert calls in all test files to use the correct parent directory path.
"""

import os
import re
import glob
from pathlib import Path

def fix_import_paths(file_path):
    """Fix import paths in a single file."""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Pattern to match the old sys.path.insert line
    old_pattern = r"sys\.path\.insert\(0, os\.path\.abspath\(os\.path\.join\(os\.path\.dirname\(__file__\), '\.\.'\)\)\)"
    
    # Replace with the new path (parent of parent)
    new_path = "sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))"
    
    # Perform the replacement
    new_content = re.sub(old_pattern, new_path, content)
    
    # Also remove duplicate sys.path.insert lines that point to the current directory
    duplicate_pattern = r"sys\.path\.insert\(0, os\.path\.abspath\(os\.path\.join\(os\.path\.dirname\(__file__\), '\.'[,\)]\)\)\)"
    new_content = re.sub(duplicate_pattern, "# Removed duplicate path insertion", new_content)
    
    # If the content changed, write the file
    if new_content != content:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        return True
    
    return False

def main():
    """Fix import paths in all test files."""
    # Get the directory of this script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Get all Python files in the tests directory
    test_dir = os.path.join(script_dir, 'tests')
    test_files = glob.glob(os.path.join(test_dir, "*.py"))
    
    # Count of files fixed
    fixed_count = 0
    
    # Process each file
    for file_path in test_files:
        # Skip __init__.py
        if os.path.basename(file_path) == "__init__.py":
            continue
        
        # Fix the file
        if fix_import_paths(file_path):
            fixed_count += 1
            print(f"Fixed import paths in {os.path.basename(file_path)}")
    
    print(f"\nFixed import paths in {fixed_count} files.")

if __name__ == "__main__":
    main() 
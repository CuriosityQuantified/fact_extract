#!/usr/bin/env python3
"""
Fix imports in Python files.

This script updates imports in all Python files to use absolute imports with the 'src.' prefix.
"""

import os
import re
import glob
from pathlib import Path

# Regex patterns for different import styles
IMPORT_PATTERNS = [
    (r'from\s+(graph|storage|models|utils|gui|config|agents|tools)(\.[a-zA-Z0-9_.]+)?\s+import', r'from src.\1\2 import'),
    (r'import\s+(graph|storage|models|utils|gui|config|agents|tools)(\.[a-zA-Z0-9_.]+)?', r'import src.\1\2'),
]

def fix_imports_in_file(file_path):
    """Fix imports in a single file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original_content = content
        
        # Apply each pattern
        for pattern, replacement in IMPORT_PATTERNS:
            content = re.sub(pattern, replacement, content)
        
        # Only write if changes were made
        if content != original_content:
            print(f"Fixing imports in {file_path}")
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return True
        return False
    except Exception as e:
        print(f"Error processing {file_path}: {str(e)}")
        return False

def fix_imports_in_directory(directory, recursive=True):
    """Fix imports in all Python files in a directory."""
    fixed_count = 0
    
    if recursive:
        # Walk through all subdirectories
        for root, _, files in os.walk(directory):
            for file in files:
                if file.endswith('.py'):
                    file_path = os.path.join(root, file)
                    if fix_imports_in_file(file_path):
                        fixed_count += 1
    else:
        # Just process files in the current directory
        for file_path in glob.glob(os.path.join(directory, "*.py")):
            if fix_imports_in_file(file_path):
                fixed_count += 1
                
    return fixed_count

def main():
    """Main function."""
    # Set the base directory
    base_dir = Path(__file__).parent
    
    # Fix imports in all Python files
    count = fix_imports_in_directory(base_dir, recursive=True)
    print(f"Fixed imports in {count} files")

if __name__ == "__main__":
    main() 
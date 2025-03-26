#!/usr/bin/env python
"""
Debug script to find and fix the approve_button issue.
This script scans all Python files for references to approve_button and fixes the issue.
"""

import os
import re
import sys

def fix_approve_button_issue():
    """Find and fix the approve_button issue in all Python files."""
    # Directories to search
    directories = ["src/gui"]
    
    # Variables to replace
    replacements = {
        "approve_button": "approve_btn",
        "reject_button": "reject_btn",
        "modify_button": "modify_btn",
    }
    
    # Files that were modified
    modified_files = []
    
    # Walk through directories and search for Python files
    for directory in directories:
        for root, _, files in os.walk(directory):
            for file in files:
                if file.endswith(".py"):
                    file_path = os.path.join(root, file)
                    
                    # Read file content
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    # Check if any of the variables to replace are in the content
                    if any(var in content for var in replacements.keys()):
                        # Make replacements
                        new_content = content
                        for old_var, new_var in replacements.items():
                            # Don't replace inside comments or docstrings
                            pattern = r'(?<![\'"])\b' + re.escape(old_var) + r'\b(?![\'"])'
                            new_content = re.sub(pattern, new_var, new_content)
                        
                        # If content changed, write the new content
                        if new_content != content:
                            with open(file_path, 'w', encoding='utf-8') as f:
                                f.write(new_content)
                            modified_files.append(file_path)
                            print(f"Fixed variable names in {file_path}")
    
    # If no files were modified, print a message
    if not modified_files:
        print("No files needed fixing. The issue might be elsewhere.")
        return
    
    print(f"\nFixed {len(modified_files)} files:")
    for file in modified_files:
        print(f"  - {file}")

def main():
    """Main function."""
    print("Fixing approve_button issue...")
    fix_approve_button_issue()
    
    print("\nDone. Run the app to see if the error is fixed.")

if __name__ == "__main__":
    main() 
#!/usr/bin/env python3
"""
Add pytest.mark.asyncio decorator to async test functions.

This script finds all async test functions in test files and adds the pytest.mark.asyncio
decorator if it's not already present.
"""

import os
import re
import sys

def ensure_pytest_import(content):
    """Ensure pytest is imported in the file."""
    if "import pytest" not in content:
        # Add import after other imports
        import_match = re.search(r'((?:^import .*?\n|^from .*?\n)+)', content, re.MULTILINE)
        if import_match:
            # Add after the last import
            last_import = import_match.group(1)
            return content.replace(last_import, last_import + "import pytest\n\n")
        else:
            # Add at the beginning
            return "import pytest\n\n" + content
    return content

def add_asyncio_decorator(file_path):
    """Add the pytest.mark.asyncio decorator to async test functions."""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # First ensure pytest is imported
    content = ensure_pytest_import(content)
    
    # Use a simple regex to find lines with async def test_
    modified_content = content
    lines = content.splitlines()
    modified_lines = []
    
    i = 0
    while i < len(lines):
        line = lines[i]
        # If we find an async test function
        if re.match(r'\s*async def (test_\w+)', line):
            # Check if the previous non-blank line is the decorator
            j = i - 1
            while j >= 0 and not lines[j].strip():
                j -= 1
            
            if j >= 0 and '@pytest.mark.asyncio' in lines[j]:
                # Decorator already exists
                modified_lines.append(line)
            else:
                # Add the decorator
                modified_lines.append('@pytest.mark.asyncio')
                modified_lines.append(line)
        else:
            modified_lines.append(line)
        i += 1
    
    modified_content = '\n'.join(modified_lines)
    
    # Only write if changes were made
    if modified_content != content:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(modified_content)
        return True
    
    return False

def main():
    """Main function to process all test files."""
    # Get the list of test files from the command arguments or use a default path
    test_files = sys.argv[1:] if len(sys.argv) > 1 else []
    if not test_files:
        # Default to all test files in src/tests
        tests_dir = os.path.join('src', 'tests')
        test_files = [
            os.path.join(tests_dir, f)
            for f in os.listdir(tests_dir)
            if f.startswith('test_') and f.endswith('.py')
        ]
    
    # Process each file
    files_modified = 0
    for file_path in test_files:
        if add_asyncio_decorator(file_path):
            print(f"Added asyncio decorator to {file_path}")
            files_modified += 1
    
    print(f"Modified {files_modified} test files")

if __name__ == "__main__":
    main() 
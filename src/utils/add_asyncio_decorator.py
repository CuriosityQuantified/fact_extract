"""
Utility script to add pytest.mark.asyncio decorator to async test functions.
"""

import os
import re
import glob
import sys

def add_asyncio_decorator(filepath):
    """
    Add pytest.mark.asyncio decorator to async test functions.
    
    Args:
        filepath: Path to the file to fix
    """
    print(f"Processing {filepath}...")
    
    # Read the file
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Check if file has async test functions
    if not re.search(r"async\s+def\s+test_", content):
        print(f"  No async test functions found in {filepath}, skipping.")
        return False
    
    # Make sure pytest is imported
    if "import pytest" not in content:
        content = re.sub(r"(import.*\n)", r"\1import pytest\n", content, count=1)
    
    # Add the @pytest.mark.asyncio decorator to async test functions
    # This pattern matches async functions that don't already have the decorator
    content = re.sub(
        r"^([ \t]*)async\s+def\s+(test_[^\(]+)(\([^\)]*\):)(?!\s*@pytest\.mark\.asyncio)",
        r"\1@pytest.mark.asyncio\n\1async def \2\3",
        content,
        flags=re.MULTILINE
    )
    
    # Write the updated content
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"  Added asyncio decorators to {filepath}")
    return True

def main():
    """Add asyncio decorators to all test files."""
    # Get all test files
    test_files = glob.glob("src/tests/test_*.py")
    
    if not test_files:
        print("No test files found in src/tests/!")
        return
    
    # Process each file
    fixed_count = 0
    for filepath in test_files:
        if add_asyncio_decorator(filepath):
            fixed_count += 1
    
    print(f"\nAdded asyncio decorators to {fixed_count} files.")

if __name__ == "__main__":
    main() 
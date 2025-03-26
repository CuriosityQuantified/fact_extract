"""
Utility script to fix import paths in test files by removing 'src.' prefix.
"""

import os
import re
import glob
import sys

def fix_imports_in_file(filepath):
    """
    Fix imports in a file, removing 'src.' prefix from imports.
    
    Args:
        filepath: Path to the file to fix
    """
    print(f"Processing {filepath}...")
    
    # Read the file
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Check if we already added the sys.path.insert line for the parent directory
    parent_path_found = "sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))" in content
    
    # Make sure we have sys and os imports
    if "import sys" not in content:
        content = re.sub(r"import.*\n", r"\g<0>import sys\n", content, count=1)
    
    if "import os" not in content:
        content = re.sub(r"import.*\n", r"\g<0>import os\n", content, count=1)
    
    # Add the pytest.mark.asyncio decorator for async tests if needed
    if "async def test_" in content and "import pytest" not in content:
        content = re.sub(r"import.*\n", r"\g<0>import pytest\n", content, count=1)
    
    # Fix async test functions by adding the @pytest.mark.asyncio decorator
    content = re.sub(
        r"(\n\s*)async def (test_[^(]+\([^)]*\))",
        r"\1@pytest.mark.asyncio\n\1async def \2",
        content
    )
    
    # Add the path fix after imports for src directory if not already there
    if not parent_path_found:
        path_fix = "\n# Ensure the src directory is in the path\nsys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))\n"
        
        # Find a good place to insert the path fix
        import_match = re.search(r"import.*\n\n", content)
        if import_match:
            pos = import_match.end()
            content = content[:pos] + path_fix + content[pos:]
        else:
            # If no clear import section, add after docstring
            docstring_match = re.search(r'""".*?"""\n', content, re.DOTALL)
            if docstring_match:
                pos = docstring_match.end()
                content = content[:pos] + path_fix + content[pos:]
            else:
                # Last resort, add at the beginning
                content = path_fix + content
    
    # Fix import patterns
    
    # 1. Fix "from src.fact_extract.XXX import XXX" -> "from XXX import XXX"
    content = re.sub(r"from\s+src\.fact_extract\.([^ ]+)\s+import", r"from \1 import", content)
    
    # 2. Fix "from src.XXX import XXX" -> "from XXX import XXX"
    content = re.sub(r"from\s+src\.([^ ]+)\s+import", r"from \1 import", content)
    
    # 3. Fix "import src.fact_extract.XXX" -> "import XXX"
    content = re.sub(r"import\s+src\.fact_extract\.([^ ]+)", r"import \1", content)
    
    # 4. Fix "import src.XXX" -> "import XXX"
    content = re.sub(r"import\s+src\.([^ ]+)", r"import \1", content)
    
    # 5. Fix patch paths in mocks
    content = re.sub(r"patch\(['\"]src\.fact_extract\.([^'\"]+)['\"]", r"patch('\1", content)
    content = re.sub(r"patch\(['\"]src\.([^'\"]+)['\"]", r"patch('\1", content)
    
    # Write the updated content
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"  Fixed imports in {filepath}")
    return True

def main():
    """Fix imports in all test files."""
    # Get all test files
    test_files = glob.glob("src/tests/test_*.py")
    
    if not test_files:
        print("No test files found in src/tests/!")
        return
    
    # Process each file
    fixed_count = 0
    for filepath in test_files:
        if fix_imports_in_file(filepath):
            fixed_count += 1
    
    print(f"\nFixed imports in {fixed_count} files.")

if __name__ == "__main__":
    main() 
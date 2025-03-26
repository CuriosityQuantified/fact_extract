"""
Script to fix imports in test files, changing fact_extract references to direct imports.
"""

import os
import re
import glob
import sys

def fix_imports_in_file(filepath):
    """Fix imports in a file, changing fact_extract references to direct imports."""
    print(f"Processing {filepath}...")
    
    # Read the file
    with open(filepath, 'r') as f:
        content = f.read()
    
    # Check if we already added the sys.path.insert line for src directory
    src_path_found = "sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))" in content
    
    # Make sure we have sys and os imports
    if "import sys" not in content:
        content = re.sub(r"import.*\n", r"\g<0>import sys\n", content, count=1)
    
    if "import os" not in content:
        content = re.sub(r"import.*\n", r"\g<0>import os\n", content, count=1)
    
    # Add the path fix after imports (for src directory)
    if not src_path_found:
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
    
    # Fix various import patterns
    
    # 1. Fix "from src.fact_extract.XXX import XXX" -> "from XXX import XXX"
    content = re.sub(r"from fact_extract\.([^ ]+) import", r"from \1 import", content)
    
    # 2. Fix "from src.fact_extract.XXX import XXX" -> "from XXX import XXX"
    content = re.sub(r"from src\.fact_extract\.([^ ]+) import", r"from \1 import", content)
    
    # 3. If we have bare imports like "from src.utils.XXX import XXX" without the path setup
    if "from utils." in content and not src_path_found:
        content = re.sub(r"from utils\.", r"from utils.", content)
    
    # 4. If we have bare imports like "from src.models.XXX import XXX" without the path setup
    if "from models." in content and not src_path_found:
        content = re.sub(r"from models\.", r"from models.", content)
    
    # Write the updated content
    with open(filepath, 'w') as f:
        f.write(content)
    
    print(f"  Fixed imports in {filepath}")
    return True

def main():
    """Main function to fix imports in all test files."""
    # Get all test files
    test_files = glob.glob("src/test_*.py") + glob.glob("src/tests/test_*.py") + glob.glob("src/unit_tests/test_*.py")
    
    # Process each file
    fixed_count = 0
    for filepath in test_files:
        if fix_imports_in_file(filepath):
            fixed_count += 1
    
    print(f"\nFixed imports in {fixed_count} files.")

if __name__ == "__main__":
    main() 
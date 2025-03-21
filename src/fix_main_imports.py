"""
Script to fix __main__ imports in test files
"""

import os
import re
import glob

def fix_main_imports_in_file(filepath):
    """Fix __main__ imports in a file."""
    print(f"Processing {filepath}...")
    
    # Read the file
    with open(filepath, 'r') as f:
        content = f.read()
    
    # Check if file imports from __main__
    if "from __main__ import" not in content:
        print(f"  No __main__ imports. Skipping.")
        return False
    
    # Replace __main__ imports with direct imports from the __main__.py file
    content = re.sub(r"from __main__ import ([^,\n]+)", r"from __main__ import \1 as main_\1", content)
    
    # Fix any references to the imported functions
    function_names = re.findall(r"from __main__ import ([^,\n]+)", content)
    for func in function_names:
        # Replace direct function calls, but not in the import statement itself
        pattern = r"(?<!from __main__ import ){}".format(func)
        content = re.sub(pattern, f"main_{func}", content)
    
    # Write the updated content
    with open(filepath, 'w') as f:
        f.write(content)
    
    print(f"  Fixed __main__ imports in {filepath}")
    return True

def main():
    """Main function to fix __main__ imports in all test files."""
    # Get all test files
    test_files = glob.glob("src/test_*.py") + glob.glob("src/tests/test_*.py") + glob.glob("src/unit_tests/test_*.py")
    
    # Process each file
    fixed_count = 0
    for filepath in test_files:
        if fix_main_imports_in_file(filepath):
            fixed_count += 1
    
    print(f"\nFixed __main__ imports in {fixed_count} files.")

if __name__ == "__main__":
    main() 
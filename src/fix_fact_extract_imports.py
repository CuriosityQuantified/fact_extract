#!/usr/bin/env python
"""
Script to fix imports in test files that incorrectly use fact_extract in paths.
"""

import os
import re
import glob

def fix_imports_in_file(filepath):
    """Fix imports in a file, changing fact_extract references to direct imports."""
    print(f"Processing {filepath}...")
    
    # Read the file
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Check if we need to make changes to this file
    if 'fact_extract' not in content:
        return False
    
    # Fix various import patterns
    
    # 1. Fix patch calls with src.fact_extract.XXX -> src.XXX
    content = re.sub(r"patch\(['\"]src\.fact_extract\.([\w\.]+)['\"]", r"patch('src.\1'", content)
    
    # 2. Fix imports like from src.fact_extract.XXX import -> from src.XXX import 
    content = re.sub(r"from src\.fact_extract\.([\w\.]+) import", r"from src.\1 import", content)
    
    # 3. Fix bare imports like from fact_extract.XXX -> from src.XXX
    content = re.sub(r"from fact_extract\.([\w\.]+) import", r"from src.\1 import", content)
    
    # 4. Fix makedirs calls with src/fact_extract/data -> src/data
    content = re.sub(r"os\.makedirs\(['\"]src/fact_extract/data['\"]", r"os.makedirs(\"src/data\"", content)
    
    # 5. Fix sys.modules assignments with 'fact_extract.tools.xxx' -> 'src.tools.xxx'
    content = re.sub(r"['\"]fact_extract\.([\w\.]+)['\"]", r"'src.\1'", content)
    
    # 6. Fix any other occurrences
    content = re.sub(r"fact_extract\.graph", r"src.graph", content)
    content = re.sub(r"fact_extract\.storage", r"src.storage", content)
    content = re.sub(r"fact_extract\.tools", r"src.tools", content)
    content = re.sub(r"fact_extract\.utils", r"src.utils", content)
    content = re.sub(r"fact_extract\.models", r"src.models", content)
    content = re.sub(r"fact_extract\.gui", r"src.gui", content)
    
    # Write the updated content
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"  Fixed imports in {filepath}")
    return True

def main():
    """Main function to fix imports in all test files."""
    # Get all test files
    test_files = glob.glob("src/tests/test_*.py")
    
    # Process each file
    fixed_count = 0
    for filepath in test_files:
        if fix_imports_in_file(filepath):
            fixed_count += 1
    
    print(f"\nFixed imports in {fixed_count} files.")

if __name__ == "__main__":
    main() 
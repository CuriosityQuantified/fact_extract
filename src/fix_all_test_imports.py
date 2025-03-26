#!/usr/bin/env python
"""
Fix all imports in test files.
This script fixes both import paths and module references in test files.
"""

import os
import re
import glob
from pathlib import Path

def fix_imports(file_path):
    """Fix imports in a single file."""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Fix the sys.path.insert line
    old_path_pattern = r"sys\.path\.insert\(0, os\.path\.abspath\(os\.path\.join\(os\.path\.dirname\(__file__\), '\.\.'\)\)\)"
    new_path = "sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))"
    content = re.sub(old_path_pattern, new_path, content)
    
    # Remove duplicate sys.path.insert lines
    duplicate_pattern = r"sys\.path\.insert\(0, os\.path\.abspath\(os\.path\.join\(os\.path\.dirname\(__file__\), '\.'[,\)]\)\)\)"
    content = re.sub(duplicate_pattern, "# Removed duplicate path insertion", content)
    
    # Fix module imports without src prefix
    fixes = [
        (r"from graph\.nodes import", "from src.graph.nodes import"),
        (r"from graph import", "from src.graph import"),
        (r"from models", "from src.models"),
        (r"from storage", "from src.storage"),
        (r"from search", "from src.search"),
        (r"from gui", "from src.gui"),
        (r"from utils", "from src.utils"),
        (r"from tools", "from src.tools"),
        (r"from tests\.test_", "from src.tests.test_"),
        (r"from tests import", "from src.tests import"),
        (r"import graph\.", "import src.graph."),
        (r"import models\.", "import src.models."),
        (r"import storage\.", "import src.storage."),
        (r"import search\.", "import src.search."),
        (r"import gui\.", "import src.gui."),
        (r"import utils\.", "import src.utils."),
        (r"import tools\.", "import src.tools."),
        (r"import tests\.", "import src.tests.")
    ]
    
    for pattern, replacement in fixes:
        content = re.sub(pattern, replacement, content)
    
    # If the content changed, write the file
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    return True

def main():
    """Fix imports in all test files."""
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
        if fix_imports(file_path):
            fixed_count += 1
            print(f"Fixed imports in {os.path.basename(file_path)}")
    
    print(f"\nFixed imports in {fixed_count} files.")

if __name__ == "__main__":
    main() 
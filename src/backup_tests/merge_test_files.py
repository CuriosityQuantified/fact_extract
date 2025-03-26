import os
import re
import glob
import shutil

def merge_test_files():
    """
    Merge test files with conflicts.
    
    This script looks for files with .unit_tests suffix in src/tests,
    analyzes them to see if they contain unique test functions,
    and merges those functions into the main test file.
    """
    # Get all .unit_tests files
    unit_test_files = glob.glob("src/tests/*.unit_tests")
    print(f"Found {len(unit_test_files)} test files with conflicts")
    
    # Process each file
    for unit_test_path in unit_test_files:
        base_name = os.path.basename(unit_test_path)
        original_name = base_name.replace(".unit_tests", "")
        original_path = os.path.join("src/tests", original_name)
        
        print(f"\nProcessing: {base_name}")
        
        # Skip if original file doesn't exist
        if not os.path.exists(original_path):
            print(f"  Original file {original_path} not found, skipping")
            continue
            
        # Read both files
        with open(unit_test_path, 'r', encoding='utf-8') as f:
            unit_test_content = f.read()
            
        with open(original_path, 'r', encoding='utf-8') as f:
            original_content = f.read()
            
        # Extract test functions from both files
        unit_test_functions = extract_test_functions(unit_test_content)
        original_functions = extract_test_functions(original_content)
        
        print(f"  Found {len(unit_test_functions)} test functions in {base_name}")
        print(f"  Found {len(original_functions)} test functions in {original_name}")
        
        # Find unique functions in unit test file
        unique_functions = []
        unique_function_names = []
        for func_name, func_content in unit_test_functions.items():
            if func_name not in original_functions:
                unique_functions.append((func_name, func_content))
                unique_function_names.append(func_name)
                
        print(f"  Found {len(unique_functions)} unique test functions in {base_name}")
        
        if not unique_functions:
            print("  No unique functions to merge, skipping this file")
            continue
            
        print("  Unique functions:")
        for func_name, _ in unique_functions:
            print(f"    - {func_name}")
            
        # Create backup of original file
        backup_path = original_path + ".bak"
        shutil.copy2(original_path, backup_path)
        print(f"  Created backup of original file at {backup_path}")
        
        # Merge unique functions into original file
        merged_content = original_content
        
        # Find the position to add new functions (end of the file)
        # We'll put them before any "if __name__ == '__main__'" block
        main_match = re.search(r'\nif\s+__name__\s*==\s*[\'"]__main__[\'"]\s*:', original_content)
        insert_pos = main_match.start() if main_match else len(original_content)
        
        # Prepare functions to insert
        functions_to_insert = "\n\n" + "\n\n".join([content for _, content in unique_functions])
        
        # Add comment indicating merged functions
        merge_comment = f"\n\n# Merged functions from {base_name}\n"
        functions_to_insert = merge_comment + functions_to_insert
        
        # Insert the functions
        merged_content = merged_content[:insert_pos] + functions_to_insert + merged_content[insert_pos:]
        
        # Write the merged content
        with open(original_path, 'w', encoding='utf-8') as f:
            f.write(merged_content)
            
        print(f"  Merged {len(unique_functions)} functions into {original_name}")
        
        # Rename the unit_test file to mark it as processed
        processed_path = unit_test_path + ".processed"
        os.rename(unit_test_path, processed_path)
        print(f"  Renamed {unit_test_path} to {processed_path}")

def extract_test_functions(content):
    """
    Extract test functions from content.
    
    Returns a dictionary of function name to function content.
    """
    # Regular expression to match function definitions
    # This pattern matches:
    # - Functions that start with 'test_'
    # - Captures the full function name and body including decorators
    pattern = r'(?:@[^\n]+\n)*(?:async\s+)?def\s+(test_[a-zA-Z0-9_]+)\s*\([^)]*\):[^\n]*(?:\n(?:[ \t]+[^\n]*)?)*'
    
    # Find all functions in the content
    functions = {}
    for match in re.finditer(pattern, content):
        # The entire matched content (function definition + body)
        full_match = match.group(0)
        
        # The function name (should start with test_)
        func_name = match.group(1)
        
        # Store in dictionary
        if func_name.startswith('test_'):
            functions[func_name] = full_match
            
    return functions

if __name__ == "__main__":
    merge_test_files() 
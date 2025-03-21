#!/usr/bin/env python
"""
Script to check if Excel files contain data.
"""

import pandas as pd
import os
import sys

def check_excel_file(file_path):
    """Check if an Excel file contains data."""
    try:
        # Read the Excel file
        df = pd.read_excel(file_path)
        
        # Check if the dataframe has any rows
        row_count = len(df)
        
        # Check if there are any non-empty cells
        non_empty_cells = df.count().sum()
        
        print(f"File: {file_path}")
        print(f"  Rows: {row_count}")
        print(f"  Non-empty cells: {non_empty_cells}")
        
        return row_count > 0 or non_empty_cells > 0
    except Exception as e:
        print(f"Error reading {file_path}: {str(e)}")
        return False

def main():
    """Main function to check all Excel files."""
    excel_files = [f for f in os.listdir('.') if f.endswith('.xlsx')]
    
    has_data = False
    for file in excel_files:
        if check_excel_file(file):
            has_data = True
            print(f"WARNING: {file} contains data!")
        else:
            print(f"OK: {file} is empty.")
    
    return 1 if has_data else 0

if __name__ == "__main__":
    sys.exit(main()) 
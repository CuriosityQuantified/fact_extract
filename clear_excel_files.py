#!/usr/bin/env python
import pandas as pd
import os

# List of Excel files to clear
excel_files = [
    "./facts.xlsx",
    "./processed_chunks.xlsx",
    "./unprocessed_chunks.xlsx",
    "./src/fact_extract/data/all_chunks.xlsx",
    "./src/fact_extract/data/all_facts.xlsx",
    "./src/fact_extract/data/rejected_facts.xlsx"
]

# Create empty DataFrames and save to Excel files
for file_path in excel_files:
    # Make sure the directory exists
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    
    # Create and save empty DataFrame
    empty_df = pd.DataFrame()
    empty_df.to_excel(file_path, index=False)
    print(f"Created empty Excel file: {file_path}")

# Now check for the nested duplicated files
root_dir = "."
for root, dirs, files in os.walk(root_dir):
    for file in files:
        if file.endswith(".xlsx") and "venv" not in root:
            file_path = os.path.join(root, file)
            if file_path not in excel_files:
                print(f"Removing duplicate Excel file: {file_path}")
                try:
                    os.remove(file_path)
                except Exception as e:
                    print(f"Failed to remove {file_path}: {str(e)}")

print("Done! All Excel files have been cleared.") 
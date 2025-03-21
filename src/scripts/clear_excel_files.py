"""
Script to clear Excel files used for storing chunks and facts.
This is useful for resetting the system for testing.
"""

import os
import shutil
import pandas as pd

# List of Excel files to clear
EXCEL_FILES = [
    "./data/all_chunks.xlsx",
    "./data/all_facts.xlsx",
    "./data/rejected_facts.xlsx"
]

def clear_excel_files():
    """Clear all Excel files by creating empty files with required columns."""
    print("Clearing Excel files...")
    
    # Create data directory if it doesn't exist
    os.makedirs("data", exist_ok=True)
    
    for file_path in EXCEL_FILES:
        try:
            if os.path.exists(file_path):
                print(f"Clearing {file_path}...")
                
                # Create empty dataframe based on file type
                if "chunks" in file_path:
                    df = pd.DataFrame(columns=[
                        "document_name", "chunk_index", "chunk_content", 
                        "status", "contains_facts", "error_message", "timestamp"
                    ])
                elif "facts" in file_path:
                    df = pd.DataFrame(columns=[
                        "document_name", "statement", "verification_status", 
                        "timestamp", "source_chunk"
                    ])
                elif "rejected" in file_path:
                    df = pd.DataFrame(columns=[
                        "document_name", "statement", "verification_status", 
                        "verification_reason", "timestamp", "source_chunk"
                    ])
                
                # Save empty dataframe to file
                df.to_excel(file_path, index=False)
                print(f"Successfully cleared {file_path}")
            else:
                print(f"File {file_path} does not exist, creating empty file...")
                # Create empty dataframe based on file type
                if "chunks" in file_path:
                    df = pd.DataFrame(columns=[
                        "document_name", "chunk_index", "chunk_content", 
                        "status", "contains_facts", "error_message", "timestamp"
                    ])
                elif "facts" in file_path:
                    df = pd.DataFrame(columns=[
                        "document_name", "statement", "verification_status", 
                        "timestamp", "source_chunk"
                    ])
                elif "rejected" in file_path:
                    df = pd.DataFrame(columns=[
                        "document_name", "statement", "verification_status", 
                        "verification_reason", "timestamp", "source_chunk"
                    ])
                
                # Create directory if it doesn't exist
                os.makedirs(os.path.dirname(file_path), exist_ok=True)
                
                # Save empty dataframe to file
                df.to_excel(file_path, index=False)
                print(f"Successfully created empty {file_path}")
        except Exception as e:
            print(f"Error clearing {file_path}: {str(e)}")

if __name__ == "__main__":
    clear_excel_files()
    print("All Excel files have been cleared.") 
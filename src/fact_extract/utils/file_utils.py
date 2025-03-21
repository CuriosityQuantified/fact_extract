"""
File utility functions for the fact extraction system.
"""

import os
import mimetypes
import csv
from pathlib import Path
from typing import List, Set
from pypdf import PdfReader
from docx import Document

# Update allowed extensions to include all supported formats
ALLOWED_EXTENSIONS: Set[str] = {
    # Text and PDF
    '.txt', '.pdf',
    # Microsoft Office
    '.doc', '.docx',
    '.xls', '.xlsx',
    # CSV
    '.csv'
}

# Maximum file sizes in MB for different formats
MAX_FILE_SIZES = {
    'default': 500,  # Default max size
    'excel': 500,    # Excel files
    'pdf': 500,      # PDFs
    'csv': 500       # CSVs
}

def extract_text_from_file(file_path: str) -> str:
    """
    Extract text content from various file types.
    
    Args:
        file_path: Path to the file
        
    Returns:
        str: Extracted text content
        
    Raises:
        Exception: If text extraction fails
    """
    file_ext = Path(file_path).suffix.lower()
    
    try:
        if file_ext == '.pdf':
            # Extract text from PDF
            reader = PdfReader(file_path)
            text = []
            for page in reader.pages:
                text.append(page.extract_text())
            return "\n\n".join(text)
            
        elif file_ext in ['.docx', '.doc']:
            # Extract text from Word document
            doc = Document(file_path)
            return "\n\n".join([paragraph.text for paragraph in doc.paragraphs])
            
        elif file_ext == '.csv':
            # Extract text from CSV
            text = []
            with open(file_path, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                for row in reader:
                    text.append(",".join(row))
            return "\n".join(text)
            
        else:
            # For text files, read directly
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
                
    except Exception as e:
        raise Exception(f"Error extracting text from {file_path}: {str(e)}")

def get_max_size_for_extension(ext: str) -> int:
    """
    Get the maximum allowed file size for a given extension.
    
    Args:
        ext: File extension (including dot)
        
    Returns:
        int: Maximum file size in MB
    """
    ext = ext.lower()
    if ext in {'.xls', '.xlsx'}:
        return MAX_FILE_SIZES['excel']
    elif ext == '.pdf':
        return MAX_FILE_SIZES['pdf']
    elif ext == '.csv':
        return MAX_FILE_SIZES['csv']
    return MAX_FILE_SIZES['default']

def is_valid_file(file_path: str) -> bool:
    """
    Check if a file is valid for processing.
    
    Args:
        file_path: Path to the file to check
        
    Returns:
        bool: True if file is valid, False otherwise
    """
    path = Path(file_path)
    
    # Check file extension
    ext = path.suffix.lower()
    print(f"Checking file: {file_path}, extension: {ext}, allowed: {ext in ALLOWED_EXTENSIONS}")
    if ext not in ALLOWED_EXTENSIONS:
        return False
        
    # Check if file exists
    if not path.exists():
        return False
        
    # Check file size
    try:
        file_size = path.stat().st_size / (1024 * 1024)  # Convert to MB
        max_size = get_max_size_for_extension(ext)
        if file_size > max_size:
            return False
    except Exception:
        return False
        
    return True

def get_temp_path(file_name: str) -> Path:
    """
    Get a temporary path for storing uploaded files.
    
    Args:
        file_name: Original file name
        
    Returns:
        Path: Temporary file path
    """
    temp_dir = Path("temp_uploads")
    temp_dir.mkdir(exist_ok=True)
    
    # Ensure unique filenames
    base = temp_dir / Path(file_name).name
    if base.exists():
        counter = 1
        while True:
            new_name = f"{base.stem}_{counter}{base.suffix}"
            new_path = temp_dir / new_name
            if not new_path.exists():
                return new_path
            counter += 1
    return base

def cleanup_temp_files(file_paths: List[str]) -> None:
    """
    Clean up temporary files after processing.
    
    Args:
        file_paths: List of file paths to clean up
    """
    for file_path in file_paths:
        try:
            path = Path(file_path)
            if path.exists() and path.is_file():
                path.unlink()
                
            # Also clean up any related temporary files
            parent = path.parent
            if parent.name == "temp_uploads" and parent.exists():
                # Clean up empty temp directories
                if not any(parent.iterdir()):
                    parent.rmdir()
        except Exception:
            pass  # Ignore cleanup errors 
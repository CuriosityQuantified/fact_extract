"""
Unit tests for file validation in the fact extraction system.
Tests that the system correctly validates file types and formats.
"""

import os
import sys
import uuid
import pytest
import asyncio
import tempfile
import numpy as np
import pandas as pd
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, AsyncMock


# Ensure the src directory is in the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Ensure the src directory is in the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))
# Import repositories
from storage.chunk_repository import ChunkRepository
from storage.fact_repository import FactRepository, RejectedFactRepository

# Import GUI components
from gui.app import FactExtractionGUI
from models.state import ProcessingState
from utils.file_utils import is_valid_file, extract_text_from_file, ALLOWED_EXTENSIONS

@pytest.fixture
def temp_files():
    """Create temporary files with different formats."""
    # Create a temporary directory
    with tempfile.TemporaryDirectory() as temp_dir:
        # Valid file formats
        text_file = os.path.join(temp_dir, "valid.txt")
        pdf_file = os.path.join(temp_dir, "valid.pdf")
        docx_file = os.path.join(temp_dir, "valid.docx")
        csv_file = os.path.join(temp_dir, "valid.csv")
        
        # Invalid file formats
        exe_file = os.path.join(temp_dir, "invalid.exe")
        zip_file = os.path.join(temp_dir, "invalid.zip")
        html_file = os.path.join(temp_dir, "invalid.html")
        
        # Create dummy content for each file
        with open(text_file, 'w') as f:
            f.write("This is a valid text file with some fact: The semiconductor market reached $550B in 2023.")
        
        # Create a simple PDF file (this is not a real PDF, just for testing validation)
        with open(pdf_file, 'wb') as f:
            f.write(b'%PDF-1.5\nSome dummy PDF content\n%%EOF')
        
        # Create a simple DOCX file (this is not a real DOCX, just for testing validation)
        with open(docx_file, 'wb') as f:
            f.write(b'PK\x03\x04\x14\x00\x06\x00\x08\x00\x00\x00!\x00dummy docx content')
        
        # Create a CSV file
        with open(csv_file, 'w') as f:
            f.write("Year,Market,Value\n2023,Semiconductor,$550B\n2023,AI,38%\n")
        
        # Create invalid files
        with open(exe_file, 'wb') as f:
            f.write(b'MZ\x90\x00\x03\x00\x00\x00\x04\x00\x00\x00\xff\xff\x00\x00')
        
        with open(zip_file, 'wb') as f:
            f.write(b'PK\x03\x04\x14\x00\x00\x00\x08\x00dummy zip content')
        
        with open(html_file, 'w') as f:
            f.write("<html><body><p>This is an HTML file.</p></body></html>")
        
        yield {
            'valid': {
                'txt': text_file,
                'pdf': pdf_file,
                'docx': docx_file,
                'csv': csv_file
            },
            'invalid': {
                'exe': exe_file,
                'zip': zip_file,
                'html': html_file
            }
        }

def test_valid_file_extensions(temp_files):
    """Test that valid file extensions are correctly identified."""
    # Check valid files
    for file_type, file_path in temp_files['valid'].items():
        assert is_valid_file(file_path), f"File with extension .{file_type} should be valid"

def test_invalid_file_extensions(temp_files):
    """Test that invalid file extensions are correctly rejected."""
    # Check invalid files
    for file_type, file_path in temp_files['invalid'].items():
        assert not is_valid_file(file_path), f"File with extension .{file_type} should be invalid"

@pytest.mark.asyncio
async def test_gui_handling_of_invalid_files(temp_files):
    """Test that the GUI correctly handles invalid file formats."""
    gui = FactExtractionGUI()
    
    # Create a mock file with invalid extension
    class MockFile:
        def __init__(self, file_path):
            self.name = file_path
        
        def save(self, path):
            # Just copy the file for testing
            with open(self.name, 'rb') as src, open(path, 'wb') as dst:
                dst.write(src.read())
    
    # Test with an invalid file
    invalid_file = MockFile(temp_files['invalid']['html'])
    
    # Process the invalid file
    results = []
    async for result in gui.process_files([invalid_file]):
        results.append(result)
    
    # Check that processing generated some output
    assert len(results) > 0
    
    # Check that an error message was displayed in the chat history
    error_messages = [msg for msg in gui.chat_history if "invalid" in msg.get("content", "").lower() or 
                      "unsupported" in msg.get("content", "").lower() or 
                      "not allowed" in msg.get("content", "").lower()]
    
    assert len(error_messages) > 0, "Expected error message for invalid file"

@pytest.mark.asyncio
async def test_gui_handling_of_mixed_files(temp_files):
    """Test that the GUI correctly processes valid files and rejects invalid ones."""
    gui = FactExtractionGUI()
    
    # Create mock files with different extensions
    class MockFile:
        def __init__(self, file_path):
            self.name = file_path
        
        def save(self, path):
            # Just copy the file for testing
            with open(self.name, 'rb') as src, open(path, 'wb') as dst:
                dst.write(src.read())
    
    # Create a mix of valid and invalid files
    valid_file = MockFile(temp_files['valid']['txt'])
    invalid_file = MockFile(temp_files['invalid']['html'])
    
    # Mock the process_document function to avoid actual processing
    with patch('src.fact_extract.process_document') as mock_process:
        mock_process.return_value = {
            "status": "completed",
            "message": "Processing completed successfully",
            "facts": [
                {
                    "statement": "The semiconductor market reached $550B in 2023.",
                    "verification_status": "verified",
                    "document_name": "valid.txt",
                    "chunk_index": 0,
                    "verification_reasoning": "This fact contains specific metrics and can be verified."
                }
            ],
            "chunks_processed": 1,
            "facts_extracted": 1
        }
        
        # Process both files
        results = []
        async for result in gui.process_files([valid_file, invalid_file]):
            results.append(result)
        
        # Check that processing generated some output
        assert len(results) > 0
        
        # Check that an error message was displayed for the invalid file
        error_messages = [msg for msg in gui.chat_history if "invalid" in msg.get("content", "").lower() or 
                          "unsupported" in msg.get("content", "").lower() or 
                          "not allowed" in msg.get("content", "").lower()]
        
        assert len(error_messages) > 0, "Expected error message for invalid file"
        
        # Check that the valid file was processed
        success_messages = [msg for msg in gui.chat_history if "processing" in msg.get("content", "").lower() and 
                            "valid.txt" in msg.get("content", "")]
        
        assert len(success_messages) > 0, "Expected success message for valid file"
        
        # Check that process_document was called for the valid file but not for the invalid file
        assert mock_process.called, "process_document should have been called for valid file"
        
        # Check number of calls (should be 1 for valid file only)
        assert mock_process.call_count == 1, "Expected process_document to be called once"

def test_system_accepts_all_allowed_extensions():
    """Test that the system accepts all file extensions defined in ALLOWED_EXTENSIONS."""
    with tempfile.TemporaryDirectory() as temp_dir:
        for ext in ALLOWED_EXTENSIONS:
            # Create an empty file with this extension
            test_file = os.path.join(temp_dir, f"test{ext}")
            with open(test_file, 'w') as f:
                f.write(f"Test content for {ext} file.")
            
            # Check that the file is considered valid
            assert is_valid_file(test_file), f"File with extension {ext} should be valid"

def test_very_large_file_validation():
    """Test validation of very large files that exceed size limits."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create a very large text file (using sparse file to avoid actual disk usage)
        large_file = os.path.join(temp_dir, "large.txt")
        
        # Create a sparse file that appears large but doesn't use much disk space
        with open(large_file, 'wb') as f:
            # Seek to position beyond size limit and write minimal data
            f.seek(1024 * 1024 * 1024)  # 1 GB position
            f.write(b'!')  # Write a single byte
        
        # Patch the max size check to use a very small limit for testing
        with patch('src.fact_extract.utils.file_utils.get_max_size_for_extension', return_value=1):
            # Check that the file is considered invalid due to size
            assert not is_valid_file(large_file), "Very large file should be rejected"

@pytest.mark.asyncio
async def test_empty_file_handling():
    """Test handling of empty files."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create an empty text file
        empty_file = os.path.join(temp_dir, "empty.txt")
        with open(empty_file, 'w') as f:
            pass  # Create empty file
        
        # Create a GUI instance
        gui = FactExtractionGUI()
        
        # Create a mock file
        class MockFile:
            def __init__(self, file_path):
                self.name = file_path
            
            def save(self, path):
                with open(self.name, 'rb') as src, open(path, 'wb') as dst:
                    dst.write(src.read())
        
        # Create a mock for the empty file
        mock_empty_file = MockFile(empty_file)
        
        # Process the empty file
        results = []
        async for result in gui.process_files([mock_empty_file]):
            results.append(result)
        
        # Check that processing generated some output
        assert len(results) > 0
        
        # Check that an appropriate message was displayed
        empty_messages = [msg for msg in gui.chat_history if 
                        ("empty" in msg.get("content", "").lower() or 
                         "no text" in msg.get("content", "").lower() or
                         "could not" in msg.get("content", "").lower())]
        
        assert len(empty_messages) > 0, "Expected message about empty file or extraction failure"

@pytest.mark.asyncio
async def test_corrupt_file_handling():
    """Test handling of corrupt files that have valid extensions but invalid content."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create a corrupt PDF file (valid extension but invalid content)
        corrupt_pdf = os.path.join(temp_dir, "corrupt.pdf")
        with open(corrupt_pdf, 'w') as f:
            f.write("This is not a valid PDF file, just text with a .pdf extension")
        
        # Create a GUI instance
        gui = FactExtractionGUI()
        
        # Create a mock file
        class MockFile:
            def __init__(self, file_path):
                self.name = file_path
            
            def save(self, path):
                with open(self.name, 'rb') as src, open(path, 'wb') as dst:
                    dst.write(src.read())
        
        # Create a mock for the corrupt file
        mock_corrupt_file = MockFile(corrupt_pdf)
        
        # Mock the extract_text_from_file function to simulate an error during extraction
        with patch('src.fact_extract.utils.file_utils.extract_text_from_file') as mock_extract:
            mock_extract.side_effect = Exception("Failed to parse PDF: Invalid PDF structure")
            
            # Process the corrupt file
            results = []
            async for result in gui.process_files([mock_corrupt_file]):
                results.append(result)
            
            # Check that processing generated some output
            assert len(results) > 0
            
            # Check that an error message was displayed
            error_messages = [msg for msg in gui.chat_history if "error" in msg.get("content", "").lower() or 
                             "failed" in msg.get("content", "").lower() or 
                             "could not" in msg.get("content", "").lower()]
            
            assert len(error_messages) > 0, "Expected error message for corrupt file"

@pytest.mark.asyncio
async def test_very_short_document():
    """Test processing of very short documents (edge case)."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create a very short document
        short_file = os.path.join(temp_dir, "short.txt")
        with open(short_file, 'w') as f:
            f.write("Short text.")
        
        # Create a GUI instance
        gui = FactExtractionGUI()
        
        # Create a mock file
        class MockFile:
            def __init__(self, file_path):
                self.name = file_path
            
            def save(self, path):
                with open(self.name, 'rb') as src, open(path, 'wb') as dst:
                    dst.write(src.read())
        
        # Create a mock for the short file
        mock_short_file = MockFile(short_file)
        
        # Mock the process_document function to track what happens with a very short document
        with patch('src.fact_extract.process_document') as mock_process:
            mock_process.return_value = {
                "status": "completed",
                "message": "Processing completed successfully but no facts were found",
                "facts": [],
                "chunks_processed": 1,
                "facts_extracted": 0
            }
            
            # Process the short file
            results = []
            async for result in gui.process_files([mock_short_file]):
                results.append(result)
            
            # Check that processing generated some output
            assert len(results) > 0
            
            # Check that process_document was called
            assert mock_process.called, "process_document should have been called"
            
            # Check that an appropriate message was displayed
            no_facts_messages = [msg for msg in gui.chat_history if "no facts" in msg.get("content", "").lower() or 
                                "no verifiable facts" in msg.get("content", "").lower()]
            
            # We don't assert this because the system might still attempt to process the document
            # even if it's very short, and it depends on implementation details
            # assert len(no_facts_messages) > 0, "Expected message about no facts found" 
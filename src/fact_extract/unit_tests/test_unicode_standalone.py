"""
Standalone tests for verifying Unicode handling in the fact extraction system.
These tests focus only on the storage components and Unicode text handling,
avoiding imports of components that require OpenAI API credentials.
"""

import os
import sys
import uuid
import pytest
import asyncio
import tempfile
import pandas as pd
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, AsyncMock
import shutil
from datetime import datetime

# Import only the specific components we need for testing
from src.fact_extract.storage.chunk_repository import ChunkRepository
from src.fact_extract.storage.fact_repository import FactRepository, RejectedFactRepository
from src.fact_extract.utils.file_utils import extract_text_from_file

@pytest.fixture
def setup_test_repositories():
    """Set up test repositories with temporary Excel files."""
    # Create unique IDs for test files to avoid conflicts
    unique_id = str(uuid.uuid4())
    temp_dir = "temp"
    
    # Create temp directory if it doesn't exist
    os.makedirs(temp_dir, exist_ok=True)
    
    chunks_file = os.path.join(temp_dir, f"temp_chunks_{unique_id}.xlsx")
    facts_file = os.path.join(temp_dir, f"temp_facts_{unique_id}.xlsx")
    rejected_facts_file = os.path.join(temp_dir, f"temp_rejected_facts_{unique_id}.xlsx")

    # Create test repositories with the temporary files
    chunk_repo = ChunkRepository(excel_path=chunks_file)
    fact_repo = FactRepository(excel_path=facts_file)
    rejected_fact_repo = RejectedFactRepository(excel_path=rejected_facts_file)

    # Also clear the main repositories to prevent test interference
    main_chunk_repo = ChunkRepository()
    main_fact_repo = FactRepository()
    main_rejected_fact_repo = RejectedFactRepository()
    
    # Clear all documents from main repositories
    for document_name in list(main_chunk_repo.chunks.keys()):
        main_chunk_repo.clear_document(document_name)
    
    for document_name in list(main_fact_repo.facts.keys()):
        main_fact_repo.clear_facts(document_name)
    
    for document_name in list(main_rejected_fact_repo.rejected_facts.keys()):
        main_rejected_fact_repo.clear_rejected_facts(document_name)

    yield chunk_repo, fact_repo, rejected_fact_repo

    # Clean up temporary files after the test
    for file in [chunks_file, facts_file, rejected_facts_file]:
        if os.path.exists(file):
            os.remove(file)

@pytest.fixture
def unicode_text_file(tmp_path):
    """Create a temporary text file with unicode content."""
    file_path = tmp_path / "unicode_text.txt"
    
    # Create text with various unicode characters and symbols
    unicode_content = """
    # International Text Sample with Facts
    
    ## European Languages
    The European Union GDP reached €15.3 trillion in 2023, with Germany contributing €3.8 trillion.
    France's unemployment rate fell to 7.1% in the last quarter.
    
    ## Asian Languages
    中国的人口超过14亿，其中城市人口占比为63.9%。
    日本的人均GDP在2023年达到40,247美元，较上年增长了2.3%。
    
    ## Symbols and Special Characters
    The temperature rose by 2.5°C in the Arctic regions last year.
    Scientists observed α-particles with energy of 5.4 MeV during the experiment.
    The π value is approximately 3.14159, used in many scientific calculations.
    
    ## Technical Data with Special Formatting
    The new CPU performance improved by 35% (±3%) compared to last year's model.
    Water quality measurements: pH = 7.2, CO₂ = 415ppm, O₂ = 8.5mg/L.
    """
    
    file_path.write_text(unicode_content, encoding='utf-8')
    return str(file_path)

def test_extract_text_from_unicode_file(unicode_text_file):
    """Test that text extraction works correctly with unicode characters."""
    # Extract text from the file
    text = extract_text_from_file(unicode_text_file)
    
    # Verify that the unicode characters are preserved
    assert "€15.3 trillion" in text
    assert "中国的人口超过14亿" in text
    assert "2.5°C" in text
    assert "α-particles" in text
    assert "π value is approximately 3.14159" in text
    assert "CO₂ = 415ppm" in text

def test_unicode_in_chunks(setup_test_repositories, unicode_text_file):
    """Test that chunks with unicode are stored correctly in the repository."""
    chunk_repo, fact_repo, rejected_fact_repo = setup_test_repositories
    
    # Create chunks with unicode content directly
    document_name = "unicode_document.txt"
    document_hash = "unicode_hash"
    
    # Extract text from the file
    with open(unicode_text_file, 'r', encoding='utf-8') as f:
        text_content = f.read()
    
    # Store chunks with unicode content
    chunk_repo.store_chunk({
        "document_name": document_name,
        "document_hash": document_hash,
        "chunk_index": 0,
        "chunk_content": "The European Union GDP reached €15.3 trillion in 2023.",
        "status": "processed",
        "contains_facts": True,
        "error_message": None,
        "all_facts_extracted": True,
        "timestamp": datetime.now().isoformat()
    })
    
    chunk_repo.store_chunk({
        "document_name": document_name,
        "document_hash": document_hash,
        "chunk_index": 1,
        "chunk_content": "中国的人口超过14亿，其中城市人口占比为63.9%。",
        "status": "processed",
        "contains_facts": True,
        "error_message": None,
        "all_facts_extracted": True,
        "timestamp": datetime.now().isoformat()
    })
    
    chunk_repo.store_chunk({
        "document_name": document_name,
        "document_hash": document_hash,
        "chunk_index": 2,
        "chunk_content": "The temperature rose by 2.5°C in the Arctic regions.",
        "status": "processed",
        "contains_facts": True,
        "error_message": None,
        "all_facts_extracted": True,
        "timestamp": datetime.now().isoformat()
    })
    
    # Store facts with unicode content
    fact_repo.store_fact({
        "id": 1,
        "document_name": document_name,
        "chunk_index": 0,
        "statement": "The European Union GDP reached €15.3 trillion in 2023.",
        "verification_status": "verified",
        "verification_reasoning": "This fact contains specific metrics and can be verified."
    })
    
    fact_repo.store_fact({
        "id": 2,
        "document_name": document_name,
        "chunk_index": 1,
        "statement": "中国的人口超过14亿，其中城市人口占比为63.9%。",
        "verification_status": "verified",
        "verification_reasoning": "This fact contains specific metrics and can be verified."
    })
    
    fact_repo.store_fact({
        "id": 3,
        "document_name": document_name,
        "chunk_index": 2,
        "statement": "The temperature rose by 2.5°C in the Arctic regions.",
        "verification_status": "verified",
        "verification_reasoning": "This fact contains specific metrics and can be verified."
    })
    
    # Check that chunks with unicode were stored correctly
    chunks = chunk_repo.get_chunks_for_document(document_name)
    assert len(chunks) == 3
    
    # Check unicode content in chunks
    unicode_texts = [chunk.get("chunk_content", "") for chunk in chunks]
    assert any("€" in text for text in unicode_texts), "Euro symbol not found in chunks"
    assert any("°C" in text for text in unicode_texts), "Degree Celsius not found in chunks"
    assert any("中国" in text for text in unicode_texts), "Chinese characters not found in chunks"
    
    # Check that facts with unicode were stored correctly
    facts = fact_repo.get_facts_for_document(document_name)
    assert len(facts) == 3
    
    # Verify unicode characters in facts
    fact_statements = [fact.get("statement", "") for fact in facts]
    assert any("€" in stmt for stmt in fact_statements), "Euro symbol not found in facts"
    assert any("°C" in stmt for stmt in fact_statements), "Degree Celsius not found in facts"
    assert any("中国" in stmt for stmt in fact_statements), "Chinese characters not found in facts"

class TestGUIUnicodeHandling:
    """Class for testing GUI with Unicode content without importing the full GUI."""
    
    def test_mock_gui_unicode_processing(self, setup_test_repositories, unicode_text_file):
        """Test a mock version of the GUI's handling of Unicode content."""
        chunk_repo, fact_repo, rejected_fact_repo = setup_test_repositories
        
        # Create a mock file class similar to what Gradio would provide
        class MockFile:
            def __init__(self, file_path):
                self.name = os.path.basename(file_path)
                self.path = file_path
            
            def save(self, path):
                shutil.copy(self.path, path)
                return path
        
        # Create a mock file from the unicode file
        mock_file = MockFile(unicode_text_file)
        
        # Read the unicode content
        with open(unicode_text_file, 'r', encoding='utf-8') as f:
            unicode_content = f.read()
        
        # Store document with unicode content
        document_name = mock_file.name
        document_hash = "mock_unicode_hash"
        
        # Store chunks with unicode content
        chunk_repo.store_chunk({
            "document_name": document_name,
            "document_hash": document_hash,
            "chunk_index": 0,
            "chunk_content": "The European Union GDP reached €15.3 trillion in 2023.",
            "status": "processed",
            "contains_facts": True,
            "error_message": None,
            "all_facts_extracted": True,
            "timestamp": datetime.now().isoformat()
        })
        
        chunk_repo.store_chunk({
            "document_name": document_name,
            "document_hash": document_hash,
            "chunk_index": 1,
            "chunk_content": "中国的人口超过14亿，其中城市人口占比为63.9%。",
            "status": "processed",
            "contains_facts": True,
            "error_message": None,
            "all_facts_extracted": True,
            "timestamp": datetime.now().isoformat()
        })
        
        # Store facts with unicode content
        fact_repo.store_fact({
            "id": 1,
            "document_name": document_name,
            "chunk_index": 0,
            "statement": "The European Union GDP reached €15.3 trillion in 2023.",
            "verification_status": "verified",
            "verification_reasoning": "This fact contains specific metrics and can be verified."
        })
        
        fact_repo.store_fact({
            "id": 2,
            "document_name": document_name,
            "chunk_index": 1,
            "statement": "中国的人口超过14亿，其中城市人口占比为63.9%。",
            "verification_status": "verified",
            "verification_reasoning": "This fact contains specific metrics and can be verified."
        })
        
        # Check that facts were stored correctly
        facts = fact_repo.get_all_facts()
        assert len(facts) > 0, "No facts were stored"
        
        # Check that unicode content was preserved in the facts
        fact_statements = [fact.get("statement", "") for fact in facts]
        assert any("€" in stmt for stmt in fact_statements), "Euro symbol not found in facts"
        assert any("中国" in stmt for stmt in fact_statements), "Chinese characters not found in facts"
        
        # Simulate updating a fact with unicode
        facts_list = fact_repo.get_facts_for_document(document_name)
        if facts_list:
            fact_to_update = facts_list[0]
            fact_id = fact_to_update.get("id")
            
            # Update the fact with more unicode content
            updated_fact = {
                "id": fact_id,
                "document_name": document_name,
                "chunk_index": 0,
                "statement": "The European Union GDP reached €15.3 trillion in 2023, showing 2.1% growth.",
                "verification_status": "verified",
                "verification_reasoning": "Updated with more precise α-numeric data."
            }
            
            # Note: The FactRepository class doesn't have an update_fact method.
            # Instead, facts are updated by removing the old fact and storing a new one with the updated information.
            # This pattern is used in the GUI's update_fact method as well.
            # First, remove all facts with the same document name and chunk index
            facts_to_keep = [f for f in facts_list if f.get("chunk_index") != 0]
            fact_repo.clear_facts(document_name)
            
            # Re-store the facts we want to keep
            for fact in facts_to_keep:
                fact_repo.store_fact(fact)
                
            # Store the updated fact
            fact_repo.store_fact(updated_fact)
            
            # Verify the update was successful
            updated_facts = fact_repo.get_facts_for_document(document_name)
            updated_statements = [fact.get("statement", "") for fact in updated_facts]
            assert any("€15.3 trillion" in stmt and "2.1% growth" in stmt for stmt in updated_statements), "Updated Unicode content not found"
            
            # Check for additional unicode characters in reasoning
            updated_reasoning = [fact.get("verification_reasoning", "") for fact in updated_facts]
            assert any("α-numeric" in reason for reason in updated_reasoning), "Unicode in reasoning not preserved" 
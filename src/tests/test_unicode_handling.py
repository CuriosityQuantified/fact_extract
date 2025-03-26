"""
Unit tests for handling unicode and special characters in the fact extraction system.
Tests that the system properly processes documents with international text and symbols.
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


# Ensure the src directory is in the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

# Ensure the src directory is in the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))
# Import repositories
from src.storage.chunk_repository import ChunkRepository
from src.storage.fact_repository import FactRepository, RejectedFactRepository

# Import GUI components
from src.gui.app import FactExtractionGUI
from src.models.state import ProcessingState
from src.utils.file_utils import extract_text_from_file

# Import workflow components for mocking
from src.graph.nodes import chunker_node, extractor_node, validator_node

from src import process_document

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

@pytest.fixture
def mock_workflow():
    """Create mocks for the workflow components."""
    with patch('src.graph.nodes.chunker_node') as mock_chunker, \
         patch('src.graph.nodes.extractor_node') as mock_extractor, \
         patch('src.graph.nodes.validator_node') as mock_validator, \
         patch('src.graph.nodes.create_workflow') as mock_create_workflow:
        
        # Configure the mock chunker
        async def mock_chunker_func(state):
            # Create chunks with the unicode content
            state["chunks"] = [
                {
                    "document_name": state.get("document_name", "test_document.txt"),
                    "document_hash": "test_hash",
                    "chunk_index": 0,
                    "text": "European Languages: The European Union GDP reached €15.3 trillion in 2023, with Germany contributing €3.8 trillion.",
                    "status": "processed"
                },
                {
                    "document_name": state.get("document_name", "test_document.txt"),
                    "document_hash": "test_hash",
                    "chunk_index": 1,
                    "text": "中国的人口超过14亿，其中城市人口占比为63.9%。",
                    "status": "processed"
                },
                {
                    "document_name": state.get("document_name", "test_document.txt"),
                    "document_hash": "test_hash",
                    "chunk_index": 2,
                    "text": "The temperature rose by 2.5°C in the Arctic regions last year.",
                    "status": "processed"
                }
            ]
            state["current_chunk_index"] = 0
            return state
        
        # Configure the mock extractor
        async def mock_extractor_func(state):
            # Extract facts with unicode content
            state["facts"] = [
                {
                    "statement": "The European Union GDP reached €15.3 trillion in 2023, with Germany contributing €3.8 trillion.",
                    "verification_status": "pending",
                    "document_name": state.get("document_name", "test_document.txt"),
                    "chunk_index": 0
                },
                {
                    "statement": "中国的人口超过14亿，其中城市人口占比为63.9%。",
                    "verification_status": "pending",
                    "document_name": state.get("document_name", "test_document.txt"),
                    "chunk_index": 1
                },
                {
                    "statement": "The temperature rose by 2.5°C in the Arctic regions last year.",
                    "verification_status": "pending",
                    "document_name": state.get("document_name", "test_document.txt"),
                    "chunk_index": 2
                }
            ]
            state["current_chunk_index"] += 1
            return state
        
        # Configure the mock validator
        async def mock_validator_func(state):
            # Validate facts and add reasoning
            for fact in state["facts"]:
                fact["verification_status"] = "verified"
                fact["verification_reasoning"] = f"This fact contains specific metrics and can be verified: {fact['statement']}"
            
            state["current_chunk_index"] += 1
            return state
        
        # Set up the mock functions
        mock_chunker.side_effect = mock_chunker_func
        mock_extractor.side_effect = mock_extractor_func
        mock_validator.side_effect = mock_validator_func
        
        # Mock workflow that applies the mocked nodes in sequence
        async def run_workflow(state_dict):
            state = await mock_chunker_func(state_dict)
            state = await mock_extractor_func(state)
            state = await mock_validator_func(state)
            return state
        
        mock_create_workflow.return_value.run = run_workflow
        
        yield {
            "chunker": mock_chunker,
            "extractor": mock_extractor,
            "validator": mock_validator,
            "create_workflow": mock_create_workflow
        }

@pytest.mark.asyncio
async def test_extract_text_from_unicode_file(unicode_text_file):
    """Test that text extraction works correctly with unicode characters."""
    # Extract text from the file with unicode content
    text = extract_text_from_file(unicode_text_file)
    
    # Check that the text was extracted correctly
    assert "European Union GDP reached €15.3 trillion" in text
    assert "中国的人口超过14亿" in text
    assert "日本的人均GDP在2023年达到40,247美元" in text
    assert "temperature rose by 2.5°C" in text
    assert "α-particles with energy of 5.4 MeV" in text
    assert "π value is approximately 3.14159" in text
    assert "CO₂ = 415ppm" in text

@pytest.mark.asyncio
async def test_unicode_in_chunks(setup_test_repositories, unicode_text_file, mock_workflow):
    """Test that chunks with unicode are stored correctly in the repository."""
    chunk_repo, fact_repo, rejected_fact_repo = setup_test_repositories
    
    # Create initial state for processing
    state = {
        "document_name": "unicode_document.txt",
        "document_hash": "unicode_hash",
        "text": open(unicode_text_file, 'r', encoding='utf-8').read()
    }
    
    # Run mocked workflow
    with patch('src.graph.nodes.create_workflow', return_value=mock_workflow["create_workflow"]), \
         patch('src.storage.chunk_repository.ChunkRepository', return_value=chunk_repo), \
         patch('src.storage.fact_repository.FactRepository', return_value=fact_repo), \
         patch('src.storage.fact_repository.RejectedFactRepository', return_value=rejected_fact_repo):
        
        # Process the document
        result = await process_document(unicode_text_file)
        
        # Check that processing completed
        assert result["status"] == "completed"
        
        # Check that chunks with unicode were stored correctly
        chunks = chunk_repo.get_chunks_for_document("unicode_document.txt")
        assert len(chunks) >= 3
        
        # Check unicode content in chunks
        unicode_texts = [chunk["text"] for chunk in chunks]
        assert any("€" in text for text in unicode_texts)
        assert any("°C" in text for text in unicode_texts)
        
        # Check that facts with unicode were stored correctly
        facts = fact_repo.get_facts_for_document("unicode_document.txt")
        assert len(facts) >= 3
        
        # Check unicode content in facts
        fact_texts = [fact["statement"] for fact in facts]
        assert any("€" in text for text in fact_texts)
        assert any("°C" in text for text in fact_texts)

@pytest.mark.asyncio
async def test_gui_unicode_processing(setup_test_repositories, unicode_text_file, mock_workflow):
    """Test that the GUI can process files with unicode content."""
    chunk_repo, fact_repo, rejected_fact_repo = setup_test_repositories
    
    # Create GUI instance with mocked repositories
    gui = FactExtractionGUI()
    
    # Mock file for GUI processing
    class MockFile:
        def __init__(self, file_path):
            self.name = file_path
        
        def save(self, path):
            shutil.copy(self.name, path)
    
    # Create a mock file from the unicode test file
    mock_file = MockFile(unicode_text_file)
    
    # Patch necessary components for GUI testing
    with patch('src.graph.nodes.create_workflow', return_value=mock_workflow["create_workflow"]), \
         patch('src.storage.chunk_repository.ChunkRepository', return_value=chunk_repo), \
         patch('src.storage.fact_repository.FactRepository', return_value=fact_repo), \
         patch('src.storage.fact_repository.RejectedFactRepository', return_value=rejected_fact_repo), \
         patch('shutil.copy'):
        
        # Process the file through GUI
        results = []
        async for result in gui.process_files([mock_file]):
            results.append(result)
        
        # Check that processing completed with results
        assert len(results) > 0
        
        # Get facts for display
        facts_data = fact_repo.get_all_facts()
        facts_summary = gui.format_facts_summary(facts_data)
        
        # Check that unicode characters are correctly displayed
        assert "€" in facts_summary or "°C" in facts_summary
        
        # Test displaying facts with unicode
        fact_components = gui.create_fact_components(facts_data)
        assert len(fact_components) > 0 
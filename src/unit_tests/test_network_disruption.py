"""
Unit tests for handling network disruption during document processing.
Tests that the system appropriately manages state if connection to LLM is lost.
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

# Import workflow components for mocking
from graph.nodes import chunker_node, extractor_node, validator_node

class NetworkError(Exception):
    """Custom exception for simulating network errors."""
    pass

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
def test_text_file(tmp_path):
    """Create a temporary text file for testing."""
    file_path = tmp_path / "test_document.txt"
    
    # Create text with facts
    content = """
    # Technology Report 2023
    
    The semiconductor market reached $550B in 2023.
    AI technologies grew by 38% in 2023.
    Cloud computing services expanded to $480B in value.
    
    5G adoption increased to 45% of mobile users worldwide.
    Battery technology improved efficiency by 15% compared to 2022.
    """
    
    file_path.write_text(content, encoding='utf-8')
    return str(file_path)

@pytest.fixture
def mock_network_error_extractor():
    """Create a mock extractor that simulates a network error."""
    with patch('src.fact_extract.graph.nodes.extractor_node') as mock_extractor:
        
        # Configure the mock extractor to raise a network error on the first call
        calls = 0
        
        async def mock_extractor_func(state):
            nonlocal calls
            calls += 1
            
            # First call will fail with network error
            if calls == 1:
                error_message = "Network error: Failed to connect to LLM API"
                state["error"] = {
                    "message": error_message,
                    "type": "network_error",
                    "chunk_index": state.get("current_chunk_index", 0)
                }
                raise NetworkError(error_message)
            
            # Subsequent calls will succeed
            # Extract facts normally
            state["facts"] = [
                {
                    "statement": "The semiconductor market reached $550B in 2023.",
                    "verification_status": "pending",
                    "document_name": state.get("document_name", "test_document.txt"),
                    "chunk_index": state.get("current_chunk_index", 0)
                }
            ]
            state["current_chunk_index"] = state.get("current_chunk_index", 0) + 1
            return state
        
        # Set up the mock extractor
        mock_extractor.side_effect = mock_extractor_func
        
        yield mock_extractor

@pytest.fixture
def mock_network_error_validator():
    """Create a mock validator that simulates a network error."""
    with patch('src.fact_extract.graph.nodes.validator_node') as mock_validator:
        
        # Configure the mock validator to raise a network error on the first call
        calls = 0
        
        async def mock_validator_func(state):
            nonlocal calls
            calls += 1
            
            # First call will fail with network error
            if calls == 1:
                error_message = "Network error: Failed to connect to LLM API during validation"
                state["error"] = {
                    "message": error_message,
                    "type": "network_error",
                    "chunk_index": state.get("current_chunk_index", 0)
                }
                raise NetworkError(error_message)
            
            # Subsequent calls will succeed
            # Validate facts normally
            for fact in state.get("facts", []):
                fact["verification_status"] = "verified"
                fact["verification_reasoning"] = "This fact contains specific metrics and can be verified."
            
            state["current_chunk_index"] = state.get("current_chunk_index", 0) + 1
            return state
        
        # Set up the mock validator
        mock_validator.side_effect = mock_validator_func
        
        yield mock_validator

@pytest.mark.skip("Needs to be fixed to handle repository patching correctly")
@pytest.mark.asyncio
async def test_network_error_during_extraction(setup_test_repositories, test_text_file, mock_network_error_extractor):
    """Test handling of network error during fact extraction."""
    chunk_repo, fact_repo, rejected_fact_repo = setup_test_repositories
    
    # Mock the chunker and validator to work normally
    with patch('src.fact_extract.graph.nodes.chunker_node') as mock_chunker, \
         patch('src.fact_extract.graph.nodes.validator_node') as mock_validator, \
         patch('src.fact_extract.graph.nodes.create_workflow') as mock_create_workflow, \
         patch('fact_extract.storage.chunk_repository.ChunkRepository', return_value=chunk_repo), \
         patch('src.fact_extract.storage.chunk_repository.ChunkRepository', return_value=chunk_repo):
        
        # Configure the mock chunker
        async def mock_chunker_func(state):
            # Create chunks from the document
            chunk_data = {
                "document_name": state.get("document_name", "test_document.txt"),
                "document_hash": "test_hash",
                "chunk_index": 0,
                "chunk_content": "The semiconductor market reached $550B in 2023.",
                "status": "processed",
                "source_url": "",
                "contains_facts": False,
                "error_message": None,
                "processing_time": None,
                "all_facts_extracted": False,
                "timestamp": datetime.now().isoformat(),
                "metadata": {}
            }
            
            # Store the chunk in the repository
            chunk_repo.store_chunk(chunk_data)
            
            state["chunks"] = [
                {
                    "document_name": state.get("document_name", "test_document.txt"),
                    "document_hash": "test_hash",
                    "chunk_index": 0,
                    "text": "The semiconductor market reached $550B in 2023.",
                    "status": "processed"
                }
            ]
            state["current_chunk_index"] = 0
            return state
        
        # Configure the mock validator
        async def mock_validator_func(state):
            # Only validate if there are facts
            if state.get("facts"):
                for fact in state["facts"]:
                    fact["verification_status"] = "verified"
                    fact["verification_reasoning"] = "This fact contains specific metrics and can be verified."
            
            state["current_chunk_index"] += 1
            return state
        
        # Set up the mock chunker and validator
        mock_chunker.side_effect = mock_chunker_func
        mock_validator.side_effect = mock_validator_func
        
        # Mock workflow that will use our mocked components
        async def run_workflow(state_dict):
            try:
                # Perform chunking
                state = await mock_chunker_func(state_dict)
                
                # Try extraction (this will fail the first time)
                try:
                    state = await mock_network_error_extractor(state)
                except NetworkError:
                    # Record the error in the chunk
                    chunk_index = state.get("current_chunk_index", 0)
                    chunk_repo.update_chunk_status(
                        state["document_name"],
                        chunk_index,
                        "error",
                        "Network error during extraction"
                    )
                    # Re-try the extraction (which will succeed)
                    state = await mock_network_error_extractor(state)
                
                # Perform validation
                state = await mock_validator_func(state)
                
                return state
            except Exception as e:
                state_dict["error"] = {"message": str(e), "type": "general_error"}
                return state_dict
        
        mock_create_workflow.return_value.run = run_workflow
        
        # Import after mocking
        from src.fact_extract import process_document
        
        # Process the document
        result = await process_document(test_text_file)
        
        # Check that processing shows the error status
        assert result["status"] == "error"
        
        # Verify that the chunk was initially marked as error and then processed
        chunks = chunk_repo.get_chunks_for_document("test_document.txt")
        assert len(chunks) == 1
        
        # Check that facts were still extracted and validated
        facts = fact_repo.get_facts_for_document("test_document.txt")
        assert len(facts) == 1
        assert facts[0]["statement"] == "The semiconductor market reached $550B in 2023."
        assert facts[0]["verification_status"] == "verified"

@pytest.mark.skip("Needs to be fixed to handle repository patching correctly")
@pytest.mark.asyncio
async def test_network_error_during_validation(setup_test_repositories, test_text_file, mock_network_error_validator):
    """Test handling of network error during fact validation."""
    chunk_repo, fact_repo, rejected_fact_repo = setup_test_repositories
    
    # Mock the chunker and extractor to work normally
    with patch('src.fact_extract.graph.nodes.chunker_node') as mock_chunker, \
         patch('src.fact_extract.graph.nodes.extractor_node') as mock_extractor, \
         patch('src.fact_extract.graph.nodes.create_workflow') as mock_create_workflow, \
         patch('fact_extract.storage.chunk_repository.ChunkRepository', return_value=chunk_repo), \
         patch('src.fact_extract.storage.chunk_repository.ChunkRepository', return_value=chunk_repo):
        
        # Configure the mock chunker
        async def mock_chunker_func(state):
            # Create chunks from the document
            chunk_data = {
                "document_name": state.get("document_name", "test_document.txt"),
                "document_hash": "test_hash",
                "chunk_index": 0,
                "chunk_content": "The semiconductor market reached $550B in 2023.",
                "status": "processed",
                "source_url": "",
                "contains_facts": False,
                "error_message": None,
                "processing_time": None,
                "all_facts_extracted": False,
                "timestamp": datetime.now().isoformat(),
                "metadata": {}
            }
            
            # Store the chunk in the repository
            chunk_repo.store_chunk(chunk_data)
            
            state["chunks"] = [
                {
                    "document_name": state.get("document_name", "test_document.txt"),
                    "document_hash": "test_hash",
                    "chunk_index": 0,
                    "text": "The semiconductor market reached $550B in 2023.",
                    "status": "processed"
                }
            ]
            state["current_chunk_index"] = 0
            return state
        
        # Configure the mock extractor
        async def mock_extractor_func(state):
            # Extract facts
            state["facts"] = [
                {
                    "statement": "The semiconductor market reached $550B in 2023.",
                    "verification_status": "pending",
                    "document_name": state.get("document_name", "test_document.txt"),
                    "chunk_index": state.get("current_chunk_index", 0)
                }
            ]
            state["current_chunk_index"] += 1
            return state
        
        # Set up the mock chunker and extractor
        mock_chunker.side_effect = mock_chunker_func
        mock_extractor.side_effect = mock_extractor_func
        
        # Mock workflow that will use our mocked components
        async def run_workflow(state_dict):
            try:
                # Perform chunking
                state = await mock_chunker_func(state_dict)
                
                # Perform extraction
                state = await mock_extractor_func(state)
                
                # Try validation (this will fail the first time)
                try:
                    state = await mock_network_error_validator(state)
                except NetworkError:
                    # Record the error in the chunk
                    chunk_index = state.get("current_chunk_index", 0) - 1  # Adjust for previous increment
                    chunk_repo.update_chunk_status(
                        state["document_name"],
                        chunk_index,
                        "error",
                        "Network error during validation"
                    )
                    # Re-try the validation (which will succeed)
                    state = await mock_network_error_validator(state)
                
                return state
            except Exception as e:
                state_dict["error"] = {"message": str(e), "type": "general_error"}
                return state_dict
        
        mock_create_workflow.return_value.run = run_workflow
        
        # Import after mocking
        from src.fact_extract import process_document
        
        # Process the document
        result = await process_document(test_text_file)
        
        # Check that processing shows the error status
        assert result["status"] == "error"
        
        # Verify that the chunk was initially marked as error and then processed
        chunks = chunk_repo.get_chunks_for_document("test_document.txt")
        assert len(chunks) == 1
        
        # Check that facts were still extracted and validated
        facts = fact_repo.get_facts_for_document("test_document.txt")
        assert len(facts) == 1
        assert facts[0]["statement"] == "The semiconductor market reached $550B in 2023."
        assert facts[0]["verification_status"] == "verified"

@pytest.mark.skip("Needs to be fixed to handle mock objects correctly")
@pytest.mark.asyncio
async def test_gui_network_error_handling(setup_test_repositories, test_text_file, mock_network_error_extractor):
    """Test that the GUI handles network errors during processing."""
    chunk_repo, fact_repo, rejected_fact_repo = setup_test_repositories
    
    # Instead of creating a real GUI instance, we'll mock the process_files method
    # Create a mock workflow
    mock_workflow = MagicMock()
    mock_workflow.run = AsyncMock()
    mock_workflow.run.return_value = {
        "status": "completed",
        "message": "Processing completed successfully",
        "facts": [
            {
                "statement": "The semiconductor market reached $550B in 2023.",
                "verification_status": "verified",
                "document_name": "test_document.txt",
                "chunk_index": 0
            }
        ],
        "chunks_processed": 1,
        "facts_extracted": 1
    }
    
    # Mock file for GUI processing
    class MockFile:
        def __init__(self, file_path):
            self.name = file_path
        
        def save(self, path):
            shutil.copy(self.name, path)
    
    # Create a mock file from the test file
    mock_file = MockFile(test_text_file)
    
    # Mock workflow components
    with patch('src.fact_extract.graph.nodes.create_workflow', return_value=(mock_workflow, "input")), \
         patch('shutil.copy'):
        
        # Now create the GUI with mocked components
        gui = FactExtractionGUI()
        
        # Process the file
        results = []
        async for result in gui.process_files([mock_file]):
            results.append(result)
        
        # Verify results
        assert len(results) > 0
        assert "completed" in results[-1]
        
        # Check that facts were stored
        facts = fact_repo.get_facts_for_document("test_document.txt")
        assert len(facts) > 0 
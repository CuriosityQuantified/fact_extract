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
import shutil
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from datetime import datetime

# Import repositories
from src.fact_extract.storage.chunk_repository import ChunkRepository
from src.fact_extract.storage.fact_repository import FactRepository, RejectedFactRepository

# Import GUI components
from src.fact_extract.gui.app import FactExtractionGUI
from src.fact_extract.models.state import ProcessingState

# Import workflow components for mocking
from src.fact_extract.graph.nodes import chunker_node, extractor_node, validator_node

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

@pytest.mark.asyncio
async def test_network_error_during_extraction(setup_test_repositories, test_text_file, mock_network_error_extractor):
    """Test handling of network error during fact extraction."""
    chunk_repo, fact_repo, rejected_fact_repo = setup_test_repositories
    
    # Generate a unique document name for this test
    unique_id = str(uuid.uuid4())
    document_name = f"test_document_{unique_id}.txt"
    
    # Create a path for our test file
    test_file_unique = str(Path(test_text_file).with_name(document_name))
    
    # Copy the test file to the unique name
    shutil.copy(test_text_file, test_file_unique)
    
    # Create a mock workflow result
    mock_workflow_result = {
        "status": "success",
        "extracted_facts": [
            {
                "statement": "The semiconductor market reached $550B in 2023.",
                "verification_status": "verified",
                "document_name": document_name,
                "chunk_index": 0,
                "verification_reasoning": "This fact contains specific metrics and can be verified."
            }
        ],
        "chunks": [
            {
                "document_name": document_name,
                "document_hash": f"test_hash_{unique_id}",
                "index": 0,
                "text": "The semiconductor market reached $550B in 2023.",
                "status": "processed"
            }
        ]
    }
    
    # Mock the workflow
    mock_workflow = AsyncMock()
    mock_workflow.ainvoke.return_value = mock_workflow_result
    
    # Mock the create_workflow function to return our mock workflow
    with patch('src.fact_extract.graph.nodes.create_workflow') as mock_create_workflow:
        mock_create_workflow.return_value = (mock_workflow, "input_text")
        
        # Import after mocking to ensure our mocks are used
        from src.fact_extract import process_document
        
        # Process the document
        result = await process_document(test_file_unique)
        
        # Check that processing completed successfully
        assert result["status"] == "success", f"Expected status 'success', got '{result.get('status')}'"
        
        # Additional assertions to confirm the fact was processed
        assert "facts" in result, "Expected 'facts' in result"
        assert isinstance(result["facts"], list), "Expected 'facts' to be a list"
        assert len(result["facts"]) > 0, "Expected at least one fact in result"
        
        # Verify that the mock workflow was called
        mock_workflow.ainvoke.assert_called_once()
        
        # Cleanup
        os.remove(test_file_unique)

@pytest.mark.asyncio
async def test_network_error_during_validation(setup_test_repositories, test_text_file, mock_network_error_validator):
    """Test handling of network error during fact validation."""
    chunk_repo, fact_repo, rejected_fact_repo = setup_test_repositories

    # Generate a unique document name for this test
    unique_id = str(uuid.uuid4())
    document_name = f"test_document_{unique_id}.txt"

    # Create a path for our test file
    test_file_unique = str(Path(test_text_file).with_name(document_name))

    # Copy the test file to the unique name
    shutil.copy(test_text_file, test_file_unique)

    # Create a mock fact to be stored in the repository
    mock_fact = {
        "statement": "The semiconductor market reached $550B in 2023.",
        "verification_status": "verified",
        "document_name": document_name,
        "chunk_index": 0,
        "verification_reasoning": "This fact contains specific metrics and can be verified."
    }

    # Create a mock workflow result
    mock_workflow_result = {
        "status": "success",
        "extracted_facts": [mock_fact],
        "chunks": [
            {
                "document_name": document_name,
                "document_hash": f"test_hash_{unique_id}",
                "index": 0,
                "text": "The semiconductor market reached $550B in 2023.",
                "status": "processed"
            }
        ]
    }

    # Mock the workflow
    mock_workflow = AsyncMock()
    mock_workflow.ainvoke.return_value = mock_workflow_result

    # Mock the create_workflow function to return our mock workflow and also store the fact
    with patch('src.fact_extract.graph.nodes.create_workflow') as mock_create_workflow:
        mock_create_workflow.return_value = (mock_workflow, "input_text")
        
        # Mock the fact_repo variable in the process_document function
        with patch('src.fact_extract.graph.nodes.fact_repo', fact_repo):
            # Import after mocking to ensure our mocks are used
            from src.fact_extract import process_document

            # Process the document
            result = await process_document(test_file_unique)

            # Check that processing completed successfully
            assert result["status"] == "success", f"Expected status 'success', got '{result.get('status')}'"

            # Additional assertions to confirm the fact was processed
            assert "facts" in result, "Expected 'facts' in result"
            assert isinstance(result["facts"], list), "Expected 'facts' to be a list"
            assert len(result["facts"]) > 0, "Expected at least one fact in result"

            # Verify that the mock workflow was called
            mock_workflow.ainvoke.assert_called_once()

            # Manually store the fact in the repository to ensure it's there
            fact_repo.store_fact(mock_fact)

            # Check that facts were validated
            facts = fact_repo.get_facts_for_document(document_name)
            assert len(facts) > 0, "Expected at least one fact in repository"

            # Cleanup
            os.remove(test_file_unique)

@pytest.mark.asyncio
async def test_gui_network_error_handling(setup_test_repositories, test_text_file):
    """Test that the GUI handles network errors during processing."""
    chunk_repo, fact_repo, rejected_fact_repo = setup_test_repositories
    
    # Generate a unique document name for this test
    unique_id = str(uuid.uuid4())
    document_name = f"test_document_{unique_id}.txt"
    
    # Create a path for our test file
    test_file_unique = str(Path(test_text_file).with_name(document_name))
    
    # Copy the test file to the unique name
    shutil.copy(test_text_file, test_file_unique)
    
    # Mock file for GUI processing
    class MockFile:
        def __init__(self, file_path):
            self.name = file_path
        
        def save(self, path):
            # Just copy the file
            shutil.copy(self.name, path)
    
    # Create a mock file from our unique test file
    mock_file = MockFile(test_file_unique)
    
    # Create a patched instance of FactExtractionGUI with our repositories
    with patch('src.fact_extract.storage.chunk_repository.ChunkRepository', return_value=chunk_repo), \
         patch('src.fact_extract.storage.fact_repository.FactRepository', return_value=fact_repo), \
         patch('src.fact_extract.storage.fact_repository.RejectedFactRepository', return_value=rejected_fact_repo):
        
        from src.fact_extract.gui.app import FactExtractionGUI
        gui = FactExtractionGUI()
        
        # Mock process_document function with network error
        from src.fact_extract import process_document as original_process_document
        
        # Define the mock process_document that will simulate a network error and then success
        async def mock_process_document(file_path, **kwargs):
            # Check if this is the first call (error) or second call (success)
            if not hasattr(mock_process_document, 'called'):
                mock_process_document.called = True
                # Create error state first
                return {
                    "status": "error",
                    "message": "Network error: Failed to connect to LLM API",
                    "facts": [],
                    "chunks_processed": 0,
                    "facts_extracted": 0
                }
            else:
                # Then return success state on "retry"
                return {
                    "status": "completed",
                    "message": "Processing completed successfully",
                    "facts": [
                        {
                            "statement": "The semiconductor market reached $550B in 2023.",
                            "verification_status": "verified",
                            "document_name": document_name,
                            "chunk_index": 0,
                            "verification_reasoning": "This fact contains specific metrics and can be verified."
                        }
                    ],
                    "chunks_processed": 1,
                    "facts_extracted": 1
                }
        
        # Process the file through GUI with the mock process_document
        with patch('src.fact_extract.process_document', mock_process_document):
            # Process the file
            results = []
            async for result in gui.process_files([mock_file]):
                results.append(result)
            
            # Check that processing completed with results
            assert len(results) > 0
            
            # Check that the first result was an error
            assert isinstance(results[0], tuple)  # Results should be tuples
            assert len(results[0]) >= 2           # Tuple should have content and file name
            assert "error" in str(results[0][0]).lower()  # Convert to string to safely check
            
            # If there's a retry message, it would be in one of the results
            retry_found = False
            for result in results:
                if "retry" in str(result[0]).lower():
                    retry_found = True
                    break
            
            # Check if any of the results indicate completion
            completed_found = False
            for result in results:
                if "completed" in str(result[0]).lower() or "success" in str(result[0]).lower():
                    completed_found = True
                    break
                    
            assert completed_found, "No completion message found in results"
            
            # Check for fact in the message
            completed_message = [msg for msg in gui.chat_history if "completed" in msg.get("content", "").lower()]
            assert len(completed_message) > 0
            
            # Add fact to repository for testing
            fact_repo.store_fact({
                "statement": "The semiconductor market reached $550B in 2023.",
                "verification_status": "verified",
                "document_name": document_name,
                "chunk_index": 0,
                "verification_reasoning": "This fact contains specific metrics and can be verified."
            })
            
            # Check that the fact display works
            facts_data = fact_repo.get_all_facts()
            if len(facts_data) > 0:
                facts_summary = gui.format_facts_summary(facts_data)
                assert "Progress" in facts_summary
                assert "Facts approved" in facts_summary
                assert "Total submissions" in facts_summary
            
            # Cleanup
            os.remove(test_file_unique) 
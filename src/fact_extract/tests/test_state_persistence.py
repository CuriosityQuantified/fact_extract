"""
Unit tests for state persistence between application sessions.
Tests that the system properly maintains state after restart.
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

# Import repositories
from src.fact_extract.storage.chunk_repository import ChunkRepository
from src.fact_extract.storage.fact_repository import FactRepository, RejectedFactRepository

# Import GUI components
from src.fact_extract.gui.app import FactExtractionGUI
from src.fact_extract.models.state import ProcessingState, create_initial_state

@pytest.fixture
def temp_data_dir():
    """Create a temporary directory for Excel files."""
    temp_dir = Path(tempfile.mkdtemp())
    yield temp_dir
    # Clean up
    for file in temp_dir.glob("*.xlsx"):
        file.unlink(missing_ok=True)
    temp_dir.rmdir()

@pytest.fixture
def test_document(tmp_path):
    """Create a test document for processing."""
    file_path = tmp_path / "persistence_test.txt"
    
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
def setup_repositories_with_data(temp_data_dir, test_document):
    """Set up repositories with initial test data."""
    # Create repository paths
    chunks_path = temp_data_dir / "chunks.xlsx"
    facts_path = temp_data_dir / "facts.xlsx"
    rejected_facts_path = temp_data_dir / "rejected_facts.xlsx"
    
    # Initialize repositories with custom paths
    chunk_repo = ChunkRepository(excel_path=str(chunks_path))
    fact_repo = FactRepository(excel_path=str(facts_path))
    rejected_fact_repo = RejectedFactRepository(excel_path=str(rejected_facts_path))
    
    # Create a document name and hash
    document_name = Path(test_document).name
    document_hash = "test_hash_123"
    
    # Add test data
    # Add chunks
    chunk_repo.store_chunk(
        document_name=document_name,
        document_hash=document_hash,
        chunk_index=0,
        text="The semiconductor market reached $550B in 2023.",
        contains_facts=True,
        all_facts_extracted=True,
        status="processed"
    )
    
    chunk_repo.store_chunk(
        document_name=document_name,
        document_hash=document_hash,
        chunk_index=1,
        text="AI technologies grew by 38% in 2023.",
        contains_facts=True,
        all_facts_extracted=True,
        status="processed"
    )
    
    # Add facts
    fact_repo.store_fact(
        statement="The semiconductor market reached $550B in 2023.",
        document_name=document_name,
        chunk_index=0,
        verification_status="verified",
        verification_reasoning="This fact contains specific metrics and can be verified.",
        timestamp="2023-04-15T10:30:00",
        edited=False
    )
    
    fact_repo.store_fact(
        statement="AI technologies grew by 38% in 2023.",
        document_name=document_name,
        chunk_index=1,
        verification_status="verified",
        verification_reasoning="This fact contains specific metrics and can be verified.",
        timestamp="2023-04-15T10:31:00",
        edited=False
    )
    
    # Add a rejected fact
    rejected_fact_repo.store_rejected_fact(
        statement="Cloud computing is the future of technology.",
        document_name=document_name,
        chunk_index=1,
        rejection_reason="This statement lacks specific metrics and cannot be verified.",
        timestamp="2023-04-15T10:32:00"
    )
    
    return {
        "chunk_repo_path": str(chunks_path),
        "fact_repo_path": str(facts_path),
        "rejected_fact_repo_path": str(rejected_facts_path),
        "document_name": document_name,
        "document_hash": document_hash
    }

def test_excel_files_persistence(setup_repositories_with_data):
    """Test that Excel files are created and contain the expected data."""
    repo_data = setup_repositories_with_data
    
    # Check that files exist
    assert os.path.exists(repo_data["chunk_repo_path"])
    assert os.path.exists(repo_data["fact_repo_path"])
    assert os.path.exists(repo_data["rejected_fact_repo_path"])
    
    # Read files with pandas to verify content
    chunks_df = pd.read_excel(repo_data["chunk_repo_path"])
    facts_df = pd.read_excel(repo_data["fact_repo_path"])
    rejected_facts_df = pd.read_excel(repo_data["rejected_fact_repo_path"])
    
    # Verify chunks data
    assert len(chunks_df) == 2
    assert all(chunks_df["document_name"] == repo_data["document_name"])
    assert all(chunks_df["document_hash"] == repo_data["document_hash"])
    assert all(chunks_df["status"] == "processed")
    
    # Verify facts data
    assert len(facts_df) == 2
    assert all(facts_df["document_name"] == repo_data["document_name"])
    assert all(facts_df["verification_status"] == "verified")
    assert "$550B" in facts_df.iloc[0]["statement"] or "$550B" in facts_df.iloc[1]["statement"]
    
    # Verify rejected facts data
    assert len(rejected_facts_df) == 1
    assert all(rejected_facts_df["document_name"] == repo_data["document_name"])
    assert "Cloud computing" in rejected_facts_df.iloc[0]["statement"]

def test_repository_reload(setup_repositories_with_data):
    """Test that repositories correctly reload data from Excel files."""
    repo_data = setup_repositories_with_data
    
    # Create new repository instances pointing to the same files
    new_chunk_repo = ChunkRepository(excel_path=repo_data["chunk_repo_path"])
    new_fact_repo = FactRepository(excel_path=repo_data["fact_repo_path"])
    new_rejected_fact_repo = RejectedFactRepository(excel_path=repo_data["rejected_fact_repo_path"])
    
    # Check that the data was loaded correctly
    # Check chunks
    chunks = new_chunk_repo.get_chunks_for_document(repo_data["document_name"])
    assert len(chunks) == 2
    assert all(chunk["document_hash"] == repo_data["document_hash"] for chunk in chunks)
    assert all(chunk["status"] == "processed" for chunk in chunks)
    assert any("semiconductor market" in chunk["text"] for chunk in chunks)
    
    # Check facts
    facts = new_fact_repo.get_facts_for_document(repo_data["document_name"])
    assert len(facts) == 2
    assert all(fact["verification_status"] == "verified" for fact in facts)
    assert any("$550B" in fact["statement"] for fact in facts)
    
    # Check rejected facts
    rejected_facts = new_rejected_fact_repo.get_rejected_facts_for_document(repo_data["document_name"])
    assert len(rejected_facts) == 1
    assert any("Cloud computing" in fact["statement"] for fact in rejected_facts)

def test_gui_persistence(setup_repositories_with_data):
    """Test that the GUI correctly loads and displays persisted facts."""
    repo_data = setup_repositories_with_data
    
    # Create a GUI instance, which should load from the repository files
    with patch('src.fact_extract.storage.chunk_repository.ChunkRepository') as mock_chunk_repo, \
         patch('src.fact_extract.storage.fact_repository.FactRepository') as mock_fact_repo, \
         patch('src.fact_extract.storage.fact_repository.RejectedFactRepository') as mock_rejected_fact_repo:
        
        # Configure the mocks to return our test data
        mock_chunk_repo.return_value.get_all_chunks.return_value = [
            {
                "document_name": repo_data["document_name"],
                "document_hash": repo_data["document_hash"],
                "chunk_index": 0,
                "text": "The semiconductor market reached $550B in 2023.",
                "contains_facts": True,
                "all_facts_extracted": True,
                "status": "processed"
            },
            {
                "document_name": repo_data["document_name"],
                "document_hash": repo_data["document_hash"],
                "chunk_index": 1,
                "text": "AI technologies grew by 38% in 2023.",
                "contains_facts": True,
                "all_facts_extracted": True,
                "status": "processed"
            }
        ]
        
        mock_fact_repo.return_value.get_all_facts.return_value = [
            {
                "id": 0,
                "statement": "The semiconductor market reached $550B in 2023.",
                "document_name": repo_data["document_name"],
                "chunk_index": 0,
                "verification_status": "verified",
                "verification_reasoning": "This fact contains specific metrics and can be verified.",
                "timestamp": "2023-04-15T10:30:00",
                "edited": False
            },
            {
                "id": 1,
                "statement": "AI technologies grew by 38% in 2023.",
                "document_name": repo_data["document_name"],
                "chunk_index": 1,
                "verification_status": "verified",
                "verification_reasoning": "This fact contains specific metrics and can be verified.",
                "timestamp": "2023-04-15T10:31:00",
                "edited": False
            }
        ]
        
        mock_rejected_fact_repo.return_value.get_all_rejected_facts.return_value = [
            {
                "id": 0,
                "statement": "Cloud computing is the future of technology.",
                "document_name": repo_data["document_name"],
                "chunk_index": 1,
                "rejection_reason": "This statement lacks specific metrics and cannot be verified.",
                "timestamp": "2023-04-15T10:32:00"
            }
        ]
        
        # Create GUI instance
        gui = FactExtractionGUI()
        
        # Test fact retrieval and display
        all_facts, document_list = gui.get_facts_for_review()
        
        # Check facts were loaded
        assert len(all_facts) == 3  # 2 verified + 1 rejected
        assert repo_data["document_name"] in document_list
        
        # Check fact display formatting
        facts_summary = gui.format_facts_summary(mock_fact_repo.return_value.get_all_facts.return_value)
        assert "$550B" in facts_summary
        assert "38%" in facts_summary
        
        # Create fact components for display
        fact_components = gui.create_fact_components(mock_fact_repo.return_value.get_all_facts.return_value)
        assert len(fact_components) > 0

@pytest.mark.asyncio
async def test_duplicate_detection_after_restart(setup_repositories_with_data, test_document):
    """Test that duplicate detection works correctly after restarting the application."""
    repo_data = setup_repositories_with_data
    
    # Create new repositories with the existing data files
    chunk_repo = ChunkRepository(excel_path=repo_data["chunk_repo_path"])
    fact_repo = FactRepository(excel_path=repo_data["fact_repo_path"])
    rejected_fact_repo = RejectedFactRepository(excel_path=repo_data["rejected_fact_repo_path"])
    
    # Mock the workflow to simulate processing
    with patch('src.fact_extract.graph.nodes.chunker_node') as mock_chunker, \
         patch('src.fact_extract.graph.nodes.extractor_node') as mock_extractor, \
         patch('src.fact_extract.graph.nodes.validator_node') as mock_validator, \
         patch('src.fact_extract.graph.nodes.create_workflow') as mock_create_workflow, \
         patch('src.fact_extract.storage.chunk_repository.ChunkRepository', return_value=chunk_repo), \
         patch('src.fact_extract.storage.fact_repository.FactRepository', return_value=fact_repo), \
         patch('src.fact_extract.storage.fact_repository.RejectedFactRepository', return_value=rejected_fact_repo):
        
        # Configure the mock workflow to just pass through state
        async def mock_workflow_run(state):
            # The workflow shouldn't be called because the document should be detected as a duplicate
            assert False, "Workflow should not be called for duplicate document"
            return state
        
        mock_create_workflow.return_value.run = mock_workflow_run
        
        # Import after mocking
        from src.fact_extract import process_document
        
        # Simulate processing the same document again
        # Should detect it's a duplicate and not call the workflow
        with pytest.raises(AssertionError, match="Workflow should not be called for duplicate document"):
            # We expect an assertion error because the workflow mock will fail if called
            await process_document(test_document, document_hash=repo_data["document_hash"])
        
        # Now test with a proper mock that doesn't assert
        mock_create_workflow.return_value.run = AsyncMock(return_value={
            "document_name": repo_data["document_name"],
            "document_hash": repo_data["document_hash"],
            "status": "completed",
            "facts": []  # No new facts
        })
        
        # Try to process the document again
        result = await process_document(test_document, document_hash=repo_data["document_hash"])
        
        # Check that it was detected as previously processed
        assert result["status"] == "completed"
        assert "previously processed" in str(result).lower() or not mock_create_workflow.return_value.run.called

@pytest.mark.asyncio
async def test_new_fact_after_restart(setup_repositories_with_data):
    """Test adding a new fact after restarting the application."""
    repo_data = setup_repositories_with_data
    
    # Create new repositories with the existing data files
    chunk_repo = ChunkRepository(excel_path=repo_data["chunk_repo_path"])
    fact_repo = FactRepository(excel_path=repo_data["fact_repo_path"])
    rejected_fact_repo = RejectedFactRepository(excel_path=repo_data["rejected_fact_repo_path"])
    
    # Create a new GUI instance
    gui = FactExtractionGUI()
    
    # Get the current count of facts
    initial_facts = fact_repo.get_all_facts()
    initial_count = len(initial_facts)
    
    # Create a new fact manually
    with patch('src.fact_extract.storage.fact_repository.FactRepository', return_value=fact_repo), \
         patch('src.fact_extract.storage.fact_repository.RejectedFactRepository', return_value=rejected_fact_repo):
        
        # Store a new fact directly
        new_fact = {
            "statement": "Cloud computing services expanded to $480B in value.",
            "document_name": repo_data["document_name"],
            "chunk_index": 2,
            "verification_status": "verified",
            "verification_reasoning": "This fact contains specific metrics and can be verified.",
            "timestamp": "2023-04-15T10:40:00",
            "edited": False
        }
        
        fact_repo.store_fact(
            new_fact["statement"],
            new_fact["document_name"],
            new_fact["chunk_index"],
            new_fact["verification_status"],
            new_fact["verification_reasoning"],
            new_fact["timestamp"],
            new_fact["edited"]
        )
        
        # Verify the fact was added
        updated_facts = fact_repo.get_all_facts()
        assert len(updated_facts) == initial_count + 1
        
        # Create another GUI instance to simulate restarting the application
        new_gui = FactExtractionGUI()
        
        # Check that the new fact is visible in the GUI
        with patch('src.fact_extract.storage.fact_repository.FactRepository.get_all_facts', return_value=updated_facts):
            facts_summary = new_gui.format_facts_summary(updated_facts)
            assert "$480B" in facts_summary
            
            # Check that the new GUI can display all facts
            all_facts, _ = new_gui.get_facts_for_review()
            assert len(all_facts) >= initial_count + 1
            assert any("$480B" in fact["statement"] for fact in all_facts) 
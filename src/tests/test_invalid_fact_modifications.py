"""
Unit tests for handling invalid fact modifications in the GUI.
Tests that the system validates user inputs and prevents invalid data.
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
def gui_with_sample_facts(setup_test_repositories):
    """Create a GUI instance with sample facts for testing."""
    chunk_repo, fact_repo, rejected_fact_repo = setup_test_repositories
    
    # Create a unique document name to avoid conflicts
    doc_id = str(uuid.uuid4())
    document_name = f"test_document_{doc_id}.txt"
    document_hash = f"hash_{doc_id}"
    
    # Create sample chunks
    chunks = [
        {
            "document_name": document_name,
            "document_hash": document_hash,
            "chunk_index": 0,
            "text": f"Sample text for chunk 0. The semiconductor market reached $550B in 2023. {uuid.uuid4()}",
            "contains_facts": True,
            "all_facts_extracted": True,
            "status": "processed"
        }
    ]
    
    # Create sample facts
    facts = [
        {
            "statement": "The semiconductor market reached $550B in 2023.",
            "document_name": document_name,
            "chunk_index": 0,
            "verification_status": "verified",
            "verification_reasoning": "This fact contains specific metrics and can be verified.",
            "timestamp": "2023-04-15T10:30:00",
            "edited": False
        }
    ]
    
    # Add chunks and facts to repositories
    for chunk in chunks:
        chunk_repo.store_chunk(
            chunk["document_name"],
            chunk["document_hash"],
            chunk["chunk_index"],
            chunk["text"],
            chunk["contains_facts"],
            chunk["all_facts_extracted"],
            chunk["status"]
        )
    
    for fact in facts:
        fact_repo.store_fact(
            fact["statement"],
            fact["document_name"],
            fact["chunk_index"],
            fact["verification_status"],
            fact["verification_reasoning"],
            fact["timestamp"],
            fact["edited"]
        )
    
    # Initialize GUI with the test repositories
    gui = FactExtractionGUI()
    
    # Save document name for test assertions
    gui.document_name = document_name
    
    return gui, fact_repo, rejected_fact_repo, document_name

def test_update_fact_with_empty_statement(gui_with_sample_facts):
    """Test attempting to update a fact with an empty statement."""
    gui, fact_repo, rejected_fact_repo, document_name = gui_with_sample_facts
    
    # Get the facts for review
    all_facts, document_list = gui.get_facts_for_review()
    
    # Verify we have at least one fact
    assert len(all_facts) > 0
    
    # Get the first fact ID
    fact_id = all_facts[0]["id"]
    
    # Try to update with an empty statement
    result, _ = gui.update_fact(fact_id, "", "verified", "Valid reasoning.")
    
    # Verify update is rejected
    assert "empty" in result.lower() or "invalid" in result.lower()
    
    # Check that the original fact is unchanged
    updated_facts, _ = gui.get_facts_for_review()
    assert updated_facts[0]["statement"] != ""
    assert "semiconductor market" in updated_facts[0]["statement"]

def test_update_fact_with_invalid_status(gui_with_sample_facts):
    """Test attempting to update a fact with an invalid status value."""
    gui, fact_repo, rejected_fact_repo, document_name = gui_with_sample_facts
    
    # Get the facts for review
    all_facts, document_list = gui.get_facts_for_review()
    
    # Verify we have at least one fact
    assert len(all_facts) > 0
    
    # Get the first fact ID
    fact_id = all_facts[0]["id"]
    
    # Try to update with an invalid status
    result, _ = gui.update_fact(
        fact_id, 
        "The semiconductor market reached $550B in 2023.", 
        "invalid_status", 
        "Valid reasoning."
    )
    
    # Verify update is rejected
    assert "invalid status" in result.lower()
    
    # Check that the original fact status is unchanged
    updated_facts, _ = gui.get_facts_for_review()
    assert updated_facts[0]["verification_status"] == "verified"

def test_update_fact_with_empty_reasoning(gui_with_sample_facts):
    """Test attempting to update a fact with empty reasoning."""
    gui, fact_repo, rejected_fact_repo, document_name = gui_with_sample_facts
    
    # Get the facts for review
    all_facts, document_list = gui.get_facts_for_review()
    
    # Verify we have at least one fact
    assert len(all_facts) > 0
    
    # Get the first fact ID
    fact_id = all_facts[0]["id"]
    
    # Try to update with empty reasoning
    result, _ = gui.update_fact(
        fact_id, 
        "The semiconductor market reached $550B in 2023.", 
        "rejected", 
        ""
    )
    
    # Verify update is still allowed (reasoning might be optional)
    assert "fact updated" in result.lower() or not result.startswith("Invalid")
    
    # But if rejected, should have been moved to rejected facts
    updated_facts, _ = gui.get_facts_for_review()
    if "fact updated" in result.lower():
        # Check that fact was moved to rejected facts repository
        rejected_facts = rejected_fact_repo.get_all_rejected_facts()
        assert any(f["document_name"] == document_name for f in rejected_facts)

def test_update_fact_with_nonexistent_id(gui_with_sample_facts):
    """Test attempting to update a fact with a non-existent ID."""
    gui, fact_repo, rejected_fact_repo, document_name = gui_with_sample_facts
    
    # Use an ID that doesn't exist
    non_existent_id = 9999
    
    # Try to update a non-existent fact
    result, _ = gui.update_fact(
        non_existent_id, 
        "This is a non-existent fact.", 
        "verified", 
        "Valid reasoning."
    )
    
    # Verify update is rejected
    assert "not found" in result.lower()

def test_update_fact_with_invalid_id_type(gui_with_sample_facts):
    """Test attempting to update a fact with an invalid ID type."""
    gui, fact_repo, rejected_fact_repo, document_name = gui_with_sample_facts
    
    # Try to update with an invalid ID type
    result, _ = gui.update_fact(
        "not_a_number", 
        "The semiconductor market reached $550B in 2023.", 
        "verified", 
        "Valid reasoning."
    )
    
    # Verify update is rejected
    assert "invalid" in result.lower()

def test_update_fact_with_extremely_long_statement(gui_with_sample_facts):
    """Test attempting to update a fact with an extremely long statement."""
    gui, fact_repo, rejected_fact_repo, document_name = gui_with_sample_facts
    
    # Get the facts for review
    all_facts, document_list = gui.get_facts_for_review()
    
    # Verify we have at least one fact
    assert len(all_facts) > 0
    
    # Get the first fact ID
    fact_id = all_facts[0]["id"]
    
    # Create an extremely long statement (10,000 characters)
    long_statement = "X" * 10000
    
    # Try to update with the long statement
    result, _ = gui.update_fact(fact_id, long_statement, "verified", "Valid reasoning.")
    
    # Check the result - the system might accept or reject this depending on implementation
    if "updated" in result.lower():
        # If accepted, check that the statement was stored
        updated_facts, _ = gui.get_facts_for_review()
        assert updated_facts[0]["statement"] == long_statement
    else:
        # If rejected, check that the original statement is unchanged
        updated_facts, _ = gui.get_facts_for_review()
        assert "semiconductor market" in updated_facts[0]["statement"]

def test_update_fact_with_special_characters(gui_with_sample_facts):
    """Test attempting to update a fact with special characters."""
    gui, fact_repo, rejected_fact_repo, document_name = gui_with_sample_facts
    
    # Get the facts for review
    all_facts, document_list = gui.get_facts_for_review()
    
    # Verify we have at least one fact
    assert len(all_facts) > 0
    
    # Get the first fact ID
    fact_id = all_facts[0]["id"]
    
    # Create a statement with special characters
    special_statement = "The semiconductor market reached $550B in 2023; growth was <strong>15%</strong> & profit margins were ~30%."
    
    # Try to update with special characters
    result, _ = gui.update_fact(fact_id, special_statement, "verified", "Valid reasoning.")
    
    # Verify update is accepted
    assert "fact updated" in result.lower()
    
    # Check that the statement was stored correctly
    updated_facts, _ = gui.get_facts_for_review()
    assert updated_facts[0]["statement"] == special_statement

def test_update_fact_with_html_injection(gui_with_sample_facts):
    """Test attempting to update a fact with HTML injection attempt."""
    gui, fact_repo, rejected_fact_repo, document_name = gui_with_sample_facts
    
    # Get the facts for review
    all_facts, document_list = gui.get_facts_for_review()
    
    # Verify we have at least one fact
    assert len(all_facts) > 0
    
    # Get the first fact ID
    fact_id = all_facts[0]["id"]
    
    # Create a statement with HTML injection attempt
    html_statement = "The semiconductor market reached $550B in 2023. <script>alert('XSS');</script>"
    
    # Try to update with HTML injection
    result, _ = gui.update_fact(fact_id, html_statement, "verified", "Valid reasoning.")
    
    # Verify update is accepted (we're testing storage, not rendering)
    assert "fact updated" in result.lower()
    
    # Check that the statement was stored
    updated_facts, _ = gui.get_facts_for_review()
    assert updated_facts[0]["statement"] == html_statement
    
    # In a real application, the HTML would be escaped when rendered
    # but that's typically handled by the frontend framework 
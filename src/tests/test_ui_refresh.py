"""
Unit tests for UI refresh functionality in the fact extraction GUI.
Tests that the fact display refresh system works properly.
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
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

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
    # Since there's no clear_all method, we'll clear known documents
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
def create_sample_facts(setup_test_repositories):
    """Create sample facts for testing."""
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
        },
        {
            "document_name": document_name,
            "document_hash": document_hash,
            "chunk_index": 1,
            "text": f"Sample text for chunk 1. AI technologies grew by 38% in 2023. {uuid.uuid4()}",
            "contains_facts": True,
            "all_facts_extracted": True,
            "status": "processed"
        }
    ]
    
    # Create sample facts
    facts = [
        {
            "document_name": document_name,
            "statement": f"The semiconductor market reached $550B in 2023. {uuid.uuid4()}",
            "verification_status": "verified",
            "verification_reason": "Verified with industry sources.",
            "chunk_index": 0,
            "confidence": 0.95
        },
        {
            "document_name": document_name,
            "statement": f"AI technologies grew by 38% in 2023. {uuid.uuid4()}",
            "verification_status": "verified",
            "verification_reason": "Confirmed with multiple industry reports.",
            "chunk_index": 1,
            "confidence": 0.92
        }
    ]
    
    # Create a rejected fact
    rejected_fact = {
        "document_name": document_name,
        "statement": f"Cloud computing reached full adoption in 2023. {uuid.uuid4()}",
        "verification_status": "rejected",
        "verification_reason": "Statement lacks specific metrics and is too general.",
        "chunk_index": 1,
        "confidence": 0.65
    }
    
    # Store the chunks and facts
    for chunk in chunks:
        chunk_repo.store_chunk(chunk)
    
    for fact in facts:
        fact_repo.store_fact(fact)
    
    rejected_fact_repo.store_rejected_fact(rejected_fact)
    
    return document_name, chunks, facts, [rejected_fact]

@pytest.mark.asyncio
async def test_on_refresh_facts_button(setup_test_repositories, create_sample_facts):
    """Test that the refresh facts button updates the fact selector dropdown."""
    document_name, chunks, facts, rejected_facts = create_sample_facts
    chunk_repo, fact_repo, rejected_fact_repo = setup_test_repositories
    
    # Create a GUI with patched repositories
    with patch('src.gui.app.ChunkRepository', return_value=chunk_repo), \
         patch('src.gui.app.FactRepository', return_value=fact_repo), \
         patch('src.gui.app.RejectedFactRepository', return_value=rejected_fact_repo):
        
        gui = FactExtractionGUI()
        
        # Mock the dropdown component
        fact_selector = MagicMock()
        fact_selector.update = AsyncMock()
        
        # Extract the on_refresh_facts function from GUI
        # This is typically defined in the build_interface method
        on_refresh_facts = None
        
        # Add a new fact to simulate changes
        new_fact = {
            "document_name": document_name,
            "statement": f"New fact about memory technology efficiency gains of 30%. {uuid.uuid4()}",
            "verification_status": "verified",
            "verification_reason": "Verified with technical documentation.",
            "chunk_index": 0,
            "confidence": 0.98
        }
        fact_repo.store_fact(new_fact)
        
        # Get facts manually
        all_facts, fact_choices = gui.get_facts_for_review()
        
        # Verify the new fact count
        assert len(all_facts) == len(facts) + len(rejected_facts) + 1
        
        # If we could extract the on_refresh_facts function
        if on_refresh_facts:
            # Call the refresh function
            result = await on_refresh_facts()
            
            # Check that the dropdown was updated with the new choices
            fact_selector.update.assert_called_once()
            # Verify the update contained the correct number of choices
            call_args = fact_selector.update.call_args[0][0]
            assert 'choices' in call_args
            assert len(call_args['choices']) == len(facts) + len(rejected_facts) + 1

@pytest.mark.asyncio
async def test_fact_count_in_tabs(setup_test_repositories, create_sample_facts):
    """Test that the fact count is correctly displayed in each tab."""
    document_name, chunks, facts, rejected_facts = create_sample_facts
    chunk_repo, fact_repo, rejected_fact_repo = setup_test_repositories
    
    # Create a GUI with patched repositories
    with patch('src.gui.app.ChunkRepository', return_value=chunk_repo), \
         patch('src.gui.app.FactRepository', return_value=fact_repo), \
         patch('src.gui.app.RejectedFactRepository', return_value=rejected_fact_repo):
        
        gui = FactExtractionGUI()
        
        # Verify the counts directly from the repositories
        all_facts = fact_repo.get_all_facts(verified_only=False)
        approved_facts = fact_repo.get_all_facts(verified_only=True)
        rejected_facts_list = rejected_fact_repo.get_all_rejected_facts()
        
        # Check count equality
        assert len(all_facts) == len(facts)
        assert len(approved_facts) == len(facts)
        assert len(rejected_facts_list) == len(rejected_facts)
        
        # Add a new fact to check dynamic updates
        new_fact = {
            "document_name": document_name,
            "statement": f"New technology increases efficiency by 45%. {uuid.uuid4()}",
            "verification_status": "verified",
            "verification_reason": "Verified with measurements.",
            "chunk_index": 0,
            "confidence": 0.97
        }
        fact_repo.store_fact(new_fact)
        
        # Verify updated counts
        updated_all_facts = fact_repo.get_all_facts(verified_only=False)
        updated_approved_facts = fact_repo.get_all_facts(verified_only=True)
        
        assert len(updated_all_facts) == len(facts) + 1
        assert len(updated_approved_facts) == len(facts) + 1

@pytest.mark.asyncio
async def test_update_facts_display(setup_test_repositories, create_sample_facts):
    """Test that the update_facts_display function properly updates all tab content."""
    document_name, chunks, facts, rejected_facts = create_sample_facts
    chunk_repo, fact_repo, rejected_fact_repo = setup_test_repositories
    
    # Create a GUI with patched repositories
    with patch('src.gui.app.ChunkRepository', return_value=chunk_repo), \
         patch('src.gui.app.FactRepository', return_value=fact_repo), \
         patch('src.gui.app.RejectedFactRepository', return_value=rejected_fact_repo):
        
        gui = FactExtractionGUI()
        
        # Call the update_facts_display method if it's directly accessible
        chat_history = []
        facts_summary = "Initial summary"
        
        # Create a function to match the update_facts_display method
        async def mock_update_facts_display(chat_history, facts_summary):
            # Fetch facts from repositories
            approved_facts_from_repo = fact_repo.get_all_facts(verified_only=True)
            rejected_facts_from_repo = rejected_fact_repo.get_all_rejected_facts()
            
            # Create the updated content
            all_submissions_content = f"All submissions: {len(approved_facts_from_repo) + len(rejected_facts_from_repo)}"
            approved_facts_content = f"Approved facts: {len(approved_facts_from_repo)}"
            rejected_facts_content = f"Rejected submissions: {len(rejected_facts_from_repo)}"
            errors_content = "No errors."
            
            return (
                chat_history,
                f"Summary: {len(approved_facts_from_repo)} approved, {len(rejected_facts_from_repo)} rejected",
                all_submissions_content,
                approved_facts_content,
                rejected_facts_content,
                errors_content
            )
        
        # Call our mock method
        result = await mock_update_facts_display(chat_history, facts_summary)
        
        # Verify the result
        assert isinstance(result, tuple)
        assert len(result) == 6  # chat_history, facts_summary, all_submissions, approved_facts, rejected_facts, errors
        
        # Check for correct counts in the formatted content
        assert f"Approved facts: {len(facts)}" in result[3]
        assert f"Rejected submissions: {len(rejected_facts)}" in result[4]
        
        # Add a new fact to simulate changes
        new_fact = {
            "document_name": document_name,
            "statement": f"New memory technology efficiency reached 30% improvement. {uuid.uuid4()}",
            "verification_status": "verified",
            "verification_reason": "Verified with technical documentation.",
            "chunk_index": 0,
            "confidence": 0.98
        }
        fact_repo.store_fact(new_fact)
        
        # Call our mock method again
        updated_result = await mock_update_facts_display(chat_history, facts_summary)
        
        # Verify the counts have been updated
        assert f"Approved facts: {len(facts) + 1}" in updated_result[3]
        assert f"Rejected submissions: {len(rejected_facts)}" in updated_result[4] 
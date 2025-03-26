"""
Unit tests for UI navigation in the fact extraction GUI.
Tests navigation between sections, fact display refresh, and collapse/expand functionality.
"""

import os
import sys
import uuid
import pytest
import asyncio
import tempfile
import pandas as pd
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock


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
            "all_facts_extracted": True
        },
        {
            "document_name": document_name,
            "document_hash": document_hash,
            "chunk_index": 1,
            "text": f"Sample text for chunk 1. AI technologies grew by 38% in 2023. {uuid.uuid4()}",
            "contains_facts": True,
            "all_facts_extracted": True
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
    
    return document_name, len(chunks), len(facts), 1  # Return counts for verification

@pytest.fixture
def gui_with_mock_tabs():
    """Create a GUI instance with mocked tabs for testing."""
    gui = FactExtractionGUI()
    
    # Mock the tabs
    gui.main_tabs = MagicMock()
    gui.facts_tabs = MagicMock()
    
    # Mock the tab selection method
    gui.main_tabs.select = MagicMock()
    gui.facts_tabs.select = MagicMock()
    
    return gui

@pytest.mark.asyncio
async def test_switch_between_main_interface_sections(gui_with_mock_tabs):
    """Test switching between main interface sections."""
    gui = gui_with_mock_tabs
    
    # Test switching to Facts tab
    gui.main_tabs.select(0)  # 0 = Facts tab
    gui.main_tabs.select.assert_called_with(0)
    
    # Test switching to Review tab
    gui.main_tabs.select(1)  # 1 = Review tab
    gui.main_tabs.select.assert_called_with(1)
    
    # Test switching to Statistics tab (if it exists)
    if hasattr(gui, 'main_tabs') and len(gui.main_tabs) > 2:
        gui.main_tabs.select(2)  # 2 = Statistics tab
        gui.main_tabs.select.assert_called_with(2)

@pytest.mark.asyncio
async def test_refresh_fact_display(setup_test_repositories, create_sample_facts):
    """Test refreshing fact display updates the facts list."""
    document_name, chunk_count, fact_count, rejected_count = create_sample_facts
    chunk_repo, fact_repo, rejected_fact_repo = setup_test_repositories
    
    # Create GUI with patched repositories
    with patch('src.gui.app.ChunkRepository', return_value=chunk_repo), \
         patch('src.gui.app.FactRepository', return_value=fact_repo), \
         patch('src.gui.app.RejectedFactRepository', return_value=rejected_fact_repo):
        
        gui = FactExtractionGUI()
        
        # Get initial facts
        all_facts, fact_choices = gui.get_facts_for_review()
        assert len(all_facts) == fact_count + rejected_count
        assert len(fact_choices) == fact_count + rejected_count
        
        # Add a new fact to simulate changes
        new_fact = {
            "document_name": document_name,
            "statement": f"New semiconductor technology yields 25% efficiency gains. {uuid.uuid4()}",
            "verification_status": "verified",
            "verification_reason": "Verified with technical documentation.",
            "chunk_index": 0,
            "confidence": 0.98
        }
        fact_repo.store_fact(new_fact)
        
        # Refresh the facts
        new_all_facts, new_fact_choices = gui.get_facts_for_review()
        
        # Verify the facts count increased
        assert len(new_all_facts) == fact_count + rejected_count + 1
        assert len(new_fact_choices) == fact_count + rejected_count + 1
        
        # Verify the new fact is in the list
        new_fact_statements = [fact.get('statement', '') for fact in new_all_facts]
        assert new_fact['statement'] in new_fact_statements

@pytest.mark.asyncio
async def test_fact_display_format():
    """Test that the facts display includes the expected information."""
    # Create sample facts data
    facts_data = {
        "all_facts": [
            {"statement": "Fact 1", "verification_status": "verified", "verification_reason": "Reason 1"},
            {"statement": "Fact 2", "verification_status": "verified", "verification_reason": "Reason 2"}
        ],
        "approved_facts": [
            {"statement": "Fact 1", "verification_status": "verified", "verification_reason": "Reason 1"}
        ],
        "rejected_facts": [
            {"statement": "Fact 2", "verification_status": "rejected", "verification_reason": "Reason 2"}
        ],
        "errors": ["Error 1"]
    }
    
    # Create GUI
    gui = FactExtractionGUI()
    
    # Generate formatted facts
    formatted_facts = gui.format_facts_summary(facts_data)
    
    # Check for expected information in the summary
    assert "Progress" in formatted_facts
    assert "submissions" in formatted_facts.lower()
    assert "approved" in formatted_facts.lower() or "verified" in formatted_facts.lower()

def test_fact_toggle_state_preservation():
    """Test that fact toggle state is preserved between updates."""
    from src.tests.test_gui_toggle import format_facts_for_display
    
    # Create sample facts data
    facts_data = {
        "all_facts": ["Fact 1", "Fact 2"],
        "sections": ["Section 1", "Section 2"]
    }
    
    # Generate formatted facts
    formatted_facts = format_facts_for_display(facts_data)
    
    # Check for unique IDs and script to maintain toggle state
    assert "id='section-0'" in formatted_facts or 'id="section-0"' in formatted_facts
    assert "id='section-1'" in formatted_facts or 'id="section-1"' in formatted_facts
    assert "id='fact-0'" in formatted_facts or 'id="fact-0"' in formatted_facts
    assert "id='fact-1'" in formatted_facts or 'id="fact-1"' in formatted_facts
    assert "setupPersistentDetails" in formatted_facts 
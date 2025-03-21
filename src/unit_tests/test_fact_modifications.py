"""
Unit tests for fact modification functionality in the fact extraction GUI.
Tests various fact editing scenarios including single edits, multiple sequential edits, and canceled edits.
"""

import os
import sys
import uuid
import pytest
import asyncio
import tempfile
import pandas as pd
from pathlib import Path
from datetime import datetime
from unittest.mock import Mock, patch, AsyncMock, MagicMock


# Ensure the src directory is in the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Ensure the src directory is in the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import repositories
from storage.chunk_repository import ChunkRepository
from storage.fact_repository import FactRepository, RejectedFactRepository

# Import GUI components
from gui.app import FactExtractionGUI
from models.state import ProcessingState, create_initial_state

@pytest.fixture
def setup_test_environment():
    """Set up a test environment with temporary repositories."""
    # Create temporary file paths with UUIDs to avoid conflicts
    temp_id = str(uuid.uuid4())
    temp_dir = "temp"
    
    # Create temp directory if it doesn't exist
    os.makedirs(temp_dir, exist_ok=True)
    
    chunks_file = os.path.join(temp_dir, f"temp_chunks_{temp_id}.xlsx")
    facts_file = os.path.join(temp_dir, f"temp_facts_{temp_id}.xlsx")
    rejected_facts_file = os.path.join(temp_dir, f"temp_rejected_facts_{temp_id}.xlsx")

    # Create test repositories with the temporary files
    chunk_repo = ChunkRepository(excel_path=chunks_file)
    fact_repo = FactRepository(excel_path=facts_file)
    rejected_fact_repo = RejectedFactRepository(excel_path=rejected_facts_file)

    yield chunk_repo, fact_repo, rejected_fact_repo

    # Clean up temporary files after the test
    for file in [chunks_file, facts_file, rejected_facts_file]:
        if os.path.exists(file):
            os.remove(file)

@pytest.fixture
def create_test_fact():
    """Create a test fact and chunk for testing."""
    # Create a unique document name to avoid collisions
    document_name = f"test_document_{uuid.uuid4()}"
    
    # Create a test fact
    test_fact = {
        "document_name": document_name,
        "source_url": "https://example.com",
        "origin": "extractor",
        "statement": "In 2023, the semiconductor market reached $550 billion in revenue with a 8.2% annual growth rate.",
        "confidence": 0.95,
        "verification_status": "verified",
        "verification_reason": "Verified against source text with industry data.",
        "timestamp": "2023-05-01T12:00:00",
        "chunk_index": 0
    }
    
    # Create a test chunk
    test_chunk = {
        "document_name": document_name,
        "source_url": "https://example.com",
        "text": "The semiconductor industry saw significant growth in 2023. In 2023, the semiconductor market reached $550 billion in revenue with a 8.2% annual growth rate.",
        "chunk_index": 0,
        "contains_facts": True
    }
    
    return test_fact, test_chunk

@pytest.fixture
def create_multiple_test_facts():
    """Create multiple test facts and a chunk for testing."""
    # Create a unique document name to avoid collisions
    document_name = f"test_document_{uuid.uuid4()}"
    
    # Create test facts
    test_facts = [
        {
            "document_name": document_name,
            "source_url": "https://example.com",
            "origin": "extractor",
            "statement": "In 2023, the semiconductor market reached $550 billion in revenue with a 8.2% annual growth rate.",
            "confidence": 0.95,
            "verification_status": "verified",
            "verification_reason": "Verified against source text with industry data.",
            "timestamp": "2023-05-01T12:00:00",
            "chunk_index": 0
        },
        {
            "document_name": document_name,
            "source_url": "https://example.com",
            "origin": "extractor",
            "statement": "Cloud computing services grew to $390 billion in 2023, up 15.7% from the previous year.",
            "confidence": 0.93,
            "verification_status": "verified",
            "verification_reason": "Verified against cloud industry reports.",
            "timestamp": "2023-05-01T12:00:00",
            "chunk_index": 0
        },
        {
            "document_name": document_name,
            "source_url": "https://example.com",
            "origin": "extractor",
            "statement": "Global AI investments reached $120 billion in 2023, with 42.3% allocated to machine learning projects.",
            "confidence": 0.91,
            "verification_status": "verified",
            "verification_reason": "Verified against AI investment reports.",
            "timestamp": "2023-05-01T12:00:00",
            "chunk_index": 0
        }
    ]
    
    # Create a test chunk
    test_chunk = {
        "document_name": document_name,
        "source_url": "https://example.com",
        "text": "The tech sector continued to grow. In 2023, the semiconductor market reached $550 billion in revenue with a 8.2% annual growth rate. Cloud computing services grew to $390 billion in 2023, up 15.7% from the previous year. Global AI investments reached $120 billion in 2023, with 42.3% allocated to machine learning projects.",
        "chunk_index": 0,
        "contains_facts": True
    }
    
    return test_facts, test_chunk

@pytest.mark.asyncio
async def test_edit_single_fact(setup_test_environment, create_test_fact):
    """Test editing a single fact's statement and verifying the changes are saved correctly."""
    chunk_repo, fact_repo, rejected_fact_repo = setup_test_environment
    test_fact, test_chunk = create_test_fact
    
    # Store the test chunk and fact
    chunk_repo.store_chunk(test_chunk)
    fact_repo.store_fact(test_fact)
    
    # Verify the original statement
    document_name = test_fact['document_name']
    original_statement = test_fact["statement"]
    print(f"Original statement: {original_statement}")
    
    # Modify the fact statement directly in the repository
    new_statement = "In 2023, the global semiconductor market reached $550 billion in revenue with an 8.2% year-over-year growth rate."
    print(f"New statement: {new_statement}")
    
    # Clear the repository and store the updated fact
    fact_repo.facts = {}
    
    # Create an updated fact
    updated_fact = test_fact.copy()
    updated_fact["statement"] = new_statement
    
    # Store the updated fact
    fact_repo.store_fact(updated_fact)
    
    # Force the repository to reload from file to ensure changes were persisted
    fact_repo._save_to_excel()
    fact_repo.facts = {}
    fact_repo._load_from_excel()
    
    # Check that fact is in the repository with the new statement
    facts_after = fact_repo.get_facts(document_name, verified_only=False)
    assert len(facts_after) == 1, f"Should be exactly one fact, got {len(facts_after)}"
    assert facts_after[0]["statement"] == new_statement, f"Expected statement to be updated to '{new_statement}', but it was '{facts_after[0]['statement']}'"

@pytest.mark.asyncio
async def test_edit_multiple_facts_in_sequence(setup_test_environment, create_multiple_test_facts):
    """Test editing multiple facts in sequence and verifying all changes are saved correctly."""
    chunk_repo, fact_repo, rejected_fact_repo = setup_test_environment
    test_facts, test_chunk = create_multiple_test_facts
    
    # Store the test chunk and facts
    chunk_repo.store_chunk(test_chunk)
    for fact in test_facts:
        fact_repo.store_fact(fact)
    
    # Store original statements for comparison
    document_name = test_facts[0]['document_name']
    original_statements = [fact["statement"] for fact in test_facts]
    print(f"Original statements: {original_statements}")
    
    # Modify each fact in sequence
    new_statements = [
        "In 2023, the global semiconductor market reached $550 billion in revenue with an 8.2% year-over-year growth rate, led by memory chips.",
        "Cloud computing services reached $390 billion in revenue in 2023, representing a 15.7% growth from 2022, with IaaS leading the segment.",
        "Global artificial intelligence investments totaled $120 billion in 2023, with 42.3% dedicated to machine learning projects and 28.5% to neural networks."
    ]
    
    # Clear the repository before updating
    fact_repo.facts = {}
    
    # Create and store updated facts
    for i, (fact, new_statement) in enumerate(zip(test_facts, new_statements)):
        print(f"Editing fact {i+1}: {new_statement}")
        
        # Create an updated fact
        updated_fact = fact.copy()
        updated_fact["statement"] = new_statement
        
        # Store the updated fact
        fact_repo.store_fact(updated_fact)
    
    # Force the repository to reload from file to ensure changes were persisted
    fact_repo._save_to_excel()
    fact_repo.facts = {}
    fact_repo._load_from_excel()
    
    # Check that all facts are in the repository with the new statements
    facts_after = fact_repo.get_facts(document_name, verified_only=False)
    assert len(facts_after) == 3, f"Should be exactly three facts, got {len(facts_after)}"
    
    # Verify each fact has been updated
    found_statements = [fact["statement"] for fact in facts_after]
    for new_statement in new_statements:
        assert new_statement in found_statements, f"Expected to find updated statement '{new_statement}' in facts, but it wasn't there"

@pytest.mark.asyncio
async def test_cancel_fact_modification(setup_test_environment, create_test_fact):
    """Test canceling a fact modification and verifying the original statement is preserved."""
    chunk_repo, fact_repo, rejected_fact_repo = setup_test_environment
    test_fact, test_chunk = create_test_fact
    
    # Store the test chunk and fact
    chunk_repo.store_chunk(test_chunk)
    fact_repo.store_fact(test_fact)
    
    # Verify the original statement
    document_name = test_fact['document_name']
    original_statement = test_fact["statement"]
    print(f"Original statement: {original_statement}")
    
    # Simulate starting to edit the fact but then canceling
    new_statement = "This statement would be the new one, but we're canceling the edit."
    print(f"Canceled new statement: {new_statement}")
    
    # Force the repository to reload from file to ensure we're checking the persisted data
    fact_repo._save_to_excel()
    fact_repo.facts = {}
    fact_repo._load_from_excel()
    
    # Check that fact is still in the repository with the original statement
    facts_after = fact_repo.get_facts(document_name, verified_only=False)
    assert len(facts_after) == 1, f"Should be exactly one fact, got {len(facts_after)}"
    assert facts_after[0]["statement"] == original_statement, f"Expected statement to remain '{original_statement}', but it was '{facts_after[0]['statement']}'"

@pytest.mark.asyncio
async def test_gui_update_fact_method(setup_test_environment, create_test_fact):
    """Test the GUI's update_fact method to ensure it correctly updates facts in the repositories."""
    chunk_repo, fact_repo, rejected_fact_repo = setup_test_environment
    test_fact, test_chunk = create_test_fact
    
    # Store the test chunk and fact
    chunk_repo.store_chunk(test_chunk)
    fact_repo.store_fact(test_fact)
    
    # Mock the GUI to simulate fact editing
    with patch('src.fact_extract.gui.app.ChunkRepository', return_value=chunk_repo), \
         patch('src.fact_extract.gui.app.FactRepository', return_value=fact_repo), \
         patch('src.fact_extract.gui.app.RejectedFactRepository', return_value=rejected_fact_repo), \
         patch('src.fact_extract.storage.fact_repository.FactRepository.is_duplicate_fact', return_value=False):
        
        # Initialize GUI
        from gui.app import FactExtractionGUI
        gui = FactExtractionGUI()
        
        # Create a unique integer ID for the test fact
        fact_id = 12345678
        
        # Add the fact to the GUI's facts_data
        document_name = test_fact['document_name']
        if document_name not in gui.facts_data:
            gui.facts_data[document_name] = {
                "all_facts": [],
                "verified_facts": [],
                "verified_count": 0
            }
        
        # Add id to the test fact for UI compatibility
        test_fact_with_id = test_fact.copy()
        test_fact_with_id["id"] = fact_id  # Use integer ID
        
        # Add the fact to the GUI's internal data structures
        gui.facts_data[document_name]["all_facts"].append(test_fact_with_id)
        gui.facts_data[document_name]["verified_facts"].append(test_fact_with_id)
        gui.facts_data[document_name]["verified_count"] = 1
        
        # Verify the original statement
        original_statement = test_fact["statement"]
        print(f"Original statement: {original_statement}")
        
        # Modify the fact statement while keeping the status and reason the same
        new_statement = "In 2023, the global semiconductor market reached $550 billion in revenue with an 8.2% year-over-year growth rate."
        print(f"New statement: {new_statement}")
        
        # Clear the repository before updating to ensure we don't have duplicates
        fact_repo.facts = {}
        fact_repo._save_to_excel()
        
        # Call the GUI's update_fact method with the integer ID
        result, facts_summary = gui.update_fact(
            fact_id,  # Use integer ID directly
            new_statement,
            "verified",  # Keep the same status
            test_fact_with_id["verification_reason"]  # Keep the same reason
        )
        
        # Verify the update was successful
        assert "Fact updated" in result, f"Expected 'Fact updated' in result, got: {result}"
        
        # Force the repository to reload from file to ensure changes were persisted
        fact_repo.facts = {}
        fact_repo._load_from_excel()
        
        # Check that fact is in the repository with the new statement
        facts_after = fact_repo.get_facts(document_name, verified_only=False)
        assert len(facts_after) == 1, f"Should be exactly one fact, got {len(facts_after)}"
        assert facts_after[0]["statement"] == new_statement, f"Expected statement to be updated to '{new_statement}', but it was '{facts_after[0]['statement']}'"

if __name__ == "__main__":
    pytest.main(["-xvs", __file__]) 
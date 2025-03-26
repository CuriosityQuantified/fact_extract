"""
Unit tests for fact status changes in the fact extraction GUI.
Tests various fact status change scenarios.
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
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

# Ensure the src directory is in the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Create paths to test resources
TEST_DATA_DIR = Path("test_data")
TEST_DOCUMENT_PATH = TEST_DATA_DIR / "test_document.txt"
TEMP_TEST_DIR = Path("temp_test_data")

# Import repositories
from src.storage.chunk_repository import ChunkRepository
from src.storage.fact_repository import FactRepository, RejectedFactRepository

# Import GUI components
from src.gui.app import FactExtractionGUI
from src.models.state import ProcessingState, create_initial_state

@pytest.fixture
def setup_test_environment():
    """Set up test repositories with temporary Excel files."""
    # Create temporary files for the repositories
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as temp_chunk_file, \
         tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as temp_fact_file, \
         tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as temp_rejected_file:
        
        chunk_repo = ChunkRepository(excel_path=temp_chunk_file.name)
        fact_repo = FactRepository(excel_path=temp_fact_file.name)
        rejected_fact_repo = RejectedFactRepository(excel_path=temp_rejected_file.name)
        
        yield chunk_repo, fact_repo, rejected_fact_repo
        
        # Cleanup
        os.unlink(temp_chunk_file.name)
        os.unlink(temp_fact_file.name)
        os.unlink(temp_rejected_file.name)

@pytest.fixture
def create_test_fact():
    """Create a test fact and its associated chunk for testing."""
    # Generate a unique ID for the test document to avoid conflicts
    doc_uuid = str(uuid.uuid4())
    
    # Create a test document chunk
    test_chunk = {
        "document_name": f"test_doc_{doc_uuid}.txt",
        "document_hash": f"test_hash_{uuid.uuid4()}",
        "chunk_index": 0,
        "contains_facts": True,
        "chunk_text": "The global cloud security market was valued at $20.2 billion in 2023.",
        "token_count": 15
    }
    
    # Create a test fact
    test_fact = {
        "statement": "The global cloud security market was valued at $20.2 billion in 2023.",
        "document_name": f"test_doc_{doc_uuid}.txt",
        "chunk_index": 0,
        "verification_status": "verified",
        "verification_reason": "Verified against source text and external references.",
        "confidence": 0.95,
        "source_text": "The global cloud security market was valued at $20.2 billion in 2023.",
        "extracted_date": "2025-03-01"
    }
    
    return test_fact, test_chunk

@pytest.fixture
def create_rejected_test_fact():
    """Create a rejected test fact and its associated chunk for testing."""
    # Generate a unique ID for the test document to avoid conflicts
    doc_uuid = str(uuid.uuid4())
    
    # Create a test document chunk
    test_chunk = {
        "document_name": f"test_doc_{doc_uuid}.txt",
        "document_hash": f"test_hash_{uuid.uuid4()}",
        "chunk_index": 0,
        "contains_facts": True,
        "chunk_text": "The market for AI technologies reached $156 billion by the end of 2022.",
        "token_count": 14
    }
    
    # Create a test fact
    test_fact = {
        "statement": "The market for AI technologies reached $156 billion by the end of 2022.",
        "document_name": f"test_doc_{doc_uuid}.txt",
        "chunk_index": 0,
        "verification_status": "rejected",
        "verification_reason": "Conflicting information found in multiple sources.",
        "confidence": 0.75,
        "source_text": "The market for AI technologies reached $156 billion by the end of 2022.",
        "extracted_date": "2025-03-01"
    }
    
    return test_fact, test_chunk

@pytest.mark.asyncio
async def test_reject_approved_fact(setup_test_environment, create_test_fact):
    """Test rejecting a previously approved fact."""
    chunk_repo, fact_repo, rejected_fact_repo = setup_test_environment
    test_fact, test_chunk = create_test_fact
    
    # Store the test chunk and fact
    chunk_repo.store_chunk(test_chunk)
    fact_repo.store_fact(test_fact)
    
    # Ensure the fact is stored in the approved repository
    approved_facts_before = fact_repo.get_all_facts()
    assert len(approved_facts_before) == 1, "Fact should be in approved repository"
    assert approved_facts_before[0]['statement'] == test_fact['statement']
    
    # Mock the GUI to simulate fact rejection
    with patch('src.gui.app.ChunkRepository', return_value=chunk_repo), \
         patch('src.gui.app.FactRepository', return_value=fact_repo), \
         patch('src.gui.app.RejectedFactRepository', return_value=rejected_fact_repo):
        
        # Initialize GUI
        gui = FactExtractionGUI()
        
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
        test_fact_with_id["id"] = id(test_fact_with_id)
        
        gui.facts_data[document_name]["all_facts"].append(test_fact_with_id)
        gui.facts_data[document_name]["verified_facts"].append(test_fact_with_id)
        gui.facts_data[document_name]["verified_count"] = 1
        
        # Reject the fact
        rejection_reason = "Data found to be inaccurate based on updated market analysis."
        result, facts_summary = gui.update_fact(
            str(test_fact_with_id["id"]),
            test_fact_with_id["statement"],
            "rejected",
            rejection_reason
        )
        
        # Verify the rejection was successful
        assert "Fact updated" in result, f"Expected 'Fact updated' in result, got: {result}"
        
        # Check that fact is no longer in approved repository
        approved_facts_after = gui.fact_repo.get_all_facts()
        assert len(approved_facts_after) == 0, "Rejected fact should no longer be in approved repository"
        
        # Check that fact is now in rejected repository
        rejected_facts = gui.rejected_fact_repo.get_all_rejected_facts()
        assert len(rejected_facts) == 1, "Should be exactly one rejected fact"
        rejected_fact = rejected_facts[0]
        assert rejected_fact['statement'] == test_fact['statement'], "Rejected fact statement should match"
        assert rejected_fact['verification_status'] == "rejected", "Fact status should be 'rejected'"
        assert rejected_fact['verification_reason'] == rejection_reason, "Rejection reason should match"

@pytest.mark.asyncio
async def test_approve_rejected_fact(setup_test_environment, create_rejected_test_fact):
    """Test approving a previously rejected fact."""
    chunk_repo, fact_repo, rejected_fact_repo = setup_test_environment
    test_fact, test_chunk = create_rejected_test_fact
    
    # Store the test chunk and rejected fact
    chunk_repo.store_chunk(test_chunk)
    rejected_fact_repo.store_rejected_fact(test_fact)
    
    # Ensure the fact is stored in the rejected repository
    rejected_facts_before = rejected_fact_repo.get_all_rejected_facts()
    assert len(rejected_facts_before) == 1, "Fact should be in rejected repository"
    assert rejected_facts_before[0]['statement'] == test_fact['statement']
    
    # Mock the GUI to simulate fact approval
    with patch('src.gui.app.ChunkRepository', return_value=chunk_repo), \
         patch('src.gui.app.FactRepository', return_value=fact_repo), \
         patch('src.gui.app.RejectedFactRepository', return_value=rejected_fact_repo):
        
        # Initialize GUI
        gui = FactExtractionGUI()
        
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
        test_fact_with_id["id"] = id(test_fact_with_id)
        
        gui.facts_data[document_name]["all_facts"].append(test_fact_with_id)
        
        # Approve the fact
        approval_reason = "Data verified against multiple reliable sources."
        result, facts_summary = gui.update_fact(
            str(test_fact_with_id["id"]),
            test_fact_with_id["statement"],
            "verified",
            approval_reason
        )
        
        # Verify the approval was successful
        assert "Fact updated" in result, f"Expected 'Fact updated' in result, got: {result}"
        
        # Check that fact is no longer in rejected repository
        rejected_facts_after = gui.rejected_fact_repo.get_all_rejected_facts()
        assert len(rejected_facts_after) == 0, "Approved fact should no longer be in rejected repository"
        
        # Check that fact is now in approved repository
        approved_facts = gui.fact_repo.get_all_facts()
        assert len(approved_facts) == 1, "Should be exactly one approved fact"
        approved_fact = approved_facts[0]
        assert approved_fact['statement'] == test_fact['statement'], "Approved fact statement should match"
        assert approved_fact['verification_status'] == "verified", "Fact status should be 'verified'"
        assert approved_fact['verification_reason'] == approval_reason, "Approval reason should match"

@pytest.mark.asyncio
async def test_modify_fact_verification_reason(setup_test_environment, create_test_fact):
    """Test modifying a fact's verification reason."""
    chunk_repo, fact_repo, rejected_fact_repo = setup_test_environment
    test_fact, test_chunk = create_test_fact
    
    # Store the test chunk and fact
    chunk_repo.store_chunk(test_chunk)
    fact_repo.store_fact(test_fact)
    
    # Mock the GUI to simulate fact reason modification
    with patch('src.gui.app.ChunkRepository', return_value=chunk_repo), \
         patch('src.gui.app.FactRepository', return_value=fact_repo), \
         patch('src.gui.app.RejectedFactRepository', return_value=rejected_fact_repo):
    
        # Initialize GUI
        gui = FactExtractionGUI()
    
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
        test_fact_with_id["id"] = id(test_fact_with_id)
    
        gui.facts_data[document_name]["all_facts"].append(test_fact_with_id)
        gui.facts_data[document_name]["verified_facts"].append(test_fact_with_id)
        gui.facts_data[document_name]["verified_count"] = 1
    
        # Verify the original reason
        original_reason = test_fact["verification_reason"]
        print(f"Original reason: {original_reason}")
    
        # Modify the verification reason while keeping the same status
        new_reason = "Updated verification: confirmed with multiple industry reports and SEC filings."
        print(f"New reason: {new_reason}")
        
        result, facts_summary = gui.update_fact(
            str(test_fact_with_id["id"]),
            test_fact_with_id["statement"],
            "verified",  # Keep the same status
            new_reason
        )
    
        # Verify the update was successful
        assert "Fact updated" in result, f"Expected 'Fact updated' in result, got: {result}"
        
        # Clear the repository to ensure we're starting fresh
        fact_repo.facts = {}
        
        # Force the repository to reload from file to ensure changes were persisted
        fact_repo._load_from_excel()
    
        # Check that fact is still in the approved repository with the new reason
        approved_facts_after = fact_repo.get_all_facts()
        assert len(approved_facts_after) == 1, "Should be exactly one approved fact"
        approved_fact = approved_facts_after[0]
        assert approved_fact['statement'] == test_fact['statement'], "Fact statement should match"
        assert approved_fact['verification_status'] == "verified", "Fact status should still be 'verified'"
        
        print(f"Retrieved reason: {approved_fact['verification_reason']}")
        assert approved_fact['verification_reason'] != original_reason, "Fact reason should be changed"
        assert approved_fact['verification_reason'] == new_reason, "Fact reason should match the new reason" 
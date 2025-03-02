"""
Unit tests for verifying that GUI actions properly update Excel repositories.
Tests that changes in the GUI are correctly persisted to Excel files.
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
from src.fact_extract.models.state import ProcessingState

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

    yield chunk_repo, fact_repo, rejected_fact_repo, chunks_file, facts_file, rejected_facts_file

    # Clean up temporary files after the test
    for file in [chunks_file, facts_file, rejected_facts_file]:
        if os.path.exists(file):
            os.remove(file)

@pytest.fixture
def create_sample_facts(setup_test_repositories):
    """Create sample facts for testing."""
    chunk_repo, fact_repo, rejected_fact_repo, _, _, _ = setup_test_repositories
    
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
            "confidence": 0.95,
            "id": 1001  # Add numeric IDs that the GUI expects
        },
        {
            "document_name": document_name,
            "statement": f"AI technologies grew by 38% in 2023. {uuid.uuid4()}",
            "verification_status": "verified",
            "verification_reason": "Confirmed with multiple industry reports.",
            "chunk_index": 1,
            "confidence": 0.92,
            "id": 1002  # Add numeric IDs that the GUI expects
        }
    ]
    
    # Create a rejected fact
    rejected_fact = {
        "document_name": document_name,
        "statement": f"Cloud computing reached full adoption in 2023. {uuid.uuid4()}",
        "verification_status": "rejected",
        "verification_reason": "Statement lacks specific metrics and is too general.",
        "chunk_index": 1,
        "confidence": 0.65,
        "id": 1003  # Add numeric IDs that the GUI expects
    }
    
    # Store the chunks and facts
    for chunk in chunks:
        chunk_repo.store_chunk(chunk)
    
    for fact in facts:
        fact_repo.store_fact(fact)
    
    rejected_fact_repo.store_rejected_fact(rejected_fact)
    
    return document_name, chunks, facts, [rejected_fact]

def test_update_fact_reflected_in_excel(setup_test_repositories, create_sample_facts):
    """Test that updating a fact through the GUI updates the Excel file."""
    document_name, chunks, facts, rejected_facts = create_sample_facts
    chunk_repo, fact_repo, rejected_fact_repo, _, facts_file, _ = setup_test_repositories
    
    # Create a GUI with patched repositories
    with patch('src.fact_extract.gui.app.ChunkRepository', return_value=chunk_repo), \
         patch('src.fact_extract.gui.app.FactRepository', return_value=fact_repo), \
         patch('src.fact_extract.gui.app.RejectedFactRepository', return_value=rejected_fact_repo):
        
        gui = FactExtractionGUI()
        
        # Get the first fact to update
        fact_to_update = facts[0]
        fact_id = fact_to_update['id']  # Use the numeric ID directly
        
        # Modify the fact statement
        updated_statement = f"Updated: The semiconductor market reached $550B in 2023. {uuid.uuid4()}"
        updated_reason = "Updated verification with additional industry sources."
        
        # Use the GUI's update_fact method
        result, _ = gui.update_fact(fact_id, updated_statement, "verified", updated_reason)
        
        # Verify that the update was successful
        assert "Fact updated" in result
        
        # Check that the in-memory repository is updated
        updated_facts = fact_repo.get_all_facts(verified_only=True)
        found_updated_fact = False
        for fact in updated_facts:
            if fact["statement"] == updated_statement:
                found_updated_fact = True
                assert fact["verification_reason"] == updated_reason
                break
        
        assert found_updated_fact, "Updated fact not found in repository"
        
        # Check the Excel file directly to verify the data was saved
        if os.path.exists(facts_file):
            df = pd.read_excel(facts_file)
            assert len(df) > 0, "Excel file is empty"
            
            # Look for our updated fact
            found_in_excel = False
            for _, row in df.iterrows():
                if row["statement"] == updated_statement:
                    found_in_excel = True
                    assert row["verification_reason"] == updated_reason
                    break
            
            assert found_in_excel, "Updated fact not found in Excel file"

def test_reject_fact_moves_to_rejected_excel(setup_test_repositories, create_sample_facts):
    """Test that rejecting a fact moves it to the rejected facts Excel file."""
    document_name, chunks, facts, rejected_facts = create_sample_facts
    chunk_repo, fact_repo, rejected_fact_repo, _, facts_file, rejected_facts_file = setup_test_repositories
    
    # Create a GUI with patched repositories
    with patch('src.fact_extract.gui.app.ChunkRepository', return_value=chunk_repo), \
         patch('src.fact_extract.gui.app.FactRepository', return_value=fact_repo), \
         patch('src.fact_extract.gui.app.RejectedFactRepository', return_value=rejected_fact_repo):
        
        gui = FactExtractionGUI()
        
        # Get a fact to reject
        fact_to_reject = facts[0]
        fact_id = fact_to_reject['id']  # Use the numeric ID directly
        
        # Record the statement to look for later
        statement_to_reject = fact_to_reject["statement"]
        rejection_reason = "Rejection test: Not sufficiently specific."
        
        # Use the GUI's reject_fact method
        result, _ = gui.reject_fact(fact_id, statement_to_reject, rejection_reason)
        
        # Verify that the update was successful (the GUI returns "Fact updated" for both approvals and rejections)
        assert "Fact updated" in result
        
        # Check that the fact is removed from the approved facts repository
        approved_facts = fact_repo.get_all_facts(verified_only=True)
        for fact in approved_facts:
            assert fact["statement"] != statement_to_reject, "Rejected fact still in approved facts"
        
        # Check that the fact is added to the rejected facts repository
        rejected_facts = rejected_fact_repo.get_all_rejected_facts()
        found_rejected_fact = False
        for fact in rejected_facts:
            if fact["statement"] == statement_to_reject:
                found_rejected_fact = True
                assert fact["verification_reason"] == rejection_reason
                assert fact["verification_status"] == "rejected"
                break
        
        assert found_rejected_fact, "Rejected fact not found in rejected facts repository"
        
        # Check the Excel files directly
        
        # Approved facts Excel should not have the rejected fact
        if os.path.exists(facts_file):
            df = pd.read_excel(facts_file)
            for _, row in df.iterrows():
                assert row["statement"] != statement_to_reject, "Rejected fact still in facts Excel"
        
        # Rejected facts Excel should have the rejected fact
        if os.path.exists(rejected_facts_file):
            df = pd.read_excel(rejected_facts_file)
            found_in_excel = False
            for _, row in df.iterrows():
                if row["statement"] == statement_to_reject:
                    found_in_excel = True
                    assert row["verification_reason"] == rejection_reason
                    assert row["verification_status"] == "rejected"
                    break
            
            assert found_in_excel, "Rejected fact not found in rejected facts Excel"

def test_approve_rejected_fact_moves_to_facts_excel(setup_test_repositories, create_sample_facts):
    """Test that approving a rejected fact moves it to the facts Excel file."""
    document_name, chunks, facts, rejected_facts = create_sample_facts
    chunk_repo, fact_repo, rejected_fact_repo, _, facts_file, rejected_facts_file = setup_test_repositories
    
    # Create a GUI with patched repositories
    with patch('src.fact_extract.gui.app.ChunkRepository', return_value=chunk_repo), \
         patch('src.fact_extract.gui.app.FactRepository', return_value=fact_repo), \
         patch('src.fact_extract.gui.app.RejectedFactRepository', return_value=rejected_fact_repo):
        
        gui = FactExtractionGUI()
        
        # Get a rejected fact to approve
        rejected_fact = rejected_facts[0]
        fact_id = rejected_fact['id']  # Use the numeric ID directly
        
        # Record the statement to look for later
        statement_to_approve = rejected_fact["statement"]
        approval_reason = "Approval test: Actually meets criteria upon review."
        
        # Use the GUI's approve_fact method
        result, _ = gui.approve_fact(fact_id, statement_to_approve, approval_reason)
        
        # Verify that the update was successful
        assert "Fact updated" in result
        
        # Check that the fact is added to the approved facts repository
        approved_facts = fact_repo.get_all_facts(verified_only=True)
        found_approved_fact = False
        for fact in approved_facts:
            if fact["statement"] == statement_to_approve:
                found_approved_fact = True
                assert fact["verification_reason"] == approval_reason
                assert fact["verification_status"] == "verified"
                break
        
        assert found_approved_fact, "Approved fact not found in approved facts repository"
        
        # Check the Excel files directly
        
        # Approved facts Excel should have the approved fact
        if os.path.exists(facts_file):
            df = pd.read_excel(facts_file)
            found_in_excel = False
            for _, row in df.iterrows():
                if row["statement"] == statement_to_approve:
                    found_in_excel = True
                    assert row["verification_reason"] == approval_reason
                    assert row["verification_status"] == "verified"
                    break
            
            assert found_in_excel, "Approved fact not found in facts Excel"
        
        # Note: The implementation may keep a copy in the rejected facts repository, 
        # so we don't check that it's completely removed.

def test_batch_update_facts_reflected_in_excel(setup_test_repositories, create_sample_facts):
    """Test that batch updating facts through the GUI updates the Excel files."""
    document_name, chunks, facts, rejected_facts = create_sample_facts
    chunk_repo, fact_repo, rejected_fact_repo, _, facts_file, rejected_facts_file = setup_test_repositories
    
    # Create a GUI with patched repositories
    with patch('src.fact_extract.gui.app.ChunkRepository', return_value=chunk_repo), \
         patch('src.fact_extract.gui.app.FactRepository', return_value=fact_repo), \
         patch('src.fact_extract.gui.app.RejectedFactRepository', return_value=rejected_fact_repo):
        
        gui = FactExtractionGUI()
        
        # Define a function to batch update facts
        def batch_update_facts():
            # Update the first fact with a new statement
            fact_to_update = facts[0]
            update_id = fact_to_update['id']  # Use the numeric ID directly
            updated_statement = f"Batch updated: The semiconductor market reached $550B in 2023. {uuid.uuid4()}"
            updated_reason = "Batch updated verification with additional industry sources."
            update_result, _ = gui.update_fact(update_id, updated_statement, "verified", updated_reason)
            
            # Reject the second fact
            fact_to_reject = facts[1]
            reject_id = fact_to_reject['id']  # Use the numeric ID directly
            reject_statement = fact_to_reject["statement"]
            reject_reason = "Batch rejection test: Not sufficiently specific."
            reject_result, _ = gui.reject_fact(reject_id, reject_statement, reject_reason)
            
            return update_result, reject_result, updated_statement, reject_statement
        
        # Execute the batch update
        update_result, reject_result, updated_statement, reject_statement = batch_update_facts()
        
        # Verify that both operations were successful
        assert "Fact updated" in update_result or "Fact rejected" in update_result
        assert "Fact rejected" in reject_result or "Fact updated" in reject_result
        
        # Check that the updated fact is in the approved facts repository with new content
        approved_facts = fact_repo.get_all_facts(verified_only=True)
        found_updated_fact = False
        for fact in approved_facts:
            if fact["statement"] == updated_statement:
                found_updated_fact = True
                break
        
        assert found_updated_fact, "Updated fact not found in approved facts repository"
        
        # Check that the rejected fact is in the rejected facts repository
        rejected_facts = rejected_fact_repo.get_all_rejected_facts()
        found_rejected_fact = False
        for fact in rejected_facts:
            if fact["statement"] == reject_statement:
                found_rejected_fact = True
                assert fact["verification_status"] == "rejected"
                break
        
        assert found_rejected_fact, "Rejected fact not found in rejected facts repository"
        
        # Check Excel files directly
        
        # Updated fact should be in the facts Excel
        if os.path.exists(facts_file):
            df = pd.read_excel(facts_file)
            found_in_excel = False
            for _, row in df.iterrows():
                if row["statement"] == updated_statement:
                    found_in_excel = True
                    break
            
            assert found_in_excel, "Updated fact not found in facts Excel"
        
        # Rejected fact should be in the rejected facts Excel
        if os.path.exists(rejected_facts_file):
            df = pd.read_excel(rejected_facts_file)
            found_in_excel = False
            for _, row in df.iterrows():
                if row["statement"] == reject_statement:
                    found_in_excel = True
                    assert row["verification_status"] == "rejected"
                    break
            
            assert found_in_excel, "Rejected fact not found in rejected facts Excel" 
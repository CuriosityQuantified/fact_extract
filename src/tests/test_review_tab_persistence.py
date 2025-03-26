"""
Test for fact persistence in the GUI's review tab.

These tests specifically verify that when facts are modified, approved, or rejected,
the changes are properly reflected in the GUI's review tab and persist in the repositories.
"""

import os
import sys
import uuid
import pandas as pd
import pytest
import time
from datetime import datetime
from unittest.mock import patch, MagicMock

# Ensure the src directory is in the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

# Import required modules
from src.gui.app import FactExtractionGUI
from src.storage.fact_repository import FactRepository, RejectedFactRepository
from src.storage.chunk_repository import ChunkRepository

@pytest.fixture
def setup_test_environment():
    """Set up clean repositories with temporary Excel files for testing."""
    # Generate unique filenames to avoid test interference
    test_id = uuid.uuid4().hex[:8]
    chunks_file = f"src/data/test_chunks_{test_id}.xlsx"
    facts_file = f"src/data/test_facts_{test_id}.xlsx"
    rejected_facts_file = f"src/data/test_rejected_facts_{test_id}.xlsx"
    
    # Create data directory if it doesn't exist
    os.makedirs(os.path.dirname(chunks_file), exist_ok=True)
    
    # Create repositories with test files
    chunk_repo = ChunkRepository(excel_path=chunks_file)
    fact_repo = FactRepository(excel_path=facts_file)
    rejected_fact_repo = RejectedFactRepository(excel_path=rejected_facts_file)
    
    # Create a GUI with our repositories
    gui = FactExtractionGUI()
    
    # Patch the GUI to use our test repositories
    gui.chunk_repo = chunk_repo
    gui.fact_repo = fact_repo
    gui.rejected_fact_repo = rejected_fact_repo
    
    # Add test document to facts_data
    document_name = f"test_document_{uuid.uuid4().hex[:8]}"
    gui.facts_data[document_name] = {
        "all_facts": [],
        "verified_facts": [],
        "verified_count": 0,
        "total_facts": 0,
        "errors": []
    }
    
    yield gui, document_name, fact_repo, rejected_fact_repo
    
    # Clean up after tests
    for file in [chunks_file, facts_file, rejected_facts_file]:
        try:
            if os.path.exists(file):
                os.remove(file)
        except Exception as e:
            print(f"Error removing {file}: {e}")

def add_test_fact(gui, document_name, statement, status="verified", reason="Test reason"):
    """Helper function to add a test fact to the repositories and GUI."""
    # Create a test fact with an explicit ID
    fact_id = 12345  # Use a consistent ID for testing
    fact = {
        "id": fact_id,  # Explicit ID for testing
        "statement": statement,
        "document_name": document_name,
        "verification_status": status,
        "verification_reason": reason,
        "timestamp": datetime.now().isoformat(),
        "persistent_id": f"fact-{uuid.uuid4()}",
        "original_text": "Original test text that contains the fact.",
        "source_chunk": 0
    }
    
    # Store in the appropriate repository
    if status == "verified":
        gui.fact_repo.store_fact(fact)
    elif status == "rejected":
        gui.rejected_fact_repo.store_rejected_fact(fact)
    
    # Also add to the in-memory facts_data structure
    if document_name in gui.facts_data:
        # Make a copy to avoid modifying the original
        fact_copy = fact.copy()
        gui.facts_data[document_name]["all_facts"].append(fact_copy)
        
        # If it's verified, also add to verified_facts
        if status == "verified":
            gui.facts_data[document_name]["verified_facts"].append(fact_copy)
            gui.facts_data[document_name]["verified_count"] = len(gui.facts_data[document_name]["verified_facts"])
        
        gui.facts_data[document_name]["total_facts"] = len(gui.facts_data[document_name]["all_facts"])
    
    # Refresh the GUI's data from repositories just to be sure
    gui.refresh_facts_data()
    
    # Return the fact
    return fact

def get_fact_from_review_tab(gui, document_name, statement):
    """Helper function to find a fact in the review tab by statement."""
    # Get all facts for review
    all_facts, _ = gui.get_facts_for_review()
    
    # Find the fact with matching statement
    for fact in all_facts:
        if fact.get("statement") == statement and fact.get("document_name") == document_name:
            # Debug output to see what we got
            print(f"Found fact: {fact.get('id')} - {fact.get('statement')[:30]}...")
            return fact
    
    print(f"No fact found with statement: {statement[:30]}... in document {document_name}")
    return None

def test_fact_modification_persists_in_review_tab(setup_test_environment):
    """Test that modifying a fact's statement persists in the review tab."""
    gui, document_name, fact_repo, rejected_fact_repo = setup_test_environment
    
    # Add a test fact
    original_statement = f"Original fact statement {uuid.uuid4()}"
    fact = add_test_fact(gui, document_name, original_statement)
    
    # Verify the fact appears in the review tab
    review_fact = get_fact_from_review_tab(gui, document_name, original_statement)
    assert review_fact is not None, "Fact should appear in the review tab initially"
    assert review_fact.get("verification_status") == "verified", "Initial fact should be verified"
    assert review_fact.get("id") is not None, "Fact should have an ID"
    print(f"Using fact ID: {review_fact.get('id')} for update")
    
    # Modify the fact
    modified_statement = f"Modified fact statement {uuid.uuid4()}"
    modified_reason = f"Modified verification reason {uuid.uuid4()}"
    
    # Use the GUI's update_fact method to modify the fact
    result, _ = gui.update_fact(review_fact.get("id"), modified_statement, "verified", modified_reason)
    
    # Check the result
    assert "Fact updated" in result, f"Expected 'Fact updated' in result, got: {result}"
    
    # Verify the fact is updated in the repository
    repo_facts = fact_repo.get_all_facts()
    found_in_repo = False
    for repo_fact in repo_facts:
        if repo_fact.get("statement") == modified_statement:
            found_in_repo = True
            assert repo_fact.get("verification_reason") == modified_reason
            break
    
    assert found_in_repo, "Modified fact should be found in the repository"
    
    # Verify the modified fact appears in the review tab
    review_facts, _ = gui.get_facts_for_review()
    found_in_review = False
    for review_fact in review_facts:
        if review_fact.get("statement") == modified_statement:
            found_in_review = True
            assert review_fact.get("verification_reason") == modified_reason
            break
    
    assert found_in_review, "Modified fact should appear in the review tab"

def test_fact_status_change_persists_in_review_tab(setup_test_environment):
    """Test that changing a fact's status persists in the review tab."""
    gui, document_name, fact_repo, rejected_fact_repo = setup_test_environment
    
    # Add a verified test fact
    original_statement = f"Verified fact statement {uuid.uuid4()}"
    fact = add_test_fact(gui, document_name, original_statement, status="verified")
    
    # Verify the fact appears in the review tab as verified
    review_fact = get_fact_from_review_tab(gui, document_name, original_statement)
    assert review_fact is not None, "Fact should appear in the review tab initially"
    assert review_fact.get("verification_status") == "verified", "Initial fact should be verified"
    assert review_fact.get("id") is not None, "Fact should have an ID"
    print(f"Using fact ID: {review_fact.get('id')} for update")
    
    # Reject the fact
    rejection_reason = f"Rejection reason {uuid.uuid4()}"
    result, _ = gui.update_fact(review_fact.get("id"), original_statement, "rejected", rejection_reason)
    
    # Check the result
    assert "Fact updated" in result, f"Expected 'Fact updated' in result, got: {result}"
    
    # Verify the fact is removed from the verified repository
    verified_facts = fact_repo.get_all_facts()
    for fact in verified_facts:
        assert fact.get("statement") != original_statement, "Fact should be removed from verified repository"
    
    # Verify the fact is added to the rejected repository
    rejected_facts = rejected_fact_repo.get_all_rejected_facts()
    found_in_rejected = False
    for fact in rejected_facts:
        if fact.get("statement") == original_statement:
            found_in_rejected = True
            assert fact.get("verification_status") == "rejected"
            assert fact.get("verification_reason") == rejection_reason
            break
    
    assert found_in_rejected, "Fact should be added to rejected repository"
    
    # Verify the rejected fact appears in the review tab
    review_facts, _ = gui.get_facts_for_review()
    found_in_review = False
    for review_fact in review_facts:
        if review_fact.get("statement") == original_statement:
            found_in_review = True
            assert review_fact.get("verification_status") == "rejected"
            assert review_fact.get("verification_reason") == rejection_reason
            break
    
    assert found_in_review, "Rejected fact should still appear in the review tab"

def test_both_approved_and_rejected_facts_visible(setup_test_environment):
    """Test that both approved and rejected facts are visible in the review tab."""
    gui, document_name, fact_repo, rejected_fact_repo = setup_test_environment
    
    # Add a verified test fact
    verified_statement = f"Verified fact statement {uuid.uuid4()}"
    verified_fact = add_test_fact(gui, document_name, verified_statement, status="verified")
    
    # Add a rejected test fact
    rejected_statement = f"Rejected fact statement {uuid.uuid4()}"
    rejected_fact = add_test_fact(gui, document_name, rejected_statement, status="rejected")
    
    # Get all facts for review
    review_facts, fact_choices = gui.get_facts_for_review()
    
    # Verify both facts are present
    verified_found = False
    rejected_found = False
    
    for fact in review_facts:
        if fact.get("statement") == verified_statement:
            verified_found = True
            assert fact.get("verification_status") == "verified"
        
        if fact.get("statement") == rejected_statement:
            rejected_found = True
            assert fact.get("verification_status") == "rejected"
    
    assert verified_found, "Verified fact should appear in the review tab"
    assert rejected_found, "Rejected fact should appear in the review tab"
    
    # Ensure the choices list includes both facts
    assert len(fact_choices) >= 2, "Should have at least two choices in fact selector"
    
    # Check for verified and rejected status icons in choices
    verified_icon_found = False
    rejected_icon_found = False
    
    for choice in fact_choices:
        if "✅" in choice and verified_statement in choice:
            verified_icon_found = True
        if "❌" in choice and rejected_statement in choice:
            rejected_icon_found = True
    
    assert verified_icon_found, "Verified fact should have a ✅ icon in choices"
    assert rejected_icon_found, "Rejected fact should have a ❌ icon in choices"

def test_approve_rejected_fact_updates_review_tab(setup_test_environment):
    """Test that approving a rejected fact updates the review tab correctly."""
    gui, document_name, fact_repo, rejected_fact_repo = setup_test_environment
    
    # Add a rejected test fact
    original_statement = f"Rejected fact statement {uuid.uuid4()}"
    fact = add_test_fact(gui, document_name, original_statement, status="rejected")
    
    # Verify the fact appears in the review tab as rejected
    review_fact = get_fact_from_review_tab(gui, document_name, original_statement)
    assert review_fact is not None, "Fact should appear in the review tab initially"
    assert review_fact.get("verification_status") == "rejected", "Initial fact should be rejected"
    assert review_fact.get("id") is not None, "Fact should have an ID"
    print(f"Using fact ID: {review_fact.get('id')} for update")
    
    # Approve the fact
    approval_reason = f"Approval reason {uuid.uuid4()}"
    result, _ = gui.update_fact(review_fact.get("id"), original_statement, "verified", approval_reason)
    
    # Check the result
    assert "Fact updated" in result, f"Expected 'Fact updated' in result, got: {result}"
    
    # Verify the fact is removed from the rejected repository
    rejected_facts = rejected_fact_repo.get_all_rejected_facts()
    for fact in rejected_facts:
        assert fact.get("statement") != original_statement, "Fact should be removed from rejected repository"
    
    # Verify the fact is added to the verified repository
    verified_facts = fact_repo.get_all_facts()
    found_in_verified = False
    for fact in verified_facts:
        if fact.get("statement") == original_statement:
            found_in_verified = True
            assert fact.get("verification_status") == "verified"
            assert fact.get("verification_reason") == approval_reason
            break
    
    assert found_in_verified, "Fact should be added to verified repository"
    
    # Verify the approved fact appears in the review tab with updated status
    review_facts, _ = gui.get_facts_for_review()
    found_in_review = False
    for review_fact in review_facts:
        if review_fact.get("statement") == original_statement:
            found_in_review = True
            assert review_fact.get("verification_status") == "verified"
            assert review_fact.get("verification_reason") == approval_reason
            break
    
    assert found_in_review, "Approved fact should appear in the review tab with updated status"

def test_refresh_facts_data_synchronizes_with_repositories(setup_test_environment):
    """Test that refresh_facts_data properly synchronizes with repositories."""
    gui, document_name, fact_repo, rejected_fact_repo = setup_test_environment
    
    # Add facts directly to repositories
    verified_statement = f"Direct verified fact {uuid.uuid4()}"
    rejected_statement = f"Direct rejected fact {uuid.uuid4()}"
    
    # Add to repositories
    fact_repo.store_fact({
        "id": 12345,  # Explicit ID for testing
        "statement": verified_statement,
        "document_name": document_name,
        "verification_status": "verified",
        "verification_reason": "Added directly to repository",
        "timestamp": datetime.now().isoformat()
    })
    
    rejected_fact_repo.store_rejected_fact({
        "id": 67890,  # Explicit ID for testing
        "statement": rejected_statement,
        "document_name": document_name,
        "verification_status": "rejected",
        "rejection_reason": "Added directly to repository",
        "timestamp": datetime.now().isoformat()
    })
    
    # Before refreshing, check if facts_data has the new facts
    verified_in_memory = False
    rejected_in_memory = False
    
    if document_name in gui.facts_data:
        for fact in gui.facts_data[document_name].get("all_facts", []):
            if fact.get("statement") == verified_statement:
                verified_in_memory = True
            if fact.get("statement") == rejected_statement:
                rejected_in_memory = True
    
    # Either both should be missing or both should be present
    assert verified_in_memory == rejected_in_memory
    
    # Now refresh facts_data
    gui.refresh_facts_data()
    
    # Check if the new facts are in facts_data
    verified_in_memory = False
    rejected_in_memory = False
    
    if document_name in gui.facts_data:
        for fact in gui.facts_data[document_name].get("all_facts", []):
            if fact.get("statement") == verified_statement:
                verified_in_memory = True
            if fact.get("statement") == rejected_statement:
                rejected_in_memory = True
    
    assert verified_in_memory, "Verified fact should be in facts_data after refresh"
    assert rejected_in_memory, "Rejected fact should be in facts_data after refresh"
    
    # Check if the new facts appear in the review tab
    review_facts, _ = gui.get_facts_for_review()
    verified_in_review = False
    rejected_in_review = False
    
    for fact in review_facts:
        if fact.get("statement") == verified_statement:
            verified_in_review = True
        if fact.get("statement") == rejected_statement:
            rejected_in_review = True
    
    assert verified_in_review, "Verified fact should appear in the review tab after refresh"
    assert rejected_in_review, "Rejected fact should appear in the review tab after refresh" 
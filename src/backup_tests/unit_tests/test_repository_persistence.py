"""
Direct tests for the fact repository persistence functionality.

These tests focus on the core repository functionality to ensure
that modifications to facts are properly persisted to Excel files.
"""

import os
import sys
import uuid
import pytest
import pandas as pd
from datetime import datetime
import traceback


# Ensure the src directory is in the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Ensure the src directory is in the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))
from src.storage.fact_repository import FactRepository, RejectedFactRepository

@pytest.fixture
def setup_test_repositories():
    """Set up clean repositories with temporary Excel files for testing."""
    # Generate unique filenames to avoid test interference
    test_id = uuid.uuid4().hex[:8]
    facts_file = f"data/test_facts_{test_id}.xlsx"
    rejected_facts_file = f"data/test_rejected_facts_{test_id}.xlsx"
    
    # Create repositories with test files
    fact_repo = FactRepository(excel_path=facts_file)
    rejected_fact_repo = RejectedFactRepository(excel_path=rejected_facts_file)
    
    yield fact_repo, rejected_fact_repo, facts_file, rejected_facts_file
    
    # Clean up after tests
    for file in [facts_file, rejected_facts_file]:
        if os.path.exists(file):
            os.remove(file)

def test_store_and_retrieve_fact(setup_test_repositories):
    """Test basic storing and retrieving of facts from the repository."""
    fact_repo, _, facts_file, _ = setup_test_repositories
    
    # Create a test fact
    document_name = f"test_document_{uuid.uuid4().hex[:8]}"
    test_fact = {
        "statement": "This is a test fact.",
        "document_name": document_name,
        "source_chunk": 0,
        "original_text": "Test content",
        "verification_status": "verified",
        "verification_reason": "Initial verification",
        "timestamp": datetime.now().isoformat(),
    }
    
    # Store the fact
    fact_repo.store_fact(test_fact)
    
    # Get facts from the repository
    facts = fact_repo.get_facts(document_name)
    assert len(facts) == 1, "Should have one fact"
    
    # Verify the fact's content
    stored_fact = facts[0]
    assert stored_fact["statement"] == test_fact["statement"], "Statement should match"
    assert stored_fact["verification_status"] == "verified", "Status should be verified"
    
    # Force reload from Excel
    fact_repo._reload_facts_from_excel()
    
    # Verify persistence to Excel
    facts_after_reload = fact_repo.get_facts(document_name)
    assert len(facts_after_reload) == 1, "Should still have one fact after reload"
    assert facts_after_reload[0]["statement"] == test_fact["statement"], "Statement should persist"

def test_update_fact(setup_test_repositories):
    """Test updating a fact in the repository."""
    fact_repo, _, facts_file, _ = setup_test_repositories
    
    # Create a test fact
    document_name = f"test_document_{uuid.uuid4().hex[:8]}"
    test_fact = {
        "statement": "Original fact statement.",
        "document_name": document_name,
        "source_chunk": 0,
        "original_text": "Test content",
        "verification_status": "verified",
        "verification_reason": "Initial verification",
        "timestamp": datetime.now().isoformat(),
    }
    
    # Store the fact
    fact_repo.store_fact(test_fact)
    
    # Update the fact
    new_data = {
        "statement": "Updated fact statement.",
        "verification_reason": "Updated verification reason",
    }
    
    # Perform the update
    result = fact_repo.update_fact(document_name, test_fact["statement"], new_data)
    assert result is True, "Update should succeed"
    
    # Get updated facts
    facts = fact_repo.get_facts(document_name)
    assert len(facts) == 1, "Should still have one fact"
    
    # Verify the update
    updated_fact = facts[0]
    assert updated_fact["statement"] == new_data["statement"], "Statement should be updated"
    assert updated_fact["verification_reason"] == new_data["verification_reason"], "Reason should be updated"
    
    # Force reload from Excel
    fact_repo._reload_facts_from_excel()
    
    # Verify persistence to Excel
    facts_after_reload = fact_repo.get_facts(document_name)
    assert len(facts_after_reload) == 1, "Should still have one fact after reload"
    assert facts_after_reload[0]["statement"] == new_data["statement"], "Updated statement should persist"
    assert facts_after_reload[0]["verification_reason"] == new_data["verification_reason"], "Updated reason should persist"

def test_move_fact_between_repositories(setup_test_repositories):
    """Test moving a fact between verified and rejected repositories."""
    fact_repo, rejected_fact_repo, facts_file, rejected_facts_file = setup_test_repositories
    
    # Create a test fact
    document_name = f"test_document_{uuid.uuid4().hex[:8]}"
    test_fact = {
        "statement": "This fact will be moved between repositories.",
        "document_name": document_name,
        "source_chunk": 0,
        "original_text": "Test content",
        "verification_status": "verified",
        "verification_reason": "Initial verification",
        "timestamp": datetime.now().isoformat(),
    }
    
    # Store the fact in verified repository
    fact_repo.store_fact(test_fact)
    
    # Verify it's in the verified repository
    verified_facts = fact_repo.get_facts(document_name)
    assert len(verified_facts) == 1, "Should have one verified fact"
    
    # Move to rejected repository
    # 1. First copy the fact data
    fact_data = verified_facts[0].copy()
    fact_data["verification_status"] = "rejected"
    fact_data["verification_reason"] = "Rejected for testing"
    
    # 2. Store in rejected repository
    rejected_fact_repo.store_rejected_fact(fact_data)
    
    # 3. Remove from verified repository
    result = fact_repo.remove_fact(document_name, test_fact["statement"])
    assert result is True, "Removal should succeed"
    
    # Verify movement
    verified_facts = fact_repo.get_facts(document_name)
    rejected_facts = rejected_fact_repo.get_rejected_facts(document_name)
    
    assert len(verified_facts) == 0, "Should have no verified facts"
    assert len(rejected_facts) == 1, "Should have one rejected fact"
    
    # Force reload from Excel
    fact_repo._reload_facts_from_excel()
    rejected_fact_repo._reload_facts_from_excel()
    
    # Verify persistence to Excel
    verified_facts_after_reload = fact_repo.get_facts(document_name)
    rejected_facts_after_reload = rejected_fact_repo.get_rejected_facts(document_name)
    
    assert len(verified_facts_after_reload) == 0, "Should still have no verified facts after reload"
    assert len(rejected_facts_after_reload) == 1, "Should still have one rejected fact after reload"
    
    # Now move back to verified
    # 1. First copy the fact data
    fact_data = rejected_facts_after_reload[0].copy()
    fact_data["verification_status"] = "verified"
    fact_data["verification_reason"] = "Re-verified for testing"
    
    # 2. Store in verified repository
    fact_repo.store_fact(fact_data)
    
    # 3. Remove from rejected repository
    result = rejected_fact_repo.remove_rejected_fact(document_name, fact_data["statement"])
    assert result is True, "Removal from rejected should succeed"
    
    # Verify movement
    verified_facts = fact_repo.get_facts(document_name)
    rejected_facts = rejected_fact_repo.get_rejected_facts(document_name)
    
    assert len(verified_facts) == 1, "Should have one verified fact"
    assert len(rejected_facts) == 0, "Should have no rejected facts"
    
    # Force reload from Excel
    fact_repo._reload_facts_from_excel()
    rejected_fact_repo._reload_facts_from_excel()
    
    # Verify persistence to Excel
    verified_facts_after_reload = fact_repo.get_facts(document_name)
    rejected_facts_after_reload = rejected_fact_repo.get_rejected_facts(document_name)
    
    assert len(verified_facts_after_reload) == 1, "Should still have one verified fact after reload"
    assert len(rejected_facts_after_reload) == 0, "Should still have no rejected facts after reload"
    assert verified_facts_after_reload[0]["verification_reason"] == "Re-verified for testing", "Verification reason should be updated"

def test_multiple_fact_operations(setup_test_repositories):
    """Test multiple sequential operations on facts to ensure persistence."""
    fact_repo, rejected_fact_repo, facts_file, rejected_facts_file = setup_test_repositories
    
    # Create a document name
    document_name = f"test_document_{uuid.uuid4().hex[:8]}"
    
    # Create multiple facts
    facts = []
    for i in range(3):
        fact = {
            "statement": f"Test fact {i}",
            "document_name": document_name,
            "source_chunk": i,
            "original_text": f"Test content {i}",
            "verification_status": "verified",
            "verification_reason": f"Initial verification {i}",
            "timestamp": datetime.now().isoformat(),
        }
        facts.append(fact)
    
    # Store all facts
    for fact in facts:
        fact_repo.store_fact(fact)
    
    # Verify facts were stored
    stored_facts = fact_repo.get_facts(document_name)
    assert len(stored_facts) == 3, "Should have three facts"
    
    # Perform various operations
    # 1. Update fact 0
    update_result = fact_repo.update_fact(
        document_name,
        facts[0]["statement"],
        {"statement": "Updated fact 0", "verification_reason": "Updated reason 0"}
    )
    assert update_result is True, "Update should succeed"
    
    # 2. Reject fact 1
    # First copy the fact data
    fact1_data = None
    for fact in fact_repo.get_facts(document_name):
        if facts[1]["statement"] in fact["statement"]:
            fact1_data = fact.copy()
            break
    
    assert fact1_data is not None, "Fact 1 should be found"
    
    fact1_data["verification_status"] = "rejected"
    fact1_data["verification_reason"] = "Rejected for testing"
    
    # Store in rejected repository
    rejected_fact_repo.store_rejected_fact(fact1_data)
    
    # Remove from verified repository
    removal_result = fact_repo.remove_fact(document_name, facts[1]["statement"])
    assert removal_result is True, "Removal should succeed"
    
    # 3. Update fact 2
    update_result2 = fact_repo.update_fact(
        document_name,
        facts[2]["statement"],
        {"verification_reason": "Updated reason for fact 2"}
    )
    assert update_result2 is True, "Second update should succeed"
    
    # Force reload from Excel
    fact_repo._reload_facts_from_excel()
    rejected_fact_repo._reload_facts_from_excel()
    
    # Verify final state
    verified_facts = fact_repo.get_facts(document_name)
    rejected_facts = rejected_fact_repo.get_rejected_facts(document_name)
    
    assert len(verified_facts) == 2, "Should have two verified facts"
    assert len(rejected_facts) == 1, "Should have one rejected fact"
    
    # Check specific updates
    # Find updated fact 0
    updated_fact0 = None
    for fact in verified_facts:
        if "Updated fact 0" in fact["statement"]:
            updated_fact0 = fact
            break
    
    assert updated_fact0 is not None, "Updated fact 0 should be found"
    assert updated_fact0["verification_reason"] == "Updated reason 0", "Reason for fact 0 should be updated"
    
    # Find rejected fact 1
    rejected_fact1 = None
    for fact in rejected_facts:
        if facts[1]["statement"] in fact["statement"]:
            rejected_fact1 = fact
            break
    
    assert rejected_fact1 is not None, "Rejected fact 1 should be found"
    assert rejected_fact1["verification_status"] == "rejected", "Status for fact 1 should be rejected"
    
    # Find updated fact 2
    updated_fact2 = None
    for fact in verified_facts:
        if facts[2]["statement"] in fact["statement"]:
            updated_fact2 = fact
            break
    
    assert updated_fact2 is not None, "Updated fact 2 should be found"
    assert updated_fact2["verification_reason"] == "Updated reason for fact 2", "Reason for fact 2 should be updated"
    
    # Verify Excel files
    facts_df = pd.read_excel(facts_file)
    rejected_df = pd.read_excel(rejected_facts_file)
    
    assert len(facts_df) == 2, "Verified facts Excel file should have 2 rows"
    assert len(rejected_df) == 1, "Rejected facts Excel file should have 1 row"
    
    # Check Excel content for fact 0
    updated_fact0_in_excel = False
    for _, row in facts_df.iterrows():
        if "Updated fact 0" in str(row["statement"]):
            assert row["verification_reason"] == "Updated reason 0", "Excel should have updated reason for fact 0"
            updated_fact0_in_excel = True
    assert updated_fact0_in_excel, "Updated fact 0 should be in Excel"
    
    # Check Excel content for fact 1
    rejected_fact1_in_excel = False
    for _, row in rejected_df.iterrows():
        if facts[1]["statement"] in str(row["statement"]):
            assert row["verification_status"] == "rejected", "Excel should have rejected status for fact 1"
            rejected_fact1_in_excel = True
    assert rejected_fact1_in_excel, "Rejected fact 1 should be in Excel"

def test_excel_reloading_consistency(setup_test_repositories):
    """Test that reloading from Excel preserves all fact data correctly."""
    fact_repo, _, facts_file, _ = setup_test_repositories
    
    # Create a test fact with complex data
    document_name = f"test_document_{uuid.uuid4().hex[:8]}"
    test_fact = {
        "statement": "This is a test fact with complex data.",
        "document_name": document_name,
        "source_chunk": 0,
        "original_text": "Test content with special characters: !@#$%^&*()",
        "verification_status": "verified",
        "verification_reason": "Complex verification reason with multiple sentences. This is the second sentence.",
        "timestamp": datetime.now().isoformat(),
        "metadata": {
            "confidence": 0.95,
            "extracted_by": "test_case",
            "complex_key": "Complex value with special characters: !@#$%^&*()"
        }
    }
    
    # Store the fact
    fact_repo.store_fact(test_fact)
    
    # Verify the initial storage
    facts = fact_repo.get_facts(document_name)
    assert len(facts) == 1, "Should have one fact"
    
    # Force reload from Excel
    fact_repo._reload_facts_from_excel()
    
    # Get facts after reload
    facts_after_reload = fact_repo.get_facts(document_name)
    assert len(facts_after_reload) == 1, "Should still have one fact after reload"
    
    # Verify all data is preserved
    reloaded_fact = facts_after_reload[0]
    
    # Check basic fields
    assert reloaded_fact["statement"] == test_fact["statement"], "Statement should be preserved"
    assert reloaded_fact["verification_status"] == test_fact["verification_status"], "Status should be preserved"
    assert reloaded_fact["verification_reason"] == test_fact["verification_reason"], "Reason should be preserved"
    assert reloaded_fact["original_text"] == test_fact["original_text"], "Original text should be preserved"
    
    # Check metadata
    assert "metadata" in reloaded_fact, "Metadata should be preserved"
    assert reloaded_fact["metadata"].get("confidence") == test_fact["metadata"]["confidence"], "Metadata confidence should be preserved"
    assert reloaded_fact["metadata"].get("extracted_by") == test_fact["metadata"]["extracted_by"], "Metadata extracted_by should be preserved"
    assert reloaded_fact["metadata"].get("complex_key") == test_fact["metadata"]["complex_key"], "Complex metadata should be preserved"
    
    # Multiple reloads should be consistent
    for _ in range(3):
        fact_repo._reload_facts_from_excel()
        facts_after_multiple_reloads = fact_repo.get_facts(document_name)
        assert len(facts_after_multiple_reloads) == 1, "Should still have one fact after multiple reloads"
        assert facts_after_multiple_reloads[0]["statement"] == test_fact["statement"], "Statement should remain consistent"
        assert facts_after_multiple_reloads[0]["verification_reason"] == test_fact["verification_reason"], "Reason should remain consistent" 
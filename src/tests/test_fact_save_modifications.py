"""
Test case to verify fixes for fact modification saving and UI refresh issues.

This test specifically addresses two issues:
1. Save Error: Modifications to facts, including accepting a rejected fact, rejecting an accepted fact,
   and saving a modification trigger an error when saving
2. UI Inconsistency: Status changes (rejected→accepted) update in "all facts" list but not in the dropdown menu

The tests verify proper Excel file operations, data integrity, and UI components refresh.
"""

import os
import sys
import uuid
import pytest
import asyncio
import tempfile
import pandas as pd
import time
import shutil
from pathlib import Path
from datetime import datetime

# Ensure the src directory is in the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import required modules
from storage.fact_repository import FactRepository, RejectedFactRepository
from storage.chunk_repository import ChunkRepository
from gui.app import FactExtractionGUI

class TestFactSaveModifications:
    """Tests for verifying fact save modifications and UI updates."""
    
    @pytest.fixture
    def setup_test_environment(self):
        """Set up clean test environment with repositories for testing."""
        # Use unique test ID to avoid conflicts between test runs
        test_id = uuid.uuid4().hex[:8]
        
        # Create test directory
        test_dir = f"data/test_{test_id}"
        os.makedirs(test_dir, exist_ok=True)
        
        # Create repository files
        chunks_file = f"{test_dir}/test_chunks.xlsx"
        facts_file = f"{test_dir}/test_facts.xlsx"
        rejected_facts_file = f"{test_dir}/test_rejected_facts.xlsx"
        
        # Create repositories with test files
        chunk_repo = ChunkRepository(excel_path=chunks_file)
        fact_repo = FactRepository(excel_path=facts_file)
        rejected_fact_repo = RejectedFactRepository(excel_path=rejected_facts_file)
        
        # Create a subclass of FactExtractionGUI for testing with direct repository access
        class TestGUI(FactExtractionGUI):
            def __init__(self):
                self.state = None
                self.processing = False
                self.chunk_repo = chunk_repo
                self.fact_repo = fact_repo
                self.rejected_fact_repo = rejected_fact_repo
                self.facts_data = {}
                self.debug = True
                # Initialize the facts data
                self.refresh_facts_data()
                
            def debug_print(self, message):
                """Override debug_print to make it more targeted for tests."""
                print(f"TEST DEBUG: {message}")

            def refresh_facts_data(self):
                """Load facts from repositories into facts_data."""
                self.facts_data = {}
                # Load all facts from the repository
                verified_facts = self.fact_repo.get_all_facts(verified_only=True)
                all_facts = self.fact_repo.get_all_facts(verified_only=False)
                rejected_facts = self.rejected_fact_repo.get_all_rejected_facts()
                
                # Group facts by document name
                documents = set()
                for fact in all_facts + rejected_facts:
                    doc_name = fact.get("document_name", "Unknown Document")
                    documents.add(doc_name)
                
                # Create facts data structure
                for doc_name in documents:
                    doc_verified = [f for f in verified_facts if f.get("document_name") == doc_name]
                    doc_all = [f for f in all_facts if f.get("document_name") == doc_name]
                    doc_rejected = [f for f in rejected_facts if f.get("document_name") == doc_name]
                    
                    self.facts_data[doc_name] = {
                        "all_facts": doc_all + doc_rejected,
                        "verified_facts": doc_verified,
                        "total_facts": len(doc_all) + len(doc_rejected),
                        "verified_count": len(doc_verified),
                        "errors": []
                    }
                return self.facts_data
        
        # Create test GUI instance
        test_gui = TestGUI()
        
        # Create seed data for testing
        document_name = f"test_document_{test_id}"
        
        # Create and store verified fact
        verified_fact = {
            "document_name": document_name,
            "statement": "Test verified fact",
            "verification_status": "verified",
            "verification_reason": "This is a verified test fact",
            "timestamp": datetime.now().isoformat()
        }
        fact_repo.store_fact(verified_fact)
        
        # Create and store rejected fact
        rejected_fact = {
            "document_name": document_name,
            "statement": "Test rejected fact", 
            "verification_status": "rejected",
            "verification_reason": "This is a rejected test fact",
            "rejection_reason": "This is a rejected test fact",
            "timestamp": datetime.now().isoformat()
        }
        rejected_fact_repo.store_rejected_fact(rejected_fact)
        
        # Refresh facts data after storing
        test_gui.refresh_facts_data()
        
        # Yield the test environment
        yield test_gui, document_name, test_dir
        
        # Cleanup after tests
        try:
            if os.path.exists(test_dir):
                shutil.rmtree(test_dir)
        except Exception as e:
            print(f"Cleanup error: {str(e)}")
    
    def test_update_fact_with_transaction(self, setup_test_environment):
        """Test fact updates with transaction to ensure proper saving."""
        # Setup
        test_gui, document_name, _ = setup_test_environment
        
        # Get all facts for review
        all_facts, fact_choices = test_gui.get_facts_for_review()
        assert len(all_facts) == 2, "Should have 2 facts (1 verified, 1 rejected)"
        
        # Find the verified fact
        verified_fact = None
        for fact in all_facts:
            if fact.get("verification_status") == "verified":
                verified_fact = fact
                break
        
        assert verified_fact is not None, "Should have found a verified fact"
        fact_id = verified_fact.get("id")
        
        # Modify the fact with transaction
        new_statement = "Updated verified fact"
        new_reason = "This is an updated verification reason"
        result, updated_choices = test_gui.update_fact_with_transaction(
            fact_id, new_statement, "verified", new_reason
        )
        
        # Verify result
        assert "Updated" in result, f"Expected update success message, got: {result}"
        assert updated_choices is not None, "Should have returned updated choices"
        assert len(updated_choices) == 2, f"Should still have 2 fact choices, got {len(updated_choices)}"
        
        # Verify fact was updated in repository
        all_facts_after, _ = test_gui.get_facts_for_review()
        updated_fact = None
        for fact in all_facts_after:
            if fact.get("statement") == new_statement:
                updated_fact = fact
                break
        
        assert updated_fact is not None, "Updated fact should be found in the repository"
        assert updated_fact.get("verification_reason") == new_reason, "Verification reason should be updated"
        
        # Check Excel file was updated properly
        fact_repo = test_gui.fact_repo
        fact_repo._reload_facts_from_excel()  # Force reload from Excel
        repo_facts = fact_repo.get_all_facts(verified_only=False)
        
        found_in_excel = False
        for fact in repo_facts:
            if fact.get("statement") == new_statement:
                found_in_excel = True
                break
        
        assert found_in_excel, "Updated fact should be found in Excel file"
        
    def test_change_fact_status(self, setup_test_environment):
        """Test changing fact status between verified and rejected."""
        # Setup
        test_gui, document_name, _ = setup_test_environment
        
        # Get all facts for review
        all_facts, fact_choices = test_gui.get_facts_for_review()
        
        # Find the verified fact
        verified_fact = None
        for fact in all_facts:
            if fact.get("verification_status") == "verified":
                verified_fact = fact
                break
        
        assert verified_fact is not None, "Should have found a verified fact"
        fact_id = verified_fact.get("id")
        statement = verified_fact.get("statement")
        
        # Change verified -> rejected
        result, updated_choices = test_gui.update_fact_with_transaction(
            fact_id, statement, "rejected", "Rejected during test"
        )
        
        # Verify result
        assert "Fact updated" in result, f"Expected update success message, got: {result}"
        assert updated_choices is not None, "Should have returned updated choices"
        
        # Verify fact moved from verified to rejected repository
        verify_repo = test_gui.fact_repo
        reject_repo = test_gui.rejected_fact_repo
        
        # Force reload from Excel
        verify_repo._reload_facts_from_excel()
        reject_repo._reload_facts_from_excel()
        
        verified_facts = verify_repo.get_all_facts(verified_only=True)
        rejected_facts = reject_repo.get_all_rejected_facts()
        
        # Should no longer be in verified facts
        verified_statements = [f.get("statement") for f in verified_facts]
        assert statement not in verified_statements, "Fact should no longer be in verified facts"
        
        # Should now be in rejected facts
        rejected_statements = [f.get("statement") for f in rejected_facts]
        assert statement in rejected_statements, "Fact should now be in rejected facts"
        
        # Verify dropdown choices updated with new status
        # Look for the new status icon in dropdown choices
        for choice in updated_choices:
            if statement in choice:
                assert "❌" in choice, f"Choice should show rejected status: {choice}"
    
    def test_rejecting_verified_updating_dropdown(self, setup_test_environment):
        """Test that rejecting a verified fact properly updates the dropdown menu."""
        # Setup
        test_gui, document_name, _ = setup_test_environment
        
        # Get all facts for review
        all_facts, fact_choices = test_gui.get_facts_for_review()
        
        # Count initial verified and rejected facts in dropdown
        initial_verified_count = sum(1 for choice in fact_choices if "✅" in choice)
        initial_rejected_count = sum(1 for choice in fact_choices if "❌" in choice)
        
        # Find the verified fact
        verified_fact = None
        for fact in all_facts:
            if fact.get("verification_status") == "verified":
                verified_fact = fact
                break
        
        assert verified_fact is not None, "Should have found a verified fact"
        fact_id = verified_fact.get("id")
        statement = verified_fact.get("statement")
        
        # Change verified -> rejected
        result, updated_choices = test_gui.update_fact_with_transaction(
            fact_id, statement, "rejected", "Rejected during test"
        )
        
        # Verify dropdown choices updated correctly
        new_verified_count = sum(1 for choice in updated_choices if "✅" in choice)
        new_rejected_count = sum(1 for choice in updated_choices if "❌" in choice)
        
        assert new_verified_count == initial_verified_count - 1, "Verified count should decrease by 1"
        assert new_rejected_count == initial_rejected_count + 1, "Rejected count should increase by 1"
        
        # Find the specific dropdown choice for our fact
        fact_in_choices = False
        for choice in updated_choices:
            if statement in choice:
                fact_in_choices = True
                assert "❌" in choice, f"Fact should have rejected status in dropdown: {choice}"
        
        assert fact_in_choices, "Fact should be present in dropdown choices"
    
    def test_accepting_rejected_updating_dropdown(self, setup_test_environment):
        """Test that accepting a rejected fact properly updates the dropdown menu."""
        # Setup
        test_gui, document_name, _ = setup_test_environment
        
        # Get all facts for review
        all_facts, fact_choices = test_gui.get_facts_for_review()
        
        # Count initial verified and rejected facts in dropdown
        initial_verified_count = sum(1 for choice in fact_choices if "✅" in choice)
        initial_rejected_count = sum(1 for choice in fact_choices if "❌" in choice)
        
        # Find the rejected fact
        rejected_fact = None
        for fact in all_facts:
            if fact.get("verification_status") == "rejected":
                rejected_fact = fact
                break
        
        assert rejected_fact is not None, "Should have found a rejected fact"
        fact_id = rejected_fact.get("id")
        statement = rejected_fact.get("statement")
        
        # Change rejected -> verified
        result, updated_choices = test_gui.update_fact_with_transaction(
            fact_id, statement, "verified", "Verified during test"
        )
        
        # Verify dropdown choices updated correctly
        new_verified_count = sum(1 for choice in updated_choices if "✅" in choice)
        new_rejected_count = sum(1 for choice in updated_choices if "❌" in choice)
        
        assert new_verified_count == initial_verified_count + 1, "Verified count should increase by 1"
        assert new_rejected_count == initial_rejected_count - 1, "Rejected count should decrease by 1"
        
        # Find the specific dropdown choice for our fact
        fact_in_choices = False
        for choice in updated_choices:
            if statement in choice:
                fact_in_choices = True
                assert "✅" in choice, f"Fact should have verified status in dropdown: {choice}"
        
        assert fact_in_choices, "Fact should be present in dropdown choices"
    
    def test_modifying_statement_and_status(self, setup_test_environment):
        """Test changing both statement and status of a fact."""
        # Setup
        test_gui, document_name, _ = setup_test_environment
        
        # Get all facts for review
        all_facts, fact_choices = test_gui.get_facts_for_review()
        
        # Find the verified fact
        verified_fact = None
        for fact in all_facts:
            if fact.get("verification_status") == "verified":
                verified_fact = fact
                break
        
        assert verified_fact is not None, "Should have found a verified fact"
        fact_id = verified_fact.get("id")
        original_statement = verified_fact.get("statement")
        
        # Change both statement and status
        new_statement = "Modified statement and rejected"
        result, updated_choices = test_gui.update_fact_with_transaction(
            fact_id, new_statement, "rejected", "Modified and rejected during test"
        )
        
        # Verify result
        assert "Fact updated" in result, f"Expected update success message, got: {result}"
        
        # Verify fact moved repositories and was modified
        verify_repo = test_gui.fact_repo
        reject_repo = test_gui.rejected_fact_repo
        
        # Force reload from Excel
        verify_repo._reload_facts_from_excel()
        reject_repo._reload_facts_from_excel()
        
        # Should no longer be in verified facts with either statement
        verified_facts = verify_repo.get_all_facts(verified_only=True)
        verified_statements = [f.get("statement") for f in verified_facts]
        assert original_statement not in verified_statements, "Original statement should no longer be in verified facts"
        assert new_statement not in verified_statements, "New statement should not be in verified facts"
        
        # Should be in rejected facts with new statement
        rejected_facts = reject_repo.get_all_rejected_facts()
        rejected_statements = [f.get("statement") for f in rejected_facts]
        assert new_statement in rejected_statements, "New statement should be in rejected facts"
        
        # Verify dropdown choices updated with new statement and status
        # Look for the new statement and status icon in dropdown choices
        found_in_dropdown = False
        for choice in updated_choices:
            if new_statement in choice:
                found_in_dropdown = True
                assert "❌" in choice, f"Choice should show rejected status: {choice}"
        
        assert found_in_dropdown, "New statement should be present in dropdown choices"
    
    def test_dropdown_status_changes_properly_updated(self, setup_test_environment):
        """
        Test specifically targeting the UI inconsistency issue where status changes
        update in "all facts" list but not in the dropdown menu.
        """
        # Setup
        test_gui, document_name, _ = setup_test_environment
        
        # Get all facts for review
        all_facts, fact_choices = test_gui.get_facts_for_review()
        
        # Find the verified fact
        verified_fact = None
        for fact in all_facts:
            if fact.get("verification_status") == "verified":
                verified_fact = fact
                break
        
        assert verified_fact is not None, "Should have found a verified fact"
        fact_id = verified_fact.get("id")
        statement = verified_fact.get("statement")
        
        # Store the initial status icon
        initial_status = None
        for choice in fact_choices:
            if statement in choice:
                initial_status = '✅' if '✅' in choice else '❌'
                assert initial_status == '✅', f"Initial status should be verified: {choice}"
                break
        
        # Change verified -> rejected
        result, updated_choices = test_gui.update_fact_with_transaction(
            fact_id, statement, "rejected", "Rejected during dropdown test"
        )
        
        # Verify dropdown contains new status
        new_status = None
        for choice in updated_choices:
            if statement in choice:
                new_status = '✅' if '✅' in choice else '❌'
                break
        
        assert new_status == '❌', f"Status in dropdown should have changed to rejected"
        
        # Change it back to verified
        all_facts_after_reject, _ = test_gui.get_facts_for_review()
        rejected_fact = None
        for fact in all_facts_after_reject:
            if fact.get("statement") == statement:
                rejected_fact = fact
                break
        
        assert rejected_fact is not None, "Should have found the rejected fact"
        fact_id = rejected_fact.get("id")
        
        # Change rejected -> verified again
        result, updated_choices = test_gui.update_fact_with_transaction(
            fact_id, statement, "verified", "Verified again during dropdown test"
        )
        
        # Verify dropdown contains updated status
        final_status = None
        for choice in updated_choices:
            if statement in choice:
                final_status = '✅' if '✅' in choice else '❌'
                break
        
        assert final_status == '✅', f"Status in dropdown should have changed back to verified"
        
        # Verify repositories reflect the changes
        verify_repo = test_gui.fact_repo
        reject_repo = test_gui.rejected_fact_repo
        
        # Force reload from Excel
        verify_repo._reload_facts_from_excel()
        reject_repo._reload_facts_from_excel()
        
        # Should be in verified facts, not in rejected facts
        verified_facts = verify_repo.get_all_facts(verified_only=True)
        rejected_facts = reject_repo.get_all_rejected_facts()
        
        verified_statements = [f.get("statement") for f in verified_facts]
        rejected_statements = [f.get("statement") for f in rejected_facts]
        
        assert statement in verified_statements, "Fact should now be in verified facts"
        assert statement not in rejected_statements, "Fact should no longer be in rejected facts"
    
    def test_save_transaction_no_errors(self, setup_test_environment):
        """
        Test specifically targeting the save error issue where modifications to facts,
        including accepting a rejected fact, rejecting an accepted fact, and saving a modification
        trigger an error when saving.
        """
        # Setup
        test_gui, document_name, _ = setup_test_environment
        
        # Get all facts for review
        all_facts, fact_choices = test_gui.get_facts_for_review()
        
        # 1. Test modifying a verified fact
        verified_fact = None
        for fact in all_facts:
            if fact.get("verification_status") == "verified":
                verified_fact = fact
                break
        
        assert verified_fact is not None, "Should have found a verified fact"
        fact_id = verified_fact.get("id")
        
        # Perform multiple modifications to increase chances of triggering any race conditions
        for i in range(3):
            new_statement = f"Updated verified fact - iteration {i}"
            result, updated_choices = test_gui.update_fact_with_transaction(
                fact_id, new_statement, "verified", f"Updated reason - iteration {i}"
            )
            
            assert "Error" not in result, f"Expected success but got error: {result}"
            
            # Get the updated fact ID for the next iteration
            all_facts_updated, _ = test_gui.get_facts_for_review()
            for fact in all_facts_updated:
                if new_statement in fact.get("statement", ""):
                    fact_id = fact.get("id")
                    break
        
        # 2. Test rejecting a verified fact
        all_facts, fact_choices = test_gui.get_facts_for_review()
        verified_fact = None
        for fact in all_facts:
            if fact.get("verification_status") == "verified":
                verified_fact = fact
                break
                
        if verified_fact is None:
            # Create a new verified fact if none exists
            verified_fact = {
                "document_name": document_name,
                "statement": "New test verified fact",
                "verification_status": "verified",
                "verification_reason": "Created for test",
                "timestamp": datetime.now().isoformat()
            }
            test_gui.fact_repo.store_fact(verified_fact)
            all_facts, fact_choices = test_gui.get_facts_for_review()
            for fact in all_facts:
                if fact.get("statement") == "New test verified fact":
                    verified_fact = fact
                    break
            
        fact_id = verified_fact.get("id")
        statement = verified_fact.get("statement")
        
        # Reject the verified fact
        result, updated_choices = test_gui.update_fact_with_transaction(
            fact_id, statement, "rejected", "Rejected during save test"
        )
        
        assert "Error" not in result, f"Expected success when rejecting verified fact but got error: {result}"
        
        # 3. Test accepting a rejected fact
        all_facts, fact_choices = test_gui.get_facts_for_review()
        rejected_fact = None
        for fact in all_facts:
            if fact.get("verification_status") == "rejected":
                rejected_fact = fact
                break
        
        assert rejected_fact is not None, "Should have found a rejected fact"
        fact_id = rejected_fact.get("id")
        statement = rejected_fact.get("statement")
        
        # Accept the rejected fact
        result, updated_choices = test_gui.update_fact_with_transaction(
            fact_id, statement, "verified", "Verified during save test"
        )
        
        assert "Error" not in result, f"Expected success when accepting rejected fact but got error: {result}"
        
        # 4. Test modifying statement and status together
        all_facts, fact_choices = test_gui.get_facts_for_review()
        fact_to_modify = all_facts[0]  # Pick any fact
        fact_id = fact_to_modify.get("id")
        original_status = fact_to_modify.get("verification_status")
        new_status = "rejected" if original_status == "verified" else "verified"
        
        # Modify both statement and status
        result, updated_choices = test_gui.update_fact_with_transaction(
            fact_id, 
            "Modified statement with status change", 
            new_status, 
            "Modified during save test"
        )
        
        assert "Error" not in result, f"Expected success when modifying statement and status but got error: {result}"
        
        # Verify all repositories are in a good state
        verify_repo = test_gui.fact_repo
        reject_repo = test_gui.rejected_fact_repo
        
        # Force reload from Excel
        verify_repo._reload_facts_from_excel()
        reject_repo._reload_facts_from_excel()
        
        # Verify data consistency
        consistency = test_gui._verify_data_consistency()
        assert consistency, "Data should be consistent after all operations" 
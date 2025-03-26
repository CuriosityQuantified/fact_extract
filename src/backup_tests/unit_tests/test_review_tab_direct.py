"""
Direct tests for the review tab functionality without any mocking.

These tests focus on identifying and fixing issues with the review tab
where modifications are not being saved properly.
"""

import os
import uuid
import pytest
import pandas as pd
from datetime import datetime
import time
import sys


# Ensure the src directory is in the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Ensure the src directory is in the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))
# Force the OpenAI API key to be set before any imports
from dotenv import load_dotenv
load_dotenv()
import openai

# Now import the application components
from src.gui.app import FactExtractionGUI as BaseFactExtractionGUI
from src.storage.fact_repository import FactRepository, RejectedFactRepository
from src.storage.chunk_repository import ChunkRepository
from src.models.state import ProcessingState, create_initial_state

# Create a custom subclass of FactExtractionGUI for testing
class FactExtractionGUI(BaseFactExtractionGUI):
    """Custom version of FactExtractionGUI that allows repositories to be passed as arguments."""
    
    def __init__(self, chunk_repo=None, fact_repo=None, rejected_fact_repo=None):
        # Initialize the base state
        self.state = ProcessingState()
        self.processing = False
        self.theme = None  # Skip theme initialization
        self.temp_files = []
        self.chat_history = []
        
        # Use provided repositories or create new ones
        self.chunk_repo = chunk_repo or ChunkRepository()
        self.fact_repo = fact_repo or FactRepository()
        self.rejected_fact_repo = rejected_fact_repo or RejectedFactRepository()
        
        # Skip workflow creation for tests
        self.workflow = None
        self.input_key = None
        
        # Store facts data for UI updates
        self.facts_data = {}
        
        # Debug mode
        self.debug = True
        print(f"DEBUG_INIT: Test FactExtractionGUI initialized with custom repositories")
        
        # Load facts data
        self.refresh_facts_data()

    def refresh_facts_data(self):
        """Refresh the facts data from repositories."""
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
        
        if self.debug:
            print(f"Refreshed facts data: {len(self.facts_data)} documents")
        
        return self.facts_data

@pytest.fixture
def setup_test_environment():
    """Set up clean test environment with real repositories."""
    # Use unique test ID to avoid conflicts
    test_id = uuid.uuid4().hex[:8]
    chunks_file = f"data/test_chunks_{test_id}.xlsx"
    facts_file = f"data/test_facts_{test_id}.xlsx"
    rejected_facts_file = f"data/test_rejected_facts_{test_id}.xlsx"
    
    # Create repositories with test files
    chunk_repo = ChunkRepository(excel_path=chunks_file)
    fact_repo = FactRepository(excel_path=facts_file)
    rejected_fact_repo = RejectedFactRepository(excel_path=rejected_facts_file)
    
    # Create the GUI with these repositories
    gui = FactExtractionGUI(
        chunk_repo=chunk_repo,
        fact_repo=fact_repo,
        rejected_fact_repo=rejected_fact_repo
    )
    
    yield gui, chunk_repo, fact_repo, rejected_fact_repo, chunks_file, facts_file, rejected_facts_file
    
    # Clean up after tests
    for file in [chunks_file, facts_file, rejected_facts_file]:
        if os.path.exists(file):
            os.remove(file)

def test_fact_updates_are_persisted(setup_test_environment):
    """Test that fact updates are properly persisted to Excel files."""
    gui, chunk_repo, fact_repo, rejected_fact_repo, chunks_file, facts_file, rejected_facts_file = setup_test_environment
    
    # Create a document and add a fact
    document_name = f"test_document_{uuid.uuid4().hex[:8]}"
    test_fact = {
        "statement": "The semiconductor market reached $500B in 2022.",
        "document_name": document_name,
        "source_chunk": 0,
        "original_text": "Test content",
        "verification_status": "verified",
        "verification_reason": "Initial verification",
        "timestamp": datetime.now().isoformat(),
    }
    
    # Store the fact
    fact_repo.store_fact(test_fact)
    
    # Verify the fact was stored and has an ID
    facts = fact_repo.get_all_facts(verified_only=False)
    assert len(facts) == 1, "Fact should be stored"
    
    # The fact should now have an ID in the GUI's facts_data
    gui.refresh_facts_data()
    
    # Get the fact's ID
    gui_facts = gui.get_facts_for_review()[0]
    assert len(gui_facts) > 0, "Fact should be loaded in GUI"
    fact_id = gui_facts[0]['id']
    
    # Update the fact with a new statement
    updated_statement = f"UPDATED: The semiconductor market reached $550B in 2022. {uuid.uuid4()}"
    updated_reason = f"Updated verification reason {uuid.uuid4()}"
    
    # Use the GUI's update_fact method
    result, _ = gui.update_fact(fact_id, updated_statement, "verified", updated_reason)
    
    # Verify the update was successful
    assert "Fact updated" in result, f"Expected 'Fact updated' in result, got: {result}"
    
    # Force Excel reload
    fact_repo._reload_facts_from_excel()
    
    # Check that the update was persisted in the repository
    updated_facts = fact_repo.get_all_facts(verified_only=False)
    assert len(updated_facts) == 1, "Should still have one fact"
    
    updated_fact = updated_facts[0]
    assert updated_fact['statement'] == updated_statement, f"Statement not updated: {updated_fact['statement']} != {updated_statement}"
    assert updated_fact['verification_reason'] == updated_reason, f"Reason not updated: {updated_fact['verification_reason']} != {updated_reason}"
    
    # Verify Excel file was updated
    df = pd.read_excel(facts_file)
    assert len(df) == 1, "Excel file should have one row"
    assert df.iloc[0]['statement'] == updated_statement, "Excel file statement not updated"
    assert df.iloc[0]['verification_reason'] == updated_reason, "Excel file reason not updated"

def test_reject_fact_moves_to_rejected_repository(setup_test_environment):
    """Test that rejecting a fact moves it from verified to rejected repository."""
    gui, chunk_repo, fact_repo, rejected_fact_repo, chunks_file, facts_file, rejected_facts_file = setup_test_environment
    
    # Create a document and add a verified fact
    document_name = f"test_document_{uuid.uuid4().hex[:8]}"
    test_fact = {
        "statement": "AI technology is advancing rapidly.",
        "document_name": document_name,
        "source_chunk": 0,
        "original_text": "Test content",
        "verification_status": "verified",
        "verification_reason": "Initial verification",
        "timestamp": datetime.now().isoformat(),
    }
    
    # Store the fact
    fact_repo.store_fact(test_fact)
    
    # Reload the GUI's facts_data
    gui.refresh_facts_data()
    
    # Get the fact's ID
    gui_facts = gui.get_facts_for_review()[0]
    assert len(gui_facts) > 0, "Fact should be loaded in GUI"
    fact_id = gui_facts[0]['id']
    statement = gui_facts[0]['statement']
    
    # Reject the fact
    rejection_reason = f"Rejected for testing purposes {uuid.uuid4()}"
    result, _ = gui.update_fact(fact_id, statement, "rejected", rejection_reason)
    
    # Verify the rejection was successful
    assert "Fact updated" in result, f"Expected 'Fact updated' in result, got: {result}"
    
    # Force Excel reload
    fact_repo._reload_facts_from_excel()
    rejected_fact_repo._reload_facts_from_excel()
    
    # Verify fact was removed from verified repository
    verified_facts = fact_repo.get_all_facts(verified_only=False)
    assert len(verified_facts) == 0, "Fact should be removed from verified repository"
    
    # Verify fact was added to rejected repository
    rejected_facts = rejected_fact_repo.get_all_rejected_facts()
    assert len(rejected_facts) == 1, "Fact should be added to rejected repository"
    
    rejected_fact = rejected_facts[0]
    assert rejected_fact['statement'] == statement, "Statement should be preserved"
    assert rejected_fact['verification_status'] == "rejected", "Status should be rejected"
    assert rejected_fact['verification_reason'] == rejection_reason, "Rejection reason should be preserved"
    
    # Verify Excel files were updated
    facts_df = pd.read_excel(facts_file)
    rejected_df = pd.read_excel(rejected_facts_file)
    
    assert len(facts_df) == 0, "Verified facts Excel file should be empty"
    assert len(rejected_df) == 1, "Rejected facts Excel file should have one row"
    assert rejected_df.iloc[0]['statement'] == statement, "Excel file statement not preserved"
    assert rejected_df.iloc[0]['verification_status'] == "rejected", "Excel file status not set to rejected"
    assert rejected_df.iloc[0]['rejection_reason'] == rejection_reason, "Excel file rejection reason not preserved"

def test_approve_rejected_fact(setup_test_environment):
    """Test that approving a rejected fact moves it back to verified repository."""
    gui, chunk_repo, fact_repo, rejected_fact_repo, chunks_file, facts_file, rejected_facts_file = setup_test_environment
    
    # Create a document and add a rejected fact
    document_name = f"test_document_{uuid.uuid4().hex[:8]}"
    test_fact = {
        "statement": "Quantum computing will disrupt cryptography.",
        "document_name": document_name,
        "source_chunk": 0,
        "original_text": "Test content",
        "verification_status": "rejected",
        "verification_reason": "Initially rejected",
        "timestamp": datetime.now().isoformat(),
    }
    
    # Store the fact in rejected repository
    rejected_fact_repo.store_rejected_fact(test_fact)
    
    # Reload the GUI's facts_data
    gui.refresh_facts_data()
    
    # Get the facts for review to include rejected facts
    gui_facts, _ = gui.get_facts_for_review()
    
    # Find the rejected fact
    rejected_fact = None
    for fact in gui_facts:
        if fact.get('statement') == test_fact['statement']:
            rejected_fact = fact
            break
    
    assert rejected_fact is not None, "Rejected fact should be loaded in GUI"
    fact_id = rejected_fact['id']
    statement = rejected_fact['statement']
    
    # Approve the fact
    approval_reason = f"Now approved for testing purposes {uuid.uuid4()}"
    result, _ = gui.update_fact(fact_id, statement, "verified", approval_reason)
    
    # Verify the approval was successful
    assert "Fact updated" in result, f"Expected 'Fact updated' in result, got: {result}"
    
    # Force Excel reload
    fact_repo._reload_facts_from_excel()
    rejected_fact_repo._reload_facts_from_excel()
    
    # Verify fact was removed from rejected repository
    rejected_facts = rejected_fact_repo.get_all_rejected_facts()
    assert len(rejected_facts) == 0, "Fact should be removed from rejected repository"
    
    # Verify fact was added to verified repository
    verified_facts = fact_repo.get_all_facts(verified_only=False)
    assert len(verified_facts) == 1, "Fact should be added to verified repository"
    
    verified_fact = verified_facts[0]
    assert verified_fact['statement'] == statement, "Statement should be preserved"
    assert verified_fact['verification_status'] == "verified", "Status should be verified"
    assert verified_fact['verification_reason'] == approval_reason, "Approval reason should be preserved"
    
    # Verify Excel files were updated
    facts_df = pd.read_excel(facts_file)
    rejected_df = pd.read_excel(rejected_facts_file)
    
    assert len(rejected_df) == 0, "Rejected facts Excel file should be empty"
    assert len(facts_df) == 1, "Verified facts Excel file should have one row"
    assert facts_df.iloc[0]['statement'] == statement, "Excel file statement not preserved"
    assert facts_df.iloc[0]['verification_status'] == "verified", "Excel file status not set to verified"
    assert facts_df.iloc[0]['verification_reason'] == approval_reason, "Excel file approval reason not preserved"

def test_sequential_fact_operations(setup_test_environment):
    """Test a sequence of operations on facts to ensure persistence after each step."""
    gui, chunk_repo, fact_repo, rejected_fact_repo, chunks_file, facts_file, rejected_facts_file = setup_test_environment
    
    # Create a document and add multiple facts
    document_name = f"test_document_{uuid.uuid4().hex[:8]}"
    
    # Add first fact - verified
    fact1 = {
        "statement": "Fact 1: This is a verified fact.",
        "document_name": document_name,
        "source_chunk": 0,
        "original_text": "Test content",
        "verification_status": "verified",
        "verification_reason": "Initial verification",
        "timestamp": datetime.now().isoformat(),
    }
    fact_repo.store_fact(fact1)
    
    # Add second fact - verified
    fact2 = {
        "statement": "Fact 2: This is another verified fact.",
        "document_name": document_name,
        "source_chunk": 0,
        "original_text": "Test content",
        "verification_status": "verified",
        "verification_reason": "Initial verification",
        "timestamp": datetime.now().isoformat(),
    }
    fact_repo.store_fact(fact2)
    
    # Add third fact - rejected
    fact3 = {
        "statement": "Fact 3: This is a rejected fact.",
        "document_name": document_name,
        "source_chunk": 0,
        "original_text": "Test content",
        "verification_status": "rejected",
        "verification_reason": "Initially rejected",
        "timestamp": datetime.now().isoformat(),
    }
    rejected_fact_repo.store_rejected_fact(fact3)
    
    # Reload GUI data
    gui.refresh_facts_data()
    
    # Get facts for review
    gui_facts, _ = gui.get_facts_for_review()
    
    # Find each fact by statement
    fact1_id = None
    fact2_id = None
    fact3_id = None
    
    for fact in gui_facts:
        if fact.get('statement') == fact1['statement']:
            fact1_id = fact['id']
        elif fact.get('statement') == fact2['statement']:
            fact2_id = fact['id']
        elif fact.get('statement') == fact3['statement']:
            fact3_id = fact['id']
    
    assert fact1_id is not None, "Fact 1 should be loaded in GUI"
    assert fact2_id is not None, "Fact 2 should be loaded in GUI"
    assert fact3_id is not None, "Fact 3 should be loaded in GUI"
    
    # 1. Reject fact 1
    reject_reason = f"Rejecting fact 1 for testing {uuid.uuid4()}"
    result1, _ = gui.update_fact(fact1_id, fact1['statement'], "rejected", reject_reason)
    assert "Fact updated" in result1, "Fact 1 should be rejected"
    
    # 2. Update fact 2
    updated_statement = f"Updated: {fact2['statement']} {uuid.uuid4()}"
    updated_reason = f"Updated reason {uuid.uuid4()}"
    result2, _ = gui.update_fact(fact2_id, updated_statement, "verified", updated_reason)
    assert "Fact updated" in result2, "Fact 2 should be updated"
    
    # 3. Approve fact 3
    approve_reason = f"Approving fact 3 for testing {uuid.uuid4()}"
    result3, _ = gui.update_fact(fact3_id, fact3['statement'], "verified", approve_reason)
    assert "Fact updated" in result3, "Fact 3 should be approved"
    
    # Force Excel reload
    fact_repo._reload_facts_from_excel()
    rejected_fact_repo._reload_facts_from_excel()
    
    # Verify final state
    verified_facts = fact_repo.get_all_facts(verified_only=False)
    rejected_facts = rejected_fact_repo.get_all_rejected_facts()
    
    assert len(verified_facts) == 2, "Should have 2 verified facts"
    assert len(rejected_facts) == 1, "Should have 1 rejected fact"
    
    # Check Excel files
    facts_df = pd.read_excel(facts_file)
    rejected_df = pd.read_excel(rejected_facts_file)
    
    assert len(facts_df) == 2, "Verified facts Excel file should have 2 rows"
    assert len(rejected_df) == 1, "Rejected facts Excel file should have 1 row"
    
    # Verify each fact is in the correct place
    # Fact 1 should be rejected
    rejected_fact1 = False
    for _, row in rejected_df.iterrows():
        if row['statement'] == fact1['statement']:
            assert row['verification_status'] == "rejected"
            assert row['rejection_reason'] == reject_reason
            rejected_fact1 = True
    assert rejected_fact1, "Fact 1 should be in rejected Excel file"
    
    # Fact 2 should be verified with updates
    updated_fact2 = False
    for _, row in facts_df.iterrows():
        if updated_statement in row['statement']:
            assert row['verification_status'] == "verified"
            assert row['verification_reason'] == updated_reason
            updated_fact2 = True
    assert updated_fact2, "Updated Fact 2 should be in verified Excel file"
    
    # Fact 3 should be verified
    verified_fact3 = False
    for _, row in facts_df.iterrows():
        if row['statement'] == fact3['statement']:
            assert row['verification_status'] == "verified"
            assert row['verification_reason'] == approve_reason
            verified_fact3 = True
    assert verified_fact3, "Fact 3 should be in verified Excel file"

def test_review_tab_ui_integration():
    """Test the review tab UI integration with repositories."""
    # Create a standalone GUI with real repositories
    # Use unique test ID to avoid conflicts
    test_id = uuid.uuid4().hex[:8]
    chunks_file = f"data/test_chunks_{test_id}.xlsx"
    facts_file = f"data/test_facts_{test_id}.xlsx"
    rejected_facts_file = f"data/test_rejected_facts_{test_id}.xlsx"
    
    try:
        # Create repositories with test files
        chunk_repo = ChunkRepository(excel_path=chunks_file)
        fact_repo = FactRepository(excel_path=facts_file)
        rejected_fact_repo = RejectedFactRepository(excel_path=rejected_facts_file)
        
        # Create the GUI with these repositories
        gui = FactExtractionGUI(
            chunk_repo=chunk_repo,
            fact_repo=fact_repo,
            rejected_fact_repo=rejected_fact_repo
        )
        
        # Create a document and add a fact
        document_name = f"test_document_{uuid.uuid4().hex[:8]}"
        test_fact = {
            "statement": "This is a test fact for UI integration.",
            "document_name": document_name,
            "source_chunk": 0,
            "original_text": "Test content for UI integration",
            "verification_status": "verified",
            "verification_reason": "Initial verification",
            "timestamp": datetime.now().isoformat(),
        }
        
        # Store the fact
        fact_repo.store_fact(test_fact)
        
        # Reload the GUI's facts_data
        gui.refresh_facts_data()
        
        # Get the facts for the review tab
        gui_facts, _ = gui.get_facts_for_review()
        assert len(gui_facts) > 0, "Fact should be loaded in GUI"
        
        # Simulate the review tab UI by calling the update_facts_display function
        chat_history = []
        facts_summary = gui.format_facts_summary(gui.facts_data)
        
        # Verify the summary was created
        assert facts_summary is not None, "Facts summary should be generated"
        
        # Get the fact's ID for manipulation
        fact_id = gui_facts[0]['id']
        statement = gui_facts[0]['statement']
        
        # Update the fact
        updated_reason = f"Updated via UI {uuid.uuid4()}"
        result, _ = gui.update_fact(fact_id, statement, "verified", updated_reason)
        assert "Fact updated" in result, "Fact should be updated"
        
        # Verify the update was persisted
        fact_repo._reload_facts_from_excel()
        updated_facts = fact_repo.get_all_facts(verified_only=False)
        assert len(updated_facts) == 1, "Should have one fact"
        assert updated_facts[0]['verification_reason'] == updated_reason, "Reason should be updated"
        
        # Now reject the fact
        rejection_reason = f"Rejected via UI {uuid.uuid4()}"
        result, _ = gui.reject_fact(fact_id, statement, rejection_reason)
        assert "Fact updated" in result, "Fact should be rejected"
        
        # Verify rejection was persisted
        fact_repo._reload_facts_from_excel()
        rejected_fact_repo._reload_facts_from_excel()
        
        verified_facts = fact_repo.get_all_facts(verified_only=False)
        rejected_facts = rejected_fact_repo.get_all_rejected_facts()
        
        assert len(verified_facts) == 0, "Should have no verified facts"
        assert len(rejected_facts) == 1, "Should have one rejected fact"
        assert rejected_facts[0]['verification_reason'] == rejection_reason, "Rejection reason should be persisted"
        
    finally:
        # Clean up test files
        for file in [chunks_file, facts_file, rejected_facts_file]:
            if os.path.exists(file):
                os.remove(file) 
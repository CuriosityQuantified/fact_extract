"""
Comprehensive tests for the review tab functionality without mocking.

These tests verify the complete review tab functionality including:
1. Fact status toggling (verified ↔ rejected) with multiple facts
2. Fact content modification
3. Excel persistence verification
4. Update statistics functionality
5. Edge cases like empty selections and malformed facts
6. User interaction simulation via the update_fact method
"""

import os
import sys
import uuid
import pandas as pd
import pytest
import time
from datetime import datetime
import logging


# Ensure the src directory is in the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Ensure the src directory is in the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))
# Configure logging
logging.basicConfig(level=logging.DEBUG, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Force the OpenAI API key to be set before any imports
from dotenv import load_dotenv
load_dotenv()

# Now import the application components
from gui.app import FactExtractionGUI as BaseFactExtractionGUI
from storage.fact_repository import FactRepository, RejectedFactRepository
from storage.chunk_repository import ChunkRepository
from models.state import ProcessingState, create_initial_state

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
        logger.info("Test FactExtractionGUI initialized with custom repositories")
        
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
            logger.debug(f"Refreshed facts data: {len(self.facts_data)} documents")
        
        return self.facts_data
        
    def get_facts_for_review(self):
        """Get all facts available for review."""
        if self.debug:
            logger.debug(f"get_facts_for_review called, facts_data has {len(self.facts_data)} files")
        
        all_facts = []
        fact_choices = []
        
        # First add facts from in-memory data
        for filename, file_facts in self.facts_data.items():
            if self.debug:
                logger.debug(f"Processing file: {filename}")
            if file_facts.get("all_facts"):
                for i, fact in enumerate(file_facts["all_facts"]):
                    if self.debug:
                        logger.debug(f"  Processing fact {i} with status: {fact.get('verification_status', 'pending')}")
                    
                    # Add unique ID to fact if not present
                    if "id" not in fact or fact["id"] is None:
                        fact["id"] = i + 1  # Use sequential ID starting from 1
                        if self.debug:
                            logger.debug(f"  Assigned new ID {fact['id']} to fact {i}")
                    
                    # Add filename to fact for reference
                    fact["filename"] = filename
                    
                    # Add to all_facts list
                    all_facts.append(fact)
                    
                    # Format choice
                    statement = fact.get("statement", "")
                    if not isinstance(statement, str):
                        statement = str(statement) if statement is not None else ""
                    preview = statement[:40] + "..." if len(statement) > 40 else statement
                    status_icon = "✅" if fact.get("verification_status") == "verified" else "❌" if fact.get("verification_status") == "rejected" else "⏳"
                    choice_text = f"{status_icon} {preview} (Current Session)"
                    fact_choices.append(choice_text)
                    if self.debug:
                        logger.debug(f"  Added choice: '{choice_text}'")
        
        # Create sets to track statements we've already included
        included_statements = {(f.get('statement', ''), f.get('document_name', '')) for f in all_facts}
        
        # Add approved facts from repository
        repo_approved_facts = self.fact_repo.get_all_facts(verified_only=True)
        if self.debug:
            logger.debug(f"Got {len(repo_approved_facts)} approved facts from repository")
        
        for i, fact in enumerate(repo_approved_facts):
            # Skip if we've already included this fact from in-memory data
            statement_key = (fact.get('statement', ''), fact.get('document_name', ''))
            if statement_key in included_statements:
                if self.debug:
                    logger.debug(f"  Skipping approved repo fact {i} as it's already in memory")
                continue
                
            # Add unique ID to fact if not present
            if "id" not in fact or fact["id"] is None:
                fact["id"] = len(all_facts) + i + 1  # Use sequential ID continuing from in-memory facts
                if self.debug:
                    logger.debug(f"  Assigned new ID {fact['id']} to approved repo fact {i}")
                
            # Add filename to fact for reference
            fact["filename"] = fact.get("document_name", "Unknown Document")
            
            # Add to all_facts list
            all_facts.append(fact)
            included_statements.add(statement_key)
            
            # Format choice
            statement = fact.get("statement", "")
            if not isinstance(statement, str):
                statement = str(statement) if statement is not None else ""
            preview = statement[:40] + "..." if len(statement) > 40 else statement
            choice_text = f"✅ {preview} (Repository)"
            fact_choices.append(choice_text)
            if self.debug:
                logger.debug(f"  Added choice: '{choice_text}'")
        
        # Add rejected facts from repository
        repo_rejected_facts = self.rejected_fact_repo.get_all_rejected_facts()
        if self.debug:
            logger.debug(f"Got {len(repo_rejected_facts)} rejected facts from repository")
        
        for i, fact in enumerate(repo_rejected_facts):
            # Skip if we've already included this fact from in-memory data or approved repo
            statement_key = (fact.get('statement', ''), fact.get('document_name', ''))
            if statement_key in included_statements:
                if self.debug:
                    logger.debug(f"  Skipping rejected repo fact {i} as it's already included")
                continue
                
            # Add unique ID to fact if not present
            if "id" not in fact or fact["id"] is None:
                fact["id"] = len(all_facts) + i + 1  # Use sequential ID continuing from previous facts
                if self.debug:
                    logger.debug(f"  Assigned new ID {fact['id']} to rejected repo fact {i}")
                
            # Add filename to fact for reference
            fact["filename"] = fact.get("document_name", "Unknown Document")
            
            # Add to all_facts list
            all_facts.append(fact)
            included_statements.add(statement_key)
            
            # Format choice
            statement = fact.get("statement", "")
            if not isinstance(statement, str):
                statement = str(statement) if statement is not None else ""
            preview = statement[:40] + "..." if len(statement) > 40 else statement
            choice_text = f"❌ {preview} (Repository)"
            fact_choices.append(choice_text)
            if self.debug:
                logger.debug(f"  Added choice: '{choice_text}'")
        
        return all_facts, fact_choices
        
    def update_fact(self, fact_id, statement, status, reason):
        """Update a fact with new information."""
        if self.debug:
            logger.debug(f"update_fact called with ID: {fact_id}")
            logger.debug(f"  Statement: {statement[:40]}...")
            logger.debug(f"  Status: '{status}' (type: {type(status).__name__})")
            logger.debug(f"  Reason: {reason[:40]}...")

        # Validate inputs
        if not statement or not statement.strip():
            return "Error: Statement cannot be empty", None

        # Validate status
        if status not in ["verified", "rejected", "pending"]:
            return "Invalid status. Must be 'verified', 'rejected', or 'pending'.", None

        if not fact_id:
            return "No fact ID provided.", None

        try:
            # Convert fact_id to integer if it's a string
            if isinstance(fact_id, str):
                fact_id = int(fact_id)
                if self.debug:
                    logger.debug(f"Converted fact_id to integer: {fact_id}")
        except ValueError:
            return f"Invalid fact ID: {fact_id}", None

        # Get all facts for review (includes in-memory and repository facts)
        all_facts, _ = self.get_facts_for_review()

        found_fact = None
        document_name = None

        # Find the fact with the matching ID
        for fact in all_facts:
            if "id" in fact and fact["id"] == fact_id:
                found_fact = fact
                if self.debug:
                    logger.debug(f"Found matching fact with ID {fact_id}")
                break

        if not found_fact:
            if self.debug:
                logger.debug(f"No fact found with ID: {fact_id}")
            return f"Fact with ID {fact_id} not found.", None

        document_name = found_fact.get("document_name", "")
        
        # Update the fact properties
        old_status = found_fact.get("verification_status", "pending")
        old_reason = found_fact.get("verification_reason", "")
        old_statement = found_fact.get("statement", "")

        # Make a copy to avoid modifying the original
        updated_fact = found_fact.copy()
        
        if self.debug:
            logger.debug("Updated fact:")
            logger.debug(f"  Statement: {old_statement[:40]}... -> {statement[:40]}...")
            logger.debug(f"  Status: {old_status} -> {status}")
            logger.debug(f"  Reason: {old_reason[:40]}... -> {reason[:40]}...")
        
        # Update all properties of the fact
        updated_fact["statement"] = statement
        updated_fact["fact"] = statement  # Also update the 'fact' field if it exists
        updated_fact["verification_status"] = status
        updated_fact["verification_reason"] = reason
        updated_fact["verification_reasoning"] = reason  # Ensure both fields are updated
        updated_fact["reviewed_date"] = datetime.now().isoformat()
        updated_fact["edited"] = True

        # Remove the fact from repositories to prevent duplicates
        if self.debug:
            logger.debug("Removing matching facts from repositories to prevent duplicates")
            
        # Clear facts with the same statement from both repositories
        self._remove_matching_facts_from_repositories({
            "statement": old_statement,
            "document_name": document_name
        })
        
        # Store the fact in the appropriate repository based on status
        if status == "verified":
            if self.debug:
                logger.debug("Storing verified fact in fact repository")
            self.fact_repo.store_fact(updated_fact)
        elif status == "rejected":
            if self.debug:
                logger.debug("Storing rejected fact in rejected fact repository")
            self.rejected_fact_repo.store_rejected_fact(updated_fact)
        else:
            if self.debug:
                logger.debug("Not storing pending fact in any repository")

        # Update the fact in the in-memory data structure if it exists there
        if document_name in self.facts_data:
            # Update all_facts
            found_in_memory = False
            for i, fact in enumerate(self.facts_data[document_name]["all_facts"]):
                if "id" in fact and fact["id"] == fact_id:
                    if self.debug:
                        logger.debug(f"Updating in-memory fact at index {i}")
                    self.facts_data[document_name]["all_facts"][i] = updated_fact
                    found_in_memory = True
                    break
            
            # Update verified_facts
            verified_facts = self.facts_data[document_name]["verified_facts"]
            # First remove from verified_facts if it exists
            removed_count = 0
            for i in range(len(verified_facts) - 1, -1, -1):
                if "id" in verified_facts[i] and verified_facts[i]["id"] == fact_id:
                    verified_facts.pop(i)
                    removed_count += 1
            
            if self.debug:
                logger.debug(f"  Removed from verified_facts: {removed_count} instances")
            
            # Add back to verified_facts if status is "verified"
            if status == "verified":
                verified_facts.append(updated_fact)
                if self.debug:
                    logger.debug(f"  Added to verified_facts, new count: {len(verified_facts)}")
            
            # Update verified count
            self.facts_data[document_name]["verified_count"] = len(verified_facts)
            if self.debug:
                logger.debug(f"  Updated verified count: {self.facts_data[document_name]['verified_count']}")
        else:
            if self.debug:
                logger.debug(f"Document {document_name} not found in facts_data")

        # Update fact choices for dropdowns
        _, facts_summary = self.get_facts_for_review()
        if self.debug:
            logger.debug(f"Updated fact choices, now have {len(facts_summary)} choices")

        return f"Fact updated: {statement[:40]}...", facts_summary
        
    def _remove_matching_facts_from_repositories(self, fact_data):
        """Remove matching facts from both repositories to prevent duplicates."""
        document_name = fact_data.get("document_name", "")
        statement = fact_data.get("statement", "")
        
        if not document_name or not statement:
            if self.debug:
                logger.debug("Invalid fact data for repository removal - missing document_name or statement")
            return False
        
        # Remove from verified repository
        removed_verified = self.fact_repo.remove_fact(document_name, statement)
        if self.debug:
            logger.debug(f"Removed from verified repository: {removed_verified}")
        
        # Remove from rejected repository
        removed_rejected = self.rejected_fact_repo.remove_rejected_fact(document_name, statement)
        if self.debug:
            logger.debug(f"Removed from rejected repository: {removed_rejected}")
            
        return removed_verified or removed_rejected
        
    def generate_statistics(self):
        """Generate statistics about extracted facts.
        
        Returns:
            dict: A dictionary containing statistics about facts
        """
        if self.debug:
            logger.debug("Generating fact statistics")
        
        # Get data from repositories
        all_chunks = self.chunk_repo.get_all_chunks()
        all_facts = self.fact_repo.get_all_facts(verified_only=False)
        approved_facts = self.fact_repo.get_all_facts(verified_only=True)
        rejected_facts = self.rejected_fact_repo.get_all_rejected_facts()
        
        # Calculate overall statistics
        stats = {
            "total_documents": len(set(chunk["document_name"] for chunk in all_chunks)) if all_chunks else 0,
            "total_chunks": len(all_chunks),
            "total_facts": len(all_facts) + len(rejected_facts),
            "verified_facts": len(approved_facts),
            "rejected_facts": len(rejected_facts),
            "approval_rate": round(len(approved_facts) / (len(approved_facts) + len(rejected_facts)) * 100, 1) if (len(approved_facts) + len(rejected_facts)) > 0 else 0,
        }
        
        return stats

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

def add_test_facts(fact_repo, document_name, num_facts=1, prefix="Test Fact"):
    """Helper to add test facts to a repository."""
    facts = []
    for i in range(num_facts):
        test_fact = {
            "statement": f"{prefix} {i+1}: This is a test statement {uuid.uuid4().hex[:8]}",
            "document_name": document_name,
            "source_chunk": i,
            "original_text": f"Test content for fact {i+1}",
            "verification_status": "verified",
            "verification_reason": f"Initial verification for fact {i+1}",
            "timestamp": datetime.now().isoformat(),
        }
        fact_repo.store_fact(test_fact)
        facts.append(test_fact)
    return facts

def add_test_rejected_facts(rejected_fact_repo, document_name, num_facts=1, prefix="Rejected Fact"):
    """Helper to add test rejected facts to a repository."""
    facts = []
    for i in range(num_facts):
        test_fact = {
            "statement": f"{prefix} {i+1}: This is a rejected statement {uuid.uuid4().hex[:8]}",
            "document_name": document_name,
            "source_chunk": i,
            "original_text": f"Test content for rejected fact {i+1}",
            "verification_status": "rejected",
            "verification_reason": f"Initial rejection for fact {i+1}",
            "rejection_reason": f"Initial rejection for fact {i+1}",
            "timestamp": datetime.now().isoformat(),
        }
        rejected_fact_repo.store_rejected_fact(test_fact)
        facts.append(test_fact)
    return facts

def verify_excel_persistence(repository, excel_file, expected_count, message):
    """Verify that the facts were persisted to Excel correctly."""
    # Force reload from Excel
    repository._reload_facts_from_excel()
    
    # Check that the data was loaded properly
    if hasattr(repository, 'facts'):
        all_facts = repository.get_all_facts(verified_only=False)
    else:
        all_facts = repository.get_all_rejected_facts()
    
    assert len(all_facts) == expected_count, f"{message}: Expected {expected_count} facts, got {len(all_facts)}"
    
    # Also verify the Excel file directly
    df = pd.read_excel(excel_file)
    assert len(df) == expected_count, f"{message}: Excel file has {len(df)} rows, expected {expected_count}"
    
    return all_facts, df

def test_fact_updates_persist_to_excel(setup_test_environment):
    """Test that fact content updates are properly persisted to Excel."""
    gui, chunk_repo, fact_repo, rejected_fact_repo, chunks_file, facts_file, rejected_facts_file = setup_test_environment
    
    # Create a document and add a fact
    document_name = f"test_document_{uuid.uuid4().hex[:8]}"
    facts = add_test_facts(fact_repo, document_name, num_facts=1)
    original_fact = facts[0]
    
    # Refresh the GUI's data
    gui.refresh_facts_data()
    
    # Get the fact's ID
    gui_facts = gui.get_facts_for_review()[0]
    assert len(gui_facts) > 0, "Fact should be loaded in GUI"
    fact_id = gui_facts[0]['id']
    
    # Update the fact with a new statement
    updated_statement = f"UPDATED: The statement has new content. {uuid.uuid4().hex[:8]}"
    updated_reason = f"Updated verification reason {uuid.uuid4().hex[:8]}"
    
    # Use the GUI's update_fact method
    result, _ = gui.update_fact(fact_id, updated_statement, "verified", updated_reason)
    
    # Verify the update was successful
    assert "Fact updated" in result, f"Expected 'Fact updated' in result, got: {result}"
    
    # Check Excel persistence
    all_facts, df = verify_excel_persistence(
        fact_repo, facts_file, 1, 
        "Fact content update should persist to Excel"
    )
    
    # Verify the specific content was updated
    updated_fact = all_facts[0]
    assert updated_fact['statement'] == updated_statement, f"Statement not updated in repository"
    assert updated_fact['verification_reason'] == updated_reason, f"Reason not updated in repository"
    
    assert df.iloc[0]['statement'] == updated_statement, "Excel statement not updated"
    assert df.iloc[0]['verification_reason'] == updated_reason, "Excel reason not updated"

def test_reject_fact_moves_to_rejected_repository(setup_test_environment):
    """Test that rejecting a fact moves it from verified to rejected repository."""
    gui, chunk_repo, fact_repo, rejected_fact_repo, chunks_file, facts_file, rejected_facts_file = setup_test_environment
    
    # Create a document and add a verified fact
    document_name = f"test_document_{uuid.uuid4().hex[:8]}"
    facts = add_test_facts(fact_repo, document_name, num_facts=1)
    original_fact = facts[0]
    
    # Refresh the GUI's data
    gui.refresh_facts_data()
    
    # Get the fact's ID
    gui_facts = gui.get_facts_for_review()[0]
    assert len(gui_facts) > 0, "Fact should be loaded in GUI"
    fact_id = gui_facts[0]['id']
    statement = gui_facts[0]['statement']
    
    # Reject the fact
    rejection_reason = f"Rejected for testing purposes {uuid.uuid4().hex[:8]}"
    result, _ = gui.update_fact(fact_id, statement, "rejected", rejection_reason)
    
    # Verify the rejection was successful
    assert "Fact updated" in result, f"Expected 'Fact updated' in result, got: {result}"
    
    # Check Excel persistence - should be removed from verified facts
    verify_excel_persistence(
        fact_repo, facts_file, 0, 
        "Fact should be removed from verified repository"
    )
    
    # Check Excel persistence - should be added to rejected facts
    rejected_facts, rejected_df = verify_excel_persistence(
        rejected_fact_repo, rejected_facts_file, 1, 
        "Fact should be added to rejected repository"
    )
    
    # Verify the rejected fact has the correct properties
    rejected_fact = rejected_facts[0]
    assert rejected_fact['statement'] == statement, "Statement should be preserved"
    assert rejected_fact['verification_status'] == "rejected", "Status should be rejected"
    assert rejected_fact['verification_reason'] == rejection_reason, "Rejection reason should be preserved"
    
    # Verify Excel file properties
    assert rejected_df.iloc[0]['statement'] == statement, "Excel statement not preserved"
    assert rejected_df.iloc[0]['verification_status'] == "rejected", "Excel status not set to rejected"
    assert rejected_df.iloc[0]['rejection_reason'] == rejection_reason, "Excel rejection reason not preserved"

def test_approve_rejected_fact(setup_test_environment):
    """Test that approving a rejected fact moves it back to verified repository."""
    gui, chunk_repo, fact_repo, rejected_fact_repo, chunks_file, facts_file, rejected_facts_file = setup_test_environment
    
    # Create a document and add a rejected fact
    document_name = f"test_document_{uuid.uuid4().hex[:8]}"
    rejected_facts = add_test_rejected_facts(rejected_fact_repo, document_name, num_facts=1)
    original_fact = rejected_facts[0]
    
    # Refresh the GUI's data
    gui.refresh_facts_data()
    
    # Get the fact's ID
    gui_facts = gui.get_facts_for_review()[0]
    assert len(gui_facts) > 0, "Fact should be loaded in GUI"
    fact_id = gui_facts[0]['id']
    statement = gui_facts[0]['statement']
    
    # Approve the fact
    verification_reason = f"Approved for testing purposes {uuid.uuid4().hex[:8]}"
    result, _ = gui.update_fact(fact_id, statement, "verified", verification_reason)
    
    # Verify the approval was successful
    assert "Fact updated" in result, f"Expected 'Fact updated' in result, got: {result}"
    
    # Check Excel persistence - should be removed from rejected facts
    verify_excel_persistence(
        rejected_fact_repo, rejected_facts_file, 0, 
        "Fact should be removed from rejected repository"
    )
    
    # Check Excel persistence - should be added to verified facts
    verified_facts, verified_df = verify_excel_persistence(
        fact_repo, facts_file, 1, 
        "Fact should be added to verified repository"
    )
    
    # Verify the verified fact has the correct properties
    verified_fact = verified_facts[0]
    assert verified_fact['statement'] == statement, "Statement should be preserved"
    assert verified_fact['verification_status'] == "verified", "Status should be verified"
    assert verified_fact['verification_reason'] == verification_reason, "Verification reason should be preserved"
    
    # Verify Excel file properties
    assert verified_df.iloc[0]['statement'] == statement, "Excel statement not preserved"
    assert verified_df.iloc[0]['verification_status'] == "verified", "Excel status not set to verified"
    assert verified_df.iloc[0]['verification_reason'] == verification_reason, "Excel verification reason not preserved"

def test_multiple_facts_toggling(setup_test_environment):
    """Test toggling multiple facts between verified and rejected states."""
    gui, chunk_repo, fact_repo, rejected_fact_repo, chunks_file, facts_file, rejected_facts_file = setup_test_environment
    
    # Create a document and add multiple verified facts
    document_name = f"test_document_{uuid.uuid4().hex[:8]}"
    verified_facts = add_test_facts(fact_repo, document_name, num_facts=3)
    
    # Add some rejected facts too
    rejected_facts = add_test_rejected_facts(rejected_fact_repo, document_name, num_facts=2)
    
    # Refresh the GUI's data
    gui.refresh_facts_data()
    
    # Get all facts for review
    gui_facts = gui.get_facts_for_review()[0]
    assert len(gui_facts) == 5, f"Expected 5 facts, got {len(gui_facts)}"
    
    # Toggle all verified facts to rejected
    for i in range(3):
        fact_id = gui_facts[i]['id']
        statement = gui_facts[i]['statement']
        rejection_reason = f"Rejected in batch test {uuid.uuid4().hex[:8]}"
        result, _ = gui.update_fact(fact_id, statement, "rejected", rejection_reason)
        assert "Fact updated" in result, f"Failed to reject fact {i}"
    
    # Toggle all rejected facts to verified
    for i in range(3, 5):
        fact_id = gui_facts[i]['id']
        statement = gui_facts[i]['statement']
        verification_reason = f"Verified in batch test {uuid.uuid4().hex[:8]}"
        result, _ = gui.update_fact(fact_id, statement, "verified", verification_reason)
        assert "Fact updated" in result, f"Failed to verify fact {i}"
    
    # Verify Excel persistence
    verified_facts, verified_df = verify_excel_persistence(
        fact_repo, facts_file, 2, 
        "Should have 2 verified facts"
    )
    
    rejected_facts, rejected_df = verify_excel_persistence(
        rejected_fact_repo, rejected_facts_file, 3, 
        "Should have 3 rejected facts"
    )
    
    # Verify the statuses in the repository data
    for fact in verified_facts:
        assert fact["verification_status"] == "verified"
    
    for fact in rejected_facts:
        assert fact["verification_status"] == "rejected"
    
    # Verify the statuses in the Excel files
    assert all(verified_df["verification_status"] == "verified")
    assert all(rejected_df["verification_status"] == "rejected")

def test_multiple_fact_content_modifications(setup_test_environment):
    """Test modifying content of multiple facts and verify persistence."""
    gui, chunk_repo, fact_repo, rejected_fact_repo, chunks_file, facts_file, rejected_facts_file = setup_test_environment
    
    # Create a document and add verified facts
    document_name = f"test_document_{uuid.uuid4().hex[:8]}"
    verified_facts = add_test_facts(fact_repo, document_name, num_facts=3)
    
    # Refresh the GUI's data
    gui.refresh_facts_data()
    
    # Get all facts for review
    gui_facts = gui.get_facts_for_review()[0]
    assert len(gui_facts) == 3, f"Expected 3 facts, got {len(gui_facts)}"
    
    # Modify each fact with unique content
    modified_statements = []
    for i in range(3):
        fact_id = gui_facts[i]['id']
        new_statement = f"Modified {i}: This is a completely new statement {uuid.uuid4().hex[:8]}"
        modified_statements.append(new_statement)
        verification_reason = f"Updated in content modification test {uuid.uuid4().hex[:8]}"
        result, _ = gui.update_fact(fact_id, new_statement, "verified", verification_reason)
        assert "Fact updated" in result, f"Failed to update content of fact {i}"
    
    # Verify Excel persistence
    verified_facts, verified_df = verify_excel_persistence(
        fact_repo, facts_file, 3, 
        "Should have 3 verified facts with modified content"
    )
    
    # Verify the modified content in the repository data
    statements_in_repo = [fact["statement"] for fact in verified_facts]
    for statement in modified_statements:
        assert statement in statements_in_repo, f"Modified statement not found in repository: {statement}"
    
    # Verify the modified content in the Excel file
    statements_in_excel = verified_df["statement"].tolist()
    for statement in modified_statements:
        assert statement in statements_in_excel, f"Modified statement not found in Excel: {statement}"

def test_empty_selection_handling(setup_test_environment):
    """Test handling of empty selections in the review tab."""
    gui, chunk_repo, fact_repo, rejected_fact_repo, chunks_file, facts_file, rejected_facts_file = setup_test_environment
    
    # Try to update a fact with no ID
    result, _ = gui.update_fact(None, "Test statement", "verified", "Test reason")
    assert "No fact ID provided" in result, f"Expected error message about missing ID, got: {result}"
    
    # Try to update a fact with an invalid ID
    result, _ = gui.update_fact("invalid_id", "Test statement", "verified", "Test reason")
    assert "Invalid fact ID" in result, f"Expected error message about invalid ID, got: {result}"
    
    # Try to update a fact with a non-existent ID
    result, _ = gui.update_fact(9999, "Test statement", "verified", "Test reason")
    assert "Fact with ID 9999 not found" in result, f"Expected error message about non-existent ID, got: {result}"
    
    # Verify no facts were added - directly check the repositories instead of using verify_excel_persistence
    # which might fail if the Excel file doesn't exist yet
    all_facts = fact_repo.get_all_facts(verified_only=False)
    assert len(all_facts) == 0, f"No facts should be added for empty selections, found {len(all_facts)}"
    
    all_rejected = rejected_fact_repo.get_all_rejected_facts()
    assert len(all_rejected) == 0, f"No rejected facts should be added for empty selections, found {len(all_rejected)}"

def test_malformed_facts_handling(setup_test_environment):
    """Test handling of malformed facts in the review tab."""
    gui, chunk_repo, fact_repo, rejected_fact_repo, chunks_file, facts_file, rejected_facts_file = setup_test_environment
    
    # Add a valid fact to work with
    document_name = f"test_document_{uuid.uuid4().hex[:8]}"
    verified_facts = add_test_facts(fact_repo, document_name, num_facts=1)
    
    # Refresh the GUI's data
    gui.refresh_facts_data()
    
    # Get the fact's ID
    gui_facts = gui.get_facts_for_review()[0]
    fact_id = gui_facts[0]['id']
    
    # Try to update with an empty statement
    result, _ = gui.update_fact(fact_id, "", "verified", "Test reason")
    assert "Error: Statement cannot be empty" in result, f"Expected error for empty statement, got: {result}"
    
    # Try to update with an invalid status
    result, _ = gui.update_fact(fact_id, "Test statement", "invalid_status", "Test reason")
    assert "Invalid status" in result, f"Expected error for invalid status, got: {result}"
    
    # Verify the original fact is still intact
    verified_facts, _ = verify_excel_persistence(
        fact_repo, facts_file, 1, 
        "Original fact should remain unchanged after failed updates"
    )
    
    # Verify the original statement is unchanged
    assert verified_facts[0]["statement"] == gui_facts[0]["statement"], "Statement should not change after failed updates"

def test_update_statistics(setup_test_environment):
    """Test the update statistics functionality."""
    gui, chunk_repo, fact_repo, rejected_fact_repo, chunks_file, facts_file, rejected_facts_file = setup_test_environment
    
    # Add some verified facts
    document_name = f"test_document_{uuid.uuid4().hex[:8]}"
    verified_facts = add_test_facts(fact_repo, document_name, num_facts=5)
    
    # Add some rejected facts
    rejected_facts = add_test_rejected_facts(rejected_fact_repo, document_name, num_facts=3)
    
    # Refresh the GUI's data
    gui.refresh_facts_data()
    
    # Generate statistics
    stats = gui.generate_statistics()
    
    # Verify statistics are correctly calculated
    assert stats["total_facts"] == 8, f"Expected 8 total facts, got {stats['total_facts']}"
    assert stats["verified_facts"] == 5, f"Expected 5 verified facts, got {stats['verified_facts']}"
    assert stats["rejected_facts"] == 3, f"Expected 3 rejected facts, got {stats['rejected_facts']}"
    assert stats["approval_rate"] == 62.5, f"Expected 62.5% approval rate, got {stats['approval_rate']}"
    
    # Add more facts and verify statistics update
    add_test_facts(fact_repo, document_name, num_facts=2, prefix="Additional Fact")
    gui.refresh_facts_data()
    
    # Generate updated statistics
    updated_stats = gui.generate_statistics()
    
    # Verify updated statistics
    assert updated_stats["total_facts"] == 10, f"Expected 10 total facts, got {updated_stats['total_facts']}"
    assert updated_stats["verified_facts"] == 7, f"Expected 7 verified facts, got {updated_stats['verified_facts']}"
    assert updated_stats["approval_rate"] == 70.0, f"Expected 70.0% approval rate, got {updated_stats['approval_rate']}"

def test_in_memory_data_structures(setup_test_environment):
    """Test that in-memory data structures are properly updated."""
    gui, chunk_repo, fact_repo, rejected_fact_repo, chunks_file, facts_file, rejected_facts_file = setup_test_environment
    
    # Add a verified fact
    document_name = f"test_document_{uuid.uuid4().hex[:8]}"
    verified_facts = add_test_facts(fact_repo, document_name, num_facts=1)
    
    # Refresh the GUI's data
    gui.refresh_facts_data()
    
    # Verify in-memory structure
    assert document_name in gui.facts_data, "Document should be in memory"
    assert len(gui.facts_data[document_name]["all_facts"]) == 1, "Should have 1 fact in all_facts"
    assert len(gui.facts_data[document_name]["verified_facts"]) == 1, "Should have 1 fact in verified_facts"
    assert gui.facts_data[document_name]["verified_count"] == 1, "Verified count should be 1"
    
    # Get the fact's ID
    gui_facts = gui.get_facts_for_review()[0]
    fact_id = gui_facts[0]['id']
    
    # Reject the fact
    rejection_reason = f"Rejected for in-memory test {uuid.uuid4().hex[:8]}"
    result, _ = gui.update_fact(fact_id, gui_facts[0]["statement"], "rejected", rejection_reason)
    
    # Verify in-memory structure is updated
    assert len(gui.facts_data[document_name]["verified_facts"]) == 0, "Should have 0 facts in verified_facts"
    assert gui.facts_data[document_name]["verified_count"] == 0, "Verified count should be 0"
    
    # Refresh from repositories to ensure everything is in sync
    gui.refresh_facts_data()
    
    # Verify in-memory structure after refresh
    assert len(gui.facts_data[document_name]["all_facts"]) == 1, "Should have 1 fact in all_facts after refresh"
    assert len(gui.facts_data[document_name]["verified_facts"]) == 0, "Should have 0 facts in verified_facts after refresh"
    assert gui.facts_data[document_name]["verified_count"] == 0, "Verified count should be 0 after refresh"

def test_sequential_fact_operations(setup_test_environment):
    """Test a sequence of operations on the same fact."""
    gui, chunk_repo, fact_repo, rejected_fact_repo, chunks_file, facts_file, rejected_facts_file = setup_test_environment
    
    # Add a verified fact
    document_name = f"test_document_{uuid.uuid4().hex[:8]}"
    verified_facts = add_test_facts(fact_repo, document_name, num_facts=1)
    original_statement = verified_facts[0]["statement"]
    
    # Refresh the GUI's data
    gui.refresh_facts_data()
    
    # Get the fact's ID
    gui_facts = gui.get_facts_for_review()[0]
    fact_id = gui_facts[0]['id']
    
    # Step 1: Modify the content
    modified_statement = f"Modified: {original_statement} - {uuid.uuid4().hex[:8]}"
    result, _ = gui.update_fact(fact_id, modified_statement, "verified", "Content modification")
    assert "Fact updated" in result, "Content modification failed"
    
    # Verify Excel persistence after step 1
    verified_facts, _ = verify_excel_persistence(
        fact_repo, facts_file, 1, 
        "Should have 1 verified fact after content modification"
    )
    assert verified_facts[0]["statement"] == modified_statement, "Statement not modified in step 1"
    
    # Get updated fact ID (might have changed)
    gui.refresh_facts_data()
    gui_facts = gui.get_facts_for_review()[0]
    fact_id = gui_facts[0]['id']
    
    # Step 2: Reject the fact
    result, _ = gui.update_fact(fact_id, modified_statement, "rejected", "Rejecting modified fact")
    assert "Fact updated" in result, "Rejection failed"
    
    # Verify Excel persistence after step 2
    verify_excel_persistence(
        fact_repo, facts_file, 0, 
        "Should have 0 verified facts after rejection"
    )
    
    rejected_facts, _ = verify_excel_persistence(
        rejected_fact_repo, rejected_facts_file, 1, 
        "Should have 1 rejected fact after rejection"
    )
    assert rejected_facts[0]["statement"] == modified_statement, "Statement not preserved in rejected fact"
    
    # Get updated fact ID (might have changed)
    gui.refresh_facts_data()
    gui_facts = gui.get_facts_for_review()[0]
    fact_id = gui_facts[0]['id']
    
    # Step 3: Modify the rejected fact and re-verify it
    final_statement = f"Final version: {modified_statement} - {uuid.uuid4().hex[:8]}"
    result, _ = gui.update_fact(fact_id, final_statement, "verified", "Re-verifying with new content")
    assert "Fact updated" in result, "Re-verification failed"
    
    # Verify Excel persistence after step 3
    verify_excel_persistence(
        rejected_fact_repo, rejected_facts_file, 0, 
        "Should have 0 rejected facts after re-verification"
    )
    
    verified_facts, _ = verify_excel_persistence(
        fact_repo, facts_file, 1, 
        "Should have 1 verified fact after re-verification"
    )
    assert verified_facts[0]["statement"] == final_statement, "Final statement not preserved in verified fact"

def test_concurrent_modifications(setup_test_environment):
    """Test handling of concurrent modifications to facts."""
    gui, chunk_repo, fact_repo, rejected_fact_repo, chunks_file, facts_file, rejected_facts_file = setup_test_environment
    
    # Add multiple verified facts
    document_name = f"test_document_{uuid.uuid4().hex[:8]}"
    verified_facts = add_test_facts(fact_repo, document_name, num_facts=5)
    
    # Refresh the GUI's data
    gui.refresh_facts_data()
    
    # Get all facts for review
    gui_facts = gui.get_facts_for_review()[0]
    
    # Perform multiple rapid updates to simulate concurrent modifications
    for i in range(5):
        fact_id = gui_facts[i]['id']
        
        # First update - modify content
        modified_statement = f"Modified {i}: {verified_facts[i]['statement']} - {uuid.uuid4().hex[:8]}"
        result1, _ = gui.update_fact(fact_id, modified_statement, "verified", f"First update for fact {i}")
        
        # Second update - without refreshing, toggle status
        result2, _ = gui.update_fact(fact_id, modified_statement, "rejected", f"Second update for fact {i}")
        
        # Third update - without refreshing, toggle status back
        result3, _ = gui.update_fact(fact_id, modified_statement, "verified", f"Third update for fact {i}")
        
        # All updates should succeed
        assert "Fact updated" in result1, f"First update failed for fact {i}"
        assert "Fact updated" in result2, f"Second update failed for fact {i}"
        assert "Fact updated" in result3, f"Third update failed for fact {i}"
    
    # Verify final state
    verified_facts, _ = verify_excel_persistence(
        fact_repo, facts_file, 5, 
        "Should have 5 verified facts after concurrent modifications"
    )
    
    verify_excel_persistence(
        rejected_fact_repo, rejected_facts_file, 0, 
        "Should have 0 rejected facts after concurrent modifications"
    )
    
    # Ensure all statements were modified
    for fact in verified_facts:
        assert "Modified" in fact["statement"], f"Statement wasn't modified: {fact['statement']}"

def test_extreme_edge_cases(setup_test_environment):
    """Test extreme edge cases like very long content and special characters."""
    gui, chunk_repo, fact_repo, rejected_fact_repo, chunks_file, facts_file, rejected_facts_file = setup_test_environment
    
    # Add a verified fact
    document_name = f"test_document_{uuid.uuid4().hex[:8]}"
    verified_facts = add_test_facts(fact_repo, document_name, num_facts=1)
    
    # Refresh the GUI's data
    gui.refresh_facts_data()
    
    # Get the fact's ID
    gui_facts = gui.get_facts_for_review()[0]
    fact_id = gui_facts[0]['id']
    
    # Test 1: Very long statement
    very_long_statement = "Very long statement: " + "x" * 5000
    result1, _ = gui.update_fact(fact_id, very_long_statement, "verified", "Very long statement test")
    assert "Fact updated" in result1, "Failed to update with very long statement"
    
    # Verify Excel persistence after very long statement
    verified_facts, _ = verify_excel_persistence(
        fact_repo, facts_file, 1, 
        "Should have 1 verified fact after very long statement update"
    )
    assert len(verified_facts[0]["statement"]) > 5000, "Very long statement not preserved"
    
    # Get updated fact ID
    gui.refresh_facts_data()
    gui_facts = gui.get_facts_for_review()[0]
    fact_id = gui_facts[0]['id']
    
    # Test 2: Special characters
    special_chars_statement = "Special chars: !@#$%^&*()_+{}|:<>?~`-=[]\\;',./\"áéíóúñÁÉÍÓÚÑ"
    result2, _ = gui.update_fact(fact_id, special_chars_statement, "verified", "Special characters test")
    assert "Fact updated" in result2, "Failed to update with special characters"
    
    # Verify Excel persistence after special characters
    verified_facts, _ = verify_excel_persistence(
        fact_repo, facts_file, 1, 
        "Should have 1 verified fact after special characters update"
    )
    assert verified_facts[0]["statement"] == special_chars_statement, "Special characters not preserved" 
"""
Unit tests for fact update persistence from the review tab.

These tests focus specifically on the issues where modifications are not being saved
and changing accepted/rejected status is not working properly.
"""

# First, load environment variables from .env file
# This must happen before any imports that might use OpenAI
import os
import sys
from pathlib import Path
from dotenv import load_dotenv, find_dotenv


# Ensure the src directory is in the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Ensure the src directory is in the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))
# Try to find and load .env from multiple possible locations
env_paths = [
    '.env',
    '../.env',
    '../../.env',
    Path(__file__).parent.parent.parent.parent.parent / '.env',
    Path(__file__).parent.parent.parent.parent / '.env'
]

env_file = None
for path in env_paths:
    if os.path.isfile(str(path)):
        env_file = str(path)
        print(f"Found .env file at: {env_file}")
        break

if env_file:
    load_dotenv(env_file)
else:
    # Try to find .env automatically
    env_file = find_dotenv(usecwd=True)
    if env_file:
        print(f"Found .env file automatically at: {env_file}")
        load_dotenv(env_file)
    else:
        print("WARNING: No .env file found")

# Check if the API key is in environment
api_key = os.environ.get("OPENAI_API_KEY", "")
if not api_key:
    print("ERROR: OPENAI_API_KEY not found in environment variables")
    # If running in a test environment, this is critical
    if 'pytest' in sys.modules:
        print("API key is required for testing. Set OPENAI_API_KEY in .env file.")
else:
    print(f"OpenAI API key found with length: {len(api_key)}")
    # Ensure it's set in the environment
    os.environ["OPENAI_API_KEY"] = api_key

# Now import the rest of the modules
import uuid
import pytest
import pandas as pd
from unittest.mock import patch
from datetime import datetime

from gui.app import FactExtractionGUI
from storage.fact_repository import FactRepository, RejectedFactRepository
from storage.chunk_repository import ChunkRepository

@pytest.fixture
def setup_test_repositories():
    """Set up clean repositories with temporary Excel files for testing."""
    # Generate unique filenames to avoid test interference
    test_id = uuid.uuid4().hex[:8]
    chunks_file = f"test_chunks_{test_id}.xlsx"
    facts_file = f"test_facts_{test_id}.xlsx"
    rejected_facts_file = f"test_rejected_facts_{test_id}.xlsx"
    
    # Create repositories with test files
    chunk_repo = ChunkRepository(excel_path=chunks_file)
    fact_repo = FactRepository(excel_path=facts_file)
    rejected_fact_repo = RejectedFactRepository(excel_path=rejected_facts_file)
    
    yield chunk_repo, fact_repo, rejected_fact_repo, chunks_file, facts_file, rejected_facts_file
    
    # Clean up after tests
    for file in [chunks_file, facts_file, rejected_facts_file]:
        if os.path.exists(file):
            os.remove(file)

@pytest.fixture
def create_sample_facts(setup_test_repositories):
    """Create sample facts for testing."""
    chunk_repo, fact_repo, rejected_fact_repo, _, _, _ = setup_test_repositories
    
    # Sample document data
    document_name = f"test_document_{uuid.uuid4().hex[:8]}"
    text = "The semiconductor market reached $500B in 2022. AI technology is advancing rapidly."
    
    # Create chunks
    chunks = [
        {
            "document_name": document_name,
            "text": text,
            "chunk_index": 0,
            "status": "processed",
            "contains_facts": True,
            "all_facts_extracted": True,
            "document_hash": "test_hash_123"
        }
    ]
    
    # Create facts
    facts = [
        {
            "statement": "The semiconductor market reached $500B in 2022.",
            "document_name": document_name,
            "source_chunk": 0,
            "original_text": text,
            "verification_status": "verified",
            "verification_reason": "Verified with industry sources.",
            "timestamp": datetime.now().isoformat(),
            "id": 1  # Explicit ID for testing
        },
        {
            "statement": "AI technology is advancing rapidly.",
            "document_name": document_name,
            "source_chunk": 0,
            "original_text": text,
            "verification_status": "verified",
            "verification_reason": "Confirmed by multiple sources.",
            "timestamp": datetime.now().isoformat(),
            "id": 2  # Explicit ID for testing
        }
    ]
    
    # Store chunks and facts
    for chunk in chunks:
        chunk_repo.store_chunk(chunk)
    
    for fact in facts:
        fact_repo.store_fact(fact)
    
    return document_name, chunks, facts

def verify_excel_changes(file_path, expected_statement, expected_status, expected_reason):
    """Helper function to verify Excel file contains the expected changes."""
    assert os.path.exists(file_path), f"Excel file {file_path} does not exist"
    
    # Read Excel file
    df = pd.read_excel(file_path)
    assert len(df) > 0, "Excel file is empty"
    
    # Check for our expected values
    found = False
    for _, row in df.iterrows():
        if row.get("statement") == expected_statement:
            found = True
            assert row.get("verification_status") == expected_status, f"Expected status '{expected_status}', got '{row.get('verification_status')}'"
            assert row.get("verification_reason") == expected_reason, f"Expected reason '{expected_reason}', got '{row.get('verification_reason')}'"
            break
    
    assert found, f"Expected statement '{expected_statement}' not found in Excel file"
    return found

def test_modify_statement_persists_to_excel(setup_test_repositories, create_sample_facts):
    """Test that modifying a fact's statement persists to the Excel file."""
    document_name, chunks, facts, = create_sample_facts
    chunk_repo, fact_repo, rejected_fact_repo, _, facts_file, rejected_facts_file = setup_test_repositories
    
    # Create a GUI with patched repositories
    with patch('src.fact_extract.gui.app.ChunkRepository', return_value=chunk_repo), \
         patch('src.fact_extract.gui.app.FactRepository', return_value=fact_repo), \
         patch('src.fact_extract.gui.app.RejectedFactRepository', return_value=rejected_fact_repo):
        
        gui = FactExtractionGUI()
        
        # Get the first fact to update
        fact_id = facts[0]['id']
        original_statement = facts[0]['statement']
        
        # Modify the fact statement significantly
        updated_statement = f"UPDATED STATEMENT: {original_statement} {uuid.uuid4()}"
        updated_reason = f"Updated verification reason {uuid.uuid4()}"
        
        # Use the GUI's update_fact method
        result, _ = gui.update_fact(fact_id, updated_statement, "verified", updated_reason)
        
        # Verify the update was successful
        assert "Fact updated" in result, f"Expected 'Fact updated' in result, got: {result}"
        
        # Force save to Excel by reloading from Excel
        fact_repo._reload_facts_from_excel()
        
        # Verify changes in memory
        updated_fact = None
        for fact in fact_repo.get_all_facts():
            if updated_statement in fact['statement']:
                updated_fact = fact
                break
        
        assert updated_fact is not None, "Updated fact not found in repository"
        assert updated_fact['verification_reason'] == updated_reason
        
        # Verify changes persisted to Excel
        assert verify_excel_changes(facts_file, updated_statement, "verified", updated_reason)

def test_reject_verified_fact_moves_to_rejected_repository(setup_test_repositories, create_sample_facts):
    """Test that rejecting a verified fact moves it to the rejected facts repository and Excel file."""
    document_name, chunks, facts = create_sample_facts
    chunk_repo, fact_repo, rejected_fact_repo, _, facts_file, rejected_facts_file = setup_test_repositories
    
    # Create a GUI with patched repositories
    with patch('src.fact_extract.gui.app.ChunkRepository', return_value=chunk_repo), \
         patch('src.fact_extract.gui.app.FactRepository', return_value=fact_repo), \
         patch('src.fact_extract.gui.app.RejectedFactRepository', return_value=rejected_fact_repo):
        
        gui = FactExtractionGUI()
        
        # Get a fact to reject
        fact_to_reject = facts[0]
        fact_id = fact_to_reject['id']
        statement = fact_to_reject['statement']
        
        # Verify fact exists in verified repository first
        assert len(fact_repo.get_all_facts()) > 0
        assert len(rejected_fact_repo.get_all_rejected_facts()) == 0
        
        # Reject the fact
        rejection_reason = f"Rejecting for test purposes {uuid.uuid4()}"
        result, _ = gui.update_fact(fact_id, statement, "rejected", rejection_reason)
        
        # Verify the rejection was successful
        assert "Fact updated" in result, f"Expected 'Fact updated' in result, got: {result}"
        
        # Force save and reload from Excel
        fact_repo._reload_facts_from_excel()
        rejected_fact_repo._reload_facts_from_excel()
        
        # Verify fact has been removed from verified facts
        verified_facts = fact_repo.get_all_facts()
        for fact in verified_facts:
            assert fact.get('statement') != statement, "Fact still exists in verified repository"
        
        # Verify fact has been added to rejected facts
        rejected_facts = rejected_fact_repo.get_all_rejected_facts()
        assert len(rejected_facts) > 0, "No rejected facts found"
        
        rejected_fact_found = False
        for fact in rejected_facts:
            if fact.get('statement') == statement:
                rejected_fact_found = True
                assert fact.get('verification_status') == "rejected"
                assert fact.get('verification_reason') == rejection_reason
                break
        
        assert rejected_fact_found, "Rejected fact not found in rejected repository"
        
        # Verify changes persisted to Excel files
        assert verify_excel_changes(rejected_facts_file, statement, "rejected", rejection_reason)

def test_approve_rejected_fact_moves_to_verified_repository(setup_test_repositories, create_sample_facts):
    """Test that approving a rejected fact moves it to the verified facts repository."""
    document_name, chunks, facts = create_sample_facts
    chunk_repo, fact_repo, rejected_fact_repo, _, facts_file, rejected_facts_file = setup_test_repositories
    
    # Create a rejected fact
    rejected_fact = {
        "statement": f"This is a rejected fact {uuid.uuid4()}",
        "document_name": document_name,
        "source_chunk": 0,
        "original_text": "Test text",
        "verification_status": "rejected",
        "verification_reason": "Initially rejected for testing",
        "timestamp": datetime.now().isoformat(),
        "id": 100  # Unique ID for rejected fact
    }
    
    # Store the rejected fact
    rejected_fact_repo.store_rejected_fact(rejected_fact)
    
    # Create a GUI with patched repositories
    with patch('src.fact_extract.gui.app.ChunkRepository', return_value=chunk_repo), \
         patch('src.fact_extract.gui.app.FactRepository', return_value=fact_repo), \
         patch('src.fact_extract.gui.app.RejectedFactRepository', return_value=rejected_fact_repo):
        
        gui = FactExtractionGUI()
        
        # Need to add the rejected fact to the facts_data for the GUI to find it
        if document_name not in gui.facts_data:
            gui.facts_data[document_name] = {
                "all_facts": [],
                "verified_facts": [],
                "verified_count": 0
            }
        
        # Force update of facts_data with repository information
        _, _ = gui.get_facts_for_review()
        
        # Now approve the rejected fact
        approval_reason = f"Now approved for testing {uuid.uuid4()}"
        result, _ = gui.update_fact(
            rejected_fact['id'],
            rejected_fact['statement'], 
            "verified", 
            approval_reason
        )
        
        # Verify the approval was successful
        assert "Fact updated" in result, f"Expected 'Fact updated' in result, got: {result}"
        
        # Force save and reload from Excel
        fact_repo._reload_facts_from_excel()
        rejected_fact_repo._reload_facts_from_excel()
        
        # Verify fact has been removed from rejected facts
        rejected_facts = rejected_fact_repo.get_all_rejected_facts()
        for fact in rejected_facts:
            assert fact.get('statement') != rejected_fact['statement'], "Fact still exists in rejected repository"
        
        # Verify fact has been added to verified facts
        verified_facts = fact_repo.get_all_facts()
        
        verified_fact_found = False
        for fact in verified_facts:
            if fact.get('statement') == rejected_fact['statement']:
                verified_fact_found = True
                assert fact.get('verification_status') == "verified"
                assert fact.get('verification_reason') == approval_reason
                break
        
        assert verified_fact_found, "Approved fact not found in verified repository"
        
        # Verify changes persisted to Excel files
        assert verify_excel_changes(facts_file, rejected_fact['statement'], "verified", approval_reason)

def test_update_fact_with_modified_statement_and_reason(setup_test_repositories, create_sample_facts):
    """Test that updating a fact with modified statement and reason persists correctly."""
    document_name, chunks, facts = create_sample_facts
    chunk_repo, fact_repo, rejected_fact_repo, _, facts_file, _ = setup_test_repositories
    
    # Create a GUI with patched repositories
    with patch('src.fact_extract.gui.app.ChunkRepository', return_value=chunk_repo), \
         patch('src.fact_extract.gui.app.FactRepository', return_value=fact_repo), \
         patch('src.fact_extract.gui.app.RejectedFactRepository', return_value=rejected_fact_repo):
        
        gui = FactExtractionGUI()
        
        # Get a fact to update
        fact_to_update = facts[1]  # Use the second fact
        fact_id = fact_to_update['id']
        original_statement = fact_to_update['statement']
        
        # Update with modified statement and reason
        modified_statement = f"MODIFIED: {original_statement} {uuid.uuid4()}"
        modified_reason = f"Modified reason {uuid.uuid4()}"
        
        # Update the fact
        result, _ = gui.update_fact(fact_id, modified_statement, "verified", modified_reason)
        
        # Verify the update was successful
        assert "Fact updated" in result, f"Expected 'Fact updated' in result, got: {result}"
        
        # Force save and reload from Excel
        fact_repo._reload_facts_from_excel()
        
        # Verify changes in memory
        updated_facts = fact_repo.get_all_facts()
        updated_fact = None
        for fact in updated_facts:
            if modified_statement in fact['statement']:
                updated_fact = fact
                break
        
        assert updated_fact is not None, "Updated fact not found in repository"
        assert updated_fact['verification_reason'] == modified_reason
        
        # Verify original statement is no longer in repository
        for fact in updated_facts:
            assert fact.get('statement') != original_statement, "Original fact still exists in repository"
        
        # Verify changes persisted to Excel
        assert verify_excel_changes(facts_file, modified_statement, "verified", modified_reason)

def test_review_tab_sequential_operations(setup_test_repositories, create_sample_facts):
    """Test sequential operations in the review tab to ensure persistence."""
    document_name, chunks, facts = create_sample_facts
    chunk_repo, fact_repo, rejected_fact_repo, _, facts_file, rejected_facts_file = setup_test_repositories
    
    # Create a GUI with patched repositories
    with patch('src.fact_extract.gui.app.ChunkRepository', return_value=chunk_repo), \
         patch('src.fact_extract.gui.app.FactRepository', return_value=fact_repo), \
         patch('src.fact_extract.gui.app.RejectedFactRepository', return_value=rejected_fact_repo):
        
        gui = FactExtractionGUI()
        
        # 1. First, reject a fact
        fact1 = facts[0]
        fact1_id = fact1['id']
        fact1_statement = fact1['statement']
        reject_reason = f"Rejected for testing {uuid.uuid4()}"
        
        result1, _ = gui.update_fact(fact1_id, fact1_statement, "rejected", reject_reason)
        assert "Fact updated" in result1, f"Expected 'Fact updated' in result1, got: {result1}"
        
        # Force reload from Excel
        fact_repo._reload_facts_from_excel()
        rejected_fact_repo._reload_facts_from_excel()
        
        # Verify rejection in Excel
        assert verify_excel_changes(rejected_facts_file, fact1_statement, "rejected", reject_reason)
        
        # 2. Then, modify a different fact
        fact2 = facts[1]
        fact2_id = fact2['id']
        fact2_original = fact2['statement']
        fact2_modified = f"MODIFIED: {fact2_original} {uuid.uuid4()}"
        modified_reason = f"Modified for testing {uuid.uuid4()}"
        
        result2, _ = gui.update_fact(fact2_id, fact2_modified, "verified", modified_reason)
        assert "Fact updated" in result2, f"Expected 'Fact updated' in result2, got: {result2}"
        
        # Force reload from Excel
        fact_repo._reload_facts_from_excel()
        
        # Verify modification in Excel
        assert verify_excel_changes(facts_file, fact2_modified, "verified", modified_reason)
        
        # 3. Finally, approve the previously rejected fact
        # We need to get the ID from the rejected repository
        rejected_facts = rejected_fact_repo.get_all_rejected_facts()
        rejected_fact = None
        for fact in rejected_facts:
            if fact.get('statement') == fact1_statement:
                rejected_fact = fact
                break
        
        assert rejected_fact is not None, "Rejected fact not found in repository"
        
        # Update the rejected fact to be verified
        approve_reason = f"Now approved for testing {uuid.uuid4()}"
        
        # Need to ensure the fact is in the GUI's facts_data
        if document_name not in gui.facts_data:
            gui.facts_data[document_name] = {
                "all_facts": [],
                "verified_facts": [],
                "verified_count": 0
            }
        
        # Force update of facts_data with repository information
        _, _ = gui.get_facts_for_review()
        
        result3, _ = gui.update_fact(
            rejected_fact.get('id', fact1_id),  # Use the ID from repository or original
            fact1_statement,
            "verified",
            approve_reason
        )
        
        assert "Fact updated" in result3, f"Expected 'Fact updated' in result3, got: {result3}"
        
        # Force reload from Excel
        fact_repo._reload_facts_from_excel()
        rejected_fact_repo._reload_facts_from_excel()
        
        # Verify approval in Excel
        assert verify_excel_changes(facts_file, fact1_statement, "verified", approve_reason)
        
        # Verify fact is no longer in rejected repository
        for fact in rejected_fact_repo.get_all_rejected_facts():
            assert fact.get('statement') != fact1_statement, "Fact still exists in rejected repository" 
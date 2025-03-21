"""
Test script for fact extraction using synthetic data.
"""

import pytest
import sys
from typing import Dict, List
import asyncio
import os
import shutil
from dotenv import load_dotenv
from pathlib import Path


# Ensure the src directory is in the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Ensure the src directory is in the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))
# Load environment variables from .env file
dotenv_path = Path(__file__).parents[2] / '.env'
load_dotenv(dotenv_path)

from utils.synthetic_data import SYNTHETIC_ARTICLE_2
from __main__ import extract_facts as main_extract_facts
from graph.nodes import create_initial_state, chunker_node, extractor_node
from storage.chunk_repository import ChunkRepository
from storage.fact_repository import FactRepository

# Define temporary directories for test data
TEST_DATA_DIR = Path("src/fact_extract/tests/temp_data")
TEMP_CHUNKS_FILE = TEST_DATA_DIR / "test_chunks.xlsx"
TEMP_FACTS_FILE = TEST_DATA_DIR / "test_facts.xlsx"

@pytest.fixture(scope="module")
def setup_test_repositories():
    """Set up temporary repositories for testing."""
    # Ensure test directory exists
    TEST_DATA_DIR.mkdir(parents=True, exist_ok=True)
    
    # Create temporary repositories with unique file paths
    chunk_repo = ChunkRepository(excel_path=str(TEMP_CHUNKS_FILE))
    fact_repo = FactRepository(excel_path=str(TEMP_FACTS_FILE))
    
    # Clear existing data by manually setting empty data and saving
    # For ChunkRepository
    chunk_repo.chunks = {}
    chunk_repo._save_to_excel()
    
    # For FactRepository
    fact_repo.facts = {}
    fact_repo._save_to_excel()
    
    # Clear the main repository data to prevent duplicate detection
    # This ensures our tests can run even if the same document was processed before
    main_chunk_repo = ChunkRepository()
    main_chunk_repo.chunks = {}
    main_chunk_repo._save_to_excel()
    
    main_fact_repo = FactRepository()
    main_fact_repo.facts = {}
    main_fact_repo._save_to_excel()
    
    yield chunk_repo, fact_repo
    
    # Clean up after tests
    if TEMP_CHUNKS_FILE.exists():
        os.remove(TEMP_CHUNKS_FILE)
    if TEMP_FACTS_FILE.exists():
        os.remove(TEMP_FACTS_FILE)
    if TEST_DATA_DIR.exists():
        shutil.rmtree(TEST_DATA_DIR)

def print_facts(facts: List[Dict]):
    """Print facts with statistics."""
    if not facts:
        print("No facts found.")
        return
        
    print("\nExtracted Facts:")
    print("-" * 80)
    for fact in facts:
        print(f"\nFact from chunk {fact['source_chunk']}:")
        print(f"  Statement: {fact['statement']}")
        print(f"  Source: {fact['document_name']}")
        print(f"  Status: {fact['verification_status']}")
        if fact.get('verification_reason'):
            print(f"  Reason: {fact['verification_reason']}")
    
    # Print statistics
    total = len(facts)
    verified = len([f for f in facts if f["verification_status"] == "verified"])
    rejected = len([f for f in facts if f["verification_status"] == "rejected"])
    pending = total - verified - rejected
    
    print("\nStatistics:")
    print("-" * 80)
    print(f"Total facts: {total}")
    print(f"Verified facts: {verified}")
    print(f"Rejected facts: {rejected}")
    print(f"Pending facts: {pending}")
    print()
    
    return {
        "total": total,
        "verified": verified,
        "rejected": rejected,
        "pending": pending
    }

@pytest.mark.asyncio
async def test_extraction_workflow(setup_test_repositories):
    """Test the extraction workflow process using nodes."""
    # Get repositories from fixture
    chunk_repo, fact_repo = setup_test_repositories
    
    # Create a unique document name with timestamp to avoid collisions
    import uuid
    unique_id = uuid.uuid4().hex[:8]
    doc_name = f"test_doc_{unique_id}"
    
    # Make the input text unique to avoid duplicate detection
    unique_text = f"{SYNTHETIC_ARTICLE_2}\n\nUnique test identifier: {unique_id}"
    
    # Initialize state with required arguments
    state = create_initial_state(
        input_text=unique_text,
        document_name=doc_name,
        source_url="https://example.com/test"
    )
    
    # Run chunker
    chunked_state = await chunker_node(state)
    
    # Verify chunking results
    assert "chunks" in chunked_state
    assert len(chunked_state["chunks"]) > 0
    
    # Run extractor
    extracted_state = await extractor_node(chunked_state)
    
    # Verify extraction results
    assert "extracted_facts" in extracted_state
    
    # Print for debugging purposes
    stats = print_facts(extracted_state["extracted_facts"])
    
    # Verify we have facts extracted
    assert stats["total"] > 0
    
    return extracted_state

@pytest.mark.asyncio
async def test_extract_facts_main(setup_test_repositories):
    """Test the main extract_facts function."""
    # Get repositories from fixture
    chunk_repo, fact_repo = setup_test_repositories
    
    # Create a unique document name with timestamp to avoid collisions
    import uuid
    unique_id = uuid.uuid4().hex[:8]
    doc_name = f"Sustainable_Article_{unique_id}"
    
    # Make the input text unique to avoid duplicate detection
    unique_text = f"{SYNTHETIC_ARTICLE_2}\n\nUnique test identifier: {unique_id}"
    
    facts = await extract_facts(
        text=unique_text,
        document_name=doc_name,
        source_url="https://example.com/sustainable-data-centers"
    )
    
    # Verify facts were extracted
    assert isinstance(facts, list)
    assert len(facts) > 0
    
    # Verify structure of the facts
    for fact in facts:
        assert "statement" in fact
        assert "document_name" in fact
        assert "verification_status" in fact
    
    # Print for debugging
    stats = print_facts(facts)
    
    # Verify we have some verified facts
    assert stats["total"] > 0
    
    return facts 
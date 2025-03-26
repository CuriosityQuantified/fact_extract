"""
Test script specifically for the extraction functionality.
Verifies that facts can be extracted from synthetic test data.
"""

from typing import Dict, List, Any
import sys
import asyncio
import os
import json
import pytest
from dotenv import load_dotenv
from pathlib import Path
import logging
import pandas as pd
import uuid
from datetime import datetime


# Ensure the src directory is in the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
# Ensure the src directory is in the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

# Load environment variables from .env file
dotenv_path = Path(__file__).parents[2] / '.env'
load_dotenv(dotenv_path)

from src.utils.synthetic_data import SYNTHETIC_ARTICLE_2
from src.models.state import create_initial_state
from src.graph.nodes import chunker_node, extractor_node
from src.storage.chunk_repository import ChunkRepository
from src.storage.fact_repository import FactRepository, RejectedFactRepository

# Configure logging
logging.basicConfig(level=logging.DEBUG, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Define the extract_facts function instead of importing from __main__
async def extract_facts(text: str, document_name: str, source_url: str = "") -> List[Dict[str, Any]]:
    """
    Extract facts from text.
    
    Args:
        text: The text to extract facts from
        document_name: The name of the document
        source_url: Optional URL source of the document
        
    Returns:
        List of extracted facts
    """
    print(f"\nExtracting facts from document: {document_name}")
    sys.stdout.flush()
    
    # Initialize state
    state = create_initial_state(
        input_text=text,
        document_name=document_name,
        source_url=source_url
    )
    
    # Process through nodes
    print("\nRunning chunker_node...")
    sys.stdout.flush()
    state = await chunker_node(state)
    print(f"Chunking complete. Generated {len(state.get('chunks', []))} chunks.")
    sys.stdout.flush()
    
    print("\nRunning extractor_node...")
    sys.stdout.flush()
    state = await extractor_node(state)
    print(f"Extraction complete. Found {len(state.get('extracted_facts', []))} facts.")
    sys.stdout.flush()
    
    return state.get("extracted_facts", [])

def print_facts(facts: List[Dict]) -> Dict[str, int]:
    """
    Print facts with statistics.
    
    Args:
        facts: List of facts to print
        
    Returns:
        Dictionary with statistics
    """
    if not facts:
        print("No facts found.")
        sys.stdout.flush()
        return {"total": 0, "verified": 0, "rejected": 0, "pending": 0}
        
    print("\nExtracted Facts:")
    print("-" * 80)
    sys.stdout.flush()
    
    for fact in facts:
        print(f"\nFact from chunk {fact.get('source_chunk', 'unknown')}:")
        print(f"  Statement: {fact.get('statement', '')}")
        print(f"  Source: {fact.get('document_name', '')}")
        print(f"  Status: {fact.get('verification_status', '')}")
        if fact.get('verification_reason'):
            print(f"  Reason: {fact['verification_reason']}")
        sys.stdout.flush()
    
    # Print statistics
    total = len(facts)
    verified = len([f for f in facts if f.get("verification_status") == "verified"])
    rejected = len([f for f in facts if f.get("verification_status") == "rejected"])
    pending = total - verified - rejected
    
    print("\nStatistics:")
    print("-" * 80)
    print(f"Total facts: {total}")
    print(f"Verified facts: {verified}")
    print(f"Rejected facts: {rejected}")
    print(f"Pending facts: {pending}")
    print()
    sys.stdout.flush()
    
    return {"total": total, "verified": verified, "rejected": rejected, "pending": pending}

@pytest.fixture
def setup_test_repositories():
    """Set up test repositories with temporary Excel files."""
    print("\nSetting up test repositories...")
    sys.stdout.flush()
    
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
    
    # Also clear the main repositories to avoid test interference
    main_chunk_repo = ChunkRepository()
    main_fact_repo = FactRepository()
    main_rejected_fact_repo = RejectedFactRepository()
    
    # Clear any existing data
    if os.path.exists(main_chunk_repo.excel_path):
        pd.DataFrame().to_excel(main_chunk_repo.excel_path, index=False)
    if os.path.exists(main_fact_repo.excel_path):
        pd.DataFrame().to_excel(main_fact_repo.excel_path, index=False)
    if os.path.exists(main_rejected_fact_repo.excel_path):
        pd.DataFrame().to_excel(main_rejected_fact_repo.excel_path, index=False)
    
    print(f"Test repositories created with unique ID: {unique_id}")
    sys.stdout.flush()
    
    yield chunk_repo, fact_repo
    
    # Clean up temporary files after test
    print("\nCleaning up test repositories...")
    sys.stdout.flush()
    
    for file_path in [chunks_file, facts_file, rejected_facts_file]:
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except:
                pass

@pytest.mark.asyncio
async def test_extraction(document_name: str = "test_doc", text: str = SYNTHETIC_ARTICLE_2):
    """Test fact extraction on a piece of text."""
    print("\nRunning test_extraction...")
    sys.stdout.flush()
    
    # Initialize state
    state = create_initial_state(
        input_text=text,
        document_name=document_name
    )

    # Run chunker
    print("\nRunning chunker_node...")
    sys.stdout.flush()
    state = await chunker_node(state)
    print(f"Split into {len(state.get('chunks', []))} chunks")
    sys.stdout.flush()

    # Run extractor
    print("\nRunning extractor_node...")
    sys.stdout.flush()
    state = await extractor_node(state)
    print(f"Extracted {len(state.get('extracted_facts', []))} facts")
    sys.stdout.flush()

    # Print results
    stats = print_facts(state.get("extracted_facts", []))
    print("\nTest complete!")
    sys.stdout.flush()
    
    return state.get("extracted_facts", [])

async def main_async():
    """Async main function."""
    print("Testing fact extraction on sustainable data centers article...")
    print("-" * 80)
    sys.stdout.flush()
    
    try:
        facts = await extract_facts(
            text=SYNTHETIC_ARTICLE_2,
            document_name="Sustainable Data Centers Article",
            source_url="https://example.com/sustainable-data-centers"
        )
        stats = print_facts(facts)
        return facts
        
    except Exception as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        sys.stderr.flush()
        return []

def main():
    """Main entry point."""
    asyncio.run(main_async())


# Merged functions from test_extraction.py.unit_tests


@pytest.mark.asyncio
async def test_extraction_workflow(setup_test_repositories):
    """Test the extraction workflow process using nodes."""
    print("\nRunning test_extraction_workflow...")
    sys.stdout.flush()
    
    # Get repositories from fixture
    chunk_repo, fact_repo = setup_test_repositories
    
    # Create a unique document name with timestamp to avoid collisions
    import uuid
    unique_id = uuid.uuid4().hex[:8]
    doc_name = f"test_doc_{unique_id}"
    
    # Make the input text unique to avoid duplicate detection
    unique_text = f"{SYNTHETIC_ARTICLE_2}\n\nUnique test identifier: {unique_id}"
    
    # Initialize state with required arguments
    print(f"\nInitializing state with document: {doc_name}")
    sys.stdout.flush()
    
    state = create_initial_state(
        input_text=unique_text,
        document_name=doc_name,
        source_url="https://example.com/test"
    )
    
    # Run chunker
    print("\nRunning chunker_node...")
    sys.stdout.flush()
    chunked_state = await chunker_node(state)
    
    # Verify chunking results
    print(f"Chunking complete. Generated {len(chunked_state.get('chunks', []))} chunks.")
    sys.stdout.flush()
    
    assert "chunks" in chunked_state
    assert len(chunked_state["chunks"]) > 0
    
    # Run extractor
    print("\nRunning extractor_node...")
    sys.stdout.flush()
    extracted_state = await extractor_node(chunked_state)
    
    # Verify extraction results
    print(f"Extraction complete. Found {len(extracted_state.get('extracted_facts', []))} facts.")
    sys.stdout.flush()
    
    assert "extracted_facts" in extracted_state
    
    # Print for debugging purposes
    stats = print_facts(extracted_state["extracted_facts"])
    
    # Verify we have facts extracted
    assert stats["total"] > 0
    
    print("\nTest complete!")
    sys.stdout.flush()
    
    return extracted_state


@pytest.mark.asyncio
async def test_extract_facts_main(setup_test_repositories):
    """Test the main extract_facts function."""
    print("\nRunning test_extract_facts_main...")
    sys.stdout.flush()
    
    # Get repositories from fixture
    chunk_repo, fact_repo = setup_test_repositories
    
    # Create a unique document name with timestamp to avoid collisions
    import uuid
    unique_id = uuid.uuid4().hex[:8]
    doc_name = f"Sustainable_Article_{unique_id}"
    
    # Make the input text unique to avoid duplicate detection
    unique_text = f"{SYNTHETIC_ARTICLE_2}\n\nUnique test identifier: {unique_id}"
    
    print(f"\nExtracting facts from document: {doc_name}")
    sys.stdout.flush()
    
    facts = await extract_facts(
        text=unique_text,
        document_name=doc_name,
        source_url="https://example.com/sustainable-data-centers-test"
    )
    
    # Print and check facts
    stats = print_facts(facts)
    
    # We should have at least some facts extracted
    assert stats["total"] > 0
    
    print("\nTest complete!")
    sys.stdout.flush()
    
    return facts

if __name__ == "__main__":
    main() 
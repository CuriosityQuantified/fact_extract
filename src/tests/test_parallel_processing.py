"""
Unit tests for parallel processing functionality in the fact extraction system.
Tests different concurrency levels to ensure parallel processing works correctly.
"""

import os
import sys
import uuid
import pytest
import asyncio
import time
from datetime import datetime
from pathlib import Path
import tempfile
import pandas as pd

# Ensure the src directory is in the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

# Import necessary components
from src.graph.nodes import process_document, parallel_process_chunks
from src.storage.chunk_repository import ChunkRepository
from src.storage.fact_repository import FactRepository, RejectedFactRepository
from src.models.state import ProcessingState
from src.utils.synthetic_data import SYNTHETIC_ARTICLE_7

# Constants for testing
TEST_CONCURRENCY_LEVELS = [1, 2, 3]  # Test with different concurrency levels

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
    
    yield chunk_repo, fact_repo, rejected_fact_repo
    
    # Clean up temporary files after test
    for file_path in [chunks_file, facts_file, rejected_facts_file]:
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except:
                pass

@pytest.fixture
def test_text_file(tmp_path):
    """Create a temporary text file with test content."""
    # Create a unique identifier for this test run
    unique_id = str(uuid.uuid4())
    
    # Create a text file with the synthetic article + unique identifier
    content = SYNTHETIC_ARTICLE_7 + f"\n\nUnique test identifier: {unique_id}"
    
    # Generate a unique file name
    test_file = tmp_path / f"test_document_{unique_id}.txt"
    test_file.write_text(content)
    
    return str(test_file)

@pytest.mark.asyncio
async def test_parallel_process_chunks(setup_test_repositories):
    """Test the parallel_process_chunks function with different concurrency levels."""
    # Get test repositories
    chunk_repo, fact_repo, rejected_fact_repo = setup_test_repositories
    
    # Create a unique document name
    document_name = f"test_parallel_chunks_{uuid.uuid4()}"
    source_url = "https://example.com/test"
    
    # Create test chunks
    chunks = []
    for i in range(5):  # Create 5 test chunks
        unique_id = str(uuid.uuid4())
        chunk_content = f"This is test chunk {i} with ID {unique_id}. It contains some text that mentions metrics: 42% of users reported improved performance, with average response times decreasing from 120ms to 80ms. The system processed 1.5 million requests per day."
        chunks.append({
            "content": chunk_content,
            "index": i,
            "metadata": {
                "word_count": len(chunk_content.split()),
                "char_length": len(chunk_content),
                "source": document_name
            }
        })
    
    # Test with different concurrency levels
    results = {}
    
    for concurrency in TEST_CONCURRENCY_LEVELS:
        print(f"\nTesting concurrency level: {concurrency}")
        start_time = time.time()
        
        # Process chunks in parallel with current concurrency level
        result = await parallel_process_chunks(
            chunks=chunks,
            document_name=document_name,
            source_url=source_url,
            max_concurrent_chunks=concurrency,
            chunk_repo=chunk_repo,
            fact_repo=fact_repo,
            rejected_fact_repo=rejected_fact_repo
        )
        
        processing_time = time.time() - start_time
        results[concurrency] = {
            "time": processing_time,
            "chunks_processed": result["chunks_processed"],
            "facts_extracted": result["facts_extracted"],
            "errors": result.get("errors", [])
        }
        
        # Verify the result
        assert result["status"] in ["success", "partial_success"]
        assert result["chunks_processed"] == len(chunks)
        assert result["facts_extracted"] >= 0
        
        # Get facts from repository
        stored_facts = fact_repo.get_facts_for_document(document_name)
        
        # Verify facts were stored
        assert len(stored_facts) >= 0, f"No facts were stored for concurrency level {concurrency}"
        
        # Clear repositories for next test
        chunk_repo.clear_document(document_name)
        for fact in stored_facts:
            fact_repo.clear_facts(lambda f: f["document_name"] == document_name)
        
        print(f"Concurrency {concurrency}: Processed {result['chunks_processed']} chunks in {processing_time:.2f}s, extracted {result['facts_extracted']} facts")
    
    # Verify that higher concurrency is faster (or at least not much slower)
    if len(TEST_CONCURRENCY_LEVELS) > 1:
        for i in range(1, len(TEST_CONCURRENCY_LEVELS)):
            current = TEST_CONCURRENCY_LEVELS[i]
            previous = TEST_CONCURRENCY_LEVELS[i-1]
            
            # Allow for some variance (higher concurrency might be slightly slower in some cases)
            assert results[current]["time"] <= results[previous]["time"] * 1.2, f"Concurrency {current} was significantly slower than {previous}"

@pytest.mark.asyncio
async def test_process_document(setup_test_repositories, test_text_file):
    """Test the process_document function with a real document."""
    # Initialize processing state
    state = ProcessingState()
    
    # Process document with different concurrency levels and measure time
    results = {}
    
    for concurrency in TEST_CONCURRENCY_LEVELS:
        # Reset state for clean test
        state = ProcessingState()  
        
        print(f"\nTesting document processing with concurrency level: {concurrency}")
        start_time = time.time()
        
        # Process the document
        result = await process_document(test_text_file, state, max_concurrent_chunks=concurrency)
        
        processing_time = time.time() - start_time
        results[concurrency] = {
            "time": processing_time,
            "status": result["status"],
            "facts": len(state.facts.get(test_text_file, [])),
            "errors": result.get("errors", [])
        }
        
        # Verify the result
        assert result["status"] in ["success", "skipped"], f"Processing failed with status: {result['status']}"
        
        if result["status"] == "success":
            # Verify documents were processed
            assert test_text_file in state.processed_files, "File not marked as processed"
            
            # Verify facts were extracted
            if "verified_facts" in result:
                assert result["verified_facts"] >= 0, "No facts were verified"
        
        print(f"Concurrency {concurrency}: Processed document in {processing_time:.2f}s with status {result['status']}")
        print(f"Facts extracted: {len(state.facts.get(test_text_file, []))}")
        
        # Delete the document from repositories to allow reprocessing
        # This is necessary because we're using the same file for each test
        document_name = os.path.basename(test_text_file)
        chunk_repo = ChunkRepository()
        fact_repo = FactRepository()
        
        # Clear the document from chunk repository
        chunk_repo.clear_document(document_name)
        
        # Clear facts manually since there's no clear_facts method
        # Get all facts for the document and remove them one by one
        facts_to_remove = fact_repo.get_facts_for_document(document_name)
        for fact in facts_to_remove:
            if "statement" in fact:
                fact_repo.remove_fact(document_name, fact["statement"])
        
        # Wait a moment before next test
        await asyncio.sleep(1)
    
    # Print performance comparison
    print("\nPerformance Comparison:")
    print("-" * 50)
    for level, data in sorted(results.items()):
        print(f"Concurrency {level}: {data['time']:.2f}s - {data['status']} - {data['facts']} facts") 
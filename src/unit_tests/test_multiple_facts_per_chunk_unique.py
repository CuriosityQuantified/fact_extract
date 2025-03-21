"""
Test script to verify how the system handles chunks with multiple unique facts.
"""

import os
import sys
import asyncio
import pandas as pd
from datetime import datetime
import hashlib
import uuid
import time
import pytest


# Ensure the src directory is in the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Ensure the src directory is in the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))
from models.state import create_initial_state
from storage.chunk_repository import ChunkRepository
from storage.fact_repository import FactRepository

@pytest.mark.asyncio
async def test_multiple_facts_per_chunk_unique():
    """Test how the system handles chunks with multiple unique facts."""
    print("\n" + "="*80)
    print("TESTING MULTIPLE UNIQUE FACTS PER CHUNK")
    print("="*80)
    
    # Create test data directory
    os.makedirs("src/fact_extract/data", exist_ok=True)
    
    # Initialize repositories
    chunk_repo = ChunkRepository()
    fact_repo = FactRepository()
    
    # Create a unique document name to avoid conflicts with previous tests
    unique_id = str(uuid.uuid4())[:8]
    timestamp = int(time.time())
    document_name = f"test_unique_facts_{unique_id}_{timestamp}.txt"
    
    # Create a test chunk with multiple facts
    test_chunk_content = f"""
    The global cloud computing market reached ${timestamp}.3 billion in 2021.
    Tesla delivered {timestamp}.31 million electric vehicles in 2022.
    The average data center uses {timestamp} times more electricity than a standard office building.
    """
    
    document_hash = hashlib.md5(test_chunk_content.encode()).hexdigest()
    
    # Store the test chunk
    print(f"\nStoring test chunk with multiple facts for document: {document_name}...")
    chunk_repo.store_chunk({
        "timestamp": datetime.now().isoformat(),
        "document_name": document_name,
        "source_url": "https://example.com/test",
        "chunk_content": test_chunk_content,
        "chunk_index": 0,
        "status": "processed",
        "contains_facts": True,
        "error_message": None,
        "processing_time": 1.5,
        "document_hash": document_hash,
        "all_facts_extracted": False,  # Initially set to False
        "metadata": {
            "word_count": len(test_chunk_content.split()),
            "char_length": len(test_chunk_content),
            "start_index": 0,
            "source": document_name,
            "url": "https://example.com/test",
            "timestamp": datetime.now().isoformat()
        }
    })
    
    # Check initial chunk status
    print("\nChecking initial chunk status...")
    chunk = chunk_repo.get_chunk(document_name, 0)
    if chunk:
        print(f"Chunk status: {chunk.get('status')}")
        print(f"Contains facts: {chunk.get('contains_facts')}")
        print(f"All facts extracted: {chunk.get('all_facts_extracted')}")
    else:
        print("Chunk not found!")
    
    # Store the first fact
    print("\nStoring first fact...")
    fact1 = {
        "statement": f"The global cloud computing market reached ${timestamp}.3 billion in 2021.",
        "source_chunk": 0,
        "original_text": test_chunk_content,
        "document_name": document_name,
        "source_url": "https://example.com/test",
        "extraction_time": datetime.now().isoformat(),
        "verification_status": "verified",
        "verification_reason": "The fact is directly stated in the text.",
        "timestamp": datetime.now().isoformat(),
        "metadata": {
            "fact_number": 1,
            "processing_time": 1.5
        }
    }
    fact_repo.store_fact(fact1)
    
    # Check if the chunk is still marked as not having all facts extracted
    print("\nChecking chunk status after storing first fact...")
    chunk = chunk_repo.get_chunk(document_name, 0)
    if chunk:
        print(f"Chunk status: {chunk.get('status')}")
        print(f"Contains facts: {chunk.get('contains_facts')}")
        print(f"All facts extracted: {chunk.get('all_facts_extracted')}")
    else:
        print("Chunk not found!")
    
    # Check facts in the repository
    print("\nChecking facts in repository after first fact...")
    facts_excel_path = "data/all_facts.xlsx"
    if os.path.exists(facts_excel_path):
        facts_df = pd.read_excel(facts_excel_path)
        test_facts = facts_df[facts_df['document_name'] == document_name]
        print(f"Facts for test document: {len(test_facts)}")
    else:
        print("Facts Excel file does not exist!")
    
    # Store a second fact from the same chunk
    print("\nStoring second fact from the same chunk...")
    fact2 = {
        "statement": f"Tesla delivered {timestamp}.31 million electric vehicles in 2022.",
        "source_chunk": 0,
        "original_text": test_chunk_content,
        "document_name": document_name,
        "source_url": "https://example.com/test",
        "extraction_time": datetime.now().isoformat(),
        "verification_status": "verified",
        "verification_reason": "The fact is directly stated in the text.",
        "timestamp": datetime.now().isoformat(),
        "metadata": {
            "fact_number": 2,
            "processing_time": 1.5
        }
    }
    fact_repo.store_fact(fact2)
    
    # Check facts in the repository again
    print("\nChecking facts in repository after second fact...")
    if os.path.exists(facts_excel_path):
        facts_df = pd.read_excel(facts_excel_path)
        test_facts = facts_df[facts_df['document_name'] == document_name]
        print(f"Facts for test document: {len(test_facts)}")
        
        # Check if both facts were stored
        if len(test_facts) >= 2:
            print("SUCCESS: Multiple facts from the same chunk were stored!")
        else:
            print("ERROR: Not all facts from the chunk were stored!")
    else:
        print("Facts Excel file does not exist!")
    
    # Mark the chunk as having all facts extracted
    print("\nMarking chunk as having all facts extracted...")
    chunk_repo.update_chunk_status(
        document_name=document_name,
        chunk_index=0,
        status="processed",
        contains_facts=True,
        all_facts_extracted=True
    )
    
    # Check if the chunk is now marked as having all facts extracted
    print("\nChecking chunk status after marking as all facts extracted...")
    chunk = chunk_repo.get_chunk(document_name, 0)
    if chunk:
        print(f"Chunk status: {chunk.get('status')}")
        print(f"Contains facts: {chunk.get('contains_facts')}")
        print(f"All facts extracted: {chunk.get('all_facts_extracted')}")
    else:
        print("Chunk not found!")
    
    # Test is_chunk_processed method
    print("\nTesting is_chunk_processed method...")
    is_processed = chunk_repo.is_chunk_processed({"index": 0}, document_name)
    print(f"Is chunk processed and all facts extracted: {is_processed}")
    
    # Try to store a third fact from the same chunk
    print("\nStoring third fact from the same chunk after marking as all facts extracted...")
    fact3 = {
        "statement": f"The average data center uses {timestamp} times more electricity than a standard office building.",
        "source_chunk": 0,
        "original_text": test_chunk_content,
        "document_name": document_name,
        "source_url": "https://example.com/test",
        "extraction_time": datetime.now().isoformat(),
        "verification_status": "verified",
        "verification_reason": "The fact is directly stated in the text.",
        "timestamp": datetime.now().isoformat(),
        "metadata": {
            "fact_number": 3,
            "processing_time": 1.5
        }
    }
    fact_repo.store_fact(fact3)
    
    # Check facts in the repository again
    print("\nChecking facts in repository after third fact...")
    if os.path.exists(facts_excel_path):
        facts_df = pd.read_excel(facts_excel_path)
        test_facts = facts_df[facts_df['document_name'] == document_name]
        print(f"Facts for test document: {len(test_facts)}")
        
        # Check if all three facts were stored
        if len(test_facts) >= 3:
            print("SUCCESS: All three facts from the same chunk were stored!")
        else:
            print(f"ERROR: Only {len(test_facts)} facts were stored!")
    
    # Simulate reprocessing the document
    print("\nSimulating reprocessing the document...")
    # Check if all chunks for this document have had all facts extracted
    existing_chunks = chunk_repo.get_all_chunks()
    all_chunks_processed = True
    chunks_to_process = []
    
    for chunk in existing_chunks:
        if chunk.get("document_hash") == document_hash:
            # Document exists, check if all facts have been extracted
            if not chunk.get("all_facts_extracted", False):
                all_chunks_processed = False
                chunks_to_process.append(chunk)
    
    if all_chunks_processed and any(chunk.get("document_hash") == document_hash for chunk in existing_chunks):
        print(f"Document with hash {document_hash} has already been fully processed.")
        print("Document would be skipped in the workflow.")
    else:
        print(f"Document with hash {document_hash} has {len(chunks_to_process)} chunks that need further processing.")
        print("Document would continue processing in the workflow.")
    
    print("\nTEST COMPLETE")
    print("="*80)

if __name__ == "__main__":
    asyncio.run(test_multiple_facts_per_chunk_unique()) 
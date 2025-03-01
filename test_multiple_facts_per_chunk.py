"""
Test script to verify how the system handles chunks with multiple facts.
"""

import os
import asyncio
import pandas as pd
from datetime import datetime
import hashlib

from src.fact_extract.models.state import create_initial_state
from src.fact_extract.storage.chunk_repository import ChunkRepository
from src.fact_extract.storage.fact_repository import FactRepository

async def test_multiple_facts_per_chunk():
    """Test how the system handles chunks with multiple facts."""
    print("\n" + "="*80)
    print("TESTING MULTIPLE FACTS PER CHUNK")
    print("="*80)
    
    # Create test data directory
    os.makedirs("src/fact_extract/data", exist_ok=True)
    
    # Initialize repositories
    chunk_repo = ChunkRepository()
    fact_repo = FactRepository()
    
    # Create a test chunk with multiple facts
    test_chunk_content = """
    The global AI market size was valued at $62.35 billion in 2022. 
    The semiconductor industry reached $573.44 billion in revenue in 2022.
    The average smartphone contains 15 AI-powered features as of 2023.
    """
    
    document_name = "test_multiple_facts.txt"
    document_hash = hashlib.md5(test_chunk_content.encode()).hexdigest()
    
    # Store the test chunk
    print("\nStoring test chunk with multiple facts...")
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
        "statement": "The global AI market size was valued at $62.35 billion in 2022.",
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
    
    # Try to store a second fact from the same chunk
    print("\nStoring second fact from the same chunk...")
    fact2 = {
        "statement": "The semiconductor industry reached $573.44 billion in revenue in 2022.",
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
    
    # Check facts in the repository
    print("\nChecking facts in repository...")
    facts_excel_path = "src/fact_extract/data/all_facts.xlsx"
    if os.path.exists(facts_excel_path):
        facts_df = pd.read_excel(facts_excel_path)
        print(f"Facts Excel file has {len(facts_df)} rows")
        
        # Filter facts for our test document
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
    
    # Try to store a third fact from the same chunk
    print("\nStoring third fact from the same chunk...")
    fact3 = {
        "statement": "The average smartphone contains 15 AI-powered features as of 2023.",
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
    
    # Test is_chunk_processed method
    print("\nTesting is_chunk_processed method...")
    is_processed = chunk_repo.is_chunk_processed({"index": 0}, document_name)
    print(f"Is chunk processed and all facts extracted: {is_processed}")
    
    print("\nTEST COMPLETE")
    print("="*80)

if __name__ == "__main__":
    asyncio.run(test_multiple_facts_per_chunk()) 
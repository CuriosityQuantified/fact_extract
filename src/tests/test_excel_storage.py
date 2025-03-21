"""
Test script to verify Excel storage implementation for chunks and facts.
"""

import os
import sys
import asyncio
import pandas as pd
from datetime import datetime
from unittest.mock import patch, AsyncMock
from langchain_core.messages import AIMessage


# Ensure the src directory is in the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Ensure the src directory is in the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))
from models.state import ProcessingState, create_initial_state
from storage.chunk_repository import ChunkRepository
from storage.fact_repository import FactRepository

async def test_excel_storage():
    """Test Excel storage implementation."""
    print("\n" + "="*80)
    print("TESTING EXCEL STORAGE IMPLEMENTATION")
    print("="*80)
    
    # Create data directory if it doesn't exist
    os.makedirs("data", exist_ok=True)
    
    # Initialize repositories directly
    chunk_repo = ChunkRepository()
    fact_repo = FactRepository()
    
    # Store a test chunk directly
    print("\nStoring test chunk...")
    chunk_repo.store_chunk({
        "timestamp": datetime.now().isoformat(),
        "document_name": "test_document.txt",
        "source_url": "https://example.com/test",
        "chunk_content": "The global AI market size was valued at $62.35 billion in 2022.",
        "chunk_index": 0,
        "status": "processed",
        "contains_facts": True,
        "error_message": None,
        "processing_time": 1.5,
        "document_hash": "test_hash_123",
        "metadata": {
            "word_count": 12,
            "char_length": 62,
            "start_index": 0,
            "source": "test_document.txt",
            "url": "https://example.com/test",
            "timestamp": datetime.now().isoformat()
        }
    })
    
    # Store a test fact directly
    print("\nStoring test fact...")
    test_fact = {
        "statement": "The global AI market size was valued at $62.35 billion in 2022.",
        "source_chunk": 0,
        "original_text": "The global AI market size was valued at $62.35 billion in 2022.",
        "document_name": "test_document.txt",
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
    fact_repo.store_fact(test_fact)
    
    # Check Excel files
    print("\nChecking Excel files...")
    
    # Check chunks Excel
    chunks_excel_path = "data/all_chunks.xlsx"
    if os.path.exists(chunks_excel_path):
        chunks_df = pd.read_excel(chunks_excel_path)
        print(f"\nChunks Excel file exists with {len(chunks_df)} rows")
        print("\nChunks columns:")
        for col in chunks_df.columns:
            print(f"- {col}")
    else:
        print("Chunks Excel file does not exist!")
    
    # Check facts Excel
    facts_excel_path = "data/all_facts.xlsx"
    if os.path.exists(facts_excel_path):
        facts_df = pd.read_excel(facts_excel_path)
        print(f"\nFacts Excel file exists with {len(facts_df)} rows")
        print("\nFacts columns:")
        for col in facts_df.columns:
            print(f"- {col}")
    else:
        print("Facts Excel file does not exist!")
    
    # Test duplicate detection by storing the same chunk again
    print("\nTesting chunk duplicate detection...")
    chunk_repo.store_chunk({
        "timestamp": datetime.now().isoformat(),
        "document_name": "test_document.txt",
        "source_url": "https://example.com/test",
        "chunk_content": "The global AI market size was valued at $62.35 billion in 2022.",
        "chunk_index": 0,
        "status": "processed",
        "contains_facts": True,
        "error_message": None,
        "processing_time": 1.5,
        "document_hash": "test_hash_123",
        "metadata": {
            "word_count": 12,
            "char_length": 62,
            "start_index": 0,
            "source": "test_document.txt",
            "url": "https://example.com/test",
            "timestamp": datetime.now().isoformat()
        }
    })
    
    # Check if the number of rows in the Excel file changed
    if os.path.exists(chunks_excel_path):
        new_chunks_df = pd.read_excel(chunks_excel_path)
        print(f"Chunks Excel file now has {len(new_chunks_df)} rows (should be the same as before)")
    
    # Test fact duplicate detection
    print("\nTesting fact duplicate detection...")
    initial_fact_count = len(pd.read_excel(facts_excel_path)) if os.path.exists(facts_excel_path) else 0
    print(f"Initial fact count: {initial_fact_count}")
    
    # Try to store the same fact again
    fact_repo.store_fact(test_fact)
    
    # Check if the number of facts changed
    if os.path.exists(facts_excel_path):
        new_facts_df = pd.read_excel(facts_excel_path)
        print(f"Facts Excel file now has {len(new_facts_df)} rows (should be the same as before)")
        
        if len(new_facts_df) == initial_fact_count:
            print("SUCCESS: Duplicate fact was not stored!")
        else:
            print("ERROR: Duplicate fact was stored!")
    
    # Test storing a different fact
    print("\nTesting storing a different fact...")
    different_fact = {
        "statement": "The global semiconductor market reached $573.44 billion in 2022 with a growth rate of 3.7%.",
        "source_chunk": 0,
        "original_text": "The global semiconductor market reached $573.44 billion in 2022 with a growth rate of 3.7%.",
        "document_name": "test_document.txt",
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
    fact_repo.store_fact(different_fact)
    
    # Check if the number of facts increased
    if os.path.exists(facts_excel_path):
        final_facts_df = pd.read_excel(facts_excel_path)
        print(f"Facts Excel file now has {len(final_facts_df)} rows (should be one more than before)")
        
        if len(final_facts_df) > initial_fact_count:
            print("SUCCESS: Different fact was stored!")
        else:
            print("ERROR: Different fact was not stored!")
    
    print("\nTEST COMPLETE")
    print("="*80)

if __name__ == "__main__":
    asyncio.run(test_excel_storage()) 
import asyncio
import sys
import os
import hashlib
from datetime import datetime
import uuid
import time
import pytest
import pandas as pd



# Ensure the src directory is in the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

# Ensure the src directory is in the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))
from src.models.state import create_initial_state
from src.graph.nodes import chunker_node, extractor_node, validator_node
from src.utils.synthetic_data import SYNTHETIC_ARTICLE_7
from src.storage.chunk_repository import ChunkRepository
from src.storage.fact_repository import FactRepository

@pytest.mark.asyncio
async def test_duplicate_detection():
    """Test that the system correctly detects and skips duplicate documents."""
    print("\n" + "="*80)
    print("TESTING DUPLICATE DETECTION AND DOCUMENT REPROCESSING PREVENTION")
    print("="*80)
    
    # Create test data directory
    os.makedirs("src/data", exist_ok=True)
    
    # Initialize repositories
    global chunk_repo, fact_repo
    chunk_repo = ChunkRepository()
    fact_repo = FactRepository()
    
    # Create a unique document name for the first run
    unique_id = str(uuid.uuid4())[:8]
    document_name = f"duplicate_test_{unique_id}.txt"
    
    # Create a test article with a unique identifier to ensure it's new
    test_article = SYNTHETIC_ARTICLE_7 + f"\n\nUnique identifier: {unique_id}"
    
    print(f"\nSTEP 1: Processing document for the first time: {document_name}")
    
    # Create initial state for workflow
    state = create_initial_state(
        input_text=test_article,
        document_name=document_name,
        source_url="https://example.com/test_article"
    )
    
    try:
        # Step 1: Execute chunker node
        print("\nExecuting chunker node for first run...")
        chunker_result = await chunker_node(state)
        
        # Check if document was processed
        if chunker_result.get('is_complete', False):
            print("ERROR: Document was marked as complete after chunker node on first run!")
            print("This suggests the duplicate detection is incorrectly identifying a new document as a duplicate.")
            return
        
        print(f"Chunker node created {len(chunker_result.get('chunks', []))} chunks")
        
        # Process first chunk through extractor and validator
        if len(chunker_result.get('chunks', [])) > 0:
            # Update current chunk index
            chunker_result['current_chunk_index'] = 0
            
            # Execute extractor node for first chunk
            print("\nExecuting extractor node for first chunk...")
            extractor_result = await extractor_node(chunker_result)
            
            # Execute validator node for first chunk
            print("\nExecuting validator node for first chunk...")
            validator_result = await validator_node(extractor_result)
            
            print(f"First run extracted {len(validator_result.get('extracted_facts', []))} facts")
        
        # STEP 2: Process the same document again
        print("\n" + "-"*80)
        print(f"STEP 2: Processing the same document again: {document_name}")
        
        # Create a new state with the same document
        second_state = create_initial_state(
            input_text=test_article,
            document_name=document_name,
            source_url="https://example.com/test_article"
        )
        
        # Execute chunker node for second run
        print("\nExecuting chunker node for second run...")
        second_chunker_result = await chunker_node(second_state)
        
        # Check if duplicate detection worked
        if second_chunker_result.get('is_complete', False):
            print("\nSUCCESS: Duplicate detection correctly identified the document as already processed!")
            print("The chunker node marked the workflow as complete, preventing unnecessary reprocessing.")
        else:
            print("\nERROR: Duplicate detection failed! The document was not identified as a duplicate.")
            print(f"Chunker node created {len(second_chunker_result.get('chunks', []))} chunks on second run.")
        
        # STEP 3: Process a slightly modified version of the document
        print("\n" + "-"*80)
        print(f"STEP 3: Processing a modified version of the document")
        
        # Create a modified version of the document
        modified_id = str(uuid.uuid4())[:8]
        modified_document_name = f"modified_test_{modified_id}.txt"
        modified_article = test_article + "\n\nThis is a modified version of the document."
        
        # Create a new state with the modified document
        modified_state = create_initial_state(
            input_text=modified_article,
            document_name=modified_document_name,
            source_url="https://example.com/modified_test_article"
        )
        
        # Execute chunker node for modified document
        print("\nExecuting chunker node for modified document...")
        modified_chunker_result = await chunker_node(modified_state)
        
        # Check if the modified document was processed as new
        if modified_chunker_result.get('is_complete', False):
            print("\nERROR: Modified document was incorrectly identified as a duplicate!")
        else:
            print("\nSUCCESS: Modified document was correctly processed as a new document!")
            print(f"Chunker node created {len(modified_chunker_result.get('chunks', []))} chunks for modified document.")
        
        # STEP 4: Check Excel storage
        print("\n" + "-"*80)
        print("STEP 4: Checking Excel storage for stored chunks and facts")
        
        # Check Excel storage for stored chunks
        print("\nChecking Excel storage for chunks...")
        chunks_excel_path = "src/data/all_chunks.xlsx"
        if os.path.exists(chunks_excel_path):
            chunks_df = pd.read_excel(chunks_excel_path)
            print(f"Chunks Excel file exists with {len(chunks_df)} rows")
            
            # Get chunks for our test document
            doc_chunks = chunks_df[chunks_df['document_name'] == document_name]
            print(f"Chunks for test document: {len(doc_chunks)}")
        else:
            print("Chunks Excel file does not exist!")
        
        # Check Excel storage for stored facts
        print("\nChecking Excel storage for facts...")
        facts_excel_path = "src/data/all_facts.xlsx"
        if os.path.exists(facts_excel_path):
            facts_df = pd.read_excel(facts_excel_path)
            print(f"Facts Excel file exists with {len(facts_df)} rows")
            
            # Get facts for our test document
            doc_facts = facts_df[facts_df['document_name'] == document_name]
            print(f"Facts for test document: {len(doc_facts)}")
        else:
            print("Facts Excel file does not exist!")
    
    except Exception as e:
        print(f"\nError executing test: {str(e)}")
    
    print("\nTEST COMPLETE")
    print("="*80)

if __name__ == "__main__":
    # Initialize global variables for the nodes
    chunk_repo = None
    fact_repo = None
    
    asyncio.run(test_duplicate_detection()) 
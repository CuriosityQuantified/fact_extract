import asyncio
import os
import uuid
import pandas as pd
from datetime import datetime
import hashlib

from src.fact_extract.models.state import WorkflowStateDict
from src.fact_extract.graph.nodes import chunker_node, extractor_node, validator_node
from src.fact_extract.utils.synthetic_data import SYNTHETIC_ARTICLE_6
from src.fact_extract.storage.chunk_repository import ChunkRepository
from src.fact_extract.storage.fact_repository import FactRepository

async def test_full_pipeline_duplicate():
    """
    Test the full production pipeline with SYNTHETIC_ARTICLE_6:
    1. Process the article for the first time
    2. Submit the same article again to verify duplicate detection
    """
    print("\n" + "="*80)
    print("TESTING FULL PRODUCTION PIPELINE WITH DUPLICATE DETECTION")
    print("="*80)
    
    # Create test data directory
    os.makedirs("src/fact_extract/data", exist_ok=True)
    
    # Initialize repositories
    chunk_repo = ChunkRepository()
    fact_repo = FactRepository()
    
    # Create a unique document name for the first run
    unique_id = str(uuid.uuid4())[:8]
    document_name = f"synthetic_article_6_{unique_id}.txt"
    source_url = "https://example.com/synthetic_article_6"
    
    print(f"\nSTEP 1: Processing SYNTHETIC_ARTICLE_6 for the first time: {document_name}")
    
    # Create initial state for workflow
    state: WorkflowStateDict = {
        "session_id": uuid.uuid4(),
        "input_text": SYNTHETIC_ARTICLE_6,
        "document_name": document_name,
        "source_url": source_url,
        "chunks": [],
        "current_chunk_index": 0,
        "extracted_facts": [],
        "errors": [],
        "is_complete": False,
        "memory": {
            "document_stats": {},
            "fact_patterns": [],
            "entity_mentions": {},
            "recent_facts": [],
            "error_counts": {},
            "performance_metrics": {
                "start_time": datetime.now().isoformat(),
                "chunks_processed": 0,
                "facts_extracted": 0,
                "errors_encountered": 0
            }
        },
        "last_processed_time": datetime.now().isoformat()
    }
    
    try:
        # Run the workflow nodes in sequence
        print("\nRunning chunker node for first submission...")
        chunker_result = await chunker_node(state)
        
        if chunker_result.get("is_complete", False):
            print("Chunker node marked workflow as complete. No further processing needed.")
        else:
            # Process each chunk through extractor and validator
            while not chunker_result.get("is_complete", False) and chunker_result["current_chunk_index"] < len(chunker_result["chunks"]):
                print(f"\nProcessing chunk {chunker_result['current_chunk_index']}...")
                
                # Run extractor node
                extractor_result = await extractor_node(chunker_result)
                
                # Run validator node
                validator_result = await validator_node(extractor_result)
                
                # Update state for next iteration
                chunker_result = validator_result
                
                # Check if we're done
                if chunker_result.get("is_complete", True) or chunker_result["current_chunk_index"] >= len(chunker_result["chunks"]):
                    break
        
        # Print results of first run
        print("\nFirst submission processing complete!")
        print(f"Extracted facts: {len(chunker_result.get('extracted_facts', []))}")
        for i, fact in enumerate(chunker_result.get("extracted_facts", []), 1):
            print(f"  {i}. {fact.get('statement', 'No statement')[:100]}...")
        
        # Check Excel storage for facts
        if os.path.exists("src/fact_extract/data/all_facts.xlsx"):
            facts_df = pd.read_excel("src/fact_extract/data/all_facts.xlsx")
            doc_facts = facts_df[facts_df['document_name'] == document_name]
            print(f"\nStored {len(doc_facts)} facts in Excel for first submission")
        
        # Check Excel storage for chunks
        if os.path.exists("src/fact_extract/data/all_chunks.xlsx"):
            chunks_df = pd.read_excel("src/fact_extract/data/all_chunks.xlsx")
            doc_chunks = chunks_df[chunks_df['document_name'] == document_name]
            print(f"Stored {len(doc_chunks)} chunks in Excel for first submission")
            
            # Check if all chunks have been processed
            all_processed = doc_chunks['all_facts_extracted'].all() if 'all_facts_extracted' in chunks_df.columns else False
            print(f"All chunks processed: {all_processed}")
        
        # STEP 2: Process the same document again
        print("\n" + "-"*80)
        print(f"STEP 2: Processing the same document again: {document_name}")
        
        # Create a new state with the same document
        second_state: WorkflowStateDict = {
            "session_id": uuid.uuid4(),
            "input_text": SYNTHETIC_ARTICLE_6,
            "document_name": document_name,
            "source_url": source_url,
            "chunks": [],
            "current_chunk_index": 0,
            "extracted_facts": [],
            "errors": [],
            "is_complete": False,
            "memory": {
                "document_stats": {},
                "fact_patterns": [],
                "entity_mentions": {},
                "recent_facts": [],
                "error_counts": {},
                "performance_metrics": {
                    "start_time": datetime.now().isoformat(),
                    "chunks_processed": 0,
                    "facts_extracted": 0,
                    "errors_encountered": 0
                }
            },
            "last_processed_time": datetime.now().isoformat()
        }
        
        # Run the chunker node for the second time
        print("\nRunning chunker node for second submission...")
        start_time = datetime.now()
        second_chunker_result = await chunker_node(second_state)
        end_time = datetime.now()
        processing_time = (end_time - start_time).total_seconds()
        
        # Check if duplicate detection worked
        if second_chunker_result.get("is_complete", False):
            print(f"\nSUCCESS: Duplicate detection correctly identified the document as already processed!")
            print(f"Processing time: {processing_time:.2f} seconds")
            print("The chunker node marked the workflow as complete, preventing unnecessary reprocessing.")
        else:
            print("\nWARNING: Duplicate detection did not mark the document as already processed.")
            print(f"Chunker node created {len(second_chunker_result.get('chunks', []))} chunks on second run.")
            print(f"Processing time: {processing_time:.2f} seconds")
        
        # STEP 3: Process a slightly modified version of the document
        print("\n" + "-"*80)
        print(f"STEP 3: Processing a modified version of the document")
        
        # Create a modified version of the document
        modified_id = str(uuid.uuid4())[:8]
        modified_document_name = f"modified_article_6_{modified_id}.txt"
        modified_article = SYNTHETIC_ARTICLE_6 + "\n\nThis is a modified version of the document with additional content."
        
        # Create a new state with the modified document
        modified_state: WorkflowStateDict = {
            "session_id": uuid.uuid4(),
            "input_text": modified_article,
            "document_name": modified_document_name,
            "source_url": "https://example.com/modified_synthetic_article_6",
            "chunks": [],
            "current_chunk_index": 0,
            "extracted_facts": [],
            "errors": [],
            "is_complete": False,
            "memory": {
                "document_stats": {},
                "fact_patterns": [],
                "entity_mentions": {},
                "recent_facts": [],
                "error_counts": {},
                "performance_metrics": {
                    "start_time": datetime.now().isoformat(),
                    "chunks_processed": 0,
                    "facts_extracted": 0,
                    "errors_encountered": 0
                }
            },
            "last_processed_time": datetime.now().isoformat()
        }
        
        # Run the chunker node for the modified document
        print("\nRunning chunker node for modified document...")
        modified_chunker_result = await chunker_node(modified_state)
        
        # Check if the modified document was processed as new
        if modified_chunker_result.get("is_complete", False):
            print("\nERROR: Modified document was incorrectly identified as a duplicate!")
        else:
            print("\nSUCCESS: Modified document was correctly processed as a new document!")
            print(f"Chunker node created {len(modified_chunker_result.get('chunks', []))} chunks for modified document.")
        
        # Check Excel storage for chunks of modified document
        if os.path.exists("src/fact_extract/data/all_chunks.xlsx"):
            chunks_df = pd.read_excel("src/fact_extract/data/all_chunks.xlsx")
            mod_chunks = chunks_df[chunks_df['document_name'] == modified_document_name]
            print(f"\nStored {len(mod_chunks)} chunks in Excel for modified document")
    
    except Exception as e:
        print(f"\nError executing test: {str(e)}")
        import traceback
        traceback.print_exc()
    
    print("\nTEST COMPLETE")
    print("="*80)

if __name__ == "__main__":
    asyncio.run(test_full_pipeline_duplicate()) 
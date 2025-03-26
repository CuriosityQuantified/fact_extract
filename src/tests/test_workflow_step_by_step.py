import asyncio
import sys
import os
import hashlib
from datetime import datetime
import uuid
import pytest
import pandas as pd
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock, MagicMock



# Ensure the src directory is in the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

# Ensure the src directory is in the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))
from src.models.state import create_initial_state
from src.graph.nodes import chunker_node, extractor_node, validator_node
from src.utils.synthetic_data import SYNTHETIC_ARTICLE_7
from src.storage.chunk_repository import ChunkRepository
from src.storage.fact_repository import FactRepository, RejectedFactRepository

@pytest.mark.asyncio
async def test_workflow_step_by_step():
    """Test the fact extraction workflow step by step with SYNTHETIC_ARTICLE_7."""
    print("\n" + "="*80)
    print("TESTING FACT EXTRACTION WORKFLOW STEP BY STEP WITH SYNTHETIC_ARTICLE_7")
    print("="*80)
    
    # Create test data directory
    os.makedirs("src/data", exist_ok=True)
    
    # Create a unique document name
    unique_id = str(uuid.uuid4())[:8]
    document_name = f"synthetic_article_7_{unique_id}.txt"
    
    # Initialize repositories (needed for the nodes)
    global chunk_repo, fact_repo
    chunk_repo = ChunkRepository()
    fact_repo = FactRepository()
    
    # Create initial state for workflow
    state = create_initial_state(
        input_text=SYNTHETIC_ARTICLE_7,
        document_name=document_name,
        source_url="https://example.com/synthetic_article_7"
    )
    
    # Add a small modification to the input text to generate a different hash
    state["input_text"] = state["input_text"] + f"\n\nTest run: {unique_id}"
    
    print(f"\nCreated workflow state with document name: {document_name}")
    
    try:
        # Step 1: Execute chunker node
        print("\nStep 1: Executing chunker node...")
        state = await chunker_node(state)
        
        # Check chunker results
        print("\nChunker node execution completed")
        print(f"Is complete: {state.get('is_complete', False)}")
        print(f"Errors: {state.get('errors', [])}")
        print(f"Chunks created: {len(state.get('chunks', []))}")
        
        if state.get('is_complete', False):
            print("Workflow completed after chunker node")
            return
        
        # Process each chunk through extractor and validator
        chunks = state.get('chunks', [])
        for chunk_idx, chunk in enumerate(chunks):
            # Update current chunk index
            state['current_chunk_index'] = chunk_idx
            
            # Step 2: Execute extractor node for this chunk
            print(f"\nStep 2: Executing extractor node for chunk {chunk_idx}...")
            state = await extractor_node(state)
            
            # Check extractor results
            print(f"\nExtractor node execution completed for chunk {chunk_idx}")
            print(f"Is complete: {state.get('is_complete', False)}")
            print(f"Errors: {state.get('errors', [])}")
            print(f"Facts extracted so far: {len(state.get('extracted_facts', []))}")
            
            if state.get('is_complete', False):
                print("Workflow completed after extractor node")
                break
            
            # Step 3: Execute validator node for this chunk
            print(f"\nStep 3: Executing validator node for chunk {chunk_idx}...")
            state = await validator_node(state)
            
            # Check validator results
            print(f"\nValidator node execution completed for chunk {chunk_idx}")
            print(f"Is complete: {state.get('is_complete', False)}")
            print(f"Errors: {state.get('errors', [])}")
            print(f"Facts extracted so far: {len(state.get('extracted_facts', []))}")
            
            if state.get('is_complete', False):
                print("Workflow completed after validator node")
                break
        
        # Print final results
        print("\nWorkflow execution completed")
        
        # Print extracted facts
        facts = state.get("extracted_facts", [])
        verified_facts = [f for f in facts if f.get("verification_status") == "verified"]
        
        print(f"\nExtracted {len(verified_facts)} verified facts from SYNTHETIC_ARTICLE_7:")
        
        for idx, fact in enumerate(verified_facts):
            print(f"\n--- Fact {idx+1} ---")
            print(f"Statement: {fact['statement']}")
            print(f"Status: {fact['verification_status']}")
            print(f"Reason: {fact.get('verification_reason', 'Not provided')}")
        
        # Check Excel storage (should have stored the fact)
        print("\nChecking Excel storage...")
        facts_excel_path = "src/data/all_facts.xlsx"
        if os.path.exists(facts_excel_path):
            facts_df = pd.read_excel(facts_excel_path)
            doc_facts = facts_df[facts_df['document_name'] == document_name]
            print(f"Facts for test document: {len(doc_facts)}")
            
            if len(doc_facts) > 0:
                print("\nFACTS:")
                for i, fact in doc_facts.iterrows():
                    print(f"  {i+1}. {fact.get('statement', 'No statement')[:100]}")
                    print(f"     Verified: {fact.get('verification_status', 'Unknown')}")
        else:
            print("Facts Excel file does not exist!")
    
    except Exception as e:
        print(f"\nError executing workflow: {str(e)}")
    
    print("\nTEST COMPLETE")
    print("="*80)

if __name__ == "__main__":
    # Initialize global variables for the nodes
    chunk_repo = None
    fact_repo = None
    
    asyncio.run(test_workflow_step_by_step()) 
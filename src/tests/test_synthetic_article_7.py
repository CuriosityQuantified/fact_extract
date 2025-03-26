import asyncio
import sys
import os
import hashlib
from datetime import datetime
import uuid
import pytest



# Ensure the src directory is in the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

# Ensure the src directory is in the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))
from src.utils.synthetic_data import SYNTHETIC_ARTICLE_7
from src.models.state import create_initial_state, ProcessingState
from src.graph.nodes import process_document
from src.storage.chunk_repository import ChunkRepository
from src.storage.fact_repository import FactRepository

@pytest.mark.asyncio
async def test_synthetic_article_7():
    """Test the fact extraction pipeline with SYNTHETIC_ARTICLE_7."""
    print("\n" + "="*80)
    print("TESTING FACT EXTRACTION WITH SYNTHETIC_ARTICLE_7")
    print("="*80)
    
    # Create test data directory
    os.makedirs("data", exist_ok=True)
    
    # Create a temporary file with the synthetic article
    unique_id = str(uuid.uuid4())[:8]
    temp_file_path = f"synthetic_article_7_{unique_id}.txt"
    with open(temp_file_path, "w") as f:
        f.write(SYNTHETIC_ARTICLE_7)
    
    print(f"\nCreated temporary file: {temp_file_path}")
    
    try:
        # Process the document
        print("\nProcessing SYNTHETIC_ARTICLE_7...")
        
        # Initialize the processing state
        state = ProcessingState()
        
        # Process the document
        result = await process_document(temp_file_path, state)
        
        # Check the results
        print("\nProcessing completed with result:")
        print(f"Status: {result.get('status', 'unknown')}")
        if result.get('status') == 'error':
            print(f"Error: {result.get('error', 'None')}")
        
        # Check extracted facts
        fact_repo = FactRepository()
        facts_excel_path = "data/all_facts.xlsx"
        
        if os.path.exists(facts_excel_path):
            import pandas as pd
            facts_df = pd.read_excel(facts_excel_path)
            
            # Filter facts for our test document
            test_facts = facts_df[facts_df['document_name'] == temp_file_path]
            
            print(f"\nExtracted {len(test_facts)} facts from SYNTHETIC_ARTICLE_7:")
            
            for idx, fact in test_facts.iterrows():
                print(f"\n--- Fact {idx+1} ---")
                print(f"Statement: {fact['statement']}")
                print(f"Status: {fact['verification_status']}")
                print(f"Reason: {fact['verification_reason']}")
        else:
            print("\nNo facts Excel file found!")
    
    finally:
        # Clean up
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)
            print(f"\nRemoved temporary file: {temp_file_path}")
    
    print("\nTEST COMPLETE")
    print("="*80)

if __name__ == "__main__":
    asyncio.run(test_synthetic_article_7()) 
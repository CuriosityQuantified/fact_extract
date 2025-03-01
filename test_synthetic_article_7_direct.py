import asyncio
import os
import hashlib
from datetime import datetime
import uuid

from src.fact_extract.models.state import create_initial_state
from src.fact_extract.graph.nodes import create_workflow
from src.fact_extract.utils.synthetic_data import SYNTHETIC_ARTICLE_7
from src.fact_extract.storage.chunk_repository import ChunkRepository
from src.fact_extract.storage.fact_repository import FactRepository

async def test_synthetic_article_7_direct():
    """Test the fact extraction pipeline with SYNTHETIC_ARTICLE_7 using direct workflow execution."""
    print("\n" + "="*80)
    print("TESTING FACT EXTRACTION WITH SYNTHETIC_ARTICLE_7 (DIRECT WORKFLOW)")
    print("="*80)
    
    # Create test data directory
    os.makedirs("src/fact_extract/data", exist_ok=True)
    
    # Create a unique document name
    unique_id = str(uuid.uuid4())[:8]
    document_name = f"synthetic_article_7_{unique_id}.txt"
    
    # Initialize repositories
    chunk_repo = ChunkRepository()
    fact_repo = FactRepository()
    
    # Create initial state for workflow
    workflow_state = create_initial_state(
        input_text=SYNTHETIC_ARTICLE_7,
        document_name=document_name,
        source_url="https://example.com/synthetic_article_7"
    )
    
    print(f"\nCreated workflow state with document name: {document_name}")
    
    try:
        # Create workflow
        workflow, input_key = create_workflow(chunk_repo, fact_repo)
        
        # Execute workflow
        print("\nExecuting workflow...")
        result = await workflow.ainvoke({input_key: SYNTHETIC_ARTICLE_7})
        
        # Check the results
        print("\nWorkflow execution completed")
        print(f"Is complete: {result.get('is_complete', False)}")
        print(f"Errors: {result.get('errors', [])}")
        print(f"Extracted facts: {len(result.get('extracted_facts', []))}")
        
        # Print extracted facts
        facts = result.get("extracted_facts", [])
        verified_facts = [f for f in facts if f.get("verification_status") == "verified"]
        
        print(f"\nExtracted {len(verified_facts)} verified facts from SYNTHETIC_ARTICLE_7:")
        
        for idx, fact in enumerate(verified_facts):
            print(f"\n--- Fact {idx+1} ---")
            print(f"Statement: {fact['statement']}")
            print(f"Status: {fact['verification_status']}")
            print(f"Reason: {fact.get('verification_reason', 'Not provided')}")
        
        # Check facts in Excel
        facts_excel_path = "src/fact_extract/data/all_facts.xlsx"
        if os.path.exists(facts_excel_path):
            import pandas as pd
            facts_df = pd.read_excel(facts_excel_path)
            
            # Filter facts for our test document
            test_facts = facts_df[facts_df['document_name'] == document_name]
            
            print(f"\nStored {len(test_facts)} facts in Excel for document {document_name}")
        else:
            print("\nNo facts Excel file found!")
    
    except Exception as e:
        print(f"\nError executing workflow: {str(e)}")
    
    print("\nTEST COMPLETE")
    print("="*80)

if __name__ == "__main__":
    asyncio.run(test_synthetic_article_7_direct()) 
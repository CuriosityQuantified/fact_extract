"""
Test script to verify the full pipeline with rejected facts storage.
"""

import os
import sys
import asyncio
import uuid
from datetime import datetime
import pandas as pd

from fact_extract.storage.fact_repository import FactRepository, RejectedFactRepository
from fact_extract.storage.chunk_repository import ChunkRepository
from fact_extract.models.state import ProcessingState, create_initial_state, FactDict
from fact_extract.graph.nodes import validator_node

TEST_TEXT = """
# Test Article for Fact Extraction

This article contains some verifiable facts and some statements that should be rejected.

## Verifiable Facts

The global semiconductor market reached $556 billion in revenue in 2021, representing a 26% year-over-year growth.

Taiwan Semiconductor Manufacturing Company (TSMC) achieved a 45% market share in the global foundry business in Q1 2022.

## Statements Without Specific Metrics (Should Be Rejected)

Artificial intelligence will transform the future of work.

Cloud computing has become increasingly important for businesses.

Companies are investing more in cybersecurity than ever before.
"""

async def test_validator_node_with_rejected_facts():
    """Test that the validator node correctly stores rejected facts."""
    print("\n" + "="*80)
    print("TESTING VALIDATOR NODE WITH REJECTED FACTS STORAGE")
    print("="*80)
    
    # Generate a unique document name to avoid conflicts with previous test runs
    document_name = f"test_validator_{uuid.uuid4()}"
    print(f"Test document name: {document_name}")
    
    # Initialize repositories
    fact_repo = FactRepository()
    rejected_fact_repo = RejectedFactRepository()
    
    # Create a temporary file with test text
    temp_file_path = f"temp_test_file_{uuid.uuid4()}.md"
    with open(temp_file_path, "w") as f:
        f.write(TEST_TEXT)
    
    print(f"\nCreated temporary test file: {temp_file_path}")
    
    try:
        # Read file content
        with open(temp_file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Create workflow state directly
        workflow_state = create_initial_state(
            input_text=content,
            document_name=document_name,
            source_url="test_url"
        )
        
        # Add both valid and invalid facts to the state
        current_time = datetime.now().isoformat()
        
        # Valid fact 1
        valid_fact1: FactDict = {
            "statement": "The global semiconductor market reached $556 billion in revenue in 2021",
            "source_chunk": 0,
            "original_text": content,
            "document_name": document_name,
            "source_url": "test_url",
            "timestamp": current_time,
            "verification_status": "pending",
            "verification_reason": None,
            "metadata": {"fact_number": 1}
        }
        
        # Valid fact 2
        valid_fact2: FactDict = {
            "statement": "Taiwan Semiconductor Manufacturing Company (TSMC) achieved a 45% market share in the global foundry business in Q1 2022",
            "source_chunk": 0,
            "original_text": content,
            "document_name": document_name,
            "source_url": "test_url",
            "timestamp": current_time,
            "verification_status": "pending",
            "verification_reason": None,
            "metadata": {"fact_number": 2}
        }
        
        # Invalid fact 1 (no specific metrics)
        invalid_fact1: FactDict = {
            "statement": "Artificial intelligence will transform the future of work",
            "source_chunk": 0,
            "original_text": content,
            "document_name": document_name,
            "source_url": "test_url",
            "timestamp": current_time,
            "verification_status": "pending",
            "verification_reason": None,
            "metadata": {"fact_number": 3}
        }
        
        # Invalid fact 2 (no specific metrics)
        invalid_fact2: FactDict = {
            "statement": "Cloud computing has become increasingly important for businesses",
            "source_chunk": 0,
            "original_text": content,
            "document_name": document_name,
            "source_url": "test_url",
            "timestamp": current_time,
            "verification_status": "pending",
            "verification_reason": None,
            "metadata": {"fact_number": 4}
        }
        
        # Add facts to state
        workflow_state["extracted_facts"] = [valid_fact1, valid_fact2, invalid_fact1, invalid_fact2]
        workflow_state["chunks"] = [{
            "content": content,
            "index": 0,
            "metadata": {
                "word_count": len(content.split()),
                "char_length": len(content),
                "start_index": 0,
                "source": document_name,
                "url": "test_url",
                "timestamp": current_time
            }
        }]
        
        print("\nRunning validator node with 4 facts (2 valid, 2 invalid)...")
        
        # Run validator node directly
        result = await validator_node(workflow_state)
        
        print("\nValidator node execution completed")
        
        # Check results
        print("\nTEST RESULTS:")
        print("-" * 40)
        
        # Check verified facts
        verified_facts = [f for f in result["extracted_facts"] if f.get("verification_status") == "verified"]
        print(f"Verified facts count: {len(verified_facts)}")
        for fact in verified_facts:
            print(f"- {fact['statement']}")
        
        # Check rejected facts
        rejected_facts = [f for f in result["extracted_facts"] if f.get("verification_status") == "rejected"]
        print(f"\nRejected facts count: {len(rejected_facts)}")
        for fact in rejected_facts:
            print(f"- {fact['statement']}")
            print(f"  Reason: {fact.get('verification_reason', 'No reason provided')}")
        
        # Verify that rejected facts are in the Excel file
        rejected_excel_path = "src/fact_extract/data/rejected_facts.xlsx"
        if os.path.exists(rejected_excel_path):
            try:
                df = pd.read_excel(rejected_excel_path)
                
                # Filter to our test document
                doc_df = df[df['document_name'] == document_name]
                print(f"\nRejected facts for test document in Excel: {len(doc_df)}")
                
                # Print rejected facts from Excel
                for _, row in doc_df.iterrows():
                    print(f"- {row['fact']}")
                    print(f"  Reason: {row['rejection_reason']}")
                
                # Check if we have rejections as expected
                has_rejections = len(doc_df) > 0
                print(f"\nTest {'PASSED' if has_rejections else 'FAILED'}")
                print(f"Expected at least 1 rejected fact, found {len(doc_df)} in Excel file")
            except Exception as e:
                print(f"Error reading Excel file: {str(e)}")
        else:
            print(f"\nRejected facts Excel file not found at {rejected_excel_path}")
            print("Test FAILED")
    
    finally:
        # Clean up: remove temporary file
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)
            print(f"\nRemoved temporary test file: {temp_file_path}")
    
    print("="*80)

if __name__ == "__main__":
    asyncio.run(test_validator_node_with_rejected_facts()) 
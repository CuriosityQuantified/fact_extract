"""
Test script to verify rejected facts storage functionality.
"""

import os
import sys
import asyncio
import uuid
import pytest
from datetime import datetime
import pandas as pd


# Ensure the src directory is in the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Ensure the src directory is in the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))
from src.storage.fact_repository import FactRepository, RejectedFactRepository
from src.models.state import WorkflowStateDict

@pytest.mark.asyncio
async def test_rejected_facts_storage():
    """Test that rejected facts are properly stored in the rejected_facts.xlsx file."""
    print("\n" + "="*80)
    print("TESTING REJECTED FACTS STORAGE")
    print("="*80)
    
    # Generate a unique document name to avoid conflicts with previous test runs
    document_name = f"test_rejected_facts_{uuid.uuid4()}"
    print(f"Test document name: {document_name}")
    
    # Initialize repositories
    fact_repo = FactRepository()
    rejected_fact_repo = RejectedFactRepository()
    
    # Create test facts
    verified_fact = {
        "statement": "This is a test fact that should be verified.",
        "original_text": "This is a test fact that should be verified. It contains a specific metric: 123 units.",
        "source_chunk": 0,
        "document_name": document_name,
        "verification_status": "verified",
        "verification_reason": "This fact is verifiable and contains specific metrics.",
        "timestamp": datetime.now().isoformat(),
        "source_url": "https://example.com/rejected_facts_test",
        "source_name": "Rejected Facts Test"
    }
    
    rejected_fact1 = {
        "statement": "This is a test fact that should be rejected.",
        "original_text": "This statement is speculative and contains no specific metrics or measurements.",
        "source_chunk": 1,
        "document_name": document_name,
        "verification_status": "rejected",
        "verification_reason": "This fact lacks specific metrics or measurements.",
        "timestamp": datetime.now().isoformat(),
        "source_url": "https://example.com/rejected_facts_test",
        "source_name": "Rejected Facts Test"
    }
    
    rejected_fact2 = {
        "statement": "Another test fact that should be rejected.",
        "original_text": "This is another statement that lacks verifiable data points.",
        "source_chunk": 2,
        "document_name": document_name,
        "verification_status": "rejected",
        "verification_reason": "This fact also lacks verifiable data points.",
        "timestamp": datetime.now().isoformat(),
        "source_url": "https://example.com/rejected_facts_test",
        "source_name": "Rejected Facts Test"
    }
    
    # Directly store facts in repositories
    print("\nStoring facts in repositories...")
    print("- Storing 1 verified fact")
    fact_repo.store_fact(verified_fact)
    
    print("- Storing 2 rejected facts")
    rejected_fact_repo.store_rejected_fact(rejected_fact1)
    rejected_fact_repo.store_rejected_fact(rejected_fact2)
    
    # Check results
    print("\nTEST RESULTS:")
    print("-" * 40)
    
    # Check if verified facts were stored
    verified_facts = fact_repo.get_facts(document_name)
    print(f"Verified facts count: {len(verified_facts)}")
    for fact in verified_facts:
        print(f"- {fact['statement']}")
    
    # Check if rejected facts were stored
    rejected_facts = rejected_fact_repo.get_rejected_facts(document_name)
    print(f"\nRejected facts count: {len(rejected_facts)}")
    for fact in rejected_facts:
        print(f"- {fact['statement']}")
    
    # Verify the rejected fact is stored in the Excel file
    print("\nVerifying Excel storage of rejected facts...")
    rejected_excel_path = "data/rejected_facts.xlsx"
    if os.path.exists(rejected_excel_path):
        try:
            df = pd.read_excel(rejected_excel_path)
            print(f"\nRejected facts in Excel file: {len(df)}")
            
            # Filter to our test document
            doc_df = df[df['document_name'] == document_name]
            print(f"Rejected facts for test document: {len(doc_df)}")
            
            # Print rejected facts from Excel
            for _, row in doc_df.iterrows():
                print(f"- {row['fact']}")
                print(f"  Reason: {row['rejection_reason']}")
            
            test_passed = len(rejected_facts) == len(doc_df)
            print(f"\nTest {'PASSED' if test_passed else 'FAILED'}")
            print(f"Expected {len(rejected_facts)} rejected facts, found {len(doc_df)} in Excel file")
            
        except Exception as e:
            print(f"Error reading Excel file: {str(e)}")
    else:
        print(f"\nRejected facts Excel file not found at {rejected_excel_path}")
        print("Test FAILED")
    
    print("="*80)

if __name__ == "__main__":
    asyncio.run(test_rejected_facts_storage()) 
"""
Test script for verifying the rejected facts functionality.
"""

import os
import sys
import asyncio
import json
from pathlib import Path
from dotenv import load_dotenv
import uuid
from datetime import datetime
import pandas as pd
import pytest



# Ensure the src directory is in the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
# Ensure the src directory is in the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

# Load environment variables from .env file
dotenv_path = Path(__file__).parents[2] / '.env'
load_dotenv(dotenv_path)

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
    
    # Create test data directory
    os.makedirs("src/data", exist_ok=True)
    
    # Check Excel storage
    print("\nChecking Excel storage...")
    rejected_excel_path = "src/data/rejected_facts.xlsx"
    if os.path.exists(rejected_excel_path):
        rejected_df = pd.read_excel(rejected_excel_path)
        print(f"\nRejected facts Excel file exists with {len(rejected_df)} rows")
        
        # Find the test fact
        test_facts = rejected_df[rejected_df['document_name'] == document_name]
        print(f"Found {len(test_facts)} test facts")
        
        if len(test_facts) > 0:
            print("\nREJECTED FACTS:")
            for i, fact in test_facts.iterrows():
                print(f"  {i+1}. {fact.get('statement', 'No statement')[:100]}")
                print(f"     Reason: {fact.get('rejection_reason', 'No reason')[:100]}")
    else:
        print("Rejected facts Excel file does not exist!")
    
    print("="*80)

if __name__ == "__main__":
    asyncio.run(test_rejected_facts_storage()) 
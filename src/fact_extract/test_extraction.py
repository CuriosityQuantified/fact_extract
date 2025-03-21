"""
Test script for fact extraction using synthetic data.
"""

from typing import Dict, List
import sys
import asyncio
import os
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables from .env file
dotenv_path = Path(__file__).parents[2] / '.env'
load_dotenv(dotenv_path)

from fact_extract.utils.synthetic_data import SYNTHETIC_ARTICLE_2
from fact_extract.__main__ import extract_facts

def print_facts(facts: List[Dict]):
    """Print facts with statistics."""
    if not facts:
        print("No facts found.")
        return
        
    print("\nExtracted Facts:")
    print("-" * 80)
    for fact in facts:
        print(f"\nFact from chunk {fact['source_chunk']}:")
        print(f"  Statement: {fact['statement']}")
        print(f"  Source: {fact['document_name']}")
        print(f"  Status: {fact['verification_status']}")
        if fact.get('verification_reason'):
            print(f"  Reason: {fact['verification_reason']}")
    
    # Print statistics
    total = len(facts)
    verified = len([f for f in facts if f["verification_status"] == "verified"])
    rejected = len([f for f in facts if f["verification_status"] == "rejected"])
    pending = total - verified - rejected
    
    print("\nStatistics:")
    print("-" * 80)
    print(f"Total facts: {total}")
    print(f"Verified facts: {verified}")
    print(f"Rejected facts: {rejected}")
    print(f"Pending facts: {pending}")
    print()

async def test_extraction(text: str, document_name: str = "test_doc"):
    """Test fact extraction on a piece of text."""
    # Initialize state
    state = create_initial_state()
    state.text = text
    state.document_name = document_name
    
    # Run chunker
    state = await chunker_node(state)
    print(f"Split into {len(state.chunks)} chunks")
    
    # Run extractor
    state = await extractor_node(state)
    print(f"Extracted {len(state.facts)} facts")
    
    # Print results
    print_facts(state.facts)
    return state.facts

async def main_async():
    """Async main function."""
    print("Testing fact extraction on sustainable data centers article...")
    print("-" * 80)
    
    try:
        facts = await extract_facts(
            text=SYNTHETIC_ARTICLE_2,
            document_name="Sustainable Data Centers Article",
            source_url="https://example.com/sustainable-data-centers"
        )
        print_facts(facts)
        return facts
        
    except Exception as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        return []

def main():
    """Main entry point."""
    asyncio.run(main_async())

if __name__ == "__main__":
    main() 
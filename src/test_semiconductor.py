"""
Test script for extracting facts from semiconductor industry documents.
"""

import os
import sys
import asyncio
import logging
from typing import List, Dict
from pathlib import Path
from dotenv import load_dotenv


# Ensure the src directory is in the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
# Ensure the src directory is in the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

# Load environment variables from .env file
dotenv_path = Path(__file__).parents[2] / '.env'
load_dotenv(dotenv_path)

from utils.synthetic_data import SYNTHETIC_ARTICLE_6
from __main__ import extract_facts as main_extract_facts, print_stats, print_fact

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

async def test_extraction():
    """Test fact extraction on semiconductor article."""
    print("Testing fact extraction on semiconductor article...")
    print("-" * 80)
    print("\nArticle content:")
    print("-" * 80)
    print(SYNTHETIC_ARTICLE_6[:500] + "...")  # Print first 500 chars
    
    try:
        facts = await extract_facts(
            text=SYNTHETIC_ARTICLE_6,
            document_name="SYNTHETIC_ARTICLE_6"
        )
        print_facts(facts)
        return facts
        
    except Exception as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        sys.exit(1)

def main():
    """Main test function."""
    asyncio.run(test_extraction())

if __name__ == "__main__":
    main() 
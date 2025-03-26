"""
Test script for extracting facts from semiconductor industry documents.
"""

import os
import sys
import asyncio
import logging
import pytest
from typing import List, Dict, Any
from pathlib import Path
from dotenv import load_dotenv


# Ensure the src directory is in the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
# Ensure the src directory is in the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

# Load environment variables from .env file
dotenv_path = Path(__file__).parents[2] / '.env'
load_dotenv(dotenv_path)

from src.utils.synthetic_data import SYNTHETIC_ARTICLE_6
from src.models.state import create_initial_state
from src.graph.nodes import chunker_node, extractor_node, validator_node

# Define our own implementation of extract_facts
async def extract_facts(text: str, document_name: str, source_url: str = "") -> List[Dict[str, Any]]:
    """
    Extract facts from text.
    
    Args:
        text: The text to extract facts from
        document_name: The name of the document
        source_url: Optional URL source of the document
        
    Returns:
        List of extracted facts
    """
    # Initialize state
    state = create_initial_state(
        input_text=text,
        document_name=document_name,
        source_url=source_url
    )
    
    # Process through nodes
    state = await chunker_node(state)
    state = await extractor_node(state)
    state = await validator_node(state)
    
    return state.get("extracted_facts", [])

def print_fact(fact: Dict[str, Any]) -> None:
    """
    Print a single fact with its details.
    
    Args:
        fact: The fact to print
    """
    status = fact.get("verification_status", "unknown")
    status_icon = "✅" if status == "verified" else "❌" if status == "rejected" else "⏳"
    
    print(f"\n{status_icon} Fact:")
    print(f"  Statement: {fact.get('statement', '')}")
    print(f"  Status: {status}")
    if fact.get("verification_reason"):
        print(f"  Reason: {fact['verification_reason']}")
    print(f"  Source: {fact.get('document_name', '')}, chunk {fact.get('source_chunk', 'unknown')}")

def print_facts(facts: List[Dict]) -> Dict[str, int]:
    """
    Print facts with statistics.
    
    Args:
        facts: List of facts to print
        
    Returns:
        Dictionary with statistics
    """
    if not facts:
        print("No facts found.")
        return {"total": 0, "verified": 0, "rejected": 0, "pending": 0}
        
    print("\nExtracted Facts:")
    print("-" * 80)
    for fact in facts:
        chunk = fact.get('source_chunk', 'unknown')
        print(f"\nFact from chunk {chunk}:")
        print(f"  Statement: {fact.get('statement', '')}")
        print(f"  Source: {fact.get('document_name', '')}")
        print(f"  Status: {fact.get('verification_status', '')}")
        if fact.get('verification_reason'):
            print(f"  Reason: {fact['verification_reason']}")
    
    # Print statistics
    total = len(facts)
    verified = len([f for f in facts if f.get("verification_status") == "verified"])
    rejected = len([f for f in facts if f.get("verification_status") == "rejected"])
    pending = total - verified - rejected
    
    print("\nStatistics:")
    print("-" * 80)
    print(f"Total facts: {total}")
    print(f"Verified facts: {verified}")
    print(f"Rejected facts: {rejected}")
    print(f"Pending facts: {pending}")
    print()
    
    return {"total": total, "verified": verified, "rejected": rejected, "pending": pending}

@pytest.mark.asyncio
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
        stats = print_facts(facts)
        
        # Verify facts were extracted correctly
        if facts:
            for fact in facts:
                assert "statement" in fact
                assert "verification_status" in fact
        
        return facts
        
    except Exception as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        raise

def main():
    """Main test function."""
    asyncio.run(test_extraction())

if __name__ == "__main__":
    main() 
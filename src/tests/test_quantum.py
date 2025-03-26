"""
Test script for extracting facts from quantum computing documents.
"""

import os
import sys
import pytest
from dotenv import load_dotenv
from pathlib import Path


# Ensure the src directory is in the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
# Ensure the src directory is in the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

# Load environment variables from .env file
dotenv_path = Path(__file__).parents[2] / '.env'
load_dotenv(dotenv_path)

import asyncio
import logging
from typing import List, Dict, Any

from src.utils.synthetic_data import SYNTHETIC_ARTICLE_5
from src.models.state import create_initial_state
from src.graph.nodes import chunker_node, extractor_node, validator_node

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    force=True  # Override any existing logging configuration
)
logger = logging.getLogger(__name__)

# Set logging level for specific modules
logging.getLogger('src.graph.nodes').setLevel(logging.INFO)
logging.getLogger('src.storage').setLevel(logging.INFO)

# Define necessary helper functions
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

def print_stats(facts: List[Dict[str, Any]]) -> Dict[str, int]:
    """
    Print statistics about the extracted facts.
    
    Args:
        facts: List of facts
        
    Returns:
        Dictionary with statistics
    """
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
    
    if total > 0:
        print(f"Verification rate: {verified/total*100:.1f}%")
    
    return {"total": total, "verified": verified, "rejected": rejected, "pending": pending}

@pytest.mark.asyncio
async def test_quantum_article():
    """Test fact extraction on quantum computing article."""
    print("Testing fact extraction on quantum computing article...")
    print("-" * 80)
    print("\nArticle excerpt:")
    print("-" * 80)
    print(SYNTHETIC_ARTICLE_5[:200] + "...\n")
    
    try:
        # Extract facts
        facts = await extract_facts(
            text=SYNTHETIC_ARTICLE_5,
            document_name="Quantum Computing Article",
            source_url="synthetic_data.py"
        )
        
        if not facts:
            print("\nNo facts were extracted.")
            return []
            
        # Print all facts with their verification status
        print("\nExtracted Facts:")
        print("-" * 80)
        for fact in facts:
            print_fact(fact)
            
        # Print statistics
        stats = print_stats(facts)
        
        # Verify we extracted either no facts or some facts with correct structure
        if facts:
            for fact in facts:
                assert "statement" in fact
                assert "verification_status" in fact
        
        return facts
        
    except Exception as e:
        logger.error(f"Error during testing: {str(e)}")
        raise

if __name__ == "__main__":
    asyncio.run(test_quantum_article()) 
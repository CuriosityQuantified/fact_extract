"""
Test script for fact extraction from quantum computing article.
"""

import asyncio
import logging
from typing import List, Dict

from fact_extract.utils.synthetic_data import SYNTHETIC_ARTICLE_5
from fact_extract.__main__ import extract_facts, print_stats, print_fact

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    force=True  # Override any existing logging configuration
)
logger = logging.getLogger(__name__)

# Set logging level for specific modules
logging.getLogger('fact_extract.graph.nodes').setLevel(logging.INFO)
logging.getLogger('fact_extract.storage').setLevel(logging.INFO)

async def test_quantum_article():
    """Test fact extraction on cybersecurity article."""
    print("Testing fact extraction on cybersecurity article...")
    print("-" * 80)
    print("\nArticle excerpt:")
    print("-" * 80)
    print(SYNTHETIC_ARTICLE_5[:200] + "...\n")
    
    try:
        # Extract facts
        facts = await extract_facts(
            text=SYNTHETIC_ARTICLE_5,
            document_name="Cybersecurity Evolution",
            source_url="synthetic_data.py"
        )
        
        if not facts:
            print("\nNo facts were extracted.")
            return
            
        # Print all facts with their verification status
        print("\nExtracted Facts:")
        print("-" * 80)
        for fact in facts:
            print_fact(fact)
            
        # Print statistics
        print_stats(facts)
        
    except Exception as e:
        logger.error(f"Error during testing: {str(e)}")
        raise

if __name__ == "__main__":
    asyncio.run(test_quantum_article()) 
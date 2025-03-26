"""
Test script for extracting facts from quantum computing documents.
"""

import os
import sys
from dotenv import load_dotenv
from pathlib import Path


# Ensure the src directory is in the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
# Ensure the src directory is in the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

# Load environment variables from .env file
dotenv_path = Path(__file__).parents[2] / '.env'
load_dotenv(dotenv_path)

import asyncio

import pytest
from src.utils.test_helpers import with_timeoutimport logging
from typing import List, Dict

from src.utils.synthetic_data import SYNTHETIC_ARTICLE_5
from __main__ import extract_facts as main_extract_facts, print_stats, print_fact

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

@pytest.mark.asyncio
@with_timeout(seconds=30)
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
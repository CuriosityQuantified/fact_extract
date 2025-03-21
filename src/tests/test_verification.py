"""
Test script for fact extraction and verification system.
"""

import logging
import sys
import asyncio
from typing import Dict, List
import os
import pytest


# Ensure the src directory is in the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Ensure the src directory is in the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))
from langchain_openai import ChatOpenAI
from utils.synthetic_data import SYNTHETIC_ARTICLE, SYNTHETIC_ARTICLE_2
from agents.verification import FactVerificationAgent, VerificationResult
from storage.fact_repository import FactRepository

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@pytest.mark.asyncio
async def test_verification_exact_match():
    """Test verification with an exact quote."""
    print("\nInitializing FactVerificationAgent for exact match test...")
    sys.stdout.flush()
    
    # Initialize the language model
    llm = ChatOpenAI(temperature=0, model="gpt-4o")
    
    verifier = FactVerificationAgent(llm=llm)
    print("FactVerificationAgent initialized successfully")
    sys.stdout.flush()
    
    # Test case 1: Exact match from the text
    original_text = """The impact of these specialized facilities extends beyond the technology sector. 
    Local communities where these data centers are located often experience significant economic benefits 
    through job creation and increased tax revenue."""
    
    fact_text = "Local communities where these data centers are located often experience significant economic benefits through job creation and increased tax revenue"
    
    print("\nTest Case 1: Exact Match")
    print("-" * 80)
    print(f"Original Text: {original_text}")
    print(f"Fact Text: {fact_text}")
    sys.stdout.flush()
    
    print("\nCalling verify_fact...")
    sys.stdout.flush()
    result = await verifier.verify_fact(fact_text, original_text, document_name="Test Document 1")
    print("verify_fact completed")
    sys.stdout.flush()
    
    print_verification_result(result)

@pytest.mark.asyncio
async def test_verification_paraphrase():
    """Test verification with a paraphrased quote."""
    print("\nInitializing FactVerificationAgent for paraphrase test...")
    sys.stdout.flush()
    
    # Initialize the language model
    llm = ChatOpenAI(temperature=0, model="gpt-4o")
    
    verifier = FactVerificationAgent(llm=llm)
    print("FactVerificationAgent initialized successfully")
    sys.stdout.flush()
    
    # Test case 2: Paraphrased version
    original_text = """In September 2022, Amazon Web Services announced that their European 
    data centers had reached an impressive milestone of 90% renewable energy usage across all 
    their facilities in the region."""
    
    fact_text = "AWS data centers in Europe achieved 90% renewable energy usage in September 2022"
    
    print("\nTest Case 2: Paraphrased Version")
    print("-" * 80)
    print(f"Original Text: {original_text}")
    print(f"Fact Text: {fact_text}")
    sys.stdout.flush()
    
    print("\nCalling verify_fact...")
    sys.stdout.flush()
    result = await verifier.verify_fact(fact_text, original_text, document_name="Test Document 2")
    print("verify_fact completed")
    sys.stdout.flush()
    
    print_verification_result(result)

@pytest.mark.asyncio
async def test_verification_incorrect():
    """Test verification with an incorrect fact."""
    print("\nInitializing FactVerificationAgent for incorrect fact test...")
    sys.stdout.flush()
    
    # Initialize the language model
    llm = ChatOpenAI(temperature=0, model="gpt-4o")
    
    verifier = FactVerificationAgent(llm=llm)
    print("FactVerificationAgent initialized successfully")
    sys.stdout.flush()
    
    # Test case 3: Incorrect fact
    original_text = """One particularly noteworthy development in this space occurred in 2023, 
    when Google's data center in Council Bluffs, Iowa, achieved a record-breaking Power Usage 
    Effectiveness (PUE) of 1.06, marking it as one of the most energy-efficient large-scale 
    data centers in the world."""
    
    fact_text = "Google's data center in Council Bluffs, Iowa, achieved a record-breaking Power Usage Effectiveness (PUE) of 1.06"
    
    print("\nTest Case 3: Incorrect Fact")
    print("-" * 80)
    print(f"Original Text: {original_text}")
    print(f"Fact Text: {fact_text}")
    sys.stdout.flush()
    
    print("\nCalling verify_fact...")
    sys.stdout.flush()
    result = await verifier.verify_fact(fact_text, original_text, document_name="Test Document 3")
    print("verify_fact completed")
    sys.stdout.flush()
    
    print_verification_result(result)

def print_verification_result(result: VerificationResult):
    """Print a verification result."""
    print("\nVerification Result:")
    print(f"Valid: {result.is_valid}")
    print(f"Reason: {result.reason}")
    print()

async def main():
    """Run all verification tests."""
    print("Starting fact verification tests...")
    print("=" * 80)
    sys.stdout.flush()
    
    try:
        print("\nRunning test_verification_exact_match...")
        sys.stdout.flush()
        await test_verification_exact_match()
        print("Exact match test completed")
        sys.stdout.flush()
        
        print("\nRunning test_verification_paraphrase...")
        sys.stdout.flush()
        await test_verification_paraphrase()
        print("Paraphrase test completed")
        sys.stdout.flush()
        
        print("\nRunning test_verification_incorrect...")
        sys.stdout.flush()
        await test_verification_incorrect()
        print("Incorrect fact test completed")
        sys.stdout.flush()
        
        print("\nAll tests completed successfully!")
    except Exception as e:
        logger.error(f"Test failed: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main()) 
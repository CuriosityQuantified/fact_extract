"""
Test script for fact extraction workflow with storage.
Tests the complete pipeline using synthetic example articles.
"""

import os
from pathlib import Path
import logging
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Verify required API keys are present
required_keys = ['OPENAI_API_KEY']
missing_keys = [key for key in required_keys if not os.getenv(key)]
if missing_keys:
    raise ValueError(f"Missing required API keys: {', '.join(missing_keys)}")

from fact_extract.graph.nodes import create_workflow
from fact_extract.storage.chunk_repository import ChunkRepository
from fact_extract.storage.fact_repository import FactRepository
from fact_extract.utils.synthetic_data import (
    SYNTHETIC_ARTICLE_2,
    SYNTHETIC_ARTICLE_3,
    SYNTHETIC_ARTICLE_4
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def setup_storage():
    """Set up storage repositories with test files in current directory."""
    # Create test directory if it doesn't exist
    test_dir = Path("test_output")
    test_dir.mkdir(exist_ok=True)
    
    # Initialize repositories with test files
    chunk_repo = ChunkRepository(str(test_dir / "test_chunks.xlsx"))
    fact_repo = FactRepository(str(test_dir / "test_facts.xlsx"))
    
    return chunk_repo, fact_repo

def process_article(workflow_chain, article_text: str, document_name: str):
    """Process a single article through the workflow."""
    logger.info(f"\nProcessing article: {document_name}")
    
    # Prepare input
    input_dict = {
        "input_text": article_text,
        "document_name": document_name,
        "source_url": f"synthetic://{document_name}"
    }
    
    # Run workflow using invoke
    result = workflow_chain.invoke(input_dict)
    
    # Log results
    logger.info(f"Processed {len(result.get('chunks', []))} chunks")
    logger.info(f"Extracted {len(result.get('extracted_facts', []))} facts")
    if 'stats' in result:
        logger.info(f"Verification stats: {result['stats']}")
    if 'errors' in result and result['errors']:
        logger.warning(f"Encountered errors: {result['errors']}")
    
    return result

def main():
    """Run the test workflow on synthetic articles."""
    logger.info("Setting up test environment...")
    chunk_repo, fact_repo = setup_storage()
    
    # Create workflow
    workflow_chain, input_key = create_workflow(chunk_repo, fact_repo)
    
    # Test articles
    articles = [
        (SYNTHETIC_ARTICLE_2, "Sustainable_Data_Centers"),
        (SYNTHETIC_ARTICLE_3, "Edge_Computing_Future"),
        (SYNTHETIC_ARTICLE_4, "Quantum_Computing_Impact")
    ]
    
    # Process each article
    for article_text, document_name in articles:
        try:
            result = process_article(workflow_chain, article_text, document_name)
            
            # Get verification stats after processing
            stats = fact_repo.get_verification_stats(document_name)
            logger.info(f"\nFinal stats for {document_name}:")
            logger.info(f"Total facts: {stats['total_facts']}")
            logger.info(f"Pending verification: {stats['pending_facts']}")
            logger.info(f"Average confidence: {stats['average_confidence']:.2f}")
            
            # Get chunks with facts
            chunks_with_facts = chunk_repo.get_chunks(
                document_name=document_name,
                contains_facts=True
            )
            logger.info(f"Chunks containing facts: {len(chunks_with_facts)}")
            
        except Exception as e:
            logger.error(f"Error processing {document_name}: {str(e)}")
    
    # Print overall statistics
    total_stats = fact_repo.get_verification_stats()
    logger.info("\nOverall statistics:")
    logger.info(f"Total facts extracted: {total_stats['total_facts']}")
    logger.info(f"Average confidence across all facts: {total_stats['average_confidence']:.2f}")
    
    # List files in test output directory
    test_dir = Path("test_output")
    logger.info("\nGenerated files:")
    for file in test_dir.glob("*.xlsx"):
        logger.info(f"- {file.name} ({file.stat().st_size / 1024:.1f} KB)")

if __name__ == "__main__":
    main() 
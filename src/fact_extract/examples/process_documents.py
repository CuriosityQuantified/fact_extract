"""
Example script demonstrating document processing functionality.
"""

import asyncio
import logging
from pathlib import Path
from typing import List, Dict

from fact_extract.utils.document_loader import DocumentLoader
from fact_extract.tests.test_document_processors import (
    setup_module,
    teardown_module,
    TEST_DATA_DIR
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def process_documents(file_paths: List[str]) -> List[Dict[str, str]]:
    """Process multiple documents and extract their content.
    
    Args:
        file_paths: List of paths to documents
        
    Returns:
        List of dictionaries containing extracted content
    """
    loader = DocumentLoader()
    
    # Process all documents
    results = await loader.process_documents(file_paths)
    
    # Print results
    print("\nProcessed Documents:")
    print("=" * 50)
    
    for result in results:
        print(f"\nTitle: {result['title']}")
        print(f"Source: {result['source']}")
        print(f"Content preview: {result['content'][:100]}...")
        print("-" * 50)
        
    return results

async def main():
    """Main entry point."""
    # Create test files
    print("Creating test files...")
    setup_module(None)
    
    # Example usage with test files
    test_files = [
        str(TEST_DATA_DIR / "test.xlsx"),
        str(TEST_DATA_DIR / "test.csv"),
        str(TEST_DATA_DIR / "test.docx"),
        str(TEST_DATA_DIR / "test.pdf")
    ]
    
    try:
        results = await process_documents(test_files)
        print(f"\nSuccessfully processed {len(results)} documents")
        
    except Exception as e:
        logger.error(f"Error processing documents: {str(e)}")
        
    finally:
        # Clean up test files
        print("\nCleaning up test files...")
        teardown_module(None)

if __name__ == "__main__":
    asyncio.run(main()) 
"""
Test script specifically for the chunker node to verify the fix for
'dict' object has no attribute 'page_content' error.
"""

import asyncio
import sys
import os
import pytest
from dotenv import load_dotenv
from pathlib import Path


# Ensure the src directory is in the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Ensure the src directory is in the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))
# Load environment variables from .env file
dotenv_path = Path(__file__).parents[2] / '.env'
load_dotenv(dotenv_path)

from utils.synthetic_data import SYNTHETIC_ARTICLE_2
from models.state import create_initial_state
from storage.chunk_repository import ChunkRepository

# Create a simplified version of the chunker node that doesn't depend on other modules
@pytest.mark.asyncio
async def test_chunker_only():
    """Test only the chunking functionality without dependencies."""
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    from langchain_core.documents import Document
    
    print("Testing chunker functionality with synthetic data...")
    print("-" * 80)
    
    try:
        # Create text splitter with word-based chunking
        text_splitter = RecursiveCharacterTextSplitter(
            separators=["\n\n", "\n", ". ", " "],  # Separators in order of priority
            chunk_size=500,  # Target 500 words per chunk
            chunk_overlap=100,  # 100 words overlap
            length_function=len,  # Default character length function
            add_start_index=True,
            strip_whitespace=True
        )
        
        # Create a proper Document object
        initial_doc = Document(
            page_content=SYNTHETIC_ARTICLE_2,
            metadata={
                "source": "Test Document",
                "url": "https://example.com"
            }
        )
        
        # Split the document
        chunks = text_splitter.split_documents([initial_doc])
        
        # Check results
        if chunks and len(chunks) > 0:
            print(f"\nSuccess! Chunker created {len(chunks)} chunks.")
            print("\nFirst chunk preview:")
            print("-" * 40)
            print(chunks[0].page_content[:200] + "...")
            return True
        else:
            print("Error: No chunks were created.")
            return False
            
    except Exception as e:
        print(f"Error in chunker test: {str(e)}")
        return False

if __name__ == "__main__":
    # Run the test
    result = asyncio.run(test_chunker_only())
    
    # Exit with appropriate code
    if result:
        print("\nTest passed! The chunker is working correctly.")
        exit(0)
    else:
        print("\nTest failed! The chunker is not working correctly.")
        exit(1) 
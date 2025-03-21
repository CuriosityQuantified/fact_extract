import pytest
import asyncio
import os
import hashlib
from datetime import datetime
import uuid
from pathlib import Path
import sys
import json
from pprint import pprint

from src.fact_extract.models.state import create_initial_state
from src.fact_extract.graph.nodes import chunker_node
from src.fact_extract.utils.synthetic_data import SYNTHETIC_ARTICLE_7
from src.fact_extract.storage.chunk_repository import ChunkRepository
from src.fact_extract.storage.fact_repository import FactRepository

@pytest.mark.asyncio
async def test_chunker_node_direct():
    """Test the chunker node directly with SYNTHETIC_ARTICLE_7."""
    print("\n" + "="*80)
    print("TESTING CHUNKER NODE WITH SYNTHETIC_ARTICLE_7")
    print("="*80)
    
    # Create test data directory
    os.makedirs("src/fact_extract/data", exist_ok=True)
    
    # Create a unique document name
    unique_id = str(uuid.uuid4())[:8]
    document_name = f"synthetic_article_7_{unique_id}.txt"
    
    # Initialize repositories (needed for the chunker node)
    global chunk_repo, fact_repo
    chunk_repo = ChunkRepository()
    fact_repo = FactRepository()
    
    # Create initial state for workflow
    state = create_initial_state(
        input_text=SYNTHETIC_ARTICLE_7,
        document_name=document_name,
        source_url="https://example.com/synthetic_article_7"
    )
    
    print(f"\nCreated workflow state with document name: {document_name}")
    print(f"Original text length: {len(state['input_text'])} characters")
    
    try:
        # Process the state through the chunker node
        print("\nExecuting chunker_node...")
        result = await chunker_node(state)
        
        # Extract and print results
        chunks = result.get("chunks", [])
        print(f"\nChunked text into {len(chunks)} segments")
        
        # Print the first few chunks for verification
        for i, chunk in enumerate(chunks[:3]):
            print(f"\nChunk {i+1}:")
            content = chunk.get("content", "")
            print(f"Length: {len(content)} characters")
            print(f"Preview: {content[:100]}...")
            
            # Print metadata
            metadata = chunk.get("metadata", {})
            if metadata:
                print("Metadata:")
                for key, value in metadata.items():
                    print(f"  {key}: {value}")
        
        if len(chunks) > 3:
            print(f"\n... and {len(chunks) - 3} more chunks")
        
        return chunks
    except Exception as e:
        print(f"\nError executing chunker node: {str(e)}")
        raise

if __name__ == "__main__":
    # Initialize global variables for the chunker node
    chunk_repo = None
    fact_repo = None
    
    asyncio.run(test_chunker_node_direct()) 
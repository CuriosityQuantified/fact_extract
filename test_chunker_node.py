import asyncio
import os
import hashlib
from datetime import datetime
import uuid

from src.fact_extract.models.state import create_initial_state
from src.fact_extract.graph.nodes import chunker_node
from src.fact_extract.utils.synthetic_data import SYNTHETIC_ARTICLE_7
from src.fact_extract.storage.chunk_repository import ChunkRepository
from src.fact_extract.storage.fact_repository import FactRepository

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
    print(f"State keys: {list(state.keys())}")
    
    try:
        # Execute chunker node directly
        print("\nExecuting chunker node...")
        result = await chunker_node(state)
        
        # Check the results
        print("\nChunker node execution completed")
        print(f"Is complete: {result.get('is_complete', False)}")
        print(f"Errors: {result.get('errors', [])}")
        print(f"Chunks created: {len(result.get('chunks', []))}")
        
        # Print chunk details
        chunks = result.get("chunks", [])
        print(f"\nCreated {len(chunks)} chunks from SYNTHETIC_ARTICLE_7:")
        
        for idx, chunk in enumerate(chunks[:3]):  # Show first 3 chunks
            print(f"\n--- Chunk {idx+1} ---")
            print(f"Index: {chunk['index']}")
            print(f"Word count: {chunk['metadata']['word_count']}")
            print(f"First 100 chars: {chunk['content'][:100]}...")
        
        if len(chunks) > 3:
            print(f"\n... and {len(chunks) - 3} more chunks")
    
    except Exception as e:
        print(f"\nError executing chunker node: {str(e)}")
    
    print("\nTEST COMPLETE")
    print("="*80)

if __name__ == "__main__":
    # Initialize global variables for the chunker node
    chunk_repo = None
    fact_repo = None
    
    asyncio.run(test_chunker_node_direct()) 
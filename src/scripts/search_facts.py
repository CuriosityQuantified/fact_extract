#!/usr/bin/env python
"""
Command-line tool for searching facts using semantic search capabilities.
"""

import os
import sys
import argparse
import logging
from typing import Dict, Any, Optional, List

# Ensure the src directory is in the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Use local imports instead of src.*
from src.storage.fact_repository import FactRepository

# Configure logging
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def setup_fact_repository() -> FactRepository:
    """
    Set up and return a FactRepository instance.
    
    Returns:
        Initialized FactRepository
    """
    # Use default paths or get from environment variables
    excel_path = os.getenv("FACT_EXCEL_PATH", "src/data/all_facts.xlsx")
    vector_store_dir = os.getenv("FACT_VECTOR_STORE_DIR", "src/data/embeddings")
    collection_name = os.getenv("FACT_COLLECTION_NAME", "fact_embeddings")
    
    return FactRepository(
        excel_path=excel_path,
        vector_store_dir=vector_store_dir,
        collection_name=collection_name
    )

def search_facts(
    query: str, 
    n_results: int = 5, 
    filter_criteria: Optional[Dict[str, Any]] = None
) -> List[Dict[str, Any]]:
    """
    Search for facts semantically similar to the query.
    
    Args:
        query: The search query text
        n_results: Number of results to return
        filter_criteria: Optional filter for metadata fields
        
    Returns:
        List of fact dictionaries matching the query
    """
    repo = setup_fact_repository()
    logger.info(f"Searching for: '{query}' with limit {n_results}")
    return repo.search_facts(query=query, n_results=n_results, filter_criteria=filter_criteria)

def display_results(results: List[Dict[str, Any]]) -> None:
    """
    Display search results in a formatted way.
    
    Args:
        results: List of fact dictionaries
    """
    if not results:
        print("\n📚 No results found. Try a different search query or check if facts have been added to the repository.")
        return
    
    print(f"\n📚 Found {len(results)} relevant facts:\n")
    
    for i, fact in enumerate(results, 1):
        # Format the similarity score as a percentage
        similarity = f"{fact.get('similarity', 0) * 100:.1f}%"
        
        print(f"Result {i} (Relevance: {similarity}):")
        print(f"  📝 Statement: {fact.get('statement', '')}")
        print(f"  📄 Source: {fact.get('document_name', '')}, Chunk: {fact.get('chunk_index', 0)}")
        if fact.get('extracted_at'):
            print(f"  🕒 Extracted: {fact.get('extracted_at', '')}")
        print()

def parse_filter(filter_str: Optional[str]) -> Optional[Dict[str, Any]]:
    """
    Parse a filter string into a filter criteria dictionary.
    
    Args:
        filter_str: String in format "key1=value1,key2=value2"
        
    Returns:
        Dictionary of filter criteria or None
    """
    if not filter_str:
        return None
    
    filter_criteria = {}
    
    try:
        pairs = filter_str.split(",")
        for pair in pairs:
            key, value = pair.split("=")
            filter_criteria[key.strip()] = value.strip()
        
        logger.info(f"Using filter criteria: {filter_criteria}")
        return filter_criteria
    except Exception as e:
        logger.error(f"Error parsing filter string: {e}")
        print(f"Error parsing filter string '{filter_str}'. Format should be key1=value1,key2=value2")
        return None

def get_vector_store_stats() -> None:
    """
    Display statistics about the vector store.
    """
    repo = setup_fact_repository()
    stats = repo.get_vector_store_stats()
    
    print("\n📊 Vector Store Statistics:")
    print(f"  • Total facts: {stats.get('fact_count', 0)}")
    print(f"  • Collection name: {stats.get('collection_name', 'N/A')}")
    print(f"  • Storage directory: {stats.get('embeddings_directory', 'N/A')}")
    print()

def main():
    """Main function to handle CLI arguments and search for facts."""
    parser = argparse.ArgumentParser(
        description="Search for facts semantically using ChromaDB vector search.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python search_facts.py "climate change impact"
  python search_facts.py "renewable energy growth" --results 3
  python search_facts.py "market trends" --filter "document_name=market_report.pdf"
  python search_facts.py --stats
        """
    )
    
    # Create a mutually exclusive group for search query and stats
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("query", type=str, nargs="?", help="The search query")
    group.add_argument("--stats", action="store_true", help="Show vector store statistics")
    
    # Other parameters
    parser.add_argument("--results", "-n", type=int, default=5, help="Number of results to return")
    parser.add_argument("--filter", "-f", type=str, help="Filter criteria (format: key1=value1,key2=value2)")
    
    args = parser.parse_args()
    
    if args.stats:
        # Display vector store statistics
        get_vector_store_stats()
        return
    
    # Parse the filter criteria if provided
    filter_criteria = parse_filter(args.filter)
    
    # Search for facts
    results = search_facts(
        query=args.query,
        n_results=args.results,
        filter_criteria=filter_criteria
    )
    
    # Display the results
    display_results(results)

if __name__ == "__main__":
    main() 
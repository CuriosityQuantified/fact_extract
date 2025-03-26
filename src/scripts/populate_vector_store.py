#!/usr/bin/env python
"""
Utility script to populate the ChromaDB vector store with existing facts from Excel.
This helps migrate existing data to use the new semantic search capabilities.
"""

import os
import sys
import argparse
import logging
import pandas as pd
from typing import Dict, Any, List, Optional
from tqdm import tqdm

# Ensure the src directory is in the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Use local imports instead of src.*
from search.vector_store import ChromaFactStore
from src.storage.fact_repository import FactRepository

# Configure logging
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def generate_fact_id(fact: Dict[str, Any]) -> str:
    """
    Generate a unique ID for a fact, using the same format as FactRepository.
    
    Args:
        fact: Fact dictionary
        
    Returns:
        String ID for the fact
    """
    document_name = fact.get("document_name", "")
    chunk_index = fact.get("chunk_index", 0)
    
    # Simple hash function to keep ID short
    statement = fact.get("statement", "")
    statement_hash = hash(statement) % 10000
    
    return f"{document_name}_{chunk_index}_{statement_hash}"

def read_facts_from_excel(excel_path: str, verified_only: bool = True) -> List[Dict[str, Any]]:
    """
    Read facts from Excel file.
    
    Args:
        excel_path: Path to the Excel file
        verified_only: If True, only include verified facts
        
    Returns:
        List of fact dictionaries
    """
    if not os.path.exists(excel_path):
        logger.error(f"Excel file not found: {excel_path}")
        return []
    
    try:
        # Read the Excel file
        df = pd.read_excel(excel_path)
        logger.info(f"Read {len(df)} total facts from {excel_path}")
        
        # Filter by verification status if needed
        if verified_only:
            # Be strict about only including verified facts
            original_count = len(df)
            df = df[df["verification_status"] == "verified"]
            filtered_count = len(df)
            logger.info(f"Strictly filtered to {filtered_count} verified facts out of {original_count}")
        
        # Convert to list of dictionaries
        facts = df.to_dict(orient="records")
        
        # Filter out facts without statements
        valid_facts = []
        for fact in facts:
            statement = fact.get("statement")
            if statement and not pd.isna(statement):
                # For verified_only, double-check the status
                if verified_only and fact.get("verification_status") != "verified":
                    logger.warning(f"Skipping fact that doesn't have verified status: {statement[:50]}...")
                    continue
                valid_facts.append(fact)
        
        logger.info(f"Final count: {len(valid_facts)} valid facts from {excel_path}")
        return valid_facts
    except Exception as e:
        logger.error(f"Error reading Excel file: {e}")
        return []

def populate_vector_store(
    excel_path: str, 
    vector_store_dir: str,
    collection_name: str,
    batch_size: int = 100,
    verified_only: bool = True,
    reset: bool = False
) -> None:
    """
    Populate the vector store with facts from Excel.
    
    Args:
        excel_path: Path to the Excel file
        vector_store_dir: Directory for the vector store
        collection_name: Name of the collection to use
        batch_size: Number of facts to process in each batch
        verified_only: If True, only include verified facts
        reset: If True, reset the vector store before populating
    """
    # Ensure directories exist
    os.makedirs(vector_store_dir, exist_ok=True)
    
    # Read facts from Excel
    facts = read_facts_from_excel(excel_path, verified_only)
    
    if not facts:
        logger.error("No facts found to populate vector store")
        return
    
    # Initialize the vector store
    vector_store = ChromaFactStore(
        persist_directory=vector_store_dir,
        collection_name=collection_name
    )
    
    # Get the current fact count
    initial_count = vector_store.get_fact_count()
    logger.info(f"Initial fact count in vector store: {initial_count}")
    
    # Reset if requested
    if reset and initial_count > 0:
        # Since ChromaDB doesn't have a clear method, we need to create a new collection
        logger.info(f"Resetting vector store by creating a new collection")
        # This effectively deletes the old collection and creates a new one
        vector_store = ChromaFactStore(
            persist_directory=vector_store_dir,
            collection_name=f"{collection_name}_clean"  # Use a clean name to indicate it contains only verified facts
        )
        initial_count = 0
    
    # Process in batches
    fact_count = len(facts)
    batch_count = (fact_count + batch_size - 1) // batch_size  # Ceiling division
    
    logger.info(f"Processing {fact_count} facts in {batch_count} batches of size {batch_size}")
    
    # Double-check that we're only processing verified facts
    if verified_only:
        # Count how many facts are actually verified
        verified_count = sum(1 for fact in facts if fact.get("verification_status") == "verified")
        logger.info(f"{verified_count} out of {fact_count} facts are verified")
        
        # Filter again to be absolutely sure
        facts = [fact for fact in facts if fact.get("verification_status") == "verified"]
        fact_count = len(facts)
        logger.info(f"After filtering, {fact_count} verified facts remain for processing")
    
    # Process all facts with a progress bar
    with tqdm(total=fact_count, desc="Populating vector store") as pbar:
        for i in range(0, fact_count, batch_size):
            end_idx = min(i + batch_size, fact_count)
            current_batch = facts[i:end_idx]
            batch_size_actual = len(current_batch)
            
            # Prepare batch data
            fact_ids = []
            statements = []
            metadatas = []
            
            for fact in current_batch:
                # Skip non-verified facts (triple check)
                if verified_only and fact.get("verification_status") != "verified":
                    logger.warning(f"Skipping non-verified fact: {fact.get('statement', '')[:50]}...")
                    continue
                
                # Generate a unique ID
                fact_id = generate_fact_id(fact)
                
                # Get the statement
                statement = fact.get("statement", "")
                if pd.isna(statement) or not statement:
                    logger.warning(f"Skipping fact with empty statement")
                    continue  # Skip facts with NaN or empty statements
                
                # Create metadata with all important fields
                metadata = {
                    "document_name": fact.get("document_name", ""),
                    "chunk_index": fact.get("chunk_index", 0),
                    "source": fact.get("source_name", ""),
                    "extracted_at": str(fact.get("date_uploaded", "")),
                    "verification_status": "verified",  # Explicitly set to verified
                    "persistent_id": fact.get("persistent_id", ""),
                    "verification_reason": fact.get("verification_reason", "")
                }
                
                # Add to batch data
                fact_ids.append(fact_id)
                statements.append(statement)
                metadatas.append(metadata)
            
            # Only add if we have valid data
            if fact_ids:
                try:
                    # Add batch to vector store
                    vector_store.add_facts_batch(
                        fact_ids=fact_ids,
                        statements=statements,
                        metadatas=metadatas
                    )
                except Exception as e:
                    logger.error(f"Error adding batch to vector store: {e}")
            
            # Update progress bar
            pbar.update(batch_size_actual)
    
    # Get the final fact count
    final_count = vector_store.get_fact_count()
    logger.info(f"Final fact count in vector store: {final_count}")
    logger.info(f"Added {final_count - initial_count} facts to vector store")
    
    # If we created a new collection due to reset, provide information about it
    if reset and initial_count > 0:
        logger.info(f"Created a new clean collection named '{collection_name}_clean'")
        logger.info(f"You should update your FactRepository to use this new collection name")
        logger.info(f"Change: collection_name=\"fact_embeddings\" to collection_name=\"{collection_name}_clean\"")

def main():
    """Main function to handle CLI arguments and populate the vector store."""
    parser = argparse.ArgumentParser(
        description="Populate the ChromaDB vector store with existing facts from Excel.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python populate_vector_store.py
  python populate_vector_store.py --excel data/my_facts.xlsx --batch-size 50
  python populate_vector_store.py --reset --verified-only
        """
    )
    
    # Parameters
    parser.add_argument("--excel", type=str, default="src/data/all_facts.xlsx", 
                      help="Path to the Excel file with facts")
    parser.add_argument("--vector-dir", type=str, default="src/data/embeddings",
                      help="Directory for the vector store files")
    parser.add_argument("--collection", type=str, default="fact_embeddings",
                      help="Name of the collection to use")
    parser.add_argument("--batch-size", type=int, default=100,
                      help="Number of facts to process in each batch")
    parser.add_argument("--verified-only", action="store_true", default=True,
                      help="Only include verified facts (default: True)")
    parser.add_argument("--all-facts", action="store_true",
                      help="Include all facts regardless of verification status")
    parser.add_argument("--reset", action="store_true",
                      help="Reset the vector store before populating")
    
    args = parser.parse_args()
    
    # If --all-facts is specified, override verified-only
    if args.all_facts:
        args.verified_only = False
        logger.info("Including all facts regardless of verification status (--all-facts specified)")
    else:
        logger.info("Including only verified facts (default behavior)")
    
    # Populate the vector store
    populate_vector_store(
        excel_path=args.excel,
        vector_store_dir=args.vector_dir,
        collection_name=args.collection,
        batch_size=args.batch_size,
        verified_only=args.verified_only,
        reset=args.reset
    )

if __name__ == "__main__":
    main() 
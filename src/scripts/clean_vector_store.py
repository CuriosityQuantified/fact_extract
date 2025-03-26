#!/usr/bin/env python
"""
Script to clean the vector store by removing all non-verified facts and
creating a fresh collection with only verified facts.
"""

import os
import sys
import argparse
import logging
from typing import Dict, Any, List
import pandas as pd

# Ensure the src directory is in the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Use local imports
from search.vector_store import ChromaFactStore
from src.storage.fact_repository import FactRepository

# Configure logging
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def create_clean_vector_store(
    excel_path: str = "src/data/all_facts.xlsx",
    vector_store_dir: str = "src/data/embeddings",
    old_collection_name: str = "fact_embeddings",
    new_collection_name: str = "fact_embeddings_clean"
) -> None:
    """
    Create a new clean vector store containing only verified facts.
    
    Args:
        excel_path: Path to the Excel file with facts
        vector_store_dir: Directory for the vector store
        old_collection_name: Name of the old collection
        new_collection_name: Name of the new clean collection
    """
    # Ensure directories exist
    os.makedirs(vector_store_dir, exist_ok=True)
    
    # Read facts from Excel and filter for verified facts
    try:
        # Read the Excel file
        df = pd.read_excel(excel_path)
        total_facts = len(df)
        
        # Filter for verified facts
        verified_df = df[df["verification_status"] == "verified"]
        verified_facts = verified_df.to_dict(orient="records")
        
        logger.info(f"Found {len(verified_facts)} verified facts out of {total_facts} total facts")
    except Exception as e:
        logger.error(f"Error reading Excel file: {e}")
        return
    
    # Initialize vector stores
    try:
        old_store = ChromaFactStore(
            persist_directory=vector_store_dir,
            collection_name=old_collection_name
        )
        
        new_store = ChromaFactStore(
            persist_directory=vector_store_dir,
            collection_name=new_collection_name
        )
        
        old_count = old_store.get_fact_count()
        new_count = new_store.get_fact_count()
        
        logger.info(f"Old vector store has {old_count} facts")
        logger.info(f"New vector store has {new_count} facts (before cleaning)")
    except Exception as e:
        logger.error(f"Error initializing vector stores: {e}")
        return
    
    # Clear the new collection if it exists
    if new_count > 0:
        logger.info(f"Clearing existing facts from new collection")
        try:
            # Re-create the collection to clear it
            new_store = ChromaFactStore(
                persist_directory=vector_store_dir,
                collection_name=f"{new_collection_name}_temp"
            )
            
            # Rename back to original name
            new_store = ChromaFactStore(
                persist_directory=vector_store_dir,
                collection_name=new_collection_name
            )
            
            logger.info(f"New collection cleared and recreated")
        except Exception as e:
            logger.error(f"Error clearing new collection: {e}")
            return
    
    # Add all verified facts to the new collection
    logger.info(f"Adding {len(verified_facts)} verified facts to new collection")
    
    # Create the fact repository to use its ID generation
    fact_repo = FactRepository()
    
    # Process all verified facts
    batch_size = 100
    for i in range(0, len(verified_facts), batch_size):
        batch = verified_facts[i:min(i+batch_size, len(verified_facts))]
        
        # Prepare batch data
        fact_ids = []
        statements = []
        metadatas = []
        
        for fact in batch:
            # Generate fact ID using repository's method
            fact_id = fact_repo._generate_fact_id(fact)
            
            # Get the statement
            statement = fact.get("statement", "")
            if pd.isna(statement) or not statement:
                continue
            
            # Create metadata
            metadata = {
                "document_name": fact.get("document_name", ""),
                "chunk_index": fact.get("chunk_index", 0),
                "source": fact.get("source_name", ""),
                "extracted_at": str(fact.get("date_uploaded", "")),
                "verification_status": "verified",  # Explicitly set to verified
                "persistent_id": fact.get("persistent_id", ""),
                "verification_reason": fact.get("verification_reason", "")
            }
            
            # Add to batch
            fact_ids.append(fact_id)
            statements.append(statement)
            metadatas.append(metadata)
        
        # Add batch to new collection
        if fact_ids:
            try:
                new_store.add_facts_batch(
                    fact_ids=fact_ids,
                    statements=statements,
                    metadatas=metadatas
                )
                logger.info(f"Added batch of {len(fact_ids)} facts to new collection")
            except Exception as e:
                logger.error(f"Error adding batch to new collection: {e}")
    
    # Verify counts
    new_count = new_store.get_fact_count()
    logger.info(f"New vector store now has {new_count} facts")
    
    # Provide instructions for using the new collection
    logger.info("=== INSTRUCTIONS ===")
    logger.info(f"To use the new clean collection, update your FactRepository initialization:")
    logger.info(f"  collection_name=\"{new_collection_name}\"")

def main():
    """Main function to handle CLI arguments and clean the vector store."""
    parser = argparse.ArgumentParser(
        description="Clean the vector store by creating a new collection with only verified facts.",
    )
    
    # Parameters
    parser.add_argument("--excel", type=str, default="src/data/all_facts.xlsx", 
                      help="Path to the Excel file with facts")
    parser.add_argument("--vector-dir", type=str, default="src/data/embeddings",
                      help="Directory for the vector store files")
    parser.add_argument("--old-collection", type=str, default="fact_embeddings",
                      help="Name of the old collection")
    parser.add_argument("--new-collection", type=str, default="fact_embeddings_clean",
                      help="Name of the new clean collection")
    
    args = parser.parse_args()
    
    # Create clean vector store
    create_clean_vector_store(
        excel_path=args.excel,
        vector_store_dir=args.vector_dir,
        old_collection_name=args.old_collection,
        new_collection_name=args.new_collection
    )

if __name__ == "__main__":
    main() 
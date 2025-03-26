"""
Vector store implementation using ChromaDB for semantic fact search.
"""

import os
import chromadb
from chromadb.utils import embedding_functions
import logging
from typing import List, Dict, Any, Optional

# Set up logging
logger = logging.getLogger(__name__)

class ChromaFactStore:
    """Class for managing fact embeddings and semantic search using ChromaDB."""
    
    def __init__(self, persist_directory: str = "src/data/embeddings", 
                 collection_name: str = "fact_embeddings",
                 embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"):
        """
        Initialize the ChromaDB client and collection.
        
        Args:
            persist_directory: Directory to store ChromaDB files
            collection_name: Name of the collection to use
            embedding_model: Name of the sentence-transformer model to use for embeddings
        """
        # Create the directory if it doesn't exist
        os.makedirs(persist_directory, exist_ok=True)
        
        # Initialize the ChromaDB client with the persistent directory
        self.client = chromadb.PersistentClient(path=persist_directory)
        logger.info(f"Initialized ChromaDB client with persist directory: {persist_directory}")
        
        # Set up the embedding function (using sentence-transformers by default)
        self.embedding_function = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=embedding_model
        )
        
        # Get or create the collection with cosine similarity metric
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            embedding_function=self.embedding_function,
            metadata={"hnsw:space": "cosine"}  # Use cosine similarity
        )
        logger.info(f"Using collection: {collection_name} with cosine similarity")
    
    def add_fact(self, fact_id: str, statement: str, metadata: Dict[str, Any]) -> None:
        """
        Add a fact to the vector store.
        
        Args:
            fact_id: Unique identifier for the fact
            statement: The factual statement text
            metadata: Additional metadata for the fact
        """
        try:
            # Add the fact to the collection
            self.collection.add(
                ids=[fact_id],
                documents=[statement],
                metadatas=[metadata]
            )
            logger.info(f"Added fact with ID: {fact_id} to vector store")
        except Exception as e:
            logger.error(f"Error adding fact to vector store: {e}")
            raise
    
    def add_facts_batch(self, fact_ids: List[str], statements: List[str], 
                        metadatas: List[Dict[str, Any]]) -> None:
        """
        Add multiple facts to the vector store in a batch.
        
        Args:
            fact_ids: List of unique identifiers for the facts
            statements: List of factual statement texts
            metadatas: List of metadata dictionaries for each fact
        """
        if len(fact_ids) != len(statements) or len(statements) != len(metadatas):
            raise ValueError("Mismatch in lengths of fact_ids, statements, and metadatas")
        
        try:
            # Add the facts to the collection in batch
            self.collection.add(
                ids=fact_ids,
                documents=statements,
                metadatas=metadatas
            )
            logger.info(f"Added {len(fact_ids)} facts to vector store in batch")
        except Exception as e:
            logger.error(f"Error adding facts batch to vector store: {e}")
            raise
    
    def search_facts(self, query: str, n_results: int = 5, 
                     filter_criteria: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Search for facts semantically similar to the query.
        
        Args:
            query: The search query text
            n_results: Number of results to return
            filter_criteria: Optional filter for metadata fields
            
        Returns:
            Dictionary containing search results (ids, distances, metadatas, documents)
        """
        try:
            # Query the collection
            results = self.collection.query(
                query_texts=[query],
                n_results=n_results,
                where=filter_criteria  # Apply any filters if provided
            )
            logger.info(f"Searched for: '{query}' and found {len(results['ids'][0])} results")
            return results
        except Exception as e:
            logger.error(f"Error searching vector store: {e}")
            raise
    
    def delete_fact(self, fact_id: str) -> None:
        """
        Delete a fact from the vector store.
        
        Args:
            fact_id: Unique identifier for the fact to delete
        """
        try:
            self.collection.delete(ids=[fact_id])
            logger.info(f"Deleted fact with ID: {fact_id} from vector store")
        except Exception as e:
            logger.error(f"Error deleting fact from vector store: {e}")
            raise
    
    def get_fact_count(self) -> int:
        """
        Get the number of facts in the vector store.
        
        Returns:
            Count of facts in the collection
        """
        return self.collection.count() 
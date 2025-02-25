"""
Repository for storing and managing text chunks.
"""

from typing import Dict, Any, Optional
from datetime import datetime

class ChunkRepository:
    """In-memory repository for storing and managing text chunks."""
    
    def __init__(self):
        self.chunks: Dict[str, Dict[int, Dict[str, Any]]] = {}
        
    def store_chunk(self, chunk_data: Dict[str, Any]) -> None:
        """
        Store a chunk with its metadata.
        
        Args:
            chunk_data: Dictionary containing chunk information
        """
        document_name = chunk_data["document_name"]
        chunk_index = chunk_data["chunk_index"]
        
        if document_name not in self.chunks:
            self.chunks[document_name] = {}
            
        self.chunks[document_name][chunk_index] = {
            **chunk_data,
            "last_updated": datetime.now().isoformat()
        }
    
    def update_chunk_status(
        self,
        document_name: str,
        chunk_index: int,
        status: str,
        contains_facts: Optional[bool] = None,
        error_message: Optional[str] = None
    ) -> None:
        """
        Update the status of a chunk.
        
        Args:
            document_name: Name of the document
            chunk_index: Index of the chunk
            status: New status
            contains_facts: Whether the chunk contains facts
            error_message: Error message if any
        """
        if document_name in self.chunks and chunk_index in self.chunks[document_name]:
            chunk = self.chunks[document_name][chunk_index]
            chunk["status"] = status
            if contains_facts is not None:
                chunk["contains_facts"] = contains_facts
            if error_message is not None:
                chunk["error_message"] = error_message
            chunk["last_updated"] = datetime.now().isoformat()
    
    def is_chunk_processed(self, chunk_data: Dict[str, Any], document_name: str) -> bool:
        """
        Check if a chunk has already been processed.
        
        Args:
            chunk_data: Dictionary containing chunk information
            document_name: Name of the document
            
        Returns:
            bool: True if chunk has been processed successfully
        """
        chunk_index = chunk_data["index"]
        if document_name in self.chunks and chunk_index in self.chunks[document_name]:
            chunk = self.chunks[document_name][chunk_index]
            return (
                chunk["status"] == "processed" and
                chunk["error_message"] is None
            )
        return False
    
    def get_chunk(self, document_name: str, chunk_index: int) -> Optional[Dict[str, Any]]:
        """
        Get a chunk by document name and index.
        
        Args:
            document_name: Name of the document
            chunk_index: Index of the chunk
            
        Returns:
            Optional[Dict]: Chunk data if found
        """
        if document_name in self.chunks and chunk_index in self.chunks[document_name]:
            return self.chunks[document_name][chunk_index]
        return None
    
    def clear_document(self, document_name: str) -> None:
        """
        Clear all chunks for a document.
        
        Args:
            document_name: Name of the document
        """
        if document_name in self.chunks:
            del self.chunks[document_name] 
"""
Repository for storing and managing text chunks.
"""

from typing import Dict, Any, Optional, List
from datetime import datetime
import os
import pandas as pd
import logging
import asyncio
import threading

# Global lock for thread safety
_chunk_repo_lock = threading.RLock()

class ChunkRepository:
    """Repository for storing and managing text chunks with Excel persistence."""
    
    def __init__(self, excel_path: str = "src/data/all_chunks.xlsx"):
        """Initialize the chunk repository with the path to the Excel file."""
        logging.debug("Initializing ChunkRepository with path: %s", excel_path)
        self.chunks: Dict[str, Dict[int, Dict[str, Any]]] = {}
        self.excel_path = excel_path
        self.lock = _chunk_repo_lock  # Use global lock to ensure all instances share the same lock
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(excel_path), exist_ok=True)
        
        # Try to load from Excel
        self._load_from_excel()
        
    def _load_from_excel(self) -> None:
        """Load chunks from Excel file if it exists."""
        with self.lock:
            if os.path.exists(self.excel_path):
                try:
                    df = pd.read_excel(self.excel_path)
                    
                    # Convert DataFrame to dictionary structure
                    for _, row in df.iterrows():
                        document_name = row["document_name"]
                        chunk_index = row["chunk_index"]
                        
                        if document_name not in self.chunks:
                            self.chunks[document_name] = {}
                        
                        # Convert row to dictionary
                        chunk_data = row.to_dict()
                        
                        # Handle metadata columns
                        metadata = {}
                        for col in df.columns:
                            if col.startswith("metadata_"):
                                metadata_key = col[len("metadata_"):]
                                metadata[metadata_key] = chunk_data.pop(col, None)
                        
                        chunk_data["metadata"] = metadata
                        self.chunks[document_name][chunk_index] = chunk_data
                        
                except Exception as e:
                    print(f"Error loading chunks from Excel: {e}")
    
    def _save_to_excel(self) -> None:
        """Save all chunks to Excel file."""
        with self.lock:
            try:
                # Flatten the nested dictionary structure
                rows = []
                for document_name, chunks in self.chunks.items():
                    for chunk_index, chunk_data in chunks.items():
                        # Create a copy of the chunk data
                        row_data = chunk_data.copy()
                        
                        # Extract metadata and flatten it with prefix
                        if "metadata" in row_data and isinstance(row_data["metadata"], dict):
                            metadata = row_data.pop("metadata", {})
                            for key, value in metadata.items():
                                row_data[f"metadata_{key}"] = value
                        
                        rows.append(row_data)
                
                # Create DataFrame and save to Excel
                if rows:
                    df = pd.DataFrame(rows)
                    df.to_excel(self.excel_path, index=False)
            except Exception as e:
                print(f"Error saving chunks to Excel: {e}")
        
    def store_chunk(self, chunk_data: Dict[str, Any]) -> None:
        """
        Store a chunk with its metadata.
        
        Args:
            chunk_data: Dictionary containing chunk information
        """
        with self.lock:
            document_name = chunk_data["document_name"]
            chunk_index = chunk_data["chunk_index"]
            
            # Add all_facts_extracted field if not present
            if "all_facts_extracted" not in chunk_data:
                chunk_data["all_facts_extracted"] = False
            
            if document_name not in self.chunks:
                self.chunks[document_name] = {}
                
            self.chunks[document_name][chunk_index] = {
                **chunk_data,
                "last_updated": datetime.now().isoformat()
            }
            
            # Save to Excel after each update
            self._save_to_excel()
    
    async def async_store_chunk(self, chunk_data: Dict[str, Any]) -> None:
        """
        Store a chunk with its metadata (async version).
        
        Args:
            chunk_data: Dictionary containing chunk information
        """
        # Create a separate thread for IO operation
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, lambda: self.store_chunk(chunk_data))
    
    def update_chunk_status(
        self,
        document_name: str,
        chunk_index: int,
        status: str,
        contains_facts: Optional[bool] = None,
        error_message: Optional[str] = None,
        all_facts_extracted: Optional[bool] = None
    ) -> None:
        """
        Update the status of a chunk.
        
        Args:
            document_name: Name of the document
            chunk_index: Index of the chunk
            status: New status
            contains_facts: Whether the chunk contains facts
            error_message: Error message if any
            all_facts_extracted: Whether all facts have been extracted from the chunk
        """
        with self.lock:
            if document_name in self.chunks and chunk_index in self.chunks[document_name]:
                chunk = self.chunks[document_name][chunk_index]
                chunk["status"] = status
                if contains_facts is not None:
                    chunk["contains_facts"] = contains_facts
                if error_message is not None:
                    chunk["error_message"] = error_message
                if all_facts_extracted is not None:
                    chunk["all_facts_extracted"] = all_facts_extracted
                chunk["last_updated"] = datetime.now().isoformat()
                
                # Save to Excel after each update
                self._save_to_excel()
    
    async def async_update_chunk_status(
        self,
        document_name: str,
        chunk_index: int,
        status: str,
        contains_facts: Optional[bool] = None,
        error_message: Optional[str] = None,
        all_facts_extracted: Optional[bool] = None
    ) -> None:
        """
        Update the status of a chunk (async version).
        
        Args:
            document_name: Name of the document
            chunk_index: Index of the chunk
            status: New status
            contains_facts: Whether the chunk contains facts
            error_message: Error message if any
            all_facts_extracted: Whether all facts have been extracted from the chunk
        """
        # Create a separate thread for IO operation
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            lambda: self.update_chunk_status(
                document_name, 
                chunk_index, 
                status, 
                contains_facts, 
                error_message, 
                all_facts_extracted
            )
        )
    
    def is_chunk_processed(self, chunk_data: Dict[str, Any], document_name: str) -> bool:
        """
        Check if a chunk has already been processed and all facts extracted.
        
        Args:
            chunk_data: Dictionary containing chunk information
            document_name: Name of the document
            
        Returns:
            bool: True if chunk has been processed successfully and all facts extracted
        """
        with self.lock:
            chunk_index = chunk_data["index"]
            if document_name in self.chunks and chunk_index in self.chunks[document_name]:
                chunk = self.chunks[document_name][chunk_index]
                return (
                    chunk["status"] == "processed" and
                    chunk["error_message"] is None and
                    chunk.get("all_facts_extracted", False) == True
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
        with self.lock:
            if document_name in self.chunks and chunk_index in self.chunks[document_name]:
                return self.chunks[document_name][chunk_index].copy()  # Return a copy to prevent race conditions
            return None
    
    def get_all_chunks(self) -> List[Dict[str, Any]]:
        """
        Get all chunks as a flat list.
        
        Returns:
            List[Dict]: All chunks
        """
        with self.lock:
            all_chunks = []
            for document_name, chunks in self.chunks.items():
                for chunk_index, chunk_data in chunks.items():
                    all_chunks.append(chunk_data.copy())  # Return copies to prevent race conditions
            return all_chunks
    
    def clear_document(self, document_name: str) -> None:
        """
        Clear all chunks for a document.
        
        Args:
            document_name: Name of the document
        """
        with self.lock:
            if document_name in self.chunks:
                del self.chunks[document_name]
                
                # Save to Excel after each update
                self._save_to_excel()
            
    def get_chunks_for_document(self, document_name: str) -> List[Dict[str, Any]]:
        """
        Get all chunks for a specific document.
        
        Args:
            document_name: Name of the document
            
        Returns:
            List[Dict]: All chunks for the document
        """
        with self.lock:
            if document_name in self.chunks:
                return [chunk_data.copy() for chunk_index, chunk_data in self.chunks[document_name].items()]
            return [] 
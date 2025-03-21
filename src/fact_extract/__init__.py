"""
Fact extraction package.

This package provides tools and utilities for extracting facts from text documents.
"""

__version__ = "0.1.0"
__author__ = "Your Name"
__email__ = "your.email@example.com"

from .graph.nodes import process_document as _process_document
from typing import Dict, Any, List, Set

class ProcessingState:
    """
    State for document processing.
    """
    def __init__(self, document_name: str = "", text: str = ""):
        self.document_name = document_name
        self.text = text
        self.chunks = []
        self.facts = []
        self.current_chunk_index = 0
        self.processed_files: Set[str] = set()
        self.errors: Dict[str, List[str]] = {}
    
    def add_error(self, file_path: str, error_msg: str):
        """Add an error message for a file."""
        if file_path not in self.errors:
            self.errors[file_path] = []
        self.errors[file_path].append(error_msg)
    
    def start_processing(self, file_path: str):
        """Mark a file as being processed."""
        self.document_name = file_path
        
    def complete_file(self, file_path: str):
        """Mark a file as completely processed."""
        self.processed_files.add(file_path)
        
    def add_fact(self, file_path: str, fact: Dict[str, Any]):
        """Add a fact extracted from a file."""
        self.facts.append(fact)

async def process_document(file_path: str, document_hash: str = None) -> Dict[str, Any]:
    """
    Process a document for fact extraction.
    
    Args:
        file_path: Path to the document file
        document_hash: Optional hash of the document content
        
    Returns:
        Dict: Processing results
    """
    # Create a state object
    state = ProcessingState(document_name=file_path)
    
    # Call the actual process_document function
    return await _process_document(file_path, state)

__all__ = ["__version__", "__author__", "__email__", "process_document"] 
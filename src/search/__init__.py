"""
Search module for semantic fact search functionality.

This module provides vector-based semantic search capabilities for facts
using ChromaDB and sentence-transformers.
"""

from .vector_store import ChromaFactStore

__all__ = ["ChromaFactStore"] 
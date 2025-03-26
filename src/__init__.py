"""
Fact extraction package.

This package provides tools and utilities for extracting facts from text documents.
"""

__version__ = "0.1.0"
__author__ = "Your Name"
__email__ = "your.email@example.com"

from src.models.state import ProcessingState
from src.graph.nodes import process_document

__all__ = ["__version__", "__author__", "__email__", "ProcessingState", "process_document"] 
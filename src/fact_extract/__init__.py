"""
Fact Extract - A simple fact extraction system using LLMs.
"""

from .models.state import Fact, TextChunk, WorkflowState
from .__main__ import extract_facts

__version__ = "0.1.0"
__all__ = ["Fact", "TextChunk", "WorkflowState", "extract_facts"] 
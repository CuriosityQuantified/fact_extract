"""
Models for semantic fact search functionality.
"""

from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field
from datetime import datetime

class SearchableFact(BaseModel):
    """Model representing a fact that can be searched semantically."""
    id: str  # Unique identifier for the fact
    statement: str  # The factual statement
    document_name: str  # Source document name
    chunk_index: int  # Chunk index within document
    metadata: Dict[str, Any] = Field(default_factory=dict)  # Additional metadata
    embedding: Optional[List[float]] = None  # Vector embedding of the fact
    extracted_at: datetime = Field(default_factory=datetime.now)  # When the fact was extracted
    
    class Config:
        arbitrary_types_allowed = True 
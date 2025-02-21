"""
State models for the fact extraction workflow.
These models define the data structures that flow through our LangGraph nodes.
"""

from typing import List, Optional, Dict
from pydantic import BaseModel, Field


class TextChunk(BaseModel):
    """A chunk of text to be processed for fact extraction."""
    content: str = Field(description="The text content of the chunk")
    index: int = Field(description="The position of this chunk in the original text")
    metadata: Dict = Field(default_factory=dict, description="Additional metadata about the chunk")


class Fact(BaseModel):
    """A single extracted fact."""
    statement: str = Field(description="The factual statement")
    confidence: float = Field(description="Confidence score of the extraction")
    source_chunk: int = Field(description="Index of the chunk this fact was extracted from")
    metadata: Dict = Field(default_factory=dict, description="Additional metadata about the fact")


class WorkflowState(BaseModel):
    """The state that flows through our LangGraph workflow."""
    # Input state
    input_text: str = Field(default="", description="The original input text")
    chunks: List[TextChunk] = Field(default_factory=list, description="Text chunks to process")
    
    # Processing state
    current_chunk_index: int = Field(default=0, description="Index of chunk being processed")
    extracted_facts: List[Fact] = Field(default_factory=list, description="Facts extracted so far")
    
    # Error handling
    errors: List[str] = Field(default_factory=list, description="Any errors encountered")
    
    # Completion state
    is_complete: bool = Field(default=False, description="Whether processing is complete")

    def add_fact(self, fact: Fact) -> None:
        """Add a new fact to the state."""
        self.extracted_facts.append(fact)
    
    def add_error(self, error: str) -> None:
        """Add an error message to the state."""
        self.errors.append(error)
    
    def next_chunk(self) -> Optional[TextChunk]:
        """Get the next chunk to process, if any."""
        if self.current_chunk_index < len(self.chunks):
            chunk = self.chunks[self.current_chunk_index]
            self.current_chunk_index += 1
            return chunk
        return None 
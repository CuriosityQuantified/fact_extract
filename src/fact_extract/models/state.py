"""
State models for the fact extraction workflow using LangGraph v0.2.28+ patterns.
These models define the data structures that flow through our LangGraph nodes.
"""

from typing import List, Optional, Dict, TypedDict
from typing_extensions import NotRequired
from datetime import datetime
from uuid import UUID


class TextChunkDict(TypedDict):
    """A chunk of text to be processed for fact extraction."""
    content: str  # The text content of the chunk
    index: int  # The position of this chunk in the original text
    metadata: NotRequired[Dict]  # Additional metadata about the chunk


class FactDict(TypedDict):
    """A single extracted fact."""
    statement: str  # The factual statement
    confidence: float  # Confidence score of the extraction
    source_chunk: int  # Index of the chunk this fact was extracted from
    metadata: NotRequired[Dict]  # Additional metadata about the fact
    timestamp: str  # When the fact was extracted
    verification_status: str  # Status of fact verification
    verification_reason: NotRequired[str]  # Reason for verification decision


class WorkflowStateDict(TypedDict):
    """The state that flows through our LangGraph workflow."""
    # Session identification
    session_id: UUID  # Unique identifier for this extraction session
    
    # Input state
    input_text: str  # The original input text
    document_name: str  # Name/title of source document
    source_url: str  # URL or identifier of source
    chunks: List[TextChunkDict]  # Text chunks to process
    
    # Processing state
    current_chunk_index: int  # Index of chunk being processed
    extracted_facts: List[FactDict]  # Facts extracted so far
    
    # Memory state
    memory: NotRequired[Dict]  # Persistent memory across runs
    last_processed_time: NotRequired[str]  # Timestamp of last processing
    
    # Error handling
    errors: List[str]  # Any errors encountered
    
    # Completion state
    is_complete: bool  # Whether processing is complete


class MemoryDict(TypedDict):
    """Persistent memory for the workflow."""
    # Document-level memory
    document_stats: Dict  # Statistics about processed documents
    fact_patterns: List[str]  # Common fact patterns seen
    entity_mentions: Dict[str, int]  # Entity frequency tracking
    
    # Session memory
    recent_facts: List[FactDict]  # Recently extracted facts
    error_counts: Dict[str, int]  # Error type frequencies
    performance_metrics: Dict  # Processing performance data


def create_initial_state(
    input_text: str,
    document_name: str,
    source_url: str = "",
    session_id: Optional[UUID] = None
) -> WorkflowStateDict:
    """Create initial workflow state.
    
    Args:
        input_text: The text to process
        document_name: Name/title of source document
        source_url: URL or identifier of source
        session_id: Optional session ID (generated if not provided)
        
    Returns:
        Initial workflow state dictionary
    """
    from uuid import uuid4
    
    return {
        "session_id": session_id or uuid4(),
        "input_text": input_text,
        "document_name": document_name,
        "source_url": source_url,
        "chunks": [],
        "current_chunk_index": 0,
        "extracted_facts": [],
        "errors": [],
        "is_complete": False,
        "memory": {
            "document_stats": {},
            "fact_patterns": [],
            "entity_mentions": {},
            "recent_facts": [],
            "error_counts": {},
            "performance_metrics": {
                "start_time": datetime.now().isoformat(),
                "chunks_processed": 0,
                "facts_extracted": 0,
                "errors_encountered": 0
            }
        },
        "last_processed_time": datetime.now().isoformat()
    } 
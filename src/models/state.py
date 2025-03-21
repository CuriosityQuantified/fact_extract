"""
State models for the fact extraction workflow using LangGraph v0.2.28+ patterns.
These models define the data structures that flow through our LangGraph nodes.
"""

from typing import List, Optional, Dict, TypedDict, Any
from typing_extensions import NotRequired
from datetime import datetime
from uuid import UUID
from dataclasses import dataclass, field


class TextChunkDict(TypedDict):
    """A chunk of text to be processed for fact extraction."""
    content: str  # The text content of the chunk
    index: int  # The position of this chunk in the original text
    metadata: NotRequired[Dict]  # Additional metadata about the chunk


class FactDict(TypedDict):
    """A single extracted fact."""
    statement: str  # The factual statement
    source_chunk: int  # Index of the chunk this fact was extracted from
    document_name: str  # Name of the source document
    source_url: str  # URL or identifier of source
    original_text: str  # The original text from which the fact was extracted
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
    
    # Initialize memory with default values
    memory: MemoryDict = {
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
    }
    
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
        "memory": memory,
        "last_processed_time": datetime.now().isoformat()
    }


@dataclass
class ProcessingState:
    """
    Maintains state for document processing.
    
    Attributes:
        processed_files: Set of files that have been processed
        current_file: Currently processing file
        facts: Dictionary of extracted facts by file
        start_time: Processing start time
        errors: List of processing errors
    """
    processed_files: set = field(default_factory=set)
    current_file: Optional[str] = None
    facts: Dict[str, List[Dict[str, Any]]] = field(default_factory=dict)
    start_time: Optional[datetime] = None
    errors: List[Dict[str, Any]] = field(default_factory=list)
    
    def start_processing(self, file_path: str) -> None:
        """
        Start processing a file.
        
        Args:
            file_path: Path to the file being processed
        """
        if not self.start_time:
            self.start_time = datetime.now()
        self.current_file = file_path
    
    def add_fact(self, file_path: str, fact: Dict[str, Any]) -> None:
        """
        Add an extracted fact.
        
        Args:
            file_path: Source file path
            fact: Extracted fact
        """
        if file_path not in self.facts:
            self.facts[file_path] = []
        self.facts[file_path].append(fact)
    
    def add_error(self, file_path: str, error: str) -> None:
        """
        Record a processing error.
        
        Args:
            file_path: File that caused the error
            error: Error message
        """
        self.errors.append({
            "file": file_path,
            "error": error,
            "timestamp": datetime.now()
        })
    
    def complete_file(self, file_path: str) -> None:
        """
        Mark a file as completely processed.
        
        Args:
            file_path: Path to the completed file
        """
        self.processed_files.add(file_path)
        if self.current_file == file_path:
            self.current_file = None
    
    def get_progress(self) -> Dict[str, Any]:
        """
        Get current processing progress.
        
        Returns:
            Dict with progress information
        """
        return {
            "processed_files": len(self.processed_files),
            "current_file": self.current_file,
            "total_facts": sum(len(facts) for facts in self.facts.values()),
            "error_count": len(self.errors),
            "duration": (
                (datetime.now() - self.start_time).total_seconds()
                if self.start_time else 0
            )
        }
    
    def reset(self) -> None:
        """Reset all state."""
        self.processed_files.clear()
        self.current_file = None
        self.facts.clear()
        self.start_time = None
        self.errors.clear() 
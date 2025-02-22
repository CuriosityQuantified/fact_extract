"""
Repository for managing processed text chunks in Excel format.
Tracks all chunks, including those with no facts, to prevent duplicate processing.
"""

import pandas as pd
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional, List, Union
import logging
from fact_extract.models.state import TextChunkDict

logger = logging.getLogger(__name__)

class ChunkRepository:
    """Manages storage and retrieval of processed text chunks."""
    
    def __init__(self, file_path: str = "processed_chunks.xlsx"):
        """Initialize the chunk repository.
        
        Args:
            file_path: Path to the Excel file for storing chunks
        """
        self.file_path = Path(file_path)
        self.columns = [
            "timestamp",           # When the chunk was processed
            "document_name",       # Name/title of source document
            "source_url",         # URL or identifier of source
            "chunk_content",      # The actual text content
            "chunk_index",        # Index in original document
            "status",            # Processing status (success/failed/pending)
            "contains_facts",     # Whether any facts were extracted
            "error_message",      # Any error during processing
            "processing_time",    # Time taken to process
            "metadata"           # Additional chunk metadata (as JSON)
        ]
        self._initialize_storage()
    
    def _initialize_storage(self) -> None:
        """Create the Excel file if it doesn't exist."""
        try:
            if not self.file_path.exists():
                pd.DataFrame(columns=self.columns).to_excel(
                    self.file_path, 
                    index=False,
                    engine='openpyxl'
                )
                logger.info(f"Created new chunk repository at {self.file_path}")
        except Exception as e:
            logger.error(f"Failed to initialize chunk storage: {str(e)}")
            raise

    def is_chunk_processed(self, chunk: Union[TextChunkDict, Dict], document_name: str) -> bool:
        """Check if a chunk has already been processed.
        
        Args:
            chunk: TextChunkDict object or dict with chunk data
            document_name: Name of the source document
            
        Returns:
            bool: True if chunk exists and was processed successfully
        """
        try:
            df = pd.read_excel(self.file_path, engine='openpyxl')
            if df.empty:
                return False
            
            # Get chunk content and index
            content = chunk.get("content", chunk.get("chunk_content"))
            chunk_index = chunk.get("index", chunk.get("chunk_index"))
            
            # Check for existing chunk with same content and index
            matching_chunks = df[
                (df['chunk_content'] == content) & 
                (df['document_name'] == document_name) &
                (df['chunk_index'] == chunk_index) &
                (df['status'] == 'success')
            ]
            
            return not matching_chunks.empty
            
        except Exception as e:
            logger.error(f"Failed to check chunk status: {str(e)}")
            return False
    
    def store_chunk(self, chunk_data: Dict) -> bool:
        """Store a processed chunk with metadata.
        
        Args:
            chunk_data: Dictionary containing chunk data matching column schema
            
        Returns:
            bool: True if stored successfully
        """
        try:
            # Read existing chunks
            df = pd.read_excel(self.file_path, engine='openpyxl')
            
            # Add timestamp if not provided
            if 'timestamp' not in chunk_data:
                chunk_data['timestamp'] = datetime.now().isoformat()
            
            # Validate required columns
            missing_cols = set(self.columns) - set(chunk_data.keys())
            if missing_cols:
                logger.error(f"Missing required columns: {missing_cols}")
                return False
            
            # Check for existing chunk with same content and index
            existing_chunk = df[
                (df['chunk_content'] == chunk_data['chunk_content']) & 
                (df['document_name'] == chunk_data['document_name']) &
                (df['chunk_index'] == chunk_data['chunk_index'])
            ]
            
            if not existing_chunk.empty:
                # Update existing chunk if status is not 'success'
                if existing_chunk['status'].iloc[0] != 'success':
                    df.loc[existing_chunk.index[0]] = chunk_data
                    logger.info(f"Updated existing chunk {chunk_data['chunk_index']} from {chunk_data['document_name']}")
                else:
                    logger.info(f"Chunk {chunk_data['chunk_index']} from {chunk_data['document_name']} already exists with success status")
                    return True
            else:
                # Store new chunk
                new_row = pd.DataFrame([chunk_data], columns=self.columns)
                df = pd.concat([df, new_row], ignore_index=True)
                logger.info(f"Added new chunk {chunk_data['chunk_index']} from {chunk_data['document_name']}")
            
            df.to_excel(self.file_path, index=False, engine='openpyxl')
            return True
            
        except Exception as e:
            logger.error(f"Failed to store chunk: {str(e)}")
            return False
    
    def get_chunks(
        self, 
        document_name: Optional[str] = None,
        status: Optional[str] = None,
        contains_facts: Optional[bool] = None
    ) -> List[Dict]:
        """Retrieve chunks matching the specified criteria.
        
        Args:
            document_name: Filter by source document name
            status: Filter by processing status
            contains_facts: Filter by whether facts were extracted
            
        Returns:
            List of chunk dictionaries matching criteria
        """
        try:
            df = pd.read_excel(self.file_path, engine='openpyxl')
            
            # Apply filters
            if document_name:
                df = df[df['document_name'] == document_name]
            if status:
                df = df[df['status'] == status]
            if contains_facts is not None:
                df = df[df['contains_facts'] == contains_facts]
            
            # Remove duplicates, keeping the latest version of each chunk
            df = df.sort_values('timestamp', ascending=False)
            df = df.drop_duplicates(subset=['document_name', 'chunk_index'], keep='first')
                
            return df.to_dict('records')
            
        except Exception as e:
            logger.error(f"Failed to retrieve chunks: {str(e)}")
            return []
    
    def update_chunk_status(
        self,
        document_name: str,
        chunk_index: int,
        status: str,
        error_message: Optional[str] = None,
        contains_facts: Optional[bool] = None
    ) -> bool:
        """Update the status of a processed chunk.
        
        Args:
            document_name: Name of the source document
            chunk_index: Index of the chunk in the document
            status: New processing status
            error_message: Optional error message if status is 'failed'
            contains_facts: Whether any facts were extracted
            
        Returns:
            bool: True if update was successful
        """
        try:
            df = pd.read_excel(self.file_path, engine='openpyxl')
            
            # Find the chunk
            mask = (df['document_name'] == document_name) & (df['chunk_index'] == chunk_index)
            if mask.any():
                # Update status
                df.loc[mask, 'status'] = status
                if error_message is not None:
                    df.loc[mask, 'error_message'] = error_message
                if contains_facts is not None:
                    df.loc[mask, 'contains_facts'] = contains_facts
                
                df.to_excel(self.file_path, index=False, engine='openpyxl')
                logger.info(f"Updated status for chunk {chunk_index} in {document_name} to {status}")
                return True
            else:
                logger.warning(f"Chunk {chunk_index} from {document_name} not found")
                return False
                
        except Exception as e:
            logger.error(f"Failed to update chunk status: {str(e)}")
            return False 
"""
Fact repository for storing and managing extracted facts in Excel format.
Includes enhanced metadata tracking and verification status management.
"""

import pandas as pd
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional, List, Union
import json
import logging
from fact_extract.models.state import FactDict

logger = logging.getLogger(__name__)

class FactRepository:
    """Manages storage and retrieval of facts in Excel format with enhanced metadata."""
    
    def __init__(self, file_path: str = "facts.xlsx"):
        """Initialize the fact repository.
        
        Args:
            file_path: Path to the Excel file for storing facts
        """
        self.file_path = Path(file_path)
        self.columns = [
            "timestamp",          # When the fact was stored
            "document_name",      # Name/title of source document
            "source_url",         # URL or identifier of source
            "original_text",      # Text chunk containing the fact
            "fact_text",         # The extracted fact statement
            "confidence",        # Confidence score from extraction
            "verification_status", # Verification status (pending/approved/rejected)
            "verification_reason", # Reason for verification decision
            "verification_time",  # When the fact was verified
            "chunk_index",       # Index of chunk in original document
            "extraction_model",   # Model used for extraction
            "extraction_time",    # Time taken for extraction
            "metadata"           # Additional fact metadata (as JSON)
        ]
        self._initialize_storage()
    
    def _initialize_storage(self) -> None:
        """Create the Excel file if it doesn't exist."""
        try:
            if not self.file_path.exists():
                # Create DataFrame with correct dtypes
                df = pd.DataFrame(columns=self.columns)
                df = df.astype({
                    'timestamp': str,
                    'document_name': str,
                    'source_url': str,
                    'original_text': str,
                    'fact_text': str,
                    'confidence': float,
                    'verification_status': str,
                    'verification_reason': str,
                    'verification_time': str,
                    'chunk_index': int,
                    'extraction_model': str,
                    'extraction_time': float,
                    'metadata': str
                })
                df.to_excel(
                    self.file_path, 
                    index=False,
                    engine='openpyxl'
                )
                logger.info(f"Created new fact repository at {self.file_path}")
        except Exception as e:
            logger.error(f"Failed to initialize storage: {str(e)}")
            raise
    
    def store_fact(self, fact_data: Dict) -> bool:
        """Store a fact with metadata.
        
        Args:
            fact_data: Dictionary containing fact data matching column schema
            
        Returns:
            bool: True if stored successfully, False if duplicate or error
        """
        try:
            # Read existing facts and ensure correct dtypes
            df = pd.read_excel(self.file_path, engine='openpyxl')
            df = df.astype({
                'timestamp': str,
                'document_name': str,
                'source_url': str,
                'original_text': str,
                'fact_text': str,
                'confidence': float,
                'verification_status': str,
                'verification_reason': str,
                'verification_time': str,
                'chunk_index': int,
                'extraction_model': str,
                'extraction_time': float,
                'metadata': str
            })
            
            # Check for duplicates (same fact from same document)
            if not df[
                (df['fact_text'] == fact_data['statement']) & 
                (df['document_name'] == fact_data['document_name'])
            ].empty:
                logger.warning("Duplicate fact detected, skipping storage")
                return False
            
            # Add timestamp and default verification status if not provided
            if 'timestamp' not in fact_data:
                fact_data['timestamp'] = datetime.now().isoformat()
            if 'verification_status' not in fact_data:
                fact_data['verification_status'] = 'pending'
            
            # Convert metadata to JSON if present
            metadata = fact_data.get('metadata', {})
            if metadata and not isinstance(metadata, str):
                metadata = json.dumps(metadata)
            
            # Map fact data to repository schema
            repo_fact = {
                "timestamp": fact_data["timestamp"],
                "document_name": fact_data["document_name"],
                "source_url": fact_data.get("source_url", ""),
                "original_text": fact_data.get("original_text", ""),
                "fact_text": fact_data["statement"],
                "confidence": float(fact_data["confidence"]),
                "verification_status": str(fact_data["verification_status"]),
                "verification_reason": str(fact_data.get("verification_reason", "")),
                "verification_time": str(fact_data.get("verification_time", "")),
                "chunk_index": int(fact_data["source_chunk"]),
                "extraction_model": "llama-3.3-70b-versatile",
                "extraction_time": float(fact_data.get("metadata", {}).get("extraction_time", 0.0)),
                "metadata": metadata
            }
            
            # Store the fact
            new_row = pd.DataFrame([repo_fact], columns=self.columns)
            if df.empty:
                df = new_row
            else:
                df = pd.concat([df, new_row], ignore_index=True)
            df.to_excel(self.file_path, index=False, engine='openpyxl')
            logger.info(f"Successfully stored fact from {fact_data.get('document_name', 'Unknown')}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to store fact: {str(e)}")
            return False
    
    def get_facts(
        self, 
        document_name: Optional[str] = None,
        min_confidence: float = 0.0,
        verification_status: Optional[str] = None,
        chunk_index: Optional[int] = None,
        extraction_model: Optional[str] = None
    ) -> List[Dict]:
        """Retrieve facts matching the specified criteria.
        
        Args:
            document_name: Filter by source document name
            min_confidence: Minimum confidence score
            verification_status: Filter by verification status
            chunk_index: Filter by source chunk index
            extraction_model: Filter by extraction model used
            
        Returns:
            List of fact dictionaries matching criteria
        """
        try:
            df = pd.read_excel(self.file_path, engine='openpyxl')
            
            # Apply filters
            if document_name:
                df = df[df['document_name'] == document_name]
            if min_confidence > 0:
                df = df[df['confidence'] >= min_confidence]
            if verification_status:
                df = df[df['verification_status'].fillna('pending') == verification_status]
            if chunk_index is not None:
                df = df[df['chunk_index'] == chunk_index]
            if extraction_model:
                df = df[df['extraction_model'] == extraction_model]
                
            # Parse metadata JSON if present
            if not df.empty and 'metadata' in df.columns:
                df['metadata'] = df['metadata'].apply(
                    lambda x: json.loads(x) if isinstance(x, str) else x
                )
                
            # Convert to FactDict format
            facts = []
            for _, row in df.iterrows():
                facts.append({
                    "statement": row["fact_text"],
                    "confidence": row["confidence"],
                    "source_chunk": row["chunk_index"],
                    "document_name": row["document_name"],
                    "source_url": row["source_url"],
                    "metadata": row["metadata"],
                    "timestamp": row["timestamp"],
                    "verification_status": row["verification_status"],
                    "verification_reason": row["verification_reason"]
                })
            
            return facts
            
        except Exception as e:
            logger.error(f"Failed to retrieve facts: {str(e)}")
            return []
    
    def update_verification_status(
        self,
        document_name: str,
        fact_text: str,
        status: str,
        reason: Optional[str] = None
    ) -> bool:
        """Update the verification status of a fact.
        
        Args:
            document_name: Name of the source document
            fact_text: The fact statement to update
            status: New verification status
            reason: Optional reason for the status update
            
        Returns:
            bool: True if update was successful
        """
        try:
            # Read existing facts and ensure correct dtypes
            df = pd.read_excel(self.file_path, engine='openpyxl')
            df = df.astype({
                'timestamp': str,
                'document_name': str,
                'source_url': str,
                'original_text': str,
                'fact_text': str,
                'confidence': float,
                'verification_status': str,
                'verification_reason': str,
                'verification_time': str,
                'chunk_index': int,
                'extraction_model': str,
                'extraction_time': float,
                'metadata': str
            })
            
            # Find the fact
            mask = (df['document_name'] == document_name) & (df['fact_text'] == fact_text)
            if mask.any():
                # Update status
                df.loc[mask, 'verification_status'] = status
                df.loc[mask, 'verification_time'] = datetime.now().isoformat()
                if reason:
                    df.loc[mask, 'verification_reason'] = reason
                
                df.to_excel(self.file_path, index=False, engine='openpyxl')
                logger.info(f"Updated verification status for fact in {document_name} to {status}")
                return True
            else:
                logger.warning(f"Fact not found in {document_name}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to update verification status: {str(e)}")
            return False
    
    def get_verification_stats(self, document_name: Optional[str] = None) -> Dict:
        """Get statistics about fact verification.
        
        Args:
            document_name: Optional document to filter stats for
            
        Returns:
            Dict containing verification statistics
        """
        try:
            df = pd.read_excel(self.file_path, engine='openpyxl')
            
            if document_name:
                df = df[df['document_name'] == document_name]
            
            stats = {
                'total_facts': len(df),
                'verified_facts': len(df[df['verification_status'] == 'approved']),
                'rejected_facts': len(df[df['verification_status'] == 'rejected']),
                'pending_facts': len(df[df['verification_status'] == 'pending']),
                'average_confidence': df['confidence'].mean() if not df.empty else 0.0
            }
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get verification stats: {str(e)}")
            return {
                'total_facts': 0,
                'verified_facts': 0,
                'rejected_facts': 0,
                'pending_facts': 0,
                'average_confidence': 0.0
            } 
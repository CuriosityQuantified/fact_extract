"""
Document loader utility for processing various document types.
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional, Union
from concurrent.futures import ThreadPoolExecutor, as_completed

from src.fact_extract.utils.document_processors import DocumentProcessorFactory

logger = logging.getLogger(__name__)

class DocumentLoader:
    """Utility for loading and processing documents."""
    
    def __init__(self):
        """Initialize document loader."""
        self.processor_factory = DocumentProcessorFactory()
        
    def process_document(self, file_path: Union[str, Path]) -> List[Dict[str, str]]:
        """Process a single document.
        
        Args:
            file_path: Path to the document
            
        Returns:
            List of dictionaries containing:
                - title: Document or section title
                - content: Text content
                - source: Original file path
        """
        file_path = Path(file_path)
        
        if not file_path.exists():
            logger.error(f"File not found: {file_path}")
            return []
            
        processor = self.processor_factory.get_processor(file_path)
        if not processor:
            logger.error(f"Unsupported file type: {file_path}")
            return []
            
        try:
            return processor.extract_content(file_path)
        except Exception as e:
            logger.error(f"Error processing document {file_path}: {str(e)}")
            return []
            
    async def process_documents(
        self,
        file_paths: List[Union[str, Path]],
        max_workers: int = 4
    ) -> List[Dict[str, str]]:
        """Process multiple documents in parallel.
        
        Args:
            file_paths: List of paths to documents
            max_workers: Maximum number of parallel workers
            
        Returns:
            List of dictionaries containing extracted content
        """
        results = []
        
        # Convert all paths to Path objects
        paths = [Path(p) for p in file_paths]
        
        # Process files in parallel using ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all tasks
            future_to_path = {
                executor.submit(self.process_document, path): path
                for path in paths
            }
            
            # Process results as they complete
            for future in as_completed(future_to_path):
                path = future_to_path[future]
                try:
                    result = future.result()
                    if result:
                        results.extend(result)
                except Exception as e:
                    logger.error(f"Error processing {path}: {str(e)}")
                    
        return results 
"""
Tool for submitting verified facts to the repository.
"""

import logging
import os
from typing import Dict, Optional, Type
from datetime import datetime
from pathlib import Path
from pydantic import BaseModel, Field
from langchain_core.tools import BaseTool
from langchain_openai import ChatOpenAI

# Explicitly load environment variables from .env file
from dotenv import load_dotenv
# Find the project root by going up 3 levels from this file
project_root = Path(__file__).parents[3]
env_path = project_root / '.env'
load_dotenv(dotenv_path=env_path)

# Ensure API key is available
api_key = os.environ.get('OPENAI_API_KEY')
if not api_key:
    print("Warning: OPENAI_API_KEY not found in environment variables.")

from ..storage.fact_repository import FactRepository
from ..agents.verification import FactVerificationAgent

logger = logging.getLogger(__name__)

# Initialize shared instances
_repository = FactRepository()
_llm = ChatOpenAI(
    model="gpt-3.5-turbo",
    temperature=0,  # Keep temperature at 0 for consistent outputs
    api_key=api_key  # Explicitly pass the API key
)
_verifier = FactVerificationAgent(llm=_llm)

class FactSubmissionInput(BaseModel):
    """Input for fact submission."""
    fact_text: str = Field(..., description="The fact statement to submit")
    document_name: str = Field(..., description="Name of the source document")
    source_url: str = Field(..., description="URL or identifier of the source")
    original_text: str = Field(..., description="Original text the fact was extracted from")
    chunk_index: int = Field(..., description="Index of the source chunk")

class FactSubmissionTool:
    """Tool for submitting facts for verification and storage."""
    
    def __init__(self, repository=None, verifier=None):
        """Initialize the submission tool.
        
        Args:
            repository: Repository for storing facts (default: global instance)
            verifier: Agent for verifying facts (default: global instance)
        """
        self._repository = repository
        self._verifier = verifier
    
    @property
    def repository(self):
        """Lazy-load the repository only when needed."""
        if self._repository is None:
            self._repository = _repository
        return self._repository
    
    @property
    def verifier(self):
        """Lazy-load the verifier only when needed."""
        if self._verifier is None:
            self._verifier = _verifier
        return self._verifier
        
    def _run(self, fact_text: str, document_name: str, source_url: str, original_text: str, chunk_index: int) -> Dict:
        """Run the fact submission workflow.
        
        Args:
            fact_text: The fact statement to submit
            document_name: Name of the source document
            source_url: URL or identifier of the source
            original_text: Original text the fact was extracted from
            chunk_index: Index of the source chunk
            
        Returns:
            Dict containing submission result
        """
        try:
            # Verify the fact
            verification = self.verifier.verify_fact(fact_text, original_text)
            
            # If verification failed due to error, store as unverified
            if not verification.is_valid and "failed" in verification.reason.lower():
                return {
                    "success": False,
                    "error": verification.reason,
                    "fact_data": {
                        "statement": fact_text,
                        "document_name": document_name,
                        "source_url": source_url,
                        "original_text": original_text,
                        "source_chunk": chunk_index,
                        "verification_status": "failed",
                        "verification_reason": verification.reason,
                        "metadata": {"submission_time": datetime.now().isoformat()}
                    }
                }
            
            # Store the fact with verification result
            fact_data = {
                "statement": fact_text,
                "document_name": document_name,
                "source_url": source_url,
                "original_text": original_text,
                "source_chunk": chunk_index,
                "verification_status": "verified" if verification.is_valid else "rejected",
                "verification_reason": verification.reason,
                "metadata": {"submission_time": datetime.now().isoformat()}
            }
            
            success = self.repository.store_fact(fact_data)
            
            return {
                "success": success,
                "error": None if success else "Failed to store fact",
                "fact_data": fact_data
            }
            
        except Exception as e:
            error_msg = f"Fact submission failed: {str(e)}"
            logger.error(error_msg)
            return {
                "success": False,
                "error": error_msg,
                "fact_data": None
            }

# Initialize the tool with default instances
submit_fact = FactSubmissionTool() 
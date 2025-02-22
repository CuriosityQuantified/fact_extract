"""
Tool for submitting verified facts to the repository.
"""

import logging
from typing import Dict, Optional, Type
from datetime import datetime
from pydantic import BaseModel, Field
from langchain_core.tools import BaseTool

from ..storage.fact_repository import FactRepository
from ..agents.verification import FactVerificationAgent

logger = logging.getLogger(__name__)

# Initialize shared instances
_repository = FactRepository()
_verifier = FactVerificationAgent()

class SubmitFactInput(BaseModel):
    fact_text: str = Field(..., description="The actual fact statement to be verified and stored")
    document_name: str = Field(..., description="Name or title of the source document")
    source_url: str = Field(..., description="URL or identifier of the source")
    original_text: str = Field(..., description="The complete context from which the fact was extracted")
    confidence: float = Field(..., description="Initial confidence score from the extraction process")
    chunk_index: int = Field(..., description="Index of the text chunk from which the fact was extracted")

class SubmitFactTool(BaseTool):
    name: str = "submit_fact"
    description: str = """Submit a fact for verification and storage in the knowledge base.
    
    This tool performs two main functions:
    1. Verifies the fact using an LLM-based verification agent
    2. Stores approved facts in a structured repository
    
    The verification process checks for:
    - Objectivity: Must be a purely factual statement without opinions
    - Verifiability: Must be independently verifiable
    - Specificity: Must contain concrete, specific information
    - Context Consistency: Must align with the provided context
    - Significance: Must be meaningful and non-trivial
    
    The storage process:
    - Checks for duplicates to prevent redundancy
    - Maintains metadata and provenance information
    - Tracks verification status and reasoning
    - Preserves original context
    """
    args_schema: Type[BaseModel] = SubmitFactInput
    
    def _run(self, fact_text: str, document_name: str, source_url: str, original_text: str, confidence: float, chunk_index: int) -> Dict:
        try:
            # Verify the fact
            verification = _verifier.verify_fact(
                fact_text=fact_text,
                original_text=original_text
            )
            
            if not verification.is_valid:
                return {
                    "status": "rejected",
                    "reason": verification.reason,
                    "confidence": verification.confidence
                }
            
            # Prepare fact data for storage
            fact_data = {
                "timestamp": datetime.now().isoformat(),
                "document_name": document_name,
                "source_url": source_url,
                "original_text": original_text,
                "fact_text": fact_text,
                "confidence": min(confidence, verification.confidence),  # Use lower confidence
                "review_status": "approved",
                "review_reason": verification.reason,
                "chunk_index": chunk_index
            }
            
            # Store the fact
            if _repository.store_fact(fact_data):
                return {
                    "status": "approved",
                    "reason": verification.reason,
                    "confidence": verification.confidence
                }
            else:
                return {
                    "status": "storage_failed",
                    "reason": "Failed to store fact (possibly duplicate)",
                    "confidence": verification.confidence
                }
                
        except Exception as e:
            error_msg = f"Fact submission failed: {str(e)}"
            logger.error(error_msg)
            return {
                "status": "error",
                "reason": error_msg,
                "confidence": 0.0
            }

submit_fact = SubmitFactTool() 
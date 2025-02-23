"""
Fact verification agent that validates extracted facts using LLM.
"""

import logging
import sys
import os
import json
import re
from typing import Dict, Union
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.output_parsers.json import parse_json_markdown

from .prompts import FACT_VERIFICATION_PROMPT

logger = logging.getLogger(__name__)

class VerificationResult(BaseModel):
    """Result of fact verification."""
    is_valid: bool = Field(description="Whether the fact is valid")
    reason: str = Field(description="Reason for the verification decision")
    verification_status: str = Field(description="Status string (verified/rejected/failed)")

def _parse_verification_output(output: str) -> Dict:
    """Parse the verification output from the LLM."""
    try:
        # Try to parse as JSON first
        parsed = json.loads(output)
        if all(k in parsed for k in ["is_valid", "reason"]):
            return {
                "is_valid": parsed["is_valid"],
                "reason": parsed["reason"],
                "verification_status": "verified" if parsed["is_valid"] else "rejected"
            }
    except:
        pass
        
    # Fallback to simple parsing
    is_valid = "valid" in output.lower() and "not valid" not in output.lower()
    reason = output.strip()
    
    return {
        "is_valid": is_valid,
        "reason": reason,
        "verification_status": "verified" if is_valid else "rejected"
    }

class FactVerificationAgent:
    """Agent for verifying extracted facts against source text."""
    
    def __init__(self, llm: ChatOpenAI):
        """Initialize the verification agent.
        
        Args:
            llm: Language model to use for verification
        """
        self.llm = llm
        
    async def verify_fact(
        self, 
        fact: str,
        source_text: str,
        document_name: str,
        source_url: str = ""
    ) -> VerificationResult:
        """Verify a fact against its source text.
        
        Args:
            fact: The fact to verify
            source_text: Original text to verify against
            document_name: Name of source document
            source_url: URL of source document
            
        Returns:
            VerificationResult with decision and explanation
        """
        try:
            # Prepare prompt
            prompt = FACT_VERIFICATION_PROMPT.format(
                fact=fact,
                source_text=source_text,
                document_name=document_name,
                source_url=source_url
            )
            
            # Get verification from LLM
            output = await self.llm.agenerate(prompt)
            parsed_output = _parse_verification_output(output)
            
            # Create result
            result = VerificationResult(
                is_valid=bool(parsed_output["is_valid"]),
                reason=str(parsed_output["reason"]),
                verification_status=parsed_output["verification_status"]
            )
            
            # Log result
            logger.info(
                "Verification result for fact: %s\n"
                "Status: %s\n"
                "Reason: %s",
                fact[:100] + "..." if len(fact) > 100 else fact,
                result.verification_status,
                result.reason
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Verification failed: {str(e)}")
            return VerificationResult(
                is_valid=False,
                reason=f"Verification failed: {str(e)}",
                verification_status="failed"
            ) 
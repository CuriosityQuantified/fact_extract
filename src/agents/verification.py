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

from src.agents.prompts import FACT_VERIFICATION_PROMPT

logger = logging.getLogger(__name__)

class VerificationResult(BaseModel):
    """Result of fact verification."""
    is_valid: bool = Field(description="Whether the fact is valid")
    reason: str = Field(description="Reason for the verification decision")
    verification_status: str = Field(description="Status string (verified/rejected/failed)")

def _parse_verification_output(output: str) -> Dict:
    """Parse the verification output from the LLM."""
    try:
        # Try to parse as XML first
        is_valid_match = re.search(r'<is_valid>(.*?)</is_valid>', output, re.DOTALL)
        reasoning_match = re.search(r'<reasoning>(.*?)</reasoning>', output, re.DOTALL)
        
        if is_valid_match and reasoning_match:
            is_valid_str = is_valid_match.group(1).strip().lower()
            is_valid = is_valid_str == "true" or is_valid_str == "yes"
            reason = reasoning_match.group(1).strip()
            
            return {
                "is_valid": is_valid,
                "reason": reason,
                "verification_status": "verified" if is_valid else "rejected"
            }
    except Exception as e:
        logger.warning(f"XML parsing failed: {str(e)}")
        
    try:
        # Try to parse as JSON
        # Find JSON block if wrapped in ``` or other markers
        json_pattern = r'```(?:json)?\s*([\s\S]*?)\s*```'
        json_match = re.search(json_pattern, output)
        
        if json_match:
            json_str = json_match.group(1)
            parsed = json.loads(json_str)
        else:
            # Try to parse the entire response as JSON
            parsed = json.loads(output)
            
        if all(k in parsed for k in ["is_valid", "reason"]):
            return {
                "is_valid": parsed["is_valid"],
                "reason": parsed["reason"],
                "verification_status": "verified" if parsed["is_valid"] else "rejected"
            }
    except Exception as e:
        logger.warning(f"JSON parsing failed: {str(e)}")
        
    # Fallback to simple parsing for free-form responses
    is_valid = False
    
    # Check for positive verification keywords
    positive_indicators = ["valid", "correct", "accurate", "supported", "verified", "true"]
    negative_indicators = ["not valid", "invalid", "incorrect", "inaccurate", "unsupported", "false", "not supported"]
    
    # Check for negative indicators first (they're more specific)
    if any(neg in output.lower() for neg in negative_indicators):
        is_valid = False
    # Then check for positive indicators
    elif any(pos in output.lower() for pos in positive_indicators):
        is_valid = True
        
    # Extract a reason if possible
    if "reason:" in output.lower():
        reason_match = re.search(r'(?:reason|reasoning):\s*(.*?)(?:\n|$)', output, re.IGNORECASE)
        reason = reason_match.group(1).strip() if reason_match else output.strip()
    else:
        reason = output.strip()
    
    logger.info(f"Used fallback parsing, determined is_valid={is_valid}")
    
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
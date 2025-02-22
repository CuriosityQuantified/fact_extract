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
from langchain_groq import ChatGroq
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.output_parsers.json import parse_json_markdown

from .prompts import FACT_VERIFICATION_PROMPT

logger = logging.getLogger(__name__)

class FactVerificationResult(BaseModel):
    """Result of fact verification."""
    is_valid: bool = Field(description="Whether the fact is valid")
    reason: str = Field(description="Reason for the verification decision")
    confidence: float = Field(description="Confidence in the verification decision", ge=0.0, le=1.0)

def clean_and_parse_llm_output(output: str) -> Dict[str, Union[bool, str, float]]:
    """Clean and parse LLM output to extract JSON response.
    
    This function handles various edge cases in LLM output formatting:
    1. Extracts JSON from markdown code blocks
    2. Handles cases where JSON is embedded in regular text
    3. Cleans up common formatting issues
    4. Provides fallback parsing for malformed JSON
    
    Args:
        output: Raw output string from LLM
        
    Returns:
        Dict containing parsed response with required fields
        
    Raises:
        ValueError: If output cannot be parsed into valid format after cleanup
    """
    try:
        # First try direct JSON parsing
        return json.loads(output)
    except json.JSONDecodeError:
        logger.debug("Direct JSON parsing failed, attempting cleanup...")
        
    try:
        # Try parsing as markdown
        cleaned = parse_json_markdown(output)
        if isinstance(cleaned, dict):
            return cleaned
    except Exception as e:
        logger.debug(f"Markdown parsing failed: {str(e)}")
    
    # Extract JSON-like structure using regex
    json_pattern = r"\{[^}]+\}"
    matches = re.findall(json_pattern, output)
    
    if matches:
        # Try each matched pattern
        for match in matches:
            try:
                # Clean up common formatting issues
                cleaned = match.replace("'", '"')  # Replace single quotes
                cleaned = re.sub(r'(\w+):', r'"\1":', cleaned)  # Quote unquoted keys
                cleaned = re.sub(r':\s*(true|false)', r': \1', cleaned)  # Fix boolean values
                cleaned = re.sub(r':\s*([0-9.]+)', r': \1', cleaned)  # Fix numeric values
                
                result = json.loads(cleaned)
                
                # Validate required fields
                if all(k in result for k in ["is_valid", "reason", "confidence"]):
                    return result
            except json.JSONDecodeError:
                continue
    
    # If all parsing attempts fail, construct a conservative default response
    logger.warning("Failed to parse LLM output, using conservative default")
    return {
        "is_valid": False,
        "reason": f"Failed to parse LLM response. Original output: {output[:100]}...",
        "confidence": 0.0
    }

class FactVerificationAgent:
    """Agent for verifying extracted facts using LLM."""
    
    def __init__(self, model_name: str = "llama-3.3-70b-versatile"):
        """Initialize the verification agent.
        
        Args:
            model_name: Name of the LLM model to use
        """
        # Check for Groq API key
        print("Checking for Groq API key...")
        sys.stdout.flush()
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            error_msg = "Groq API key not found. Please set GROQ_API_KEY environment variable."
            print(f"ERROR: {error_msg}")
            sys.stdout.flush()
            raise ValueError(error_msg)
        print("Groq API key found")
        sys.stdout.flush()
        
        print(f"Initializing ChatGroq with model {model_name}...")
        sys.stdout.flush()
        self.llm = ChatGroq(model=model_name, temperature=0)
        print("ChatGroq initialized")
        sys.stdout.flush()
        
        print("Setting up verification chain...")
        sys.stdout.flush()
        # Create the verification chain - we'll handle parsing separately
        self.chain = FACT_VERIFICATION_PROMPT | self.llm
        print("Verification chain ready")
        sys.stdout.flush()
        
    def verify_fact(
        self, 
        fact_text: str, 
        original_text: str
    ) -> FactVerificationResult:
        """Verify a fact using the LLM.
        
        Args:
            fact_text: The fact statement to verify
            original_text: Original context the fact was extracted from
            
        Returns:
            FactVerificationResult with verification decision
        """
        try:
            print("\nPreparing to verify fact...")
            sys.stdout.flush()
            print("Input fact text:", fact_text[:100] + "..." if len(fact_text) > 100 else fact_text)
            print("Input original text:", original_text[:100] + "..." if len(original_text) > 100 else original_text)
            sys.stdout.flush()
            
            print("\nInvoking LLM chain...")
            sys.stdout.flush()
            # Run verification and get raw output
            raw_output = self.chain.invoke({
                "fact_text": fact_text,
                "original_text": original_text
            })
            print("LLM chain completed")
            sys.stdout.flush()
            
            print("\nProcessing verification result...")
            sys.stdout.flush()
            
            # Clean and parse the output
            parsed_output = clean_and_parse_llm_output(raw_output.content)
            
            # Convert to FactVerificationResult
            result = FactVerificationResult(
                is_valid=parsed_output["is_valid"],
                reason=parsed_output["reason"],
                confidence=float(parsed_output["confidence"])
            )
            
            logger.info(
                f"Fact verification complete - "
                f"Valid: {result.is_valid}, "
                f"Confidence: {result.confidence:.2f}"
            )
            
            print("Verification complete")
            sys.stdout.flush()
            return result
            
        except Exception as e:
            error_msg = f"Fact verification failed: {str(e)}"
            print(f"\nERROR: {error_msg}")
            sys.stdout.flush()
            logger.error(error_msg)
            # Return conservative default on error
            return FactVerificationResult(
                is_valid=False,
                reason=f"Verification failed due to error: {str(e)}",
                confidence=0.0
            ) 
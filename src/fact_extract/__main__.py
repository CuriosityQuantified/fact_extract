"""
Main entry point for the fact extraction system.
"""

import sys
from typing import List, Dict

from .utils.config import load_config
from .graph.nodes import create_workflow
from .models.state import WorkflowState, Fact


def extract_facts(text: str) -> List[Dict]:
    """Extract facts from the given text.
    
    Args:
        text: The input text to extract facts from
        
    Returns:
        List of extracted facts as dictionaries
    """
    # Load configuration
    config = load_config()
    
    # Create workflow
    workflow, input_key = create_workflow()
    
    # Run workflow
    result = workflow.invoke({input_key: text})
    
    # Convert to simple dict format for output
    facts = []
    for fact in result.extracted_facts:
        facts.append({
            "statement": fact.statement,
            "confidence": fact.confidence,
            "chunk_index": fact.source_chunk,
            "metadata": fact.metadata
        })
    
    return facts


def main():
    """Main entry point."""
    # Simple command line interface
    if len(sys.argv) != 2:
        print("Usage: python -m fact_extract 'text to analyze'")
        sys.exit(1)
    
    text = sys.argv[1]
    try:
        facts = extract_facts(text)
        
        # Print results
        print("\nExtracted Facts:")
        print("-" * 40)
        for fact in facts:
            print(f"Statement: {fact['statement']}")
            print(f"Confidence: {fact['confidence']:.2f}")
            print(f"From chunk: {fact['chunk_index']}")
            print("-" * 40)
            
    except Exception as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main() 
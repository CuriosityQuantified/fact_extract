"""
Test script for fact extraction using synthetic data.
"""

from typing import Dict, List
import sys

from src.fact_extract.utils.synthetic_data import SYNTHETIC_ARTICLE_2
from src.fact_extract.__main__ import extract_facts

def print_facts_by_confidence(facts: List[Dict]):
    """Print facts grouped by confidence level with statistics."""
    print("\nExtracted Facts:")
    print("-" * 80)
    
    # Group facts by confidence level
    high_conf = [f for f in facts if f["confidence"] >= 0.8]
    med_conf = [f for f in facts if 0.5 <= f["confidence"] < 0.8]
    low_conf = [f for f in facts if f["confidence"] < 0.5]
    
    # Print high confidence facts
    if high_conf:
        print("\nHigh Confidence Facts (≥0.8):")
        print("-" * 80)
        for fact in high_conf:
            print(f"• {fact['statement']}")
            print(f"  Confidence: {fact['confidence']:.2f}")
            print(f"  From chunk: {fact['chunk_index']}\n")
    
    # Print medium confidence facts        
    if med_conf:
        print("\nMedium Confidence Facts (0.5-0.8):")
        print("-" * 80)
        for fact in med_conf:
            print(f"• {fact['statement']}")
            print(f"  Confidence: {fact['confidence']:.2f}")
            print(f"  From chunk: {fact['chunk_index']}\n")
            
    # Print low confidence facts
    if low_conf:
        print("\nLow Confidence Facts (<0.5):")
        print("-" * 80)
        for fact in low_conf:
            print(f"• {fact['statement']}")
            print(f"  Confidence: {fact['confidence']:.2f}")
            print(f"  From chunk: {fact['chunk_index']}\n")
            
    # Print statistics
    print("\nStatistics:")
    print("-" * 80)
    print(f"Total facts extracted: {len(facts)}")
    print(f"High confidence facts: {len(high_conf)}")
    print(f"Medium confidence facts: {len(med_conf)}")
    print(f"Low confidence facts: {len(low_conf)}")
    if facts:
        avg_conf = sum(f["confidence"] for f in facts) / len(facts)
        print(f"Average confidence: {avg_conf:.2f}")

def main():
    """Main test function."""
    print("Testing fact extraction on sustainable data centers article...")
    print("-" * 80)
    
    try:
        facts = extract_facts(SYNTHETIC_ARTICLE_2)
        print_facts_by_confidence(facts)
        
    except Exception as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main() 
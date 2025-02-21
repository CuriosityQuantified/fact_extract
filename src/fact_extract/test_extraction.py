"""
Test script for fact extraction using synthetic data.
"""

from src.fact_extract.utils.synthetic_data import SYNTHETIC_ARTICLE
from src.fact_extract import extract_facts


def main():
    """Run fact extraction on synthetic article."""
    print("Testing fact extraction on synthetic article about data centers...")
    print("-" * 80)
    
    try:
        # Extract facts
        facts = extract_facts(SYNTHETIC_ARTICLE)
        
        # Print results with formatting
        print(f"\nExtracted {len(facts)} facts:")
        print("-" * 80)
        
        # Group facts by confidence level
        high_conf = []
        medium_conf = []
        low_conf = []
        
        for fact in facts:
            if fact['confidence'] >= 0.8:
                high_conf.append(fact)
            elif fact['confidence'] >= 0.5:
                medium_conf.append(fact)
            else:
                low_conf.append(fact)
        
        # Print high confidence facts
        print("\nHigh Confidence Facts (≥0.8):")
        print("-" * 80)
        for fact in high_conf:
            print(f"• {fact['statement']}")
            print(f"  Confidence: {fact['confidence']:.2f}")
            print(f"  From chunk: {fact['chunk_index']}")
            print()
        
        # Print medium confidence facts
        if medium_conf:
            print("\nMedium Confidence Facts (0.5-0.8):")
            print("-" * 80)
            for fact in medium_conf:
                print(f"• {fact['statement']}")
                print(f"  Confidence: {fact['confidence']:.2f}")
                print(f"  From chunk: {fact['chunk_index']}")
                print()
        
        # Print low confidence facts
        if low_conf:
            print("\nLow Confidence Facts (<0.5):")
            print("-" * 80)
            for fact in low_conf:
                print(f"• {fact['statement']}")
                print(f"  Confidence: {fact['confidence']:.2f}")
                print(f"  From chunk: {fact['chunk_index']}")
                print()
        
        # Print statistics
        print("\nStatistics:")
        print("-" * 80)
        print(f"Total facts extracted: {len(facts)}")
        print(f"High confidence facts: {len(high_conf)}")
        print(f"Medium confidence facts: {len(medium_conf)}")
        print(f"Low confidence facts: {len(low_conf)}")
        print(f"Average confidence: {sum(f['confidence'] for f in facts) / len(facts):.2f}")
        
    except Exception as e:
        print(f"Error during testing: {str(e)}")
        raise


if __name__ == "__main__":
    main() 
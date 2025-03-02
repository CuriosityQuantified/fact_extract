"""
Main entry point for the fact extraction system.
"""

import sys
import asyncio
import logging
from typing import List, Dict
from datetime import datetime
from pathlib import Path

from fact_extract.utils.config import load_config
from fact_extract.graph.nodes import create_workflow
from fact_extract.models.state import create_initial_state
from fact_extract.storage.chunk_repository import ChunkRepository
from fact_extract.storage.fact_repository import FactRepository
from fact_extract.utils.synthetic_data import *

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def format_fact_output(fact: Dict) -> str:
    """Format a fact for console output.
    
    Args:
        fact: Dictionary containing fact data
        
    Returns:
        Formatted string for display
    """
    # Get verification status and reason
    status = fact.get("verification_status", "unknown")
    reason = fact.get("verification_reason", "")
    
    # Format the output
    lines = [
        f"• Statement: {fact['statement']}",
        f"  Source Chunk: {fact['source_chunk']}",
        f"  Status: {status.upper()}",
    ]
    
    if reason:
        lines.append(f"  Reason: {reason}")
        
    return "\n".join(lines)

async def extract_facts(
    text: str,
    document_name: str = "Unknown",
    source_url: str = "",
    output_dir: str = "output"
) -> List[Dict]:
    """Extract facts from the given text using LangGraph workflow.
    
    Args:
        text: The input text to extract facts from
        document_name: Name/title of the source document
        source_url: URL or identifier of the source
        output_dir: Directory for output files
        
    Returns:
        List of extracted facts as dictionaries
    """
    try:
        # Load configuration
        config = load_config()
        
        # Initialize repositories
        chunk_repo = ChunkRepository()
        fact_repo = FactRepository()
        
        # Create workflow
        app, input_key = create_workflow(chunk_repo, fact_repo)
        
        # Create initial state
        initial_state = create_initial_state(
            input_text=text,
            document_name=document_name,
            source_url=source_url
        )
        
        # Run workflow using invoke
        final_state = await app.ainvoke(initial_state)
            
        # Return extracted facts from final state
        return final_state["extracted_facts"] if final_state else []
        
    except Exception as e:
        logger.error(f"Fact extraction failed: {str(e)}")
        return []

def print_fact(fact: Dict):
    """Print a single fact with its metadata."""
    print(
        "\nFact:",
        f"  Statement: {fact['statement']}",
        f"  Source: {fact['document_name']}",
        f"  Chunk: {fact['source_chunk']}",
        f"  Status: {fact['verification_status']}",
        sep="\n"
    )
    if fact.get('verification_reason'):
        print(f"  Reason: {fact['verification_reason']}")
    print()

def print_stats(facts: List[Dict]):
    """Print statistics about extracted facts."""
    if not facts:
        print("No facts found.")
        return
        
    total = len(facts)
    verified = len([f for f in facts if f["verification_status"] == "verified"])
    rejected = len([f for f in facts if f["verification_status"] == "rejected"])
    pending = total - verified - rejected
    
    print(f"\nFact Statistics:")
    print(f"Total facts: {total}")
    print(f"Verified: {verified}")
    print(f"Rejected: {rejected}")
    print(f"Pending: {pending}")
    print()

async def main():
    """Main entry point."""
    print("Extracting facts from synthetic article about sustainable data centers...")
    print("-" * 80)
    
    try:
        # Extract facts
        facts = await extract_facts(
            text=SYNTHETIC_ARTICLE_3,
            document_name="Sustainable Data Centers Article",
            source_url="synthetic_data.py"
        )
        
        if not facts:
            # Get chunk processing stats from repositories
            chunk_repo = ChunkRepository()
            processed_chunks = chunk_repo.get_chunks(
                document_name="Sustainable Data Centers Article",
                status="success"
            )
            
            print("\nNo new facts were extracted.")
            print(f"Previously processed chunks: {len(processed_chunks)}")
            
            # Print chunk details for debugging
            if processed_chunks:
                print("\nProcessed chunk details:")
                for chunk in processed_chunks:
                    print(f"- Chunk {chunk['chunk_index']}: " + 
                          f"Contains facts: {chunk['contains_facts']}, " +
                          f"Processed at: {chunk['timestamp']}")
            return
        
        # Group facts by verification status
        approved = []
        rejected = []
        pending = []
        
        for fact in facts:
            status = fact.get("verification_status", "pending")
            if status == "verified":
                approved.append(fact)
            elif status == "rejected":
                rejected.append(fact)
            else:
                pending.append(fact)
        
        # Print results by category
        if approved:
            print("\nVerified Facts:")
            print("-" * 80)
            for fact in approved:
                print(format_fact_output(fact))
                print()
        
        if rejected:
            print("\nRejected Facts:")
            print("-" * 80)
            for fact in rejected:
                print(format_fact_output(fact))
                print()
        
        if pending:
            print("\nPending Facts:")
            print("-" * 80)
            for fact in pending:
                print(format_fact_output(fact))
                print()
        
        # Print statistics
        print_stats(facts)
        
        # Get repository stats
        repo = FactRepository()
        stored_facts = repo.get_facts(
            document_name="Sustainable Data Centers Article",
            verified_only=True
        )
        print(f"Facts stored in repository: {len(stored_facts)}")
            
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main()) 
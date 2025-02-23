"""
LangGraph nodes for the fact extraction workflow using v0.2.28+ patterns.
Each node represents a discrete step in our processing pipeline.
"""

from typing import Dict, Any, Tuple, List, cast
from operator import itemgetter
from datetime import datetime
from uuid import UUID
import json
import asyncio

from langgraph.graph import END, StateGraph
from langgraph.prebuilt import ToolExecutor
from langgraph.graph.message import MessageGraph
from langchain_core.messages import HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import ChatOpenAI

from fact_extract.models.state import (
    WorkflowStateDict,
    TextChunkDict,
    FactDict,
    MemoryDict,
    create_initial_state
)
from fact_extract.agents import FACT_EXTRACTOR_PROMPT, FACT_VERIFICATION_PROMPT
from fact_extract.storage.chunk_repository import ChunkRepository
from fact_extract.storage.fact_repository import FactRepository
from fact_extract.tools.submission import submit_fact

import logging
logger = logging.getLogger(__name__)

# Initialize repositories and LLM as module-level variables
chunk_repo = ChunkRepository()
fact_repo = FactRepository()
llm = ChatOpenAI(
    model="gpt-3.5-turbo",
    temperature=0  # Keep temperature at 0 for consistent outputs
)

async def chunker_node(state: WorkflowStateDict) -> WorkflowStateDict:
    """Split input text into chunks and track them."""
    print("\n" + "="*80)
    print("CHUNKER NODE START")
    print("="*80)
    print("\nInput:")
    print("-"*40)
    print(f"Document: {state['document_name']}")
    print(f"Source URL: {state['source_url']}")
    print(f"Input text length: {len(state['input_text'])} characters")
    print(f"First 200 chars: {state['input_text'][:200]}...")
    
    try:
        # Initialize text splitter with adjusted size
        text_splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
            model_name="gpt-4",
            chunk_size=500,  # Adjusted chunk size
            chunk_overlap=100,  # Adjusted overlap
            add_start_index=True,
            separators=["\n\n", "\n", " ", ""]  # Natural breaks
        )
        
        print("\nChunking Configuration:")
        print("-"*40)
        print(f"Chunk size: 500 tokens")
        print(f"Chunk overlap: 100 tokens")
        print(f"Model: gpt-4")
        print(f"Separators: [\\n\\n, \\n, space, empty]")
        
        # Split text into chunks
        chunks = text_splitter.split_text(state["input_text"])
        
        # Process chunks
        new_chunks: List[TextChunkDict] = []
        skipped_chunks = 0
        for i, chunk in enumerate(chunks):
            if not chunk.strip():
                continue
                
            chunk_data: TextChunkDict = {
                "content": chunk.strip(),
                "index": i,
                "metadata": {
                    "char_length": len(chunk),
                    "timestamp": datetime.now().isoformat()
                }
            }
            
            # Check if chunk has already been processed successfully
            if chunk_repo.is_chunk_processed(chunk_data, state["document_name"]):
                logger.info(f"Chunk {i} has already been processed successfully, skipping...")
                skipped_chunks += 1
                continue
                
            # Store new chunk as pending
            chunk_repo.store_chunk({
                "timestamp": chunk_data["metadata"]["timestamp"],
                "document_name": state["document_name"],
                "source_url": state["source_url"],
                "chunk_content": chunk_data["content"],
                "chunk_index": chunk_data["index"],
                "status": "pending",
                "contains_facts": False,
                "error_message": None,
                "processing_time": None,
                "metadata": chunk_data["metadata"]
            })
            
            # Add chunk to state for processing
            new_chunks.append(chunk_data)
        
        # Update state
        state["chunks"] = new_chunks
        state["current_chunk_index"] = 0
        state["is_complete"] = len(new_chunks) == 0
        
        # Update memory metrics
        memory = cast(MemoryDict, state["memory"])
        memory["performance_metrics"]["chunks_processed"] = len(new_chunks)
        memory["performance_metrics"]["chunks_skipped"] = skipped_chunks
        
        print("\nChunking Results:")
        print("-"*40)
        print(f"Total chunks created: {len(chunks)}")
        print(f"Empty chunks filtered: {len(chunks) - len(new_chunks) - skipped_chunks}")
        print(f"Skipped (already processed): {skipped_chunks}")
        print(f"New chunks to process: {len(new_chunks)}")
        
        print("\nChunk Details:")
        print("-"*40)
        for i, chunk in enumerate(new_chunks):
            print(f"\nChunk {i}:")
            print(f"Length: {len(chunk['content'])} chars")
            print(f"First 100 chars: {chunk['content'][:100]}...")
        
        print("\nCHUNKER NODE COMPLETE")
        print("="*80)
        
    except Exception as e:
        error_msg = f"Error in chunking: {str(e)}"
        logger.error(error_msg)
        state["errors"].append(error_msg)
        
        print("\nERROR IN CHUNKER NODE:")
        print("-"*40)
        print(error_msg)
        
        # Create single chunk with entire text
        state["chunks"] = [{
            "content": state["input_text"],
            "index": 0,
            "metadata": {"error": str(e)}
        }]
        state["current_chunk_index"] = 0
        state["is_complete"] = False
        
        # Update error stats in memory
        memory = cast(MemoryDict, state["memory"])
        memory["error_counts"]["chunking_error"] = memory["error_counts"].get("chunking_error", 0) + 1
    
    return state


async def extractor_node(state: WorkflowStateDict) -> WorkflowStateDict:
    """Extract facts from chunks and manage storage."""
    print("\n" + "="*80)
    print("EXTRACTOR NODE START")
    print("="*80)
    
    try:
        # Check if we're done processing chunks
        if state["current_chunk_index"] >= len(state["chunks"]):
            print("\nNo more chunks to process")
            state["is_complete"] = True
            return state
            
        current_chunk = state["chunks"][state["current_chunk_index"]]
        start_time = datetime.now()
        
        print("\nProcessing Chunk:")
        print("-"*40)
        print(f"Chunk Index: {current_chunk['index']}")
        print(f"Chunk Length: {len(current_chunk['content'])} chars")
        print("\nChunk Content:")
        print("-"*40)
        print(current_chunk["content"])
        print("-"*40)
        
        # Extract facts using LLM
        print("\nSending to LLM for fact extraction...")
        response = await llm.ainvoke(
            [HumanMessage(content=FACT_EXTRACTOR_PROMPT.format(text=current_chunk["content"]))]
        )
        
        print("\nLLM Response:")
        print("-"*40)
        print(response.content)
        print("-"*40)
        
        # Track processing time
        processing_time = (datetime.now() - start_time).total_seconds()
        
        # Parse facts
        facts_found = False
        facts = []
        import re
        
        print("\nParsing Facts:")
        print("-"*40)
        
        # Try numbered facts first
        fact_pattern = re.compile(r'<fact (\d+)>(.*?)</fact \1>')
        matches = fact_pattern.finditer(response.content)
        facts_found = False
        
        # If no numbered facts found, try unnumbered facts
        if not any(matches):
            print("No numbered facts found, trying unnumbered facts...")
            fact_pattern = re.compile(r'<fact>(.*?)</fact>')
            matches = fact_pattern.finditer(response.content)
            
        # Process matches
        for i, match in enumerate(matches, 1):
            if fact_pattern.pattern == r'<fact (\d+)>(.*?)</fact \1>':
                fact_num = int(match.group(1))
                fact_text = match.group(2).strip()
            else:
                fact_num = i
                fact_text = match.group(1).strip()
            
            # Skip empty facts
            if not fact_text:
                print(f"Skipping empty fact {fact_num}")
                continue
                
            # Special handling for "None" facts
            if fact_num == 1 and fact_text.lower() == "none" and not re.search(r'<fact[^>]*>(?!none)', response.content, re.IGNORECASE):
                print("Single 'None' fact detected - marking chunk as processed with no facts")
                chunk_repo.update_chunk_status(
                    document_name=state["document_name"],
                    chunk_index=current_chunk["index"],
                    status="processed",
                    contains_facts=False,
                    error_message=None
                )
                facts_found = False
                break
            
            facts_found = True
            print(f"\nExtracted Fact {fact_num}:")
            print(f"Statement: {fact_text}")
            
            # Create fact data
            fact_data: FactDict = {
                "statement": fact_text,
                "source_chunk": current_chunk["index"],
                "document_name": state["document_name"],
                "source_url": state["source_url"],
                "original_text": current_chunk["content"],
                "metadata": {
                    "chunk_metadata": current_chunk["metadata"],
                    "llm_response": response.content,
                    "extraction_time": processing_time,
                    "extraction_model": "gpt-3.5-turbo",
                    "fact_number": fact_num
                },
                "timestamp": datetime.now().isoformat(),
                "verification_status": "pending",
                "verification_reason": None
            }
            
            # Add fact to collection
            facts.append(fact_data)
            
            # Update memory metrics
            memory = cast(MemoryDict, state["memory"])
            memory["recent_facts"].append(fact_data)
            memory["performance_metrics"]["facts_extracted"] += 1
        
        # Add all facts to state at once
        state["extracted_facts"].extend(facts)
        
        print("\nExtraction Summary:")
        print("-"*40)
        print(f"Processing time: {processing_time:.2f} seconds")
        print(f"Facts found: {len(facts)}")
        
        # Update chunk status based on whether facts were found
        if facts_found:
            print("Marking chunk as pending verification")
            chunk_repo.update_chunk_status(
                document_name=state["document_name"],
                chunk_index=current_chunk["index"],
                status="pending",
                contains_facts=None,  # Will be determined after verification
                error_message=None
            )
        else:
            print("No facts found - marking chunk as processed")
            chunk_repo.update_chunk_status(
                document_name=state["document_name"],
                chunk_index=current_chunk["index"],
                status="processed",
                contains_facts=False,
                error_message=None
            )
        
        # Move to next chunk
        state["current_chunk_index"] += 1
        state["last_processed_time"] = datetime.now().isoformat()
        
        # Check if we should continue processing
        if state["current_chunk_index"] >= len(state["chunks"]):
            state["is_complete"] = True
            print("\nAll chunks processed")
        else:
            print(f"\nMoving to chunk {state['current_chunk_index']}")
        
        print("\nEXTRACTOR NODE COMPLETE")
        print("="*80)
        return state
        
    except Exception as e:
        error_msg = f"Error processing chunk {current_chunk['index']}: {str(e)}"
        logger.error(error_msg)
        state["errors"].append(error_msg)
        
        print("\nERROR IN EXTRACTOR NODE:")
        print("-"*40)
        print(error_msg)
        
        # Update chunk status
        chunk_repo.update_chunk_status(
            document_name=state["document_name"],
            chunk_index=current_chunk["index"],
            status="failed",
            error_message=str(e)
        )
        
        # Update error stats in memory
        memory = cast(MemoryDict, state["memory"])
        memory["error_counts"]["extraction_error"] = memory["error_counts"].get("extraction_error", 0) + 1
        memory["performance_metrics"]["errors_encountered"] += 1
        
        # Move to next chunk even on error
        state["current_chunk_index"] += 1
        state["last_processed_time"] = datetime.now().isoformat()
        
        # Check if we should continue processing
        if state["current_chunk_index"] >= len(state["chunks"]):
            state["is_complete"] = True
            
        return state


async def validator_node(state: WorkflowStateDict) -> WorkflowStateDict:
    """Validate extracted facts using LLM and store approved facts."""
    print("\n" + "="*80)
    print("VALIDATOR NODE START")
    print("="*80)
    
    try:
        # Track verified facts per chunk
        chunk_verified_facts: Dict[int, List[FactDict]] = {}
        
        print("\nFacts to Validate:")
        print("-"*40)
        pending_facts = [f for f in state["extracted_facts"] if f["verification_status"] == "pending"]
        print(f"Total pending facts: {len(pending_facts)}")
        
        # Validate each pending fact
        for fact in pending_facts:
            try:
                # Get the original text from the fact data
                original_text = fact["original_text"]
                chunk_index = fact["source_chunk"]
                
                print("\nValidating Fact:")
                print("-"*40)
                print(f"From chunk: {chunk_index}")
                print(f"Statement: {fact['statement']}")
                print("\nOriginal Context:")
                print("-"*40)
                print(original_text)
                print("-"*40)
                
                # Validate fact using LLM with FACT_VERIFICATION_PROMPT
                max_retries = 3
                retry_delay = 5
                
                print("\nSending to LLM for verification...")
                for attempt in range(max_retries):
                    try:
                        response = await llm.ainvoke(
                            FACT_VERIFICATION_PROMPT.format_messages(
                                fact_text=fact["statement"],
                                original_text=original_text
                            )
                        )
                        break
                    except Exception as e:
                        if "429" in str(e) and attempt < max_retries - 1:
                            print(f"Rate limited, retrying in {retry_delay} seconds...")
                            await asyncio.sleep(retry_delay)
                            retry_delay *= 2  # Exponential backoff
                        else:
                            raise
                
                print("\nLLM Response:")
                print("-"*40)
                print(response.content)
                print("-"*40)
                
                # Parse XML response
                try:
                    import re
                    
                    # Extract reasoning and is_valid from XML
                    reasoning_match = re.search(r'<reasoning>(.*?)</reasoning>', response.content, re.DOTALL)
                    is_valid_match = re.search(r'<is_valid>(.*?)</is_valid>', response.content, re.DOTALL)
                    
                    if not reasoning_match or not is_valid_match:
                        raise ValueError("Missing required XML fields")
                        
                    reasoning = reasoning_match.group(1).strip()
                    is_valid = is_valid_match.group(1).strip().lower() == "true"
                    
                    print("\nVerification Result:")
                    print("-"*40)
                    print(f"Valid: {is_valid}")
                    print(f"Reasoning: {reasoning}")
                    
                    # Update fact status based on validation
                    fact["verification_status"] = "verified" if is_valid else "rejected"
                    fact["verification_reason"] = reasoning
                    
                    # Store fact only if approved
                    if is_valid:
                        print("Fact verified - storing in repository")
                        fact_repo.store_fact(fact)
                        # Track verified facts by chunk
                        if chunk_index not in chunk_verified_facts:
                            chunk_verified_facts[chunk_index] = []
                        chunk_verified_facts[chunk_index].append(fact)
                    else:
                        print("Fact rejected - not storing")
                    
                except (ValueError, AttributeError) as e:
                    print(f"\nError parsing validation response: {str(e)}")
                    fact["verification_status"] = "rejected"
                    fact["verification_reason"] = "Invalid validation response format"
                
            except Exception as e:
                error_msg = f"Error validating fact: {str(e)}"
                print(f"\nError: {error_msg}")
                state["errors"].append(error_msg)
                
                # Update error stats in memory
                memory = cast(MemoryDict, state["memory"])
                memory["error_counts"]["validation_error"] = memory["error_counts"].get("validation_error", 0) + 1
        
        print("\nValidation Summary:")
        print("-"*40)
        verified_count = len([f for f in state["extracted_facts"] if f["verification_status"] == "verified"])
        rejected_count = len([f for f in state["extracted_facts"] if f["verification_status"] == "rejected"])
        print(f"Total facts processed: {len(pending_facts)}")
        print(f"Verified: {verified_count}")
        print(f"Rejected: {rejected_count}")
        
        # Update chunk statuses based on verification results
        print("\nUpdating Chunk Statuses:")
        print("-"*40)
        for chunk_index, verified_facts in chunk_verified_facts.items():
            print(f"Chunk {chunk_index}: {len(verified_facts)} verified facts")
            chunk_repo.update_chunk_status(
                document_name=state["document_name"],
                chunk_index=chunk_index,
                status="processed",
                contains_facts=len(verified_facts) > 0,
                error_message=None
            )
        
        # Mark state as complete
        state["is_complete"] = True
        print("\nVALIDATOR NODE COMPLETE")
        print("="*80)
        return state
        
    except Exception as e:
        error_msg = f"Error in validator node: {str(e)}"
        print("\nERROR IN VALIDATOR NODE:")
        print("-"*40)
        print(error_msg)
        state["errors"].append(error_msg)
        return state


def create_workflow(
    chunk_repo: ChunkRepository,
    fact_repo: FactRepository
) -> Tuple[StateGraph, str]:
    """Create the complete workflow graph with memory persistence.
    
    Args:
        chunk_repo: Repository for tracking chunks
        fact_repo: Repository for storing facts
        
    Returns:
        Tuple of workflow graph and input key
    """
    # Create workflow graph
    workflow = StateGraph(WorkflowStateDict)
    
    # Add nodes with async wrappers
    workflow.add_node("chunker", chunker_node)
    workflow.add_node("extractor", extractor_node)
    workflow.add_node("validator", validator_node)
    
    # Define edges
    workflow.add_edge("chunker", "extractor")
    workflow.add_edge("extractor", "validator")
    
    # Add conditional edges with explicit completion check
    def should_continue(state: WorkflowStateDict) -> str:
        """Determine if processing should continue or end."""
        if state["is_complete"]:
            return END
        if state["current_chunk_index"] >= len(state["chunks"]):
            return END
        return "extractor"
    
    workflow.add_conditional_edges(
        "validator",
        should_continue
    )
    
    # Set entry point
    workflow.set_entry_point("chunker")
    
    # Compile the graph
    app = workflow.compile()
    
    return app, "input_text" 
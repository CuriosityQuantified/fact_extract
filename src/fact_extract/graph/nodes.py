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
from langchain_groq import ChatGroq

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
llm = ChatGroq(
    model="llama-3.3-70b-versatile",
    temperature=0,
    max_tokens=1024
)

async def chunker_node(state: WorkflowStateDict) -> WorkflowStateDict:
    """Split input text into chunks and track them."""
    try:
        # Initialize text splitter
        text_splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
            model_name="gpt-4",
            chunk_size=500,
            chunk_overlap=50,
            add_start_index=True
        )
        
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
        
        logger.info(f"Split text into {len(chunks)} chunks total")
        logger.info(f"Skipped {skipped_chunks} already processed chunks")
        logger.info(f"Processing {len(new_chunks)} new chunks")
        
    except Exception as e:
        error_msg = f"Error in chunking: {str(e)}"
        logger.error(error_msg)
        state["errors"].append(error_msg)
        
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
    try:
        # Check if we're done processing chunks
        if state["current_chunk_index"] >= len(state["chunks"]):
            state["is_complete"] = True
            return state
            
        current_chunk = state["chunks"][state["current_chunk_index"]]
        start_time = datetime.now()
        
        # Extract facts using LLM
        logger.info(f"Processing chunk {current_chunk['index']}...")
        logger.debug(f"Chunk content: {current_chunk['content'][:100]}...")
        
        response = await llm.ainvoke(
            [HumanMessage(content=FACT_EXTRACTOR_PROMPT.format(text=current_chunk["content"]))]
        )
        logger.debug(f"LLM Response: {response.content}")
        
        # Track processing time
        processing_time = (datetime.now() - start_time).total_seconds()
        
        # Parse and store facts
        facts_found = False
        for line in response.content.split("\n"):
            if "<fact>" in line and "</fact>" in line:
                facts_found = True
                # Extract fact and confidence
                fact_text = line.split("<fact>")[1].split("</fact>")[0]
                conf_text = line.split("<confidence>")[1].split("</confidence>")[0]
                
                # Create fact data
                fact_data: FactDict = {
                    "statement": fact_text,
                    "confidence": float(conf_text),
                    "source_chunk": current_chunk["index"],
                    "document_name": state["document_name"],
                    "source_url": state["source_url"],
                    "original_text": current_chunk["content"],  # Store original text
                    "metadata": {
                        "chunk_metadata": current_chunk["metadata"],
                        "llm_response": response.content,
                        "extraction_time": processing_time,
                        "extraction_model": "llama-3.3-70b-versatile"
                    },
                    "timestamp": datetime.now().isoformat(),
                    "verification_status": "pending",
                    "verification_reason": None
                }
                
                # Store fact
                fact_repo.store_fact(fact_data)
                state["extracted_facts"].append(fact_data)
                
                # Update memory metrics
                memory = cast(MemoryDict, state["memory"])
                memory["recent_facts"].append(fact_data)
                memory["performance_metrics"]["facts_extracted"] += 1
        
        # Update chunk status
        chunk_repo.update_chunk_status(
            document_name=state["document_name"],
            chunk_index=current_chunk["index"],
            status="success",
            contains_facts=facts_found,
            error_message=None
        )
        
        # Move to next chunk
        state["current_chunk_index"] += 1
        state["last_processed_time"] = datetime.now().isoformat()
        
        # Check if we should continue processing
        if state["current_chunk_index"] >= len(state["chunks"]):
            state["is_complete"] = True
        
        return state
        
    except Exception as e:
        error_msg = f"Error processing chunk {current_chunk['index']}: {str(e)}"
        logger.error(error_msg)
        state["errors"].append(error_msg)
        
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
    """Validate extracted facts using LLM."""
    try:
        # Validate each pending fact
        for fact in state["extracted_facts"]:
            if fact["verification_status"] == "pending":
                try:
                    # Get the original text from the fact data
                    original_text = fact["original_text"]
                    
                    # Print fact and chunk for verification transparency
                    print("\nVerifying fact:")
                    print(f"Statement: {fact['statement']}")
                    print(f"Confidence: {fact['confidence']}")
                    print("\nOriginal chunk content:")
                    print("-" * 80)
                    print(original_text)
                    print("-" * 80)
                    
                    # Validate fact using LLM with FACT_VERIFICATION_PROMPT
                    max_retries = 3
                    retry_delay = 5
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
                                logger.warning(f"Rate limited, retrying in {retry_delay} seconds...")
                                await asyncio.sleep(retry_delay)
                                retry_delay *= 2  # Exponential backoff
                            else:
                                raise
                    
                    # Parse JSON response
                    try:
                        validation_result = json.loads(response.content)
                        is_valid = validation_result.get("is_valid", False)
                        reason = validation_result.get("reason", "No reason provided")
                        confidence = validation_result.get("confidence", 0.0)
                        
                        # Print verification result
                        print(f"\nVerification result: {is_valid}")
                        print(f"Reason: {reason}")
                        print(f"Confidence: {confidence}\n")
                        
                        # Update fact status based on validation
                        fact["verification_status"] = "approved" if is_valid else "rejected"
                        fact["verification_reason"] = reason
                        fact["confidence"] = min(fact["confidence"], confidence)  # Adjust confidence
                        
                        # Update in repository
                        fact_repo.update_verification_status(
                            document_name=state["document_name"],
                            fact_text=fact["statement"],
                            status=fact["verification_status"],
                            reason=fact["verification_reason"]
                        )
                        
                        # Update memory metrics
                        memory = cast(MemoryDict, state["memory"])
                        if is_valid:
                            memory["fact_patterns"].append(fact["statement"])
                            
                    except json.JSONDecodeError as e:
                        logger.error(f"Failed to parse validation response: {str(e)}")
                        fact["verification_status"] = "rejected"
                        fact["verification_reason"] = "Invalid validation response format"
                    
                except Exception as e:
                    error_msg = f"Error validating fact: {str(e)}"
                    logger.error(error_msg)
                    state["errors"].append(error_msg)
                    
                    # Update error stats in memory
                    memory = cast(MemoryDict, state["memory"])
                    memory["error_counts"]["validation_error"] = memory["error_counts"].get("validation_error", 0) + 1
        
        # Mark state as complete since we've processed all facts
        state["is_complete"] = True
        return state
        
    except Exception as e:
        error_msg = f"Error in validator node: {str(e)}"
        logger.error(error_msg)
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
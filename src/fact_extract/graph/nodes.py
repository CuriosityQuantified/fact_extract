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
import os
import hashlib

from langgraph.graph import END, StateGraph
# Try different import paths for ToolNode based on langgraph version
try:
    # Newer versions
    from langgraph.prebuilt.tool_node import ToolNode
except ImportError:
    try:
        # Alternative location
        from langgraph.prebuilt import ToolNode
    except ImportError:
        # Original location (older versions)
        from langgraph.prebuilt import ToolNode
from langgraph.graph.message import MessageGraph
from langchain_core.messages import HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import ChatOpenAI
from langchain_core.documents import Document

from fact_extract.models.state import (
    WorkflowStateDict,
    TextChunkDict,
    FactDict,
    MemoryDict,
    create_initial_state,
    ProcessingState
)
from fact_extract.agents import FACT_EXTRACTOR_PROMPT, FACT_VERIFICATION_PROMPT
from fact_extract.storage.chunk_repository import ChunkRepository
from fact_extract.storage.fact_repository import FactRepository, RejectedFactRepository
from fact_extract.tools.submission import submit_fact

import logging
logger = logging.getLogger(__name__)

# Initialize repositories and LLM as module-level variables
chunk_repo = ChunkRepository()
fact_repo = FactRepository()
rejected_fact_repo = RejectedFactRepository()
llm = ChatOpenAI(
    model="gpt-3.5-turbo",
    temperature=0  # Keep temperature at 0 for consistent outputs
)

async def chunker_node(state: WorkflowStateDict) -> WorkflowStateDict:
    """Split input text into chunks and manage chunk storage."""
    print("\n" + "="*80)
    print("CHUNKER NODE START")
    print("="*80)
    
    try:
        # Initialize state fields if not present
        if "extracted_facts" not in state:
            state["extracted_facts"] = []
        if "errors" not in state:
            state["errors"] = []
        if "memory" not in state:
            state["memory"] = {
                "document_stats": {},
                "fact_patterns": [],
                "entity_mentions": {},
                "recent_facts": [],
                "error_counts": {},
                "performance_metrics": {
                    "start_time": datetime.now().isoformat(),
                    "chunks_processed": 0,
                    "facts_extracted": 0,
                    "errors_encountered": 0
                }
            }
        
        print("\nInput:")
        print("-"*40)
        print(f"Document: {state['document_name']}")
        print(f"Source URL: {state['source_url']}")
        print(f"Input text length: {len(state['input_text'])} characters")
        print(f"First 200 chars: {state['input_text'][:200]}...")
        
        # Generate a document hash for duplicate detection
        document_hash = hashlib.md5(state['input_text'].encode()).hexdigest()
        print(f"Document hash: {document_hash}")
        
        # Check if document has already been processed
        existing_chunks = chunk_repo.get_all_chunks()
        for chunk in existing_chunks:
            if chunk.get("document_hash") == document_hash:
                print(f"Document with hash {document_hash} has already been processed.")
                print("Skipping processing and marking as complete.")
                state["is_complete"] = True
                state["chunks"] = []
                return state
        
        print("\nChunking Configuration:")
        print("-"*40)
        print("Chunk size: 750 words")
        print("Chunk overlap: 50 words")
        print("Using: RecursiveCharacterTextSplitter")
        print("Separators: [\\n\\n, \\n, . , ]")
        
        # Create text splitter with word-based chunking
        text_splitter = RecursiveCharacterTextSplitter(
            separators=["\n\n", "\n", ". ", " "],  # Separators in order of priority
            chunk_size=750,  # Target 750 words per chunk
            chunk_overlap=50,  # 50 words overlap
            length_function=lambda x: len(x.split()),  # Word-based length function
            add_start_index=True,
            strip_whitespace=True
        )
        
        # Create a proper Document object
        initial_doc = Document(
            page_content=state["input_text"],
            metadata={
                "source": state["document_name"],
                "url": state["source_url"]
            }
        )
        
        # Split the document
        text_splitter = text_splitter.split_documents([initial_doc])
        
        # Initialize tracking variables
        new_chunks = []
        skipped_chunks = 0
        
        # Process each chunk
        for i, doc in enumerate(text_splitter):
            chunk = doc.page_content
            if not chunk.strip():
                continue
                
            # Count words in chunk
            word_count = len(chunk.split())
            
            chunk_data: TextChunkDict = {
                "content": chunk.strip(),
                "index": i,
                "metadata": {
                    "word_count": word_count,
                    "char_length": len(chunk),
                    "start_index": doc.metadata.get("start_index", 0),
                    "source": doc.metadata.get("source", ""),
                    "url": doc.metadata.get("url", ""),
                    "timestamp": datetime.now().isoformat(),
                    "document_hash": document_hash
                }
            }
            
            # Check if chunk has already been processed successfully
            if chunk_repo.is_chunk_processed(chunk_data, state["document_name"]):
                print(f"Chunk {i} has already been processed successfully, skipping...")
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
                "document_hash": document_hash,
                "all_facts_extracted": False,  # Initialize as false
                "metadata": chunk_data["metadata"]
            })
            
            # Add chunk to state for processing
            new_chunks.append(chunk_data)
        
        # Update state
        state["chunks"] = new_chunks
        state["current_chunk_index"] = 0
        state["is_complete"] = len(new_chunks) == 0
        
        # Update memory metrics
        state["memory"]["performance_metrics"]["chunks_processed"] = len(new_chunks)
        state["memory"]["performance_metrics"]["chunks_skipped"] = skipped_chunks
        
        print("\nChunking Results:")
        print("-"*40)
        print(f"Total chunks created: {len(text_splitter)}")
        print(f"Empty chunks filtered: {len(text_splitter) - len(new_chunks) - skipped_chunks}")
        print(f"Skipped (already processed): {skipped_chunks}")
        print(f"New chunks to process: {len(new_chunks)}")
        
        print("\nChunk Details:")
        print("-"*40)
        for i, chunk in enumerate(new_chunks):
            print(f"\nChunk {i}:")
            print(f"Word count: {chunk['metadata']['word_count']} words")
            print(f"Length: {len(chunk['content'])} chars")
            print(f"Start index: {chunk['metadata']['start_index']}")
            print(f"First 100 chars: {chunk['content'][:100]}...")
        
        print("\nCHUNKER NODE COMPLETE")
        print("="*80)
        
        return state
        
    except Exception as e:
        error_msg = f"Error in chunking: {str(e)}"
        print("\nERROR IN CHUNKER NODE:")
        print("-"*40)
        print(error_msg)
        
        # Initialize errors list if not present
        if "errors" not in state:
            state["errors"] = []
        state["errors"].append(error_msg)
        
        # Update error stats
        state["memory"]["error_counts"]["chunking_error"] = state["memory"]["error_counts"].get("chunking_error", 0) + 1
        state["memory"]["performance_metrics"]["errors_encountered"] += 1
        
        # Ensure state is marked as complete on error
        state["is_complete"] = True
        return state


async def extractor_node(state: WorkflowStateDict) -> WorkflowStateDict:
    """Extract facts from chunks and manage storage."""
    print("\n" + "="*80)
    print("EXTRACTOR NODE START")
    print("="*80)
    
    try:
        # Initialize state fields if not present
        if "extracted_facts" not in state:
            state["extracted_facts"] = []
        if "errors" not in state:
            state["errors"] = []
        if "memory" not in state:
            state["memory"] = {
                "document_stats": {},
                "fact_patterns": [],
                "entity_mentions": {},
                "recent_facts": [],
                "error_counts": {},
                "performance_metrics": {
                    "start_time": datetime.now().isoformat(),
                    "chunks_processed": 0,
                    "facts_extracted": 0,
                    "errors_encountered": 0
                }
            }
        
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
        
        # Check if this chunk has already been processed but not all facts extracted
        existing_chunk = chunk_repo.get_chunk(state["document_name"], current_chunk["index"])
        if existing_chunk and existing_chunk.get("status") == "processed" and existing_chunk.get("contains_facts") and not existing_chunk.get("all_facts_extracted", False):
            print(f"Chunk {current_chunk['index']} has been processed before but may have more facts to extract.")
        
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
                
            # Create fact dictionary
            fact: FactDict = {
                "statement": fact_text,
                "source_chunk": current_chunk["index"],
                "original_text": current_chunk["content"],
                "document_name": state["document_name"],
                "source_url": state["source_url"],
                "extraction_time": datetime.now().isoformat(),
                "verification_status": "pending",
                "verification_reason": None,
                "metadata": {
                    "fact_number": fact_num,
                    "processing_time": processing_time
                }
            }
            
            facts.append(fact)
            facts_found = True
            
            print(f"\nFact {fact_num}:")
            print("-"*20)
            print(fact_text)
        
        # Update state with extracted facts
        if facts:
            state["extracted_facts"].extend(facts)
            state["memory"]["performance_metrics"]["facts_extracted"] += len(facts)
            
            # Update chunk status
            chunk_repo.update_chunk_status(
                document_name=state["document_name"],
                chunk_index=current_chunk["index"],
                status="processed",
                contains_facts=True,
                error_message=None
            )
        else:
            print("\nNo facts found in chunk")
            chunk_repo.update_chunk_status(
                document_name=state["document_name"],
                chunk_index=current_chunk["index"],
                status="processed",
                contains_facts=False,
                error_message=None
            )
        
        # Move to next chunk
        state["current_chunk_index"] += 1
        state["memory"]["performance_metrics"]["chunks_processed"] += 1
        
        print("\nExtraction Summary:")
        print("-"*40)
        print(f"Facts found: {len(facts)}")
        print(f"Processing time: {processing_time:.2f} seconds")
        
        print("\nEXTRACTOR NODE COMPLETE")
        print("="*80)
        return state
        
    except Exception as e:
        error_msg = f"Error in extractor node: {str(e)}"
        print("\nERROR IN EXTRACTOR NODE:")
        print("-"*40)
        print(error_msg)
        
        # Initialize errors list if not present
        if "errors" not in state:
            state["errors"] = []
        state["errors"].append(error_msg)
        
        # Update error stats
        state["memory"]["error_counts"]["extraction_error"] = state["memory"]["error_counts"].get("extraction_error", 0) + 1
        state["memory"]["performance_metrics"]["errors_encountered"] += 1
        
        # Update chunk status
        if "current_chunk_index" in state and state["current_chunk_index"] < len(state["chunks"]):
            current_chunk = state["chunks"][state["current_chunk_index"]]
            chunk_repo.update_chunk_status(
                document_name=state["document_name"],
                chunk_index=current_chunk["index"],
                status="error",
                contains_facts=False,
                error_message=str(e)
            )
        
        # Move to next chunk even on error
        state["current_chunk_index"] = state.get("current_chunk_index", 0) + 1
        return state


async def validator_node(state: WorkflowStateDict) -> WorkflowStateDict:
    """Validate extracted facts using LLM and store approved facts."""
    print("\n" + "="*80)
    print("VALIDATOR NODE START")
    print("="*80)
    
    try:
        # Initialize state fields if not present
        if "extracted_facts" not in state:
            state["extracted_facts"] = []
        if "errors" not in state:
            state["errors"] = []
        if "memory" not in state:
            state["memory"] = {
                "document_stats": {},
                "fact_patterns": [],
                "entity_mentions": {},
                "recent_facts": [],
                "error_counts": {},
                "performance_metrics": {
                    "start_time": datetime.now().isoformat(),
                    "chunks_processed": 0,
                    "facts_extracted": 0,
                    "errors_encountered": 0
                }
            }
        
        # Track verified facts per chunk
        chunk_verified_facts: Dict[int, List[FactDict]] = {}
        
        print("\nFacts to Validate:")
        print("-"*40)
        pending_facts = [f for f in state["extracted_facts"] if f.get("verification_status") == "pending"]
        print(f"Total pending facts: {len(pending_facts)}")
        
        if not pending_facts:
            print("No facts to validate")
            state["is_complete"] = True
            return state
        
        # Validate each pending fact
        for fact in pending_facts:
            try:
                # Get the original text from the fact data
                original_text = fact.get("original_text", "")
                chunk_index = fact.get("source_chunk", 0)
                
                print("\nValidating Fact:")
                print("-"*40)
                print(f"From chunk: {chunk_index}")
                print(f"Statement: {fact.get('statement', 'No statement')}")
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
                            [HumanMessage(content=FACT_VERIFICATION_PROMPT.format(
                                fact_text=fact.get("statement", ""),
                                original_text=original_text
                            ))]
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
                    
                    # Ensure all required fields are present for Excel storage
                    current_time = datetime.now().isoformat()
                    
                    # Add or update required fields
                    if "timestamp" not in fact:
                        fact["timestamp"] = current_time
                    
                    fact["date_uploaded"] = current_time
                    fact["source_name"] = state.get("source_name", "")
                    fact["source_url"] = state.get("source_url", "")
                    
                    # Store fact based on validation status
                    if is_valid:
                        print("Fact verified - storing in approved repository")
                        fact_repo.store_fact(fact)
                        # Track verified facts by chunk
                        if chunk_index not in chunk_verified_facts:
                            chunk_verified_facts[chunk_index] = []
                        chunk_verified_facts[chunk_index].append(fact)
                    else:
                        print("Fact rejected - storing in rejected repository")
                        rejected_fact_repo.store_rejected_fact(fact)
                    
                except (ValueError, AttributeError) as e:
                    print(f"\nError parsing validation response: {str(e)}")
                    fact["verification_status"] = "rejected"
                    fact["verification_reason"] = "Invalid validation response format"
                    state["errors"].append(f"Error parsing validation response: {str(e)}")
                    # Store the rejected fact due to parsing error
                    rejected_fact_repo.store_rejected_fact(fact)
                
            except Exception as e:
                error_msg = f"Error validating fact: {str(e)}"
                print(f"\nError: {error_msg}")
                state["errors"].append(error_msg)
                
                # Update error stats in memory
                state["memory"]["error_counts"]["validation_error"] = state["memory"]["error_counts"].get("validation_error", 0) + 1
                state["memory"]["performance_metrics"]["errors_encountered"] += 1
        
        print("\nValidation Summary:")
        print("-"*40)
        verified_count = len([f for f in state["extracted_facts"] if f.get("verification_status") == "verified"])
        rejected_count = len([f for f in state["extracted_facts"] if f.get("verification_status") == "rejected"])
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
                error_message=None,
                all_facts_extracted=True  # Mark as having all facts extracted
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
        
        # Initialize errors list if not present
        if "errors" not in state:
            state["errors"] = []
        state["errors"].append(error_msg)
        
        # Ensure state is marked as complete even on error
        state["is_complete"] = True
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


async def process_document(file_path: str, state: ProcessingState) -> Dict[str, Any]:
    """
    Process a document for fact extraction.
    
    Args:
        file_path: Path to the document to process
        state: Processing state
        
    Returns:
        Dict with processing results
    """
    import os
    import hashlib
    
    # Create data directory if it doesn't exist
    os.makedirs("src/fact_extract/data", exist_ok=True)
    
    # Check if file has already been processed
    if file_path in state.processed_files:
        print(f"File {file_path} has already been processed in this session.")
        return {
            "status": "skipped",
            "reason": "already_processed_in_session",
            "file_path": file_path
        }
    
    # Read file content
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        error_msg = f"Error reading file {file_path}: {str(e)}"
        state.add_error(file_path, error_msg)
        return {
            "status": "error",
            "error": error_msg,
            "file_path": file_path
        }
    
    # Generate document hash for duplicate detection
    document_hash = hashlib.md5(content.encode()).hexdigest()
    
    # Check if document has already been processed by checking chunks repository
    from fact_extract.storage.chunk_repository import ChunkRepository
    chunk_repo = ChunkRepository()
    existing_chunks = chunk_repo.get_all_chunks()
    
    # Check if all chunks for this document have had all facts extracted
    all_chunks_processed = True
    chunks_to_process = []
    
    for chunk in existing_chunks:
        if chunk.get("document_hash") == document_hash:
            # Document exists, check if all facts have been extracted
            if not chunk.get("all_facts_extracted", False):
                all_chunks_processed = False
                chunks_to_process.append(chunk)
    
    if all_chunks_processed and any(chunk.get("document_hash") == document_hash for chunk in existing_chunks):
        print(f"Document with hash {document_hash} has already been fully processed.")
        state.complete_file(file_path)
        return {
            "status": "skipped",
            "reason": "already_processed_in_repository",
            "file_path": file_path,
            "document_hash": document_hash
        }
    
    # If some chunks need further processing, we'll continue with those
    if chunks_to_process:
        print(f"Document with hash {document_hash} has {len(chunks_to_process)} chunks that need further processing.")
    
    # Start processing
    state.start_processing(file_path)
    
    # Create initial state for workflow
    document_name = os.path.basename(file_path)
    workflow_state = create_initial_state(
        input_text=content,
        document_name=document_name,
        source_url=""
    )
    
    # Run workflow
    try:
        # Create workflow
        workflow, input_key = create_workflow(chunk_repo, fact_repo)
        
        # Execute workflow
        result = await workflow.ainvoke({input_key: content})
        
        # Extract facts from result
        facts = []
        for fact in result.get("extracted_facts", []):
            if fact.get("verification_status") == "verified":
                facts.append(fact)
                state.add_fact(file_path, fact)
        
        # Mark all chunks as having all facts extracted
        for chunk in result.get("chunks", []):
            chunk_index = chunk.get("index")
            chunk_repo.update_chunk_status(
                document_name=document_name,
                chunk_index=chunk_index,
                status="processed",
                all_facts_extracted=True
            )
        
        # Mark file as processed
        state.complete_file(file_path)
        
        return {
            "status": "success",
            "facts": facts,
            "file_path": file_path,
            "document_hash": document_hash
        }
        
    except Exception as e:
        error_msg = f"Error processing file {file_path}: {str(e)}"
        state.add_error(file_path, error_msg)
        return {
            "status": "error",
            "error": error_msg,
            "file_path": file_path
        } 
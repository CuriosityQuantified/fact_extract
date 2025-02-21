"""
LangGraph nodes for the fact extraction workflow.
Each node represents a discrete step in our processing pipeline.
"""

from typing import Tuple, Annotated
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langgraph.prebuilt import ToolExecutor
from langgraph.graph import END, StateGraph

from ..models.state import WorkflowState, TextChunk, Fact


def create_chunker_node():
    """Creates a node that splits input text into chunks using RecursiveCharacterTextSplitter.
    
    The splitter uses a recursive approach to split text on multiple characters:
    1. First tries to split on double newlines (paragraphs)
    2. Then single newlines
    3. Then periods (sentences)
    4. Finally, splits on spaces if needed
    
    This ensures more natural text chunks that preserve context.
    """
    # Initialize the text splitter
    text_splitter = RecursiveCharacterTextSplitter(
        separators=["\n\n", "\n", ".", " "],  # Split first by paragraph, then by sentence, then by word
        chunk_size=500,  # Target chunk size in characters
        chunk_overlap=50,  # Overlap between chunks to maintain context
        length_function=len,  # Use character count for length
        is_separator_regex=False  # Treat separators as literal strings
    )
    
    def chunker(state: WorkflowState) -> WorkflowState:
        try:
            # Split the text into chunks
            chunks = text_splitter.split_text(state.input_text)
            
            # Convert to TextChunk objects
            state.chunks = [
                TextChunk(
                    content=chunk.strip(),
                    index=i,
                    metadata={
                        "char_length": len(chunk),
                        "separator_used": next(
                            sep for sep in text_splitter.separators 
                            if sep in chunk
                        ) if any(sep in chunk for sep in text_splitter.separators) else None
                    }
                )
                for i, chunk in enumerate(chunks)
                if chunk.strip()  # Skip empty chunks
            ]
            
        except Exception as e:
            state.add_error(f"Error in chunking: {str(e)}")
            # Create a single chunk with the entire text if chunking fails
            state.chunks = [TextChunk(content=state.input_text, index=0, metadata={"error": str(e)})]
            
        return state
    
    return chunker


def create_extractor_node():
    """Creates a node that extracts facts from a chunk of text using GPT-4."""
    # Initialize LLM
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    
    # Create prompt template
    prompt = ChatPromptTemplate.from_messages([
        ("system", """You are a precise fact extractor specializing in technical content. Extract clear, verifiable facts from the given text.

Guidelines for fact extraction:
1. Focus on specific, verifiable information:
   - Numerical data and statistics
   - Dates and timelines
   - Named entities (companies, technologies, locations)
   - Specific achievements or milestones
   - Technical specifications or measurements

2. For each fact:
   - Extract it verbatim from the text - do not paraphrase or modify
   - Ensure it's factual (not opinion, speculation, or general statements)
   - Include relevant context if needed for clarity
   - Assign a confidence score (0.0-1.0):
     * 1.0: Explicit, specific fact with numbers/dates
     * 0.8-0.9: Clear fact but without specific metrics
     * 0.5-0.7: Fact that requires some context/interpretation
     * <0.5: Facts with uncertainty or requiring verification

Format each fact as: <fact>statement</fact> <confidence>0.95</confidence>"""),
        ("user", "{text}")
    ])
    
    def extract_facts(state: WorkflowState) -> WorkflowState:
        chunk = state.next_chunk()
        if not chunk:
            state.is_complete = True
            return state
            
        try:
            # Get facts from LLM
            response = llm.invoke(prompt.format(text=chunk.content))
            
            # Parse facts from response
            # This is a simple parser - you might want more robust parsing in practice
            for line in response.content.split("\n"):
                if "<fact>" in line and "</fact>" in line:
                    # Extract fact and confidence
                    fact_text = line.split("<fact>")[1].split("</fact>")[0]
                    conf_text = line.split("<confidence>")[1].split("</confidence>")[0]
                    
                    # Create and add fact
                    fact = Fact(
                        statement=fact_text,
                        confidence=float(conf_text),
                        source_chunk=chunk.index,
                        metadata={
                            "chunk_content": chunk.content,
                            "chunk_metadata": chunk.metadata
                        }
                    )
                    state.add_fact(fact)
                    
        except Exception as e:
            state.add_error(f"Error processing chunk {chunk.index}: {str(e)}")
            
        return state
    
    return extract_facts


def create_workflow() -> Tuple[StateGraph, str]:
    """Creates the complete workflow graph.
    
    Returns:
        Tuple[StateGraph, str]: The workflow graph and the name of the input key
    """
    # Create graph
    workflow = StateGraph(WorkflowState)
    
    # Add nodes
    workflow.add_node("chunker", create_chunker_node())
    workflow.add_node("extractor", create_extractor_node())
    
    # Define edges
    workflow.set_entry_point("chunker")
    workflow.add_edge("chunker", "extractor")
    
    # Add conditional edge from extractor
    workflow.add_conditional_edges(
        "extractor",
        lambda x: "end" if x.is_complete else "extractor",
        {
            "end": END,
            "extractor": "extractor"
        }
    )
    
    # Compile graph
    workflow.compile()
    
    return workflow, "input_text" 
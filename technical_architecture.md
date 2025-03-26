# Fact Extraction System: Technical Architecture

## 1. System Overview

The fact extraction system is a pipeline that processes documents to extract factual statements, validate them, and store them for later retrieval and searching. The system follows a workflow-based architecture using LangGraph for orchestrating the various processing steps.

Key features:
- Document chunking and processing
- Fact extraction using LLMs
- Fact validation and verification
- Excel-based persistence
- Vector-based semantic search
- Gradio-based GUI interface
- Error handling and recovery mechanisms
- Duplicate detection
- Fact approval/rejection workflow

## 2. Core Components

### 2.1 State Models (`src/models/state.py`)

The state models define the data structures that flow through the workflow:

```python
# Core state models
class TextChunkDict(TypedDict):
    content: str           # Text content of the chunk
    index: int             # Position in the original text
    metadata: NotRequired[Dict]  # Additional metadata

class FactDict(TypedDict):
    statement: str         # The factual statement
    source_chunk: int      # Index of the source chunk
    document_name: str     # Name of source document
    source_url: str        # URL of source
    original_text: str     # Original text from which fact was extracted
    metadata: NotRequired[Dict]  # Additional metadata
    timestamp: str         # Extraction timestamp
    verification_status: str  # Status of verification
    verification_reason: NotRequired[str]  # Reason for verification decision

class WorkflowStateDict(TypedDict):
    session_id: UUID       # Session identifier
    input_text: str        # Original input text
    document_name: str     # Document name/title
    source_url: str        # Source URL
    chunks: List[TextChunkDict]  # Text chunks to process
    current_chunk_index: int  # Current chunk being processed
    extracted_facts: List[FactDict]  # Extracted facts
    memory: NotRequired[Dict]  # Persistent memory
    last_processed_time: NotRequired[str]  # Last processing timestamp
    errors: List[str]      # Errors encountered
    is_complete: bool      # Whether processing is complete
```

The `ProcessingState` class tracks overall document processing:

```python
@dataclass
class ProcessingState:
    processed_files: set = field(default_factory=set)  # Processed files
    current_file: Optional[str] = None                 # Currently processing file
    facts: Dict[str, List[Dict[str, Any]]] = field(default_factory=dict)  # Extracted facts
    start_time: Optional[datetime] = None              # Processing start time
    errors: List[Dict[str, Any]] = field(default_factory=list)  # Processing errors
```

### 2.2 Storage Components

#### 2.2.1 ChunkRepository (`src/storage/chunk_repository.py`)

Manages text chunks with Excel persistence:

```python
class ChunkRepository:
    def __init__(self, excel_path: str = "src/data/all_chunks.xlsx"):
        self.chunks: Dict[str, Dict[int, Dict[str, Any]]] = {}
        self.excel_path = excel_path
        self.lock = _chunk_repo_lock  # Thread-safety lock
        self._load_from_excel()
        
    # Key methods:
    def store_chunk(self, chunk_data: Dict[str, Any]) -> None
    def update_chunk_status(self, document_name, chunk_index, status, contains_facts, error_message, all_facts_extracted)
    def is_chunk_processed(self, chunk_data: Dict[str, Any], document_name: str) -> bool
    def get_chunk(self, document_name: str, chunk_index: int) -> Optional[Dict[str, Any]]
    def get_all_chunks(self) -> List[Dict[str, Any]]
```

#### 2.2.2 FactRepository (`src/storage/fact_repository.py`)

Manages extracted facts with Excel persistence and vector search:

```python
class FactRepository:
    def __init__(self, excel_path: str = "data/all_facts.xlsx", 
                 vector_store_dir: str = "src/data/embeddings",
                 collection_name: str = "fact_embeddings"):
        self.facts: Dict[str, List[Dict[str, Any]]] = {}
        self.excel_path = excel_path
        self.valid_statuses = ["verified", "rejected", "pending"]
        self.vector_store = ChromaFactStore(persist_directory=vector_store_dir, collection_name="fact_embeddings_new")
        self._load_from_excel()
    
    # Key methods:
    def store_fact(self, fact_data: Dict[str, Any]) -> str
    def get_facts(self, document_name: str, verified_only: bool = True) -> List[Dict[str, Any]]
    def get_all_facts(self, verified_only: bool = True) -> List[Dict[str, Any]]
    def update_fact(self, document_name: str, old_statement: str, new_data: Dict[str, Any]) -> bool
    def search_facts(self, query: str, n_results: int = 5, filter_criteria: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]
    def is_duplicate_fact(self, fact_data: Dict[str, Any]) -> bool
```

#### 2.2.3 RejectedFactRepository (`src/storage/fact_repository.py`)

Manages rejected facts with Excel persistence:

```python
class RejectedFactRepository:
    def __init__(self, excel_path: str = "data/rejected_facts.xlsx"):
        self.rejected_facts: Dict[str, List[Dict[str, Any]]] = {}
        self.excel_path = excel_path
        self._load_from_excel()
    
    # Key methods:
    def store_rejected_fact(self, fact_data: Dict[str, Any]) -> None
    def get_rejected_facts(self, document_name: str) -> List[Dict[str, Any]]
    def get_all_rejected_facts(self) -> List[Dict[str, Any]]
```

#### 2.2.4 ChromaFactStore (`src/search/vector_store.py`)

Manages semantic search with ChromaDB:

```python
class ChromaFactStore:
    def __init__(self, persist_directory: str = "src/data/embeddings", 
                 collection_name: str = "fact_embeddings",
                 embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"):
        os.makedirs(persist_directory, exist_ok=True)
        self.client = chromadb.PersistentClient(path=persist_directory)
        self.embedding_function = embedding_functions.SentenceTransformerEmbeddingFunction(model_name=embedding_model)
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            embedding_function=self.embedding_function,
            metadata={"hnsw:space": "cosine"}
        )
    
    # Key methods:
    def add_fact(self, fact_id: str, statement: str, metadata: Dict[str, Any]) -> None
    def add_facts_batch(self, fact_ids: List[str], statements: List[str], metadatas: List[Dict[str, Any]]) -> None
    def search_facts(self, query: str, n_results: int = 5, filter_criteria: Optional[Dict[str, Any]] = None) -> Dict[str, Any]
    def delete_fact(self, fact_id: str) -> None
    def get_fact_count(self) -> int
```

### 2.3 Workflow Nodes (`src/graph/nodes.py`)

The workflow consists of three main nodes:

#### 2.3.1 Chunker Node

```python
async def chunker_node(state: WorkflowStateDict) -> WorkflowStateDict:
    """Split input text into chunks and manage chunk storage."""
    # 1. Generate document hash for duplicate detection
    document_hash = hashlib.md5(state['input_text'].encode()).hexdigest()
    
    # 2. Check if document already processed
    existing_chunks = chunk_repo.get_all_chunks()
    for chunk in existing_chunks:
        if chunk.get("document_hash") == document_hash:
            state["is_complete"] = True
            state["chunks"] = []
            return state
    
    # 3. Create text splitter with word-based chunking
    text_splitter = RecursiveCharacterTextSplitter(
        separators=["\n\n", "\n", ". ", " "],
        chunk_size=750,  # 750 words per chunk
        chunk_overlap=50,  # 50 words overlap
        length_function=lambda x: len(x.split()),
        add_start_index=True,
        strip_whitespace=True
    )
    
    # 4. Create Document object and split
    initial_doc = Document(page_content=state["input_text"], metadata={...})
    text_splitter = text_splitter.split_documents([initial_doc])
    
    # 5. Process chunks and store in repository
    new_chunks = []
    for i, doc in enumerate(text_splitter):
        chunk = doc.page_content
        if not chunk.strip(): continue
        
        chunk_data: TextChunkDict = {...}
        
        # 6. Skip already processed chunks
        if chunk_repo.is_chunk_processed(chunk_data, state["document_name"]):
            continue
        
        # 7. Store new chunk as pending
        chunk_repo.store_chunk({...})
        new_chunks.append(chunk_data)
    
    # 8. Update state
    state["chunks"] = new_chunks
    state["current_chunk_index"] = 0
    state["is_complete"] = len(new_chunks) == 0
    
    return state
```

#### 2.3.2 Extractor Node

```python
async def extractor_node(state: WorkflowStateDict) -> WorkflowStateDict:
    """Extract facts from the current chunk."""
    # 1. Get current chunk
    current_index = state["current_chunk_index"]
    if current_index >= len(state["chunks"]):
        state["is_complete"] = True
        return state
    
    current_chunk = state["chunks"][current_index]
    
    # 2. Update chunk status to processing
    await chunk_repo.async_update_chunk_status(
        state["document_name"],
        current_chunk["index"],
        "processing"
    )
    
    # 3. Prepare prompt for LLM
    prompt = ChatPromptTemplate.from_messages([
        HumanMessage(content=FACT_EXTRACTOR_PROMPT.format(
            text=current_chunk["content"]
        ))
    ])
    
    # 4. Call LLM with retries for rate limiting
    try:
        with_backoff = True
        max_retries = 5
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                chain = prompt | llm
                response = await chain.ainvoke({})
                break
            except Exception as e:
                if "rate limit" in str(e).lower() and with_backoff:
                    retry_count += 1
                    wait_time = 2 ** retry_count  # Exponential backoff
                    await asyncio.sleep(wait_time)
                else:
                    raise
        
        # 5. Parse facts from response
        facts_xml = response.content
        # Extract facts from XML response
        # ...
        
        # 6. Store extracted facts in state
        contains_facts = False
        if extracted_facts:
            contains_facts = True
            for fact in extracted_facts:
                state["extracted_facts"].append({
                    "statement": fact,
                    "source_chunk": current_chunk["index"],
                    "document_name": state["document_name"],
                    "source_url": state["source_url"],
                    "original_text": current_chunk["content"],
                    "timestamp": datetime.now().isoformat(),
                    "verification_status": "pending",
                })
        
        # 7. Update chunk status
        await chunk_repo.async_update_chunk_status(
            state["document_name"],
            current_chunk["index"],
            "processed",
            contains_facts=contains_facts
        )
        
    except Exception as e:
        # 8. Handle errors
        error_message = str(e)
        state["errors"].append(f"Error extracting facts from chunk {current_index}: {error_message}")
        
        # 9. Update chunk with error status
        await chunk_repo.async_update_chunk_status(
            state["document_name"],
            current_chunk["index"],
            "error",
            error_message=error_message
        )
    
    # 10. Move to next chunk
    state["current_chunk_index"] = current_index + 1
    
    # 11. Check if complete
    if state["current_chunk_index"] >= len(state["chunks"]):
        state["is_complete"] = True
    
    return state
```

#### 2.3.3 Validator Node

```python
async def validator_node(state: WorkflowStateDict) -> WorkflowStateDict:
    """Validate extracted facts."""
    # Skip if no facts extracted
    if not state["extracted_facts"]:
        return state
    
    validated_facts = []
    rejected_facts = []
    
    # Process each extracted fact
    for fact in state["extracted_facts"]:
        # Skip facts that already have a verification status other than pending
        if fact.get("verification_status") != "pending":
            continue
        
        # Prepare verification prompt
        prompt = ChatPromptTemplate.from_messages([
            HumanMessage(content=FACT_VERIFICATION_PROMPT.format(
                statement=fact["statement"],
                context=fact["original_text"]
            ))
        ])
        
        # Call LLM with retries for rate limiting
        try:
            # Similar retry logic as extractor_node
            # ...
            
            chain = prompt | llm
            response = await chain.ainvoke({})
            
            # Parse XML response to get verification result
            # ...
            
            # Update fact with verification results
            fact["verification_status"] = is_valid
            fact["verification_reason"] = reason
            fact["verification_reasoning"] = reasoning
            
            # Add to appropriate list
            if is_valid == "verified":
                # Store verified fact
                fact_id = fact_repo.store_fact(fact)
                validated_facts.append(fact)
            else:
                # Store rejected fact
                rejected_fact_repo.store_rejected_fact(fact)
                rejected_facts.append(fact)
                
        except Exception as e:
            # Handle validation errors
            # ...
    
    # Update chunk status to mark all facts as extracted
    for chunk in state["chunks"]:
        await chunk_repo.async_update_chunk_status(
            state["document_name"],
            chunk["index"],
            "processed",
            all_facts_extracted=True
        )
    
    return state
```

### 2.4 Workflow Definition

```python
def create_workflow(chunk_repo: ChunkRepository, fact_repo: FactRepository) -> Tuple[StateGraph, str]:
    """Create the workflow graph."""
    # Create graph
    workflow = StateGraph(WorkflowStateDict)
    
    # Add nodes
    workflow.add_node("chunker", chunker_node)
    workflow.add_node("extractor", extractor_node)
    workflow.add_node("validator", validator_node)
    
    # Define edges
    workflow.add_edge("chunker", "extractor")
    workflow.add_edge("extractor", should_continue)
    workflow.add_conditional_edges(
        "should_continue",
        {
            "continue": "extractor",
            "complete": "validator",
        }
    )
    workflow.add_edge("validator", END)
    
    # Set entry point
    workflow.set_entry_point("chunker")
    
    return workflow, "input_text"
```

### 2.5 Document Processing

```python
async def process_document(file_path: str, state: ProcessingState, max_concurrent_chunks: int = None) -> Dict[str, Any]:
    """Process a document to extract facts."""
    # 1. Read file content
    document_name = os.path.basename(file_path)
    document_content = ""
    
    try:
        document_content = extract_text_from_file(file_path)
    except Exception as e:
        state.add_error(file_path, f"Error reading file: {str(e)}")
        return {"status": "error", "message": f"Error reading file: {str(e)}"}
    
    # 2. Check for empty content
    if not document_content.strip():
        state.add_error(file_path, "File content is empty")
        return {"status": "error", "message": "File content is empty"}
    
    # 3. Create initial workflow state
    workflow_state = create_initial_state(
        input_text=document_content,
        document_name=document_name,
        source_url=file_path
    )
    
    # 4. Run the workflow
    try:
        # Initialize chunking
        chunker_repo = ChunkRepository()
        fact_repo = FactRepository()
        rejected_fact_repo = RejectedFactRepository()
        
        # Create workflow
        workflow, input_key = create_workflow(chunker_repo, fact_repo)
        
        # Process chunks in parallel
        result = await parallel_process_chunks(
            workflow_state["chunks"],
            document_name,
            file_path,
            max_concurrent_chunks=max_concurrent_chunks or MAX_CONCURRENT_CHUNKS,
            chunk_repo=chunker_repo,
            fact_repo=fact_repo,
            rejected_fact_repo=rejected_fact_repo,
            llm=llm
        )
        
        # 5. Update processing state
        facts = result.get("facts", [])
        for fact in facts:
            state.add_fact(file_path, fact)
            
        # 6. Mark file as processed
        state.complete_file(file_path)
        
        return {
            "status": "success",
            "facts": facts,
            "chunks_processed": result.get("chunks_processed", 0),
            "chunks_with_facts": result.get("chunks_with_facts", 0),
            "errors": result.get("errors", [])
        }
        
    except Exception as e:
        state.add_error(file_path, f"Error processing document: {str(e)}")
        return {"status": "error", "message": f"Error processing document: {str(e)}"}
```

## 3. GUI Interface and Backend Integration

### 3.1 GUI Architecture Overview

The GUI is implemented in `src/gui/app.py` and launched via `src/run_gui.py`. It's built using Gradio, a Python library for creating web interfaces for machine learning models. The GUI consists of multiple tabs for different functionality:

1. **Upload Tab**: For uploading documents and viewing extraction results
2. **Fact Review Tab**: For reviewing, approving, rejecting, and editing extracted facts
3. **Fact Search Tab**: For searching facts using semantic search
4. **Export Tab**: For exporting verified facts to different formats (CSV, JSON, Markdown)

The GUI provides a complete frontend for interacting with the fact extraction system while abstracting away the complexity of the backend processing.

### 3.2 Main GUI Components (`src/gui/app.py`)

#### 3.2.1 FactExtractionGUI Class

This is the main class that implements the GUI and its connection to the backend:

```python
class FactExtractionGUI:
    def __init__(self):
        # Application state
        self.state = ProcessingState()              # Tracks document processing
        self.processing = False                     # Flag for ongoing processing
        self.chat_history = []                      # Chat-like status messages
        self.temp_files = []                        # Temporary file management
        self.facts_data = {}                        # In-memory facts data structure
        
        # Theme configuration
        self.theme = gr.themes.Soft(
            primary_hue="blue",
            secondary_hue="gray",
        )
        
        # Connect to backend repositories
        self.chunk_repo = ChunkRepository()         # Chunk storage
        self.fact_repo = FactRepository()           # Fact storage
        self.rejected_fact_repo = RejectedFactRepository()  # Rejected fact storage
        
        # Create workflow connection
        self.workflow, self.input_key = create_workflow(self.chunk_repo, self.fact_repo)
        
        # Debug mode flag
        self.debug = True
```

### 3.3 Backend Integration Points

#### 3.3.1 Document Processing Interface

The GUI connects to the backend workflow through the `process_files` method, which processes uploaded files:

```python
async def process_files(self, files):
    """Process uploaded files to extract facts."""
    self.processing = True
    facts = {}
    
    try:
        for file in files:
            try:
                # Validate file
                if not is_valid_file(file.name):
                    error_msg = f"Invalid file: {file.name}. Must be one of: {format_file_types()}"
                    self.chat_history.append(create_message(f"⚠️ {error_msg}"))
                    yield self.chat_history, self.format_facts_summary(facts), *self.format_tabs_content(facts), []
                    continue
                    
                # Process file
                self.chat_history.append(create_message(f"📄 Processing {file.name}...", is_user=True))
                yield self.chat_history, self.format_facts_summary(facts), *self.format_tabs_content(facts), []
                
                # Save to temp directory
                temp_path = get_temp_path(file.name)
                shutil.copy2(file.name, temp_path)
                self.temp_files.append(temp_path)
                
                # Start processing in state
                self.state.start_processing(temp_path)
                
                # Extract text from file
                self.chat_history.append(create_message(f"📄 Extracting text from {file.name}..."))
                yield self.chat_history, self.format_facts_summary(facts), *self.format_tabs_content(facts), []
                
                # Process the document using LangGraph workflow
                result = await self.workflow.ainvoke({
                    self.input_key: {
                        "file_path": temp_path
                    }
                })
                
                # Update facts data
                if result["status"] == "success":
                    # ... process successful result ...
                else:
                    # ... handle errors ...
            except Exception as e:
                # ... handle exceptions ...
```

#### 3.3.2 Fact Management Interface

The GUI interacts with the backend repositories for fact management through several methods:

```python
def update_fact(self, fact_id, statement, status, reason):
    """Update a fact in the repositories."""
    self.debug_print(f"Updating fact {fact_id}: status={status}, statement={statement[:30]}...")
    
    try:
        # Find the fact in memory or repositories
        fact_to_update = None
        for fact in self.find_fact_by_id(fact_id):
            fact_to_update = fact
            break
            
        if not fact_to_update:
            return f"Error: Fact with ID {fact_id} not found", None
        
        # Get current data
        current_statement = fact_to_update.get("statement", "")
        current_doc_name = fact_to_update.get("document_name", "")
        current_status = fact_to_update.get("verification_status", "pending")
        
        # Create a deep copy to avoid modifying the original
        import copy
        updated_fact = copy.deepcopy(fact_to_update)
        
        # Update the fact data
        updated_fact["statement"] = statement
        updated_fact["verification_status"] = status
        updated_fact["verification_reason"] = reason
        
        # Status transition actions
        if current_status != status:
            if status == "verified":
                # Move from rejected to verified
                if current_status == "rejected":
                    # Remove from rejected repo
                    self.rejected_fact_repo.remove_fact(current_doc_name, current_statement)
                # Store in fact repo
                fact_id = self.fact_repo.store_fact(updated_fact)
            elif status == "rejected":
                # Move from verified to rejected
                if current_status == "verified":
                    # Remove from verified repo
                    self.fact_repo.remove_fact(current_doc_name, current_statement)
                # Store in rejected repo
                self.rejected_fact_repo.store_rejected_fact(updated_fact)
        else:
            # Same status, just update the fact
            if status == "verified":
                self.fact_repo.update_fact(current_doc_name, current_statement, updated_fact)
            elif status == "rejected":
                self.rejected_fact_repo.update_rejected_fact(current_doc_name, current_statement, updated_fact)
        
        # Refresh facts data
        self.refresh_facts_data()
        
        # Get updated fact choices for the dropdown
        all_facts, fact_choices = self.get_facts_for_review()
        
        return "Fact updated", fact_choices
    except Exception as e:
        self.debug_print(f"Error updating fact: {str(e)}")
        return f"Error updating fact: {str(e)}", None
```

#### 3.3.3 Search Interface

The GUI connects to the vector search functionality through the `search_facts` method:

```python
def search_facts(self, query: str, n_results: int = 5) -> Tuple[str, str]:
    """Search for facts using semantic search."""
    self.debug_print(f"Searching for facts with query: '{query}'")
    
    try:
        # Ensure we have fresh fact data
        self.refresh_facts_data()
        
        # Get all verified facts
        all_facts = self.fact_repo.get_all_facts(verified_only=True)
        self.debug_print(f"Got {len(all_facts)} facts to search through")
        
        if not all_facts:
            return "No facts available to search.", "No facts in the database."
            
        # Perform search using the vector store
        search_results = self.fact_repo.search_facts(
            query=query,
            n_results=n_results
        )
        
        # Format results as Markdown
        results_md = f"# Search Results for: '{query}'\n\n"
        stats_md = f"Found {len(search_results)} relevant facts."
        
        for i, result in enumerate(search_results):
            fact = result["fact"]
            similarity = result["similarity"]
            doc_name = fact.get("document_name", "Unknown")
            
            results_md += f"## Result {i+1} (Score: {similarity:.2f})\n\n"
            results_md += f"**Document:** {doc_name}\n\n"
            results_md += f"**Fact:** {fact.get('statement', 'No statement')}\n\n"
            
            if "original_text" in fact and fact["original_text"]:
                results_md += f"**Source Text:**\n\n> {fact['original_text']}\n\n"
                
            results_md += "---\n\n"
            
        return results_md, stats_md
    except Exception as e:
        self.debug_print(f"Error searching facts: {str(e)}")
        return f"Error searching facts: {str(e)}", "Search failed."
```

### 3.4 GUI Structure and Components

The GUI is built using Gradio's `Blocks` API, which allows for a flexible layout with multiple tabs:

```python
def build_interface(self) -> gr.Blocks:
    """Build the Gradio interface."""
    self.debug_print("Building Gradio interface")
    
    # Create interface with custom theme
    interface = gr.Blocks(
        title="Fact Extraction System",
        theme=self.theme,
        css="""
        /* Custom CSS goes here */
        """
    )
    
    # Build the interface layout
    with interface:
        gr.Markdown("# Fact Extraction System")
        
        # Main tabs
        with gr.Tabs() as tabs:
            # Upload tab
            with gr.TabItem("Upload", elem_id="upload-tab"):
                # File upload components
                with gr.Row():
                    with gr.Column(scale=1):
                        # File upload area
                        file_upload = gr.Files(
                            label="Upload Documents",
                            file_count="multiple",
                            file_types=list(ALLOWED_EXTENSIONS),
                            elem_id="file-upload"
                        )
                        
                        # Upload button
                        upload_button = gr.Button("Extract Facts", variant="primary")
                        
                    with gr.Column(scale=2):
                        # Chat-like message history for status updates
                        chatbot = gr.Chatbot(
                            value=[],
                            elem_id="chat-history",
                            height=400,
                            show_copy_button=True
                        )
                
                # Facts summary section
                with gr.Row():
                    facts_summary = gr.Markdown("No facts extracted yet.")
                
                # Facts tabs for different views
                with gr.Row():
                    with gr.Tabs(elem_id="facts-tabs") as facts_tabs:
                        # ... Tab definitions ...
            
            # Fact Review tab
            with gr.TabItem("Fact Review", elem_id="fact-review-tab"):
                # ... Fact review components ...
            
            # Fact Search tab  
            with gr.TabItem("Fact Search", elem_id="fact-search-tab"):
                # ... Search components ...
                
            # Export tab
            with gr.TabItem("Export", elem_id="export-tab"):
                # ... Export components ...
        
        # Set up event handlers
        # Connect process_files to the upload button
        upload_button.click(
            fn=self.process_files,
            inputs=[file_upload],
            outputs=[
                chatbot,  
                facts_summary,
                all_submissions,
                approved_facts,
                rejected_facts,
                errors_display,
                fact_selector
            ]
        )
        
        # ... Other event handlers ...
    
    return interface
```

### 3.5 System Integration

The GUI is initialized and started via the `run_gui.py` script:

```python
# src/run_gui.py
def main():
    """Run the Fact Extraction GUI."""
    print("Starting Fact Extraction GUI...")
    app = create_app()
    app.launch(share=False)

if __name__ == "__main__":
    main()
```

The `create_app` function is defined in `src/gui/app.py`:

```python
def create_app():
    """Create and configure the Gradio app."""
    print("Creating Fact Extraction GUI application")
    gui = FactExtractionGUI()
    interface = gui.build_interface()
    print("Interface built successfully")
    return interface
```

### 3.6 Transaction Support and Data Consistency

The GUI implements transaction-like support for fact operations to ensure data consistency between in-memory state and Excel storage:

```python
def update_fact_with_transaction(self, fact_id, statement, status, reason):
    """Update a fact using a transaction-like pattern to ensure consistency."""
    # Create a backup of the current state
    current_state = self._snapshot_current_state()
    
    try:
        # Perform the update operation
        result, facts_summary = self.update_fact(fact_id, statement, status, reason)
        
        # Force a save of Excel files
        self.fact_repo._save_to_excel()
        self.rejected_fact_repo._save_to_excel()
        
        # Verify data consistency
        if self._verify_data_consistency():
            # Synchronize repositories
            self.synchronize_repositories()
            # Refresh fact choices
            all_facts, fact_choices = self.get_facts_for_review()
            return result, fact_choices
        else:
            # Roll back on inconsistency
            self._restore_state(current_state)
            return "Error: Data consistency check failed. Changes rolled back.", None
    except Exception as e:
        # Roll back on error
        self._restore_state(current_state)
        return f"Error during update: {str(e)}. Changes rolled back.", None
```

### 3.7 Export Functionality

The GUI provides export capabilities for verified facts in different formats:

```python
def export_facts_to_csv(self, output_path: str) -> str:
    """Export verified facts to CSV format."""
    try:
        # Get all verified facts
        facts = self.fact_repo.get_all_facts(verified_only=True)
        
        if not facts:
            return "No verified facts to export."
        
        # Create DataFrame
        df = pd.DataFrame(facts)
        
        # Ensure output path has .csv extension
        if not output_path.lower().endswith('.csv'):
            output_path += '.csv'
            
        # Export to CSV
        df.to_csv(output_path, index=False)
        
        return f"Successfully exported {len(facts)} facts to {output_path}"
    except Exception as e:
        return f"Error exporting facts to CSV: {str(e)}"
```

Similar methods exist for JSON and Markdown export formats.

## 4. Vector Search Implementation

### 4.1 Search Models (`src/models/search_models.py`)

```python
class SearchableFact(BaseModel):
    """Model representing a fact that can be searched semantically."""
    id: str                 # Unique identifier for the fact
    statement: str          # The factual statement
    document_name: str      # Source document name
    chunk_index: int        # Chunk index within document
    metadata: Dict[str, Any] = Field(default_factory=dict)  # Additional metadata
    embedding: Optional[List[float]] = None  # Vector embedding of the fact
    extracted_at: datetime = Field(default_factory=datetime.now)  # When the fact was extracted
```

### 4.2 ChromaDB Integration (`src/search/vector_store.py`)

The system uses ChromaDB with sentence-transformers to provide semantic search:

```python
class ChromaFactStore:
    def __init__(self, persist_directory: str = "src/data/embeddings", 
                 collection_name: str = "fact_embeddings",
                 embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"):
        # Initialize ChromaDB client and collection
        # ...
    
    def add_fact(self, fact_id: str, statement: str, metadata: Dict[str, Any]) -> None:
        # Add fact to vector store
        self.collection.add(
            ids=[fact_id],
            documents=[statement],
            metadatas=[metadata]
        )
    
    def search_facts(self, query: str, n_results: int = 5, 
                     filter_criteria: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        # Query the collection
        results = self.collection.query(
            query_texts=[query],
            n_results=n_results,
            where=filter_criteria
        )
        return results
```

## 5. System Workflows

### 5.1 Document Processing Workflow

1. **Document Upload**: User uploads a document through the GUI
2. **Text Extraction**: System extracts text from the document
3. **Chunking**: Text is split into manageable chunks (750 words with 50 word overlap)
4. **Duplicate Detection**: System checks if document has already been processed using MD5 hash
5. **Fact Extraction**: Each chunk is processed to extract factual statements
6. **Fact Validation**: Each extracted fact is validated against verification criteria
7. **Storage**: Valid facts are stored in the fact repository, rejected facts in the rejected fact repository
8. **Vector Indexing**: Facts are indexed in the vector store for semantic search
9. **Results Display**: Extracted facts are displayed in the GUI for review

### 5.2 Fact Review Workflow

1. **Fact Display**: Facts are displayed in a tabbed interface by document
2. **Fact Selection**: User selects a fact for review
3. **Fact Review**: User reviews the fact and can edit, approve, or reject it
4. **Status Update**: Fact status is updated in the repositories
5. **Vector Store Update**: If approved, fact is updated in the vector store

### 5.3 Search Workflow

1. **Query Input**: User enters a search query
2. **Vector Search**: Query is converted to a vector and compared to fact vectors
3. **Results Ranking**: Facts are ranked by similarity to the query
4. **Results Display**: Top matching facts are displayed with relevance scores

## 6. Libraries and Dependencies

- **LangGraph**: For workflow orchestration (`StateGraph`, nodes, edges)
- **LangChain**: For LLM integration, prompt templates, and text splitting
- **Gradio**: For GUI implementation
- **ChromaDB**: For vector storage and semantic search
- **Sentence-Transformers**: For generating embeddings
- **Pandas**: For Excel file operations
- **PyPDF**, **python-docx**: For document parsing
- **asyncio**: For asynchronous processing
- **pydantic**: For data validation and schemas

## 7. Error Handling and Recovery

The system implements robust error handling:
- **Rate Limiting**: Exponential backoff for LLM API rate limits
- **Network Errors**: Retries with backoff for network disruptions
- **Chunk Status Tracking**: Each chunk's processing status is tracked
- **Transaction Support**: GUI operations use snapshot-based transactions
- **Logging**: Extensive logging for debugging

## 8. Data Persistence

- **Chunks**: Stored in `src/data/all_chunks.xlsx`
- **Facts**: Stored in `data/all_facts.xlsx`
- **Rejected Facts**: Stored in `data/rejected_facts.xlsx`
- **Vector Embeddings**: Stored in `src/data/embeddings/`

## 9. Future Enhancements

- PDF annotation for fact sources
- Real-time collaborative fact review
- Enhanced search filtering and metadata querying
- Integration with knowledge graphs
- Automated fact verification against reference sources
- API endpoints for programmatic access 
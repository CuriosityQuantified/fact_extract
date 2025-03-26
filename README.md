# Document Processing System

A robust document processing system that extracts content from various document formats with support for edge cases and special characters.

## Supported Formats

- Excel (.xlsx, .xls)
- CSV (with auto-dialect detection)
- Word (.docx, .doc)
- PDF (with metadata extraction)

## Features

- Parallel document processing
- Robust error handling
- Multiple character encoding support
- Memory-efficient processing
- Special character support (Unicode, CJK, emojis)
- Auto-detection of document structure
- Excel-based storage for chunks and facts
- Duplicate detection for documents and facts

## Parallel Processing

The system now features parallel chunk processing that significantly improves performance for large documents:

### Key Benefits

- **Faster Processing**: Process multiple document chunks simultaneously
- **Configurable Parallelism**: Adjust the number of concurrent workers based on your system's capabilities
- **Efficient Resource Usage**: Optimized for I/O-bound operations with asyncio
- **Graceful Error Handling**: Individual chunk failures don't affect the entire process
- **Thread-Safe Operations**: Robust synchronization for shared resources

### Configuration

You can configure parallel processing settings using:

1. **Environment Variables**:
   ```bash
   # Set maximum concurrent chunks
   export MAX_CONCURRENT_CHUNKS=8
   
   # Configure chunk size settings
   export CHUNK_SIZE=3000
   export CHUNK_OVERLAP=200
   
   # Set API rate limiting
   export MAX_REQUESTS_PER_MINUTE=60
   ```

2. **Configuration File**:
   The `src/config.py` file contains all configuration options with reasonable defaults:
   ```python
   # Default parallelism settings
   DEFAULT_SETTINGS = {
       "max_concurrent_chunks": 5,
       "max_requests_per_minute": 60,
       "chunk_size": 3000,
       "chunk_overlap": 200,
       # ...
   }
   ```

### Performance Benchmarking

To determine the optimal parallelism level for your system, run the included benchmark tool:

```bash
# Run benchmark with default concurrency levels (1, 2, 4, 8, 16)
venv/bin/python -m src.benchmarks your_large_document.pdf

# Test specific concurrency levels
venv/bin/python -m src.benchmarks your_large_document.pdf --levels 1 3 5 7

# Save benchmark results to a specific file
venv/bin/python -m src.benchmarks your_large_document.pdf --output results.png
```

The benchmark tool:
- Tests different concurrency levels
- Measures processing time for each level
- Calculates speedup compared to sequential processing
- Generates a plot showing performance metrics
- Recommends the optimal concurrency level for your system

### Implementation Details

- Uses asyncio for lightweight concurrent processing
- Implements semaphore-based concurrency limiting
- Ensures thread-safe repository access with locks
- Manages chunk queues efficiently
- Provides detailed progress tracking

## Installation

```bash
# Clone the repository
git clone [repository-url]
cd fact-extract-fresh

# Create virtual environment
python -m venv venv

# Activate virtual environment
# On macOS/Linux:
source venv/bin/activate
# On Windows:
# venv\Scripts\activate

# If pip is missing from the virtual environment, install it
curl https://bootstrap.pypa.io/get-pip.py -o get-pip.py
venv/bin/python get-pip.py

# Install dependencies
venv/bin/python -m pip install -r requirements.txt

# Configure OpenAI API key in .env file
echo "OPENAI_API_KEY=your_api_key_here" > .env
```

### Environment Configuration

For the system to work properly, you'll need to set up the following environment variables:

1. Create a `.env` file in the project root with:
```
OPENAI_API_KEY=your_api_key_here
```

2. Alternatively, you can set the environment variable directly in your shell:
```bash
# On macOS/Linux:
export OPENAI_API_KEY=your_api_key_here
# On Windows:
# set OPENAI_API_KEY=your_api_key_here
```

## Usage

```python
from fact_extract.utils.document_loader import DocumentLoader

async def process_documents():
    loader = DocumentLoader()
    
    # Process multiple documents
    results = await loader.process_documents([
        "documents/data.xlsx",
        "documents/report.csv",
        "documents/memo.docx",
        "documents/paper.pdf"
    ])
    
    # Each result contains:
    # - title: Document or section title
    # - content: Cleaned text content
    # - source: Original file path
    
    for result in results:
        print(f"Title: {result['title']}")
        print(f"Content: {result['content'][:100]}...")
        print("-" * 50)
```

## Data Storage

The system stores all processed chunks, extracted facts, and rejected facts in Excel files:

- **Chunks**: All document chunks are stored in `src/fact_extract/data/all_chunks.xlsx`
- **Facts**: All verified facts are stored in `src/fact_extract/data/all_facts.xlsx`
- **Rejected Facts**: All rejected facts are stored in `src/fact_extract/data/rejected_facts.xlsx`

### Storage Features

1. **Persistence**: All data is stored persistently across sessions
2. **Metadata**: Complete metadata is preserved for analysis
3. **Duplicate Detection**:
   - Document-level: Prevents reprocessing the same document multiple times
   - Fact-level: Prevents storing duplicate facts from the same or different documents
4. **Structured Format**: Data is organized in a consistent, tabular format

## Edge Cases Handled

1. Empty Files
   - Empty documents
   - Minimal valid file structures

2. Malformed Files
   - Invalid file formats
   - Corrupted content
   - Mixed delimiters in CSV

3. Large Files
   - Excel/CSV with 10,000+ rows
   - Word with 1,000+ paragraphs
   - PDF with 100+ pages

4. Special Characters
   - Unicode characters (CJK)
   - Accented characters
   - Emojis and symbols

5. Mixed Encodings
   - UTF-8 content
   - Latin1 content
   - ASCII fallback

6. Duplicate Content
   - Same document uploaded multiple times
   - Same facts appearing in different documents
   - Similar facts with minor variations

## Testing

Run the test suite:

```bash
# Run all tests
venv/bin/python -m pytest

# Run specific test files
venv/bin/python -m pytest src/fact_extract/unit_tests/test_unicode_handling.py

# Run tests with verbosity
venv/bin/python -m pytest -v

# Run specific test class
venv/bin/python -m pytest src/fact_extract/unit_tests/test_state_persistence.py::TestStatePersistence
```

### Test Structure

- All tests are located in the `src/fact_extract/unit_tests/` directory
- The test configuration is defined in `pyproject.toml`
- The system uses pytest-asyncio for testing asynchronous functions
- Some tests require the OpenAI API key to be set in the environment

### Debugging Tests

If you encounter issues with tests:

1. Ensure your virtual environment is active and all dependencies are installed
2. Verify that your OpenAI API key is correctly set in the `.env` file
3. Run specific test files with increased verbosity: `venv/bin/python -m pytest -v path/to/test_file.py`
4. For asynchronous test errors, check that the `@pytest.mark.asyncio` decorator is applied to async test functions

## License

MIT License

## GUI Usage

The system includes a web-based GUI for easy document processing and fact extraction. To use the GUI:

1. Install the required dependencies:
```bash
venv/bin/python -m pip install -r requirements.txt
```

2. Launch the GUI:
```bash
venv/bin/python -m src.fact_extract.gui.app
```

3. Access the interface:
- Open your web browser and navigate to `http://localhost:7860`
- The interface will be available at this address while the server is running

### Features

- **Document Upload**: Drag and drop or click to upload multiple documents
- **Supported Formats**: .txt, .pdf, .docx files (up to 10MB each)
- **Real-time Processing**: Watch the extraction progress in real-time
- **Interactive Results**: View extracted facts in a structured JSON format
- **Error Handling**: Clear feedback for invalid files or processing errors
- **Duplicate Detection**: Automatic detection and prevention of duplicate documents and facts
- **Persistent Storage**: All processed chunks and facts are stored in Excel files

### Usage Tips

1. **File Preparation**:
   - Ensure files are in supported formats (.txt, .pdf, .docx)
   - Files should be under 10MB
   - Text should be clear and well-formatted

2. **Processing**:
   - Upload one or more files
   - Click "Start Processing" to begin extraction
   - Monitor progress in the chat display
   - View results in the JSON output area

3. **Results**:
   - Extracted facts are displayed per document
   - Results can be copied or saved for further use
   - Processing history is maintained during the session
   - All facts are stored persistently in Excel files
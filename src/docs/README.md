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

## Installation

```bash
# Clone the repository
git clone [repository-url]
cd document-processing-system

# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
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

The system stores all processed chunks and extracted facts in Excel files:

- **Chunks**: All document chunks are stored in `data/all_chunks.xlsx`
- **Facts**: All verified facts are stored in `data/all_facts.xlsx`
- **Rejected Facts**: Facts that fail verification are stored in `data/rejected_facts.xlsx`

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
python -m pytest

# Run edge case tests
python -m pytest src/fact_extract/tests/test_document_processors_edge_cases.py

# Test Excel storage and duplicate detection
python test_excel_storage.py
```

## License

MIT License

## GUI Usage

The system includes a web-based GUI for easy document processing and fact extraction. To use the GUI:

1. Install the required dependencies:
```bash
pip install -r requirements.txt
```

2. Launch the GUI:
```bash
python -m src.fact_extract.gui.app
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
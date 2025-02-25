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

## Testing

Run the test suite:

```bash
# Run all tests
python -m pytest

# Run edge case tests
python -m pytest src/fact_extract/tests/test_document_processors_edge_cases.py
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
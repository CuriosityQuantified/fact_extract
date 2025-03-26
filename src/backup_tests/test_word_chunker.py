"""
Test script to verify word-based chunking with 750 word chunks and 50 word overlaps.
"""

import os
import sys
from pathlib import Path
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document


# Ensure the src directory is in the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Ensure the src directory is in the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))
def test_word_chunking():
    """Test word-based chunking with 750 word chunks and 50 word overlaps."""
    print("Testing word-based chunking...")
    
    # Create a test document with a known number of words
    # Generate a document with 2000 words
    words = ["word" + str(i) for i in range(2000)]
    text = " ".join(words)
    
    # Create a Document object
    doc = Document(
        page_content=text,
        metadata={"source": "test_document"}
    )
    
    # Create text splitter with word-based chunking
    text_splitter = RecursiveCharacterTextSplitter(
        separators=["\n\n", "\n", ". ", " "],  # Separators in order of priority
        chunk_size=750,  # Target 750 words per chunk
        chunk_overlap=50,  # 50 words overlap
        length_function=lambda x: len(x.split()),  # Word-based length function
        add_start_index=True,
        strip_whitespace=True
    )
    
    # Split the document
    chunks = text_splitter.split_documents([doc])
    
    print(f"Original document word count: {len(text.split())}")
    print(f"Number of chunks created: {len(chunks)}")
    
    # Verify each chunk's word count
    for i, chunk in enumerate(chunks):
        word_count = len(chunk.page_content.split())
        print(f"Chunk {i+1}: {word_count} words")
        
        # Verify overlap with next chunk if not the last chunk
        if i < len(chunks) - 1:
            current_words = chunk.page_content.split()
            next_words = chunks[i+1].page_content.split()
            
            # Check the last 50 words of current chunk against first 50 words of next chunk
            overlap_count = 0
            for j in range(1, min(51, len(current_words), len(next_words))):
                if current_words[-j] == next_words[j-1]:
                    overlap_count += 1
            
            print(f"  Overlap with next chunk: {overlap_count} words")
    
    # Verify that all words are included (accounting for overlaps)
    all_words = []
    for chunk in chunks:
        all_words.extend(chunk.page_content.split())
    
    # Account for overlaps in the total count
    expected_total = len(text.split()) + (len(chunks) - 1) * 50
    print(f"Total words in all chunks (including overlaps): {len(all_words)}")
    print(f"Expected total (original + overlaps): {expected_total}")
    
    print("Test completed.")

if __name__ == "__main__":
    test_word_chunking() 
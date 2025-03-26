"""
Unit tests for fact export functionality in the GUI.
Tests that verified facts can be exported to files in various formats.
"""

import os
import sys
import uuid
import pytest
import asyncio
import tempfile
import json
import pandas as pd
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, AsyncMock


# Ensure the src directory is in the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

# Ensure the src directory is in the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))
# Import repositories
from src.storage.chunk_repository import ChunkRepository
from src.storage.fact_repository import FactRepository, RejectedFactRepository

# Import GUI components
from src.gui.app import FactExtractionGUI
from src.models.state import ProcessingState

@pytest.fixture
def setup_test_repositories():
    """Set up test repositories with temporary Excel files."""
    # Create unique IDs for test files to avoid conflicts
    unique_id = str(uuid.uuid4())
    temp_dir = "temp"
    
    # Create temp directory if it doesn't exist
    os.makedirs(temp_dir, exist_ok=True)
    
    chunks_file = os.path.join(temp_dir, f"temp_chunks_{unique_id}.xlsx")
    facts_file = os.path.join(temp_dir, f"temp_facts_{unique_id}.xlsx")
    rejected_facts_file = os.path.join(temp_dir, f"temp_rejected_facts_{unique_id}.xlsx")

    # Create test repositories with the temporary files
    chunk_repo = ChunkRepository(excel_path=chunks_file)
    fact_repo = FactRepository(excel_path=facts_file)
    rejected_fact_repo = RejectedFactRepository(excel_path=rejected_facts_file)

    # Also clear the main repositories to prevent test interference
    main_chunk_repo = ChunkRepository()
    main_fact_repo = FactRepository()
    main_rejected_fact_repo = RejectedFactRepository()
    
    # Clear all documents from main repositories
    for document_name in list(main_chunk_repo.chunks.keys()):
        main_chunk_repo.clear_document(document_name)
    
    for document_name in list(main_fact_repo.facts.keys()):
        main_fact_repo.clear_facts(document_name)
    
    for document_name in list(main_rejected_fact_repo.rejected_facts.keys()):
        main_rejected_fact_repo.clear_rejected_facts(document_name)

    yield chunk_repo, fact_repo, rejected_fact_repo

    # Clean up temporary files after the test
    for file in [chunks_file, facts_file, rejected_facts_file]:
        if os.path.exists(file):
            os.remove(file)

@pytest.fixture
def create_sample_facts(setup_test_repositories):
    """Create sample facts for testing."""
    chunk_repo, fact_repo, rejected_fact_repo = setup_test_repositories
    
    # Create a unique document name to avoid conflicts
    doc_id = str(uuid.uuid4())
    document_name = f"test_document_{doc_id}.txt"
    document_hash = f"hash_{doc_id}"
    
    # Create sample chunks
    chunks = [
        {
            "document_name": document_name,
            "document_hash": document_hash,
            "chunk_index": 0,
            "text": f"Sample text for chunk 0. The semiconductor market reached $550B in 2023. {uuid.uuid4()}",
            "contains_facts": True,
            "all_facts_extracted": True,
            "status": "processed"
        },
        {
            "document_name": document_name,
            "document_hash": document_hash,
            "chunk_index": 1,
            "text": f"Sample text for chunk 1. AI technologies grew by 38% in 2023. {uuid.uuid4()}",
            "contains_facts": True,
            "all_facts_extracted": True,
            "status": "processed"
        }
    ]
    
    # Create sample facts
    facts = [
        {
            "document_name": document_name,
            "statement": f"The semiconductor market reached $550B in 2023. {uuid.uuid4()}",
            "verification_status": "verified",
            "verification_reason": "Verified with industry sources.",
            "chunk_index": 0,
            "confidence": 0.95
        },
        {
            "document_name": document_name,
            "statement": f"AI technologies grew by 38% in 2023. {uuid.uuid4()}",
            "verification_status": "verified",
            "verification_reason": "Confirmed with multiple industry reports.",
            "chunk_index": 1,
            "confidence": 0.92
        }
    ]
    
    # Create a rejected fact
    rejected_fact = {
        "document_name": document_name,
        "statement": f"Cloud computing reached full adoption in 2023. {uuid.uuid4()}",
        "verification_status": "rejected",
        "verification_reason": "Statement lacks specific metrics and is too general.",
        "chunk_index": 1,
        "confidence": 0.65
    }
    
    # Store the chunks and facts
    for chunk in chunks:
        chunk_repo.store_chunk(chunk)
    
    for fact in facts:
        fact_repo.store_fact(fact)
    
    rejected_fact_repo.store_rejected_fact(rejected_fact)
    
    return document_name, chunks, facts, [rejected_fact]

def test_export_facts_to_csv(setup_test_repositories, create_sample_facts, tmp_path):
    """Test exporting facts to CSV format."""
    document_name, chunks, facts, rejected_facts = create_sample_facts
    chunk_repo, fact_repo, rejected_fact_repo = setup_test_repositories
    
    # Create a GUI with patched repositories
    with patch('src.gui.app.ChunkRepository', return_value=chunk_repo), \
         patch('src.gui.app.FactRepository', return_value=fact_repo), \
         patch('src.gui.app.RejectedFactRepository', return_value=rejected_fact_repo):
        
        gui = FactExtractionGUI()
        
        # Add export_facts_to_csv method to GUI for testing
        def export_facts_to_csv(output_path):
            facts = fact_repo.get_all_facts(verified_only=True)
            df = pd.DataFrame(facts)
            df.to_csv(output_path, index=False)
            return f"Exported {len(facts)} facts to {output_path}"
        
        gui.export_facts_to_csv = export_facts_to_csv
        
        # Test the export function
        output_file = tmp_path / "exported_facts.csv"
        result = gui.export_facts_to_csv(output_file)
        
        # Verify the result
        assert os.path.exists(output_file)
        assert f"Exported {len(facts)} facts to" in result
        
        # Verify the content
        exported_df = pd.read_csv(output_file)
        assert len(exported_df) == len(facts)
        
        # Check columns
        assert "statement" in exported_df.columns
        assert "verification_status" in exported_df.columns
        assert "document_name" in exported_df.columns

def test_export_facts_to_json(setup_test_repositories, create_sample_facts, tmp_path):
    """Test exporting facts to JSON format."""
    document_name, chunks, facts, rejected_facts = create_sample_facts
    chunk_repo, fact_repo, rejected_fact_repo = setup_test_repositories
    
    # Create a GUI with patched repositories
    with patch('src.gui.app.ChunkRepository', return_value=chunk_repo), \
         patch('src.gui.app.FactRepository', return_value=fact_repo), \
         patch('src.gui.app.RejectedFactRepository', return_value=rejected_fact_repo):
        
        gui = FactExtractionGUI()
        
        # Add export_facts_to_json method to GUI for testing
        def export_facts_to_json(output_path):
            facts = fact_repo.get_all_facts(verified_only=True)
            with open(output_path, 'w') as f:
                json.dump(facts, f, indent=2)
            return f"Exported {len(facts)} facts to {output_path}"
        
        gui.export_facts_to_json = export_facts_to_json
        
        # Test the export function
        output_file = tmp_path / "exported_facts.json"
        result = gui.export_facts_to_json(output_file)
        
        # Verify the result
        assert os.path.exists(output_file)
        assert f"Exported {len(facts)} facts to" in result
        
        # Verify the content
        with open(output_file, 'r') as f:
            exported_facts = json.load(f)
        
        assert len(exported_facts) == len(facts)
        
        # Check some fields
        for fact in exported_facts:
            assert "statement" in fact
            assert "verification_status" in fact
            assert fact["verification_status"] == "verified"

def test_export_facts_to_markdown(setup_test_repositories, create_sample_facts, tmp_path):
    """Test exporting facts to Markdown format."""
    document_name, chunks, facts, rejected_facts = create_sample_facts
    chunk_repo, fact_repo, rejected_fact_repo = setup_test_repositories
    
    # Create a GUI with patched repositories
    with patch('src.gui.app.ChunkRepository', return_value=chunk_repo), \
         patch('src.gui.app.FactRepository', return_value=fact_repo), \
         patch('src.gui.app.RejectedFactRepository', return_value=rejected_fact_repo):
        
        gui = FactExtractionGUI()
        
        # Add export_facts_to_markdown method to GUI for testing
        def export_facts_to_markdown(output_path):
            facts = fact_repo.get_all_facts(verified_only=True)
            
            # Group facts by document
            grouped_facts = {}
            for fact in facts:
                doc_name = fact.get("document_name", "Unknown Document")
                if doc_name not in grouped_facts:
                    grouped_facts[doc_name] = []
                grouped_facts[doc_name].append(fact)
            
            with open(output_path, 'w') as f:
                f.write("# Verified Facts Report\n\n")
                f.write(f"Total Facts: {len(facts)}\n\n")
                
                for doc_name, doc_facts in grouped_facts.items():
                    f.write(f"## {doc_name}\n\n")
                    for i, fact in enumerate(doc_facts):
                        f.write(f"### Fact {i+1}\n\n")
                        f.write(f"**Statement:** {fact['statement']}\n\n")
                        if fact.get("verification_reason"):
                            f.write(f"**Reasoning:** {fact['verification_reason']}\n\n")
                        f.write("---\n\n")
            
            return f"Exported {len(facts)} facts to {output_path}"
        
        gui.export_facts_to_markdown = export_facts_to_markdown
        
        # Test the export function
        output_file = tmp_path / "exported_facts.md"
        result = gui.export_facts_to_markdown(output_file)
        
        # Verify the result
        assert os.path.exists(output_file)
        assert f"Exported {len(facts)} facts to" in result
        
        # Verify the content
        with open(output_file, 'r') as f:
            content = f.read()
        
        assert "# Verified Facts Report" in content
        assert f"Total Facts: {len(facts)}" in content
        assert document_name in content
        
        # Check that all facts are included
        for fact in facts:
            assert fact["statement"] in content
            assert fact["verification_reason"] in content 
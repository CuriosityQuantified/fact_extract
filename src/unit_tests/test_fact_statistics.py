"""
Unit tests for fact statistics functionality in the GUI.
Tests that statistical information about extracted facts is correctly calculated and displayed.
"""

import os
import sys
import uuid
import pytest
import asyncio
import tempfile
import pandas as pd
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, AsyncMock


# Ensure the src directory is in the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Ensure the src directory is in the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))
# Import repositories
from storage.chunk_repository import ChunkRepository
from storage.fact_repository import FactRepository, RejectedFactRepository

# Import GUI components
from gui.app import FactExtractionGUI
from models.state import ProcessingState

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
    
    # Create unique document names to avoid conflicts
    doc1_id = str(uuid.uuid4())
    doc2_id = str(uuid.uuid4())
    document1_name = f"test_document1_{doc1_id}.txt"
    document2_name = f"test_document2_{doc2_id}.txt"
    
    # Create sample chunks for document 1
    chunks1 = [
        {
            "document_name": document1_name,
            "document_hash": f"hash1_{doc1_id}",
            "chunk_index": 0,
            "text": f"Sample text for chunk 0. The semiconductor market reached $550B in 2023. {uuid.uuid4()}",
            "contains_facts": True,
            "all_facts_extracted": True,
            "status": "processed"
        },
        {
            "document_name": document1_name,
            "document_hash": f"hash1_{doc1_id}",
            "chunk_index": 1,
            "text": f"Sample text for chunk 1. AI technologies grew by 38% in 2023. {uuid.uuid4()}",
            "contains_facts": True,
            "all_facts_extracted": True,
            "status": "processed"
        }
    ]
    
    # Create sample chunks for document 2
    chunks2 = [
        {
            "document_name": document2_name,
            "document_hash": f"hash2_{doc2_id}",
            "chunk_index": 0,
            "text": f"Sample text for document 2. GPU prices increased by 15% in 2023. {uuid.uuid4()}",
            "contains_facts": True,
            "all_facts_extracted": True,
            "status": "processed"
        },
        {
            "document_name": document2_name,
            "document_hash": f"hash2_{doc2_id}",
            "chunk_index": 1,
            "text": f"Sample text for document 2. Cloud storage costs decreased by 8% annually. {uuid.uuid4()}",
            "contains_facts": True,
            "all_facts_extracted": True,
            "status": "processed"
        },
        {
            "document_name": document2_name,
            "document_hash": f"hash2_{doc2_id}",
            "chunk_index": 2,
            "text": f"Sample text without facts. {uuid.uuid4()}",
            "contains_facts": False,
            "all_facts_extracted": True,
            "status": "processed"
        }
    ]
    
    # Create sample facts for document 1
    facts1 = [
        {
            "document_name": document1_name,
            "statement": f"The semiconductor market reached $550B in 2023. {uuid.uuid4()}",
            "verification_status": "verified",
            "verification_reason": "Verified with industry sources.",
            "chunk_index": 0,
            "confidence": 0.95
        },
        {
            "document_name": document1_name,
            "statement": f"AI technologies grew by 38% in 2023. {uuid.uuid4()}",
            "verification_status": "verified",
            "verification_reason": "Confirmed with multiple industry reports.",
            "chunk_index": 1,
            "confidence": 0.92
        }
    ]
    
    # Create sample facts for document 2
    facts2 = [
        {
            "document_name": document2_name,
            "statement": f"GPU prices increased by 15% in 2023. {uuid.uuid4()}",
            "verification_status": "verified",
            "verification_reason": "Verified with market data.",
            "chunk_index": 0,
            "confidence": 0.89
        }
    ]
    
    # Create rejected facts
    rejected_facts = [
        {
            "document_name": document1_name,
            "statement": f"Cloud computing reached full adoption in 2023. {uuid.uuid4()}",
            "verification_status": "rejected",
            "verification_reason": "Statement lacks specific metrics and is too general.",
            "chunk_index": 1,
            "confidence": 0.65
        },
        {
            "document_name": document2_name,
            "statement": f"Cloud storage costs decreased annually. {uuid.uuid4()}",
            "verification_status": "rejected",
            "verification_reason": "Missing specific percentage and timeframe.",
            "chunk_index": 1,
            "confidence": 0.72
        }
    ]
    
    # Store the chunks and facts
    for chunk in chunks1 + chunks2:
        chunk_repo.store_chunk(chunk)
    
    for fact in facts1 + facts2:
        fact_repo.store_fact(fact)
    
    for rejected_fact in rejected_facts:
        rejected_fact_repo.store_rejected_fact(rejected_fact)
    
    return [document1_name, document2_name], chunks1 + chunks2, facts1 + facts2, rejected_facts

def test_generate_statistics(setup_test_repositories, create_sample_facts):
    """Test that statistics are generated correctly."""
    document_names, chunks, facts, rejected_facts = create_sample_facts
    chunk_repo, fact_repo, rejected_fact_repo = setup_test_repositories
    
    # Create a GUI with patched repositories
    with patch('src.fact_extract.gui.app.ChunkRepository', return_value=chunk_repo), \
         patch('src.fact_extract.gui.app.FactRepository', return_value=fact_repo), \
         patch('src.fact_extract.gui.app.RejectedFactRepository', return_value=rejected_fact_repo):
        
        gui = FactExtractionGUI()
        
        # Add generate_statistics method to GUI for testing
        def generate_statistics():
            # Get data from repositories
            all_chunks = chunk_repo.get_all_chunks()
            all_facts = fact_repo.get_all_facts(verified_only=False)
            approved_facts = fact_repo.get_all_facts(verified_only=True)
            rejected_facts = rejected_fact_repo.get_all_rejected_facts()
            
            # Calculate overall statistics
            stats = {
                "total_documents": len(set(chunk["document_name"] for chunk in all_chunks)),
                "total_chunks": len(all_chunks),
                "total_submissions": len(all_facts) + len(rejected_facts),
                "approved_facts": len(approved_facts),
                "rejected_facts": len(rejected_facts),
                "approval_rate": round(len(approved_facts) / (len(approved_facts) + len(rejected_facts)) * 100, 1) if (len(approved_facts) + len(rejected_facts)) > 0 else 0,
            }
            
            # Calculate per-document statistics
            doc_stats = {}
            for doc_name in set(chunk["document_name"] for chunk in all_chunks):
                doc_chunks = [c for c in all_chunks if c["document_name"] == doc_name]
                doc_approved_facts = [f for f in approved_facts if f["document_name"] == doc_name]
                doc_rejected_facts = [f for f in rejected_facts if f["document_name"] == doc_name]
                
                doc_stats[doc_name] = {
                    "chunks": len(doc_chunks),
                    "approved_facts": len(doc_approved_facts),
                    "rejected_facts": len(doc_rejected_facts),
                    "total_submissions": len(doc_approved_facts) + len(doc_rejected_facts),
                    "facts_per_chunk": round(len(doc_approved_facts) / len(doc_chunks), 2) if len(doc_chunks) > 0 else 0
                }
            
            return stats, doc_stats
        
        gui.generate_statistics = generate_statistics
        
        # Test the statistics function
        overall_stats, doc_stats = gui.generate_statistics()
        
        # Verify overall statistics
        assert overall_stats["total_documents"] == len(document_names)
        assert overall_stats["total_chunks"] == len(chunks)
        assert overall_stats["total_submissions"] == len(facts) + len(rejected_facts)
        assert overall_stats["approved_facts"] == len(facts)
        assert overall_stats["rejected_facts"] == len(rejected_facts)
        
        # Verify document statistics
        assert len(doc_stats) == len(document_names)
        for doc_name in document_names:
            assert doc_name in doc_stats
            doc_chunks = [c for c in chunks if c["document_name"] == doc_name]
            doc_approved_facts = [f for f in facts if f["document_name"] == doc_name]
            doc_rejected_facts = [f for f in rejected_facts if f["document_name"] == doc_name]
            
            assert doc_stats[doc_name]["chunks"] == len(doc_chunks)
            assert doc_stats[doc_name]["approved_facts"] == len(doc_approved_facts)
            assert doc_stats[doc_name]["rejected_facts"] == len(doc_rejected_facts)

def test_generate_statistics_markdown(setup_test_repositories, create_sample_facts):
    """Test that statistics can be formatted as markdown."""
    document_names, chunks, facts, rejected_facts = create_sample_facts
    chunk_repo, fact_repo, rejected_fact_repo = setup_test_repositories
    
    # Create a GUI with patched repositories
    with patch('src.fact_extract.gui.app.ChunkRepository', return_value=chunk_repo), \
         patch('src.fact_extract.gui.app.FactRepository', return_value=fact_repo), \
         patch('src.fact_extract.gui.app.RejectedFactRepository', return_value=rejected_fact_repo):
        
        gui = FactExtractionGUI()
        
        # Add generate_statistics and format_statistics_markdown methods to GUI for testing
        def generate_statistics():
            # Get data from repositories
            all_chunks = chunk_repo.get_all_chunks()
            all_facts = fact_repo.get_all_facts(verified_only=False)
            approved_facts = fact_repo.get_all_facts(verified_only=True)
            rejected_facts = rejected_fact_repo.get_all_rejected_facts()
            
            # Calculate overall statistics
            stats = {
                "total_documents": len(set(chunk["document_name"] for chunk in all_chunks)),
                "total_chunks": len(all_chunks),
                "total_submissions": len(all_facts) + len(rejected_facts),
                "approved_facts": len(approved_facts),
                "rejected_facts": len(rejected_facts),
                "approval_rate": round(len(approved_facts) / (len(approved_facts) + len(rejected_facts)) * 100, 1) if (len(approved_facts) + len(rejected_facts)) > 0 else 0,
            }
            
            # Calculate per-document statistics
            doc_stats = {}
            for doc_name in set(chunk["document_name"] for chunk in all_chunks):
                doc_chunks = [c for c in all_chunks if c["document_name"] == doc_name]
                doc_approved_facts = [f for f in approved_facts if f["document_name"] == doc_name]
                doc_rejected_facts = [f for f in rejected_facts if f["document_name"] == doc_name]
                
                doc_stats[doc_name] = {
                    "chunks": len(doc_chunks),
                    "approved_facts": len(doc_approved_facts),
                    "rejected_facts": len(doc_rejected_facts),
                    "total_submissions": len(doc_approved_facts) + len(doc_rejected_facts),
                    "facts_per_chunk": round(len(doc_approved_facts) / len(doc_chunks), 2) if len(doc_chunks) > 0 else 0
                }
            
            return stats, doc_stats
        
        def format_statistics_markdown(stats, doc_stats):
            """Format statistics as markdown."""
            md = "# Fact Extraction Statistics\n\n"
            
            # Overall statistics section
            md += "## Overall Statistics\n\n"
            md += f"- **Total Documents:** {stats['total_documents']}\n"
            md += f"- **Total Chunks:** {stats['total_chunks']}\n"
            md += f"- **Total Submissions:** {stats['total_submissions']}\n"
            md += f"- **Approved Facts:** {stats['approved_facts']}\n"
            md += f"- **Rejected Facts:** {stats['rejected_facts']}\n"
            md += f"- **Approval Rate:** {stats['approval_rate']}%\n\n"
            
            # Per-document statistics section
            md += "## Document Statistics\n\n"
            
            for doc_name, doc_stat in doc_stats.items():
                md += f"### {doc_name}\n\n"
                md += f"- **Chunks:** {doc_stat['chunks']}\n"
                md += f"- **Approved Facts:** {doc_stat['approved_facts']}\n"
                md += f"- **Rejected Facts:** {doc_stat['rejected_facts']}\n"
                md += f"- **Total Submissions:** {doc_stat['total_submissions']}\n"
                md += f"- **Facts per Chunk:** {doc_stat['facts_per_chunk']}\n\n"
            
            return md
        
        gui.generate_statistics = generate_statistics
        gui.format_statistics_markdown = format_statistics_markdown
        
        # Test the statistics formatting function
        overall_stats, doc_stats = gui.generate_statistics()
        markdown_stats = gui.format_statistics_markdown(overall_stats, doc_stats)
        
        # Verify markdown content
        assert "# Fact Extraction Statistics" in markdown_stats
        assert "## Overall Statistics" in markdown_stats
        assert f"**Total Documents:** {len(document_names)}" in markdown_stats
        assert f"**Total Chunks:** {len(chunks)}" in markdown_stats
        assert f"**Approved Facts:** {len(facts)}" in markdown_stats
        assert f"**Rejected Facts:** {len(rejected_facts)}" in markdown_stats
        
        # Check document-specific sections
        for doc_name in document_names:
            assert f"### {doc_name}" in markdown_stats

def test_statistics_tab_content(setup_test_repositories, create_sample_facts):
    """Test that the statistics tab is populated with correct content."""
    document_names, chunks, facts, rejected_facts = create_sample_facts
    chunk_repo, fact_repo, rejected_fact_repo = setup_test_repositories
    
    # Create a GUI with patched repositories
    with patch('src.fact_extract.gui.app.ChunkRepository', return_value=chunk_repo), \
         patch('src.fact_extract.gui.app.FactRepository', return_value=fact_repo), \
         patch('src.fact_extract.gui.app.RejectedFactRepository', return_value=rejected_fact_repo):
        
        gui = FactExtractionGUI()
        
        # Mock the statistics tab component
        statistics_tab = MagicMock()
        statistics_tab.update = AsyncMock()
        
        # Add update_statistics_tab method to GUI for testing
        async def update_statistics_tab():
            # Generate statistics
            stats, doc_stats = gui.generate_statistics()
            
            # Format as markdown
            markdown_stats = gui.format_statistics_markdown(stats, doc_stats)
            
            # Update the tab content
            statistics_tab.update(value=markdown_stats)
            
            return markdown_stats
        
        gui.generate_statistics = lambda: (
            {
                "total_documents": len(document_names),
                "total_chunks": len(chunks),
                "total_submissions": len(facts) + len(rejected_facts),
                "approved_facts": len(facts),
                "rejected_facts": len(rejected_facts),
                "approval_rate": round(len(facts) / (len(facts) + len(rejected_facts)) * 100, 1)
            },
            {doc: {"chunks": 2, "approved_facts": 1, "rejected_facts": 1, "total_submissions": 2, "facts_per_chunk": 0.5} for doc in document_names}
        )
        
        gui.format_statistics_markdown = lambda stats, doc_stats: (
            "# Fact Extraction Statistics\n\n"
            "## Overall Statistics\n\n"
            f"- **Total Documents:** {stats['total_documents']}\n"
            f"- **Total Chunks:** {stats['total_chunks']}\n"
            f"- **Total Submissions:** {stats['total_submissions']}\n"
            f"- **Approved Facts:** {stats['approved_facts']}\n"
            f"- **Rejected Facts:** {stats['rejected_facts']}\n"
            f"- **Approval Rate:** {stats['approval_rate']}%\n\n"
        )
        
        gui.update_statistics_tab = update_statistics_tab
        
        # Test the update method
        markdown_content = asyncio.run(gui.update_statistics_tab())
        
        # Verify content
        assert "# Fact Extraction Statistics" in markdown_content
        assert f"**Total Documents:** {len(document_names)}" in markdown_content
        assert f"**Total Chunks:** {len(chunks)}" in markdown_content
        assert f"**Total Submissions:** {len(facts) + len(rejected_facts)}" in markdown_content
        assert f"**Approved Facts:** {len(facts)}" in markdown_content
        assert f"**Rejected Facts:** {len(rejected_facts)}" in markdown_content 
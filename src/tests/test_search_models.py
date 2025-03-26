"""
Test script to verify SearchableFact model implementation.
"""

import os
import sys
import pytest
from datetime import datetime

# Ensure the src directory is in the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from src.models.search_models import SearchableFact

def test_searchable_fact_creation():
    """Test creating a SearchableFact instance with basic attributes."""
    # Create a basic fact
    fact = SearchableFact(
        id="doc1_chunk2_fact3",
        statement="The average global temperature has risen by 1.1°C since the pre-industrial era.",
        document_name="climate_report.pdf",
        chunk_index=2
    )
    
    # Check basic attributes
    assert fact.id == "doc1_chunk2_fact3"
    assert fact.statement == "The average global temperature has risen by 1.1°C since the pre-industrial era."
    assert fact.document_name == "climate_report.pdf"
    assert fact.chunk_index == 2
    assert isinstance(fact.metadata, dict)
    assert len(fact.metadata) == 0
    assert fact.embedding is None
    assert isinstance(fact.extracted_at, datetime)

def test_searchable_fact_with_metadata():
    """Test creating a SearchableFact with metadata and embedding."""
    # Create metadata
    metadata = {
        "source": "IPCC Report 2021",
        "confidence": 0.92,
        "verified": True
    }
    
    # Create a mock embedding
    embedding = [0.1, 0.2, 0.3, 0.4, 0.5]
    
    # Set a specific extraction time
    extraction_time = datetime(2023, 5, 15, 10, 30, 0)
    
    # Create a fact with all attributes
    fact = SearchableFact(
        id="doc1_chunk2_fact3",
        statement="The average global temperature has risen by 1.1°C since the pre-industrial era.",
        document_name="climate_report.pdf",
        chunk_index=2,
        metadata=metadata,
        embedding=embedding,
        extracted_at=extraction_time
    )
    
    # Check all attributes are set correctly
    assert fact.id == "doc1_chunk2_fact3"
    assert fact.statement == "The average global temperature has risen by 1.1°C since the pre-industrial era."
    assert fact.document_name == "climate_report.pdf"
    assert fact.chunk_index == 2
    assert fact.metadata == metadata
    assert fact.metadata["source"] == "IPCC Report 2021"
    assert fact.metadata["confidence"] == 0.92
    assert fact.metadata["verified"] is True
    assert fact.embedding == embedding
    assert fact.extracted_at == extraction_time

def test_searchable_fact_dict_conversion():
    """Test conversion of SearchableFact to dictionary and back."""
    # Create a fact
    original_fact = SearchableFact(
        id="doc1_chunk2_fact3",
        statement="The average global temperature has risen by 1.1°C since the pre-industrial era.",
        document_name="climate_report.pdf",
        chunk_index=2,
        metadata={"source": "IPCC Report 2021"}
    )
    
    # Convert to dict
    fact_dict = original_fact.dict()
    
    # Check dict has all expected keys
    assert "id" in fact_dict
    assert "statement" in fact_dict
    assert "document_name" in fact_dict
    assert "chunk_index" in fact_dict
    assert "metadata" in fact_dict
    assert "embedding" in fact_dict
    assert "extracted_at" in fact_dict
    
    # Create a new fact from the dict
    new_fact = SearchableFact(**fact_dict)
    
    # Check the new fact matches the original
    assert new_fact.id == original_fact.id
    assert new_fact.statement == original_fact.statement
    assert new_fact.document_name == original_fact.document_name
    assert new_fact.chunk_index == original_fact.chunk_index
    assert new_fact.metadata == original_fact.metadata
    assert new_fact.embedding == original_fact.embedding
    assert new_fact.extracted_at == original_fact.extracted_at 
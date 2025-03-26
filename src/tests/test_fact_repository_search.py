"""
Test script to verify semantic search integration with FactRepository.
"""

import os
import sys
import pytest
import tempfile
import shutil
import uuid
from typing import Dict, Any, List
from unittest.mock import patch, MagicMock

# Ensure the src directory is in the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from src.storage.fact_repository import FactRepository
from src.search.vector_store import ChromaFactStore

class TestFactRepositorySearch:
    """Test class for FactRepository with semantic search capabilities."""
    
    def setup_method(self):
        """Set up temporary directories and repository instances for each test."""
        # Create temporary directories
        self.temp_dir = tempfile.mkdtemp()
        self.vector_store_dir = os.path.join(self.temp_dir, "embeddings")
        self.excel_path = os.path.join(self.temp_dir, "test_facts.xlsx")
        
        # Create unique collection name for each test
        self.collection_name = f"test_facts_{uuid.uuid4().hex}"
        
        # Initialize FactRepository with temporary paths
        self.fact_repo = FactRepository(
            excel_path=self.excel_path,
            vector_store_dir=self.vector_store_dir,
            collection_name=self.collection_name
        )
        
        # Sample facts for testing
        self.sample_facts = [
            {
                "document_name": "climate_report.pdf",
                "chunk_index": 1,
                "statement": "The global average surface temperature has increased by 1.1°C since the pre-industrial era.",
                "source_name": "IPCC",
                "verification_status": "verified"
            },
            {
                "document_name": "energy_report.pdf",
                "chunk_index": 3,
                "statement": "Renewable energy capacity increased by 45% worldwide between 2015 and 2020.",
                "source_name": "IEA",
                "verification_status": "verified"
            },
            {
                "document_name": "ev_market_report.pdf",
                "chunk_index": 2,
                "statement": "Electric vehicle sales grew by 65% in 2022 compared to the previous year.",
                "source_name": "Bloomberg",
                "verification_status": "verified"
            }
        ]
    
    def teardown_method(self):
        """Clean up after each test by removing temporary directories."""
        shutil.rmtree(self.temp_dir)
    
    def test_initialization(self):
        """Test proper initialization of FactRepository with vector store."""
        # Check that the instance was created properly
        assert self.fact_repo is not None
        assert self.fact_repo.vector_store is not None
        
        # Check that the vector store is configured correctly
        assert isinstance(self.fact_repo.vector_store, ChromaFactStore)
        assert self.fact_repo.vector_store.collection.name == self.collection_name
        
        # Verify Excel path is set correctly
        assert self.fact_repo.excel_path == self.excel_path
    
    def test_store_fact_with_vector_store(self):
        """Test that facts are stored in both Excel and the vector store."""
        # Store a fact
        fact = self.sample_facts[0]
        fact_id = self.fact_repo.store_fact(fact)
        
        # Check the fact was stored in Excel
        assert len(self.fact_repo.facts.get(fact["document_name"], [])) == 1
        
        # Check the fact was stored in vector store
        assert self.fact_repo.vector_store.get_fact_count() == 1
        
        # Verify fact ID format
        assert fact["document_name"] in fact_id
        assert str(fact["chunk_index"]) in fact_id
    
    def test_search_facts(self):
        """Test searching for facts using semantic search."""
        # Store sample facts
        for fact in self.sample_facts:
            self.fact_repo.store_fact(fact)
        
        # Search for facts related to climate
        results = self.fact_repo.search_facts(
            query="global warming and temperature increase",
            n_results=2
        )
        
        # Check results structure
        assert isinstance(results, list)
        assert len(results) > 0
        
        # Check result fields
        first_result = results[0]
        assert "id" in first_result
        assert "statement" in first_result
        assert "similarity" in first_result
        assert "document_name" in first_result
        
        # The most relevant result should be about temperature (the first fact)
        assert "temperature" in first_result["statement"].lower()
        
        # Similarity score should be between 0 and 1
        assert 0 <= first_result["similarity"] <= 1
    
    def test_search_with_filter(self):
        """Test searching with filter criteria."""
        # Store sample facts
        for fact in self.sample_facts:
            self.fact_repo.store_fact(fact)
        
        # Search with a filter for a specific document
        results = self.fact_repo.search_facts(
            query="energy",
            n_results=3,
            filter_criteria={"document_name": "energy_report.pdf"}
        )
        
        # Check that we only got results from the energy report
        assert len(results) == 1
        assert results[0]["document_name"] == "energy_report.pdf"
        assert "renewable" in results[0]["statement"].lower()
    
    def test_update_fact(self):
        """Test updating a fact updates both Excel and vector store."""
        # Store a fact
        fact = self.sample_facts[0]
        self.fact_repo.store_fact(fact)
        
        # Update the fact
        new_statement = "Updated statement: The global temperature has increased by 1.2°C."
        updated = self.fact_repo.update_fact(
            document_name=fact["document_name"],
            old_statement=fact["statement"],
            new_data={"statement": new_statement}
        )
        
        # Check the update was successful
        assert updated is True
        
        # Verify Excel update
        stored_facts = self.fact_repo.get_facts(fact["document_name"])
        assert len(stored_facts) == 1
        assert stored_facts[0]["statement"] == new_statement
        
        # Search for the updated statement
        results = self.fact_repo.search_facts(
            query="updated global temperature",
            n_results=1
        )
        
        # Check that we found the updated statement
        assert len(results) == 1
        assert results[0]["statement"] == new_statement
    
    def test_remove_fact(self):
        """Test removing a fact removes it from both Excel and vector store."""
        # Store facts
        for fact in self.sample_facts:
            self.fact_repo.store_fact(fact)
        
        # Initial counts
        initial_excel_count = len(self.fact_repo.get_all_facts())
        initial_vector_count = self.fact_repo.vector_store.get_fact_count()
        assert initial_excel_count == 3
        assert initial_vector_count == 3
        
        # Remove one fact
        removed = self.fact_repo.remove_fact(
            document_name=self.sample_facts[0]["document_name"],
            statement=self.sample_facts[0]["statement"]
        )
        
        # Check removal was successful
        assert removed is True
        
        # Check counts after removal
        final_excel_count = len(self.fact_repo.get_all_facts())
        final_vector_count = self.fact_repo.vector_store.get_fact_count()
        assert final_excel_count == 2
        assert final_vector_count == 2
        
        # Search for the removed fact
        results = self.fact_repo.search_facts(
            query="temperature increase",
            n_results=1
        )
        
        # Should not find the removed fact about temperature
        assert "temperature" not in results[0]["statement"].lower()
    
    def test_duplicate_detection(self):
        """Test that duplicate facts are not stored twice."""
        # Store a fact
        fact = self.sample_facts[0]
        first_id = self.fact_repo.store_fact(fact)
        
        # Try to store the same fact again
        second_id = self.fact_repo.store_fact(fact)
        
        # Should return the same ID and not store it again
        assert first_id == second_id
        assert len(self.fact_repo.facts.get(fact["document_name"], [])) == 1
        assert self.fact_repo.vector_store.get_fact_count() == 1
    
    def test_get_vector_store_stats(self):
        """Test getting statistics about the vector store."""
        # Store facts
        for fact in self.sample_facts:
            self.fact_repo.store_fact(fact)
            
        # Get stats
        stats = self.fact_repo.get_vector_store_stats()
        
        # Check stats structure
        assert "fact_count" in stats
        assert "collection_name" in stats
        assert "embeddings_directory" in stats
        
        # Check values
        assert stats["fact_count"] == 3
        assert stats["collection_name"] == self.collection_name
        assert self.vector_store_dir in stats["embeddings_directory"]
    
    def test_error_handling_in_search(self):
        """Test error handling in search_facts method."""
        # Create a mock vector_store that raises an exception during search
        with patch.object(self.fact_repo.vector_store, 'search_facts', side_effect=Exception("Test exception")):
            # Search should not raise the exception but return empty results
            results = self.fact_repo.search_facts(
                query="anything",
                n_results=5
            )
            
            # Should return empty list on error
            assert results == []
    
    def test_empty_search_results(self):
        """Test handling of empty search results."""
        # Search with no facts added
        results = self.fact_repo.search_facts(
            query="anything",
            n_results=5
        )
        
        # Should return empty list
        assert results == []


if __name__ == "__main__":
    pytest.main(["-xvs", __file__]) 
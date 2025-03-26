"""
Test script to verify ChromaFactStore implementation.
"""

import os
import sys
import pytest
import tempfile
import shutil
import uuid
from unittest.mock import patch, MagicMock

# Ensure the src directory is in the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from src.search.vector_store import ChromaFactStore


class TestChromaFactStore:
    """Test class for ChromaFactStore."""
    
    def setup_method(self):
        """Set up temporary directory and ChromaFactStore instance for each test."""
        # Create a temporary directory for ChromaDB files
        self.temp_dir = tempfile.mkdtemp()
        
        # Generate a unique collection name for each test to avoid conflicts
        self.collection_name = f"test_collection_{uuid.uuid4().hex}"
        
        # Create the ChromaFactStore instance
        self.store = ChromaFactStore(
            persist_directory=self.temp_dir,
            collection_name=self.collection_name
        )
        
        # Sample fact data for testing
        self.sample_facts = [
            {
                "id": "doc1_1_fact1",
                "statement": "The global average surface temperature has increased by 1.1°C since the pre-industrial era.",
                "metadata": {
                    "document_name": "climate_report.pdf",
                    "chunk_index": 1,
                    "source": "IPCC"
                }
            },
            {
                "id": "doc2_3_fact2",
                "statement": "Renewable energy capacity increased by 45% worldwide between 2015 and 2020.",
                "metadata": {
                    "document_name": "energy_report.pdf",
                    "chunk_index": 3,
                    "source": "IEA"
                }
            },
            {
                "id": "doc3_2_fact3",
                "statement": "Electric vehicle sales grew by 65% in 2022 compared to the previous year.",
                "metadata": {
                    "document_name": "ev_market_report.pdf",
                    "chunk_index": 2,
                    "source": "Bloomberg"
                }
            }
        ]
    
    def teardown_method(self):
        """Clean up after each test by removing the temporary directory."""
        shutil.rmtree(self.temp_dir)
    
    def test_initialization(self):
        """Test initialization of ChromaFactStore."""
        # Check that the instance was created properly
        assert self.store is not None
        assert self.store.client is not None
        assert self.store.collection is not None
        
        # Check the collection name
        assert self.store.collection.name == self.collection_name
        
        # Check the embedding function
        assert self.store.embedding_function is not None
    
    def test_add_fact(self):
        """Test adding a single fact to the store."""
        # Add a single fact
        fact = self.sample_facts[0]
        self.store.add_fact(
            fact_id=fact["id"],
            statement=fact["statement"],
            metadata=fact["metadata"]
        )
        
        # Check that the fact count is 1
        assert self.store.get_fact_count() == 1
    
    def test_add_facts_batch(self):
        """Test adding multiple facts in a batch."""
        # Extract data from sample facts
        fact_ids = [fact["id"] for fact in self.sample_facts]
        statements = [fact["statement"] for fact in self.sample_facts]
        metadatas = [fact["metadata"] for fact in self.sample_facts]
        
        # Add facts in batch
        self.store.add_facts_batch(
            fact_ids=fact_ids,
            statements=statements,
            metadatas=metadatas
        )
        
        # Check that the fact count matches
        assert self.store.get_fact_count() == len(self.sample_facts)
    
    def test_search_facts(self):
        """Test searching for facts."""
        # Add facts first
        for fact in self.sample_facts:
            self.store.add_fact(
                fact_id=fact["id"],
                statement=fact["statement"],
                metadata=fact["metadata"]
            )
        
        # Search for facts related to climate
        results = self.store.search_facts(
            query="climate change temperature increase",
            n_results=2
        )
        
        # Check results structure
        assert "ids" in results
        assert "distances" in results
        assert "metadatas" in results
        assert "documents" in results
        
        # Check result count
        assert len(results["ids"][0]) <= 2  # May be less if not enough relevant results
        
        # The most relevant result should be about temperature (the first fact)
        assert "temperature" in results["documents"][0][0].lower()
    
    def test_search_with_filter(self):
        """Test searching with filter criteria."""
        # Add facts first
        for fact in self.sample_facts:
            self.store.add_fact(
                fact_id=fact["id"],
                statement=fact["statement"],
                metadata=fact["metadata"]
            )
        
        # Search with a filter for a specific document
        results = self.store.search_facts(
            query="energy",
            n_results=3,
            filter_criteria={"document_name": "energy_report.pdf"}
        )
        
        # Check result count
        assert len(results["ids"][0]) == 1  # Should only get the energy report fact
        
        # Check that the document name matches
        assert results["metadatas"][0][0]["document_name"] == "energy_report.pdf"
    
    def test_delete_fact(self):
        """Test deleting a fact."""
        # Add facts first
        for fact in self.sample_facts:
            self.store.add_fact(
                fact_id=fact["id"],
                statement=fact["statement"],
                metadata=fact["metadata"]
            )
        
        # Initial count should be 3
        assert self.store.get_fact_count() == 3
        
        # Delete one fact
        self.store.delete_fact(fact_id=self.sample_facts[0]["id"])
        
        # Count should now be 2
        assert self.store.get_fact_count() == 2
        
        # Search should not return the deleted fact
        results = self.store.search_facts(
            query="temperature",
            n_results=3
        )
        
        # The deleted fact ID should not be in the results
        assert self.sample_facts[0]["id"] not in results["ids"][0]
    
    def test_empty_search_results(self):
        """Test handling of empty search results."""
        # Search with no facts added
        results = self.store.search_facts(
            query="anything",
            n_results=5
        )
        
        # Results should have empty lists
        assert len(results["ids"][0]) == 0
        assert len(results["distances"][0]) == 0
        assert len(results["metadatas"][0]) == 0
        assert len(results["documents"][0]) == 0
    
    def test_error_handling(self):
        """Test error handling in add_fact method."""
        # Create a mock collection that raises an exception
        with patch.object(self.store.collection, 'add', side_effect=Exception("Test exception")):
            # Adding a fact should raise the exception
            with pytest.raises(Exception) as excinfo:
                self.store.add_fact(
                    fact_id="test_id",
                    statement="Test statement",
                    metadata={}
                )
            
            # Check exception message
            assert "Test exception" in str(excinfo.value)
    
    def test_batch_validation(self):
        """Test validation of batch parameters."""
        # Try to add batches with mismatched lengths
        with pytest.raises(ValueError) as excinfo:
            self.store.add_facts_batch(
                fact_ids=["id1", "id2"],
                statements=["statement1"],
                metadatas=[{}]
            )
        
        # Check error message
        assert "Mismatch in lengths" in str(excinfo.value) 
"""
Test vector store synchronization with the fact repository.
"""

import sys
import os
import pytest
import tempfile
import shutil
import asyncio
import uuid
from unittest.mock import patch, MagicMock

# Ensure the src directory is in the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

# Use absolute imports
from src.search.vector_store import ChromaFactStore
from src.storage.fact_repository import FactRepository
from src.storage.chunk_repository import ChunkRepository

class TestVectorStoreSync:
    """Tests for vector store synchronization with fact repositories."""
    
    def setup_method(self):
        """Set up temporary repositories and vector store for testing."""
        # Create unique test directory
        self.test_id = str(uuid.uuid4())[:8]
        self.test_dir = f"src/data/test_{self.test_id}"
        os.makedirs(self.test_dir, exist_ok=True)
        
        # Create temporary Excel paths
        self.excel_path = f"{self.test_dir}/test_facts.xlsx"
        self.rejected_excel_path = f"{self.test_dir}/test_rejected_facts.xlsx"
        self.vector_store_dir = f"{self.test_dir}/embeddings"
        
        # Initialize repositories
        self.fact_repo = FactRepository(
            excel_path=self.excel_path,
            vector_store_dir=self.vector_store_dir,
            collection_name=f"test_facts_{self.test_id}"
        )
        
    def teardown_method(self):
        """Clean up temporary files after tests."""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
    
    def test_search_only_returns_verified_facts(self):
        """Test that search results only include verified facts."""
        # Create test document with a unique name
        doc_name = f"test_document_{uuid.uuid4()}"
        
        # Create test facts
        verified_fact = {
            "document_name": doc_name,
            "statement": f"This is a verified fact {uuid.uuid4()}",
            "verification_status": "verified",
            "verification_reason": "This is a valid fact"
        }
        
        rejected_fact = {
            "document_name": doc_name,
            "statement": f"This is a rejected fact {uuid.uuid4()}",
            "verification_status": "rejected",
            "verification_reason": "This is not a valid fact"
        }
        
        pending_fact = {
            "document_name": doc_name,
            "statement": f"This is a pending fact {uuid.uuid4()}",
            "verification_status": "pending",
            "verification_reason": ""
        }
        
        # Store all facts
        self.fact_repo.store_fact(verified_fact)
        self.fact_repo.store_fact(pending_fact)
        
        # Create a separate rejected fact repository
        rejected_repo = FactRepository(
            excel_path=self.rejected_excel_path,
            vector_store_dir=self.vector_store_dir,
            collection_name=f"test_facts_{self.test_id}"
        )
        rejected_repo.store_fact(rejected_fact)
        
        # Search for "fact" with verified_only=True (default)
        results = self.fact_repo.search_facts(query="fact", n_results=10)
        
        # Check that only the verified fact is returned
        assert len(results) > 0, "Search should return at least one result"
        assert all(r.get("verification_status") == "verified" for r in results), "All results should be verified facts"
        assert any(verified_fact["statement"] in r.get("statement", "") for r in results), "Verified fact should be in results"
        assert not any(rejected_fact["statement"] in r.get("statement", "") for r in results), "Rejected fact should not be in results"
        assert not any(pending_fact["statement"] in r.get("statement", "") for r in results), "Pending fact should not be in results"
        
        # Search for "fact" with verified_only=False
        all_results = self.fact_repo.search_facts(query="fact", n_results=10, verified_only=False)
        
        # Check that all facts are returned
        assert len(all_results) >= len(results), "All results should include at least as many facts as verified-only results"
        
    def test_update_fact_in_vector_store(self):
        """Test that updating a fact properly syncs with the vector store."""
        # Create test document with a unique name
        doc_name = f"test_document_{uuid.uuid4()}"
        
        # Create a verified fact
        verified_fact = {
            "document_name": doc_name,
            "statement": f"This is a verified fact {uuid.uuid4()}",
            "verification_status": "verified",
            "verification_reason": "This is a valid fact"
        }
        
        # Store the fact
        self.fact_repo.store_fact(verified_fact)
        
        # Search to confirm it's in the vector store
        results = self.fact_repo.search_facts(query="verified fact", n_results=10)
        assert len(results) > 0, "Search should return the verified fact"
        
        # Update the fact to rejected status
        updated_fact = verified_fact.copy()
        updated_fact["verification_status"] = "rejected"
        updated_fact["verification_reason"] = "This is now rejected"
        
        # Update in vector store
        success = self.fact_repo.update_fact_in_vector_store(updated_fact)
        assert success, "Update should succeed"
        
        # Search again to confirm it's removed from vector store
        results = self.fact_repo.search_facts(query="verified fact", n_results=10)
        assert not any(verified_fact["statement"] in r.get("statement", "") for r in results), "Rejected fact should not be in search results"
        
    def test_fact_status_transitions(self):
        """Test that approving and rejecting facts properly updates the vector store."""
        # Create test document with a unique name
        doc_name = f"test_document_{uuid.uuid4()}"
        
        # Create a pending fact
        pending_fact = {
            "document_name": doc_name,
            "statement": f"This is a pending fact {uuid.uuid4()}",
            "verification_status": "pending",
            "verification_reason": ""
        }
        
        # Store the fact
        self.fact_repo.store_fact(pending_fact)
        
        # Search to confirm it's not in the vector store
        results = self.fact_repo.search_facts(query="pending fact", n_results=10)
        assert not any(pending_fact["statement"] in r.get("statement", "") for r in results), "Pending fact should not be in search results"
        
        # Approve the fact
        approved_fact = pending_fact.copy()
        approved_fact["verification_status"] = "verified"
        approved_fact["verification_reason"] = "This is now approved"
        
        # Update in vector store
        success = self.fact_repo.update_fact_in_vector_store(approved_fact)
        assert success, "Update should succeed"
        
        # Store the updated fact
        self.fact_repo.store_fact(approved_fact)
        
        # Search again to confirm it's in the vector store
        results = self.fact_repo.search_facts(query="pending fact", n_results=10)
        assert any(pending_fact["statement"] in r.get("statement", "") for r in results), "Approved fact should be in search results"
        
        # Reject the fact
        rejected_fact = approved_fact.copy()
        rejected_fact["verification_status"] = "rejected"
        rejected_fact["verification_reason"] = "This is now rejected"
        
        # Update in vector store
        success = self.fact_repo.update_fact_in_vector_store(rejected_fact)
        assert success, "Update should succeed"
        
        # Search again to confirm it's removed from the vector store
        results = self.fact_repo.search_facts(query="pending fact", n_results=10)
        assert not any(pending_fact["statement"] in r.get("statement", "") for r in results), "Rejected fact should not be in search results" 
"""
Pytest configuration for the fact extraction tests.
This file ensures proper import paths and fixtures for all tests.
"""

import os
import sys
import pytest
import importlib

# Ensure the src directory is in the path for all tests
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

@pytest.fixture(scope="session", autouse=True)
def ensure_correct_imports():
    """
    Ensure correct imports for all tests.
    This fixture runs automatically for all tests.
    """
    # Check if our imports work, and if not, add paths to fix them
    try:
        # Try to import directly from graph.nodes first
        from src.graph.nodes import chunker_node
        print("\n✅ Successfully imported chunker_node directly")
    except ImportError as e:
        print(f"\n❌ Error importing chunker_node: {e}")
        
        # Try to fix by importing from the package first
        try:
            import src.graph
            if hasattr(src.graph, 'chunker_node'):
                print("✅ src.graph has chunker_node attribute")
            else:
                print("❌ src.graph doesn't have chunker_node attribute")
                
            # Also try to access the nodes module explicitly
            nodes_module = importlib.import_module('src.graph.nodes')
            if hasattr(nodes_module, 'chunker_node'):
                print("✅ src.graph.nodes has chunker_node attribute")
            else:
                print("❌ src.graph.nodes doesn't have chunker_node attribute")
                
        except ImportError as e:
            print(f"❌ Error importing src.graph: {e}")
    
    # Yield control back to the test
    yield 
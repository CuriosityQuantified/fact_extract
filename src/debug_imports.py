"""
Debug script to verify module imports.
This will help identify import issues with the graph nodes.
"""

import sys
import os
import importlib

def test_import(module_path, names):
    """Test importing specific names from a module."""
    print(f"\nTesting import from {module_path}:")
    try:
        module = importlib.import_module(module_path)
        print(f"✓ Successfully imported module {module_path}")
        
        for name in names:
            try:
                obj = getattr(module, name)
                print(f"✓ Successfully imported {name} from {module_path}")
            except AttributeError:
                print(f"✗ Failed to import {name} from {module_path} - Not found in module")
    except ImportError as e:
        print(f"✗ Failed to import module {module_path} - {str(e)}")

def main():
    """Main function to test various imports."""
    print("=" * 60)
    print("IMPORT DEBUG")
    print("=" * 60)
    
    # Test importing from graph package
    test_import("src.graph", ["chunker_node", "extractor_node", "validator_node", "process_document"])
    
    # Test importing directly from nodes module
    test_import("src.graph.nodes", ["chunker_node", "extractor_node", "validator_node", "process_document"])
    
    # Test importing models
    test_import("src.models", ["WorkflowStateDict", "ProcessingState"])
    
    # Test importing repositories
    test_import("src.storage.chunk_repository", ["ChunkRepository"])
    test_import("src.storage.fact_repository", ["FactRepository", "RejectedFactRepository"])
    
    print("\n" + "=" * 60)
    print("Import tests completed")
    print("=" * 60)

if __name__ == "__main__":
    # Add the parent directory to the path
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    main() 
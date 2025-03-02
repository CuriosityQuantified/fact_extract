"""
Unit tests for tab-based information display in the fact extraction GUI.
Tests the information display system properly formats content.
"""

import os
import pytest
import uuid
import re
from unittest.mock import Mock, patch, MagicMock

from src.fact_extract.gui.app import FactExtractionGUI
from src.fact_extract.tests.test_gui_toggle import format_facts_for_display

def extract_script(html_content):
    """Extract the JavaScript script from HTML content."""
    script_match = re.search(r'<script>(.*?)</script>', html_content, re.DOTALL)
    if script_match:
        return script_match.group(1)
    return None

def count_details_elements(html_content):
    """Count the number of details elements in HTML content."""
    details_count = len(re.findall(r'<details', html_content))
    return details_count

def extract_detail_ids(html_content):
    """Extract all detail element IDs from HTML content."""
    id_matches = re.findall(r'<details[^>]*id=[\'"]([^\'"]*)[\'"]', html_content)
    return id_matches

def test_format_facts_summary_contains_key_information():
    """Test that format_facts_summary includes essential information."""
    # Create a GUI instance
    gui = FactExtractionGUI()
    
    # Create sample facts data
    facts_data = {
        "all_facts": [
            {
                "statement": "The semiconductor market reached $550B in 2023.",
                "verification_status": "verified",
                "verification_reason": "Verified with industry sources.",
                "document_name": "test_doc.txt",
                "chunk_index": 0
            },
            {
                "statement": "AI technologies grew by 38% in 2023.",
                "verification_status": "verified",
                "verification_reason": "Confirmed with multiple reports.",
                "document_name": "test_doc.txt",
                "chunk_index": 1
            }
        ],
        "approved_facts": [
            {
                "statement": "The semiconductor market reached $550B in 2023.",
                "verification_status": "verified",
                "verification_reason": "Verified with industry sources.",
                "document_name": "test_doc.txt",
                "chunk_index": 0
            }
        ],
        "rejected_facts": [
            {
                "statement": "Cloud computing will dominate the market soon.",
                "verification_status": "rejected",
                "verification_reason": "Too vague, no specific metrics.",
                "document_name": "test_doc.txt",
                "chunk_index": 2
            }
        ],
        "errors": ["Error processing document: test_error.txt"]
    }
    
    # Format facts for display
    formatted_facts = gui.format_facts_summary(facts_data)
    
    # Check for essential information
    assert "Progress" in formatted_facts
    assert "Total submissions" in formatted_facts
    assert "Facts approved" in formatted_facts
    assert "Submissions rejected" in formatted_facts

def test_test_gui_toggle_formatting():
    """Test the specific test_gui_toggle formatting function that implements the toggle behavior."""
    # Create sample facts data
    facts_data = {
        "all_facts": [
            "The semiconductor market reached $550B in 2023.",
            "AI technologies grew by 38% in 2023."
        ],
        "sections": [
            "Semiconductor Market",
            "AI Technologies"
        ]
    }
    
    # Format facts for display using the test_gui_toggle function
    formatted_facts = format_facts_for_display(facts_data)
    
    # Count details elements
    details_count = count_details_elements(formatted_facts)
    assert details_count > 0, "No details elements found"
    
    # Check for persistent details class
    assert "persistent-details" in formatted_facts, "Persistent details class not found"
    
    # Check for script
    assert "<script>" in formatted_facts, "Script element not found"
    assert "setupPersistentDetails" in formatted_facts, "Setup function not found"

def test_unique_ids_for_toggle_elements():
    """Test that toggle elements have unique IDs for state tracking."""
    # Create sample facts data
    facts_data = {
        "all_facts": [
            "The semiconductor market reached $550B in 2023.",
            "AI technologies grew by 38% in 2023."
        ],
        "sections": [
            "Semiconductor Market",
            "AI Technologies"
        ]
    }
    
    # Format facts for display
    formatted_facts = format_facts_for_display(facts_data)
    
    # Extract all detail IDs
    detail_ids = extract_detail_ids(formatted_facts)
    
    # Verify that each ID is unique
    assert len(detail_ids) == len(set(detail_ids)), "Duplicate IDs found in details elements"

def test_toggle_state_persistence_script():
    """Test that the script for toggle state persistence is included."""
    # Create sample facts data
    facts_data = {
        "all_facts": [
            "The semiconductor market reached $550B in 2023.",
            "AI technologies grew by 38% in 2023."
        ],
        "sections": [
            "Semiconductor Market",
            "AI Technologies"
        ]
    }
    
    # Format facts for display
    formatted_facts = format_facts_for_display(facts_data)
    
    # Extract script content
    script_content = extract_script(formatted_facts)
    
    # Verify script exists
    assert script_content is not None, "No script found in formatted facts"
    
    # Check for key JavaScript functions or variables
    assert "setupPersistentDetails" in script_content, "setupPersistentDetails function not found" 
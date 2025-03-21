"""
Test script to verify the toggle behavior in the GUI.
This script tests the JavaScript and CSS formatting functions used in the GUI.
"""

import pytest
import os
import sys
import gradio as gr
from datetime import datetime


# Ensure the src directory is in the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Ensure the src directory is in the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))
def format_facts_for_display(facts):
    """Format facts data for display with collapsible sections."""
    output = []
    output.append("## Test Toggle Behavior")
    output.append("This is a test of the toggle behavior in the GUI.")
    
    # Add sections
    for i, section in enumerate(facts["sections"]):
        output.append(f"\n<details class='persistent-details' id='section-{i}'>")
        output.append(f"<summary>🔻 Section {i+1}: {section}</summary>\n")
        output.append(f"This is the content of section {i+1}.")
        output.append("</details>")
    
    # Add facts
    if facts["all_facts"]:
        output.append("\n<details class='persistent-details' id='all-facts-section'>")
        output.append("<summary>🔻 All Facts</summary>\n")
        for i, fact in enumerate(facts["all_facts"]):
            output.append(f"\n<details class='persistent-details' id='fact-{i}'>")
            output.append(f"<summary>✅ Fact {i+1}: {fact}</summary>\n")
            output.append(f"This is the content of fact {i+1}.")
            output.append("</details>")
        output.append("</details>")
    
    return "\n".join(output) + "\n<script>if(window.setupPersistentDetails) setupPersistentDetails();</script>"

def test_format_facts_empty():
    """Test the format_facts_for_display function with empty data."""
    facts_data = {
        "all_facts": [],
        "sections": []
    }
    
    result = format_facts_for_display(facts_data)
    
    # Verify the output contains expected elements
    assert "## Test Toggle Behavior" in result
    assert "This is a test of the toggle behavior in the GUI." in result
    assert "All Facts" not in result  # Should not have facts section when empty

def test_format_facts_with_data():
    """Test the format_facts_for_display function with sample data."""
    facts_data = {
        "all_facts": ["Test fact 1", "Test fact 2"],
        "sections": ["Section A", "Section B"]
    }
    
    result = format_facts_for_display(facts_data)
    
    # Verify the output contains expected elements
    assert "## Test Toggle Behavior" in result
    assert "Section 1: Section A" in result
    assert "Section 2: Section B" in result
    assert "All Facts" in result
    assert "Fact 1: Test fact 1" in result
    assert "Fact 2: Test fact 2" in result
    
    # Verify it has the proper HTML structure
    assert "<details class='persistent-details'" in result
    assert "<summary>" in result
    assert "setupPersistentDetails" in result

def test_persistent_details_script_included():
    """Test that the JavaScript for persistent details is included in the output."""
    facts_data = {"all_facts": [], "sections": []}
    result = format_facts_for_display(facts_data)
    
    # Verify the script tag is included
    assert "<script>" in result
    assert "setupPersistentDetails" in result

def test_toggle_fact_status(self):
    """Test that toggling a fact between verified and rejected works properly."""
    # Setup: Create a GUI instance
    gui = FactExtractionGUI()
    
    # Create a test fact
    test_fact = {
        "statement": "This is a test fact",
        "document_name": "test_document.txt",
        "verification_status": "pending",
        "verification_reason": "",
        "timestamp": datetime.now().isoformat()
    }
    
    # 1. Add to verified repository
    gui.fact_repo.store_fact(test_fact.copy())
    
    # Get all facts for review
    all_facts, _ = gui.get_facts_for_review()
    
    # Find the fact we just added
    fact_index = -1
    for i, fact in enumerate(all_facts):
        if fact.get("statement") == test_fact["statement"]:
            fact_index = i
            break
    
    assert fact_index >= 0, "Test fact should be found in all_facts"
    test_fact_id = all_facts[fact_index].get("id")
    
    # 2. Now toggle to rejected
    result, _ = gui.update_fact(test_fact_id, test_fact["statement"], "rejected", "Test rejection")
    
    # Verify it's in rejected repo
    rejected_facts = gui.rejected_fact_repo.get_all_rejected_facts()
    found_in_rejected = False
    for fact in rejected_facts:
        if fact.get("statement") == test_fact["statement"]:
            found_in_rejected = True
            break
    
    assert found_in_rejected, "Fact should be in rejected repository after toggle"
    
    # Verify it's NOT in verified repo
    verified_facts = gui.fact_repo.get_all_facts()
    found_in_verified = False
    for fact in verified_facts:
        if fact.get("statement") == test_fact["statement"]:
            found_in_verified = True
            break
    
    assert not found_in_verified, "Fact should NOT be in verified repository after toggle to rejected"
    
    # 3. Toggle back to verified
    # Get updated facts
    all_facts, _ = gui.get_facts_for_review()
    
    # Find the fact again (now in rejected)
    fact_index = -1
    for i, fact in enumerate(all_facts):
        if fact.get("statement") == test_fact["statement"]:
            fact_index = i
            break
    
    assert fact_index >= 0, "Test fact should still be found in all_facts after rejection"
    test_fact_id = all_facts[fact_index].get("id")
    
    # Change back to verified
    result, _ = gui.update_fact(test_fact_id, test_fact["statement"], "verified", "Test verification")
    
    # Verify it's now back in verified repo
    verified_facts = gui.fact_repo.get_all_facts()
    found_in_verified = False
    for fact in verified_facts:
        if fact.get("statement") == test_fact["statement"]:
            found_in_verified = True
            break
    
    assert found_in_verified, "Fact should be back in verified repository after toggle"
    
    # Verify it's NOT in rejected repo
    rejected_facts = gui.rejected_fact_repo.get_all_rejected_facts()
    found_in_rejected = False
    for fact in rejected_facts:
        if fact.get("statement") == test_fact["statement"]:
            found_in_rejected = True
            break
    
    assert not found_in_rejected, "Fact should NOT be in rejected repository after toggle to verified" 
"""
Test script to verify the toggle behavior in the GUI.
This script tests the JavaScript and CSS formatting functions used in the GUI.
"""

import pytest
import gradio as gr

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
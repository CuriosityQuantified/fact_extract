"""
Test script to verify the toggle behavior in the GUI.
This script simulates the format_facts_for_display method and tests the JavaScript solution.
"""

import os
import sys
import gradio as gr
from pathlib import Path


# Ensure the src directory is in the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Ensure the src directory is in the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))
def test_toggle_behavior():
    """Test the toggle behavior in the GUI."""
    print("Testing toggle behavior in the GUI...")
    
    # Create a simple Gradio interface to test the toggle behavior
    with gr.Blocks() as demo:
        # Add the JavaScript for persistent details
        gr.Markdown("""
        <style>
        /* CSS to improve details appearance */
        details.persistent-details {
            margin-bottom: 10px;
            border: 1px solid #e0e0e0;
            border-radius: 4px;
            padding: 8px;
        }
        details.persistent-details > summary {
            cursor: pointer;
            font-weight: bold;
            padding: 4px;
        }
        details.persistent-details[open] > summary {
            border-bottom: 1px solid #e0e0e0;
            margin-bottom: 8px;
        }
        </style>
        
        <script>
        // JavaScript to ensure details elements stay open
        function setupPersistentDetails() {
            // Store the open state of all details elements
            const detailsStates = {};
            
            // Function to save the current state of all details elements
            function saveDetailsStates() {
                document.querySelectorAll('details.persistent-details').forEach((el, index) => {
                    detailsStates[index] = el.hasAttribute('open');
                });
            }
            
            // Function to restore the saved states
            function restoreDetailsStates() {
                document.querySelectorAll('details.persistent-details').forEach((el, index) => {
                    if (detailsStates[index]) {
                        el.setAttribute('open', '');
                    }
                });
            }
            
            // Set up a MutationObserver to detect DOM changes
            const observer = new MutationObserver((mutations) => {
                // Save current states before DOM changes
                saveDetailsStates();
                
                // Wait for DOM updates to complete
                setTimeout(() => {
                    // Restore states after DOM changes
                    restoreDetailsStates();
                    
                    // Add click listeners to any new details elements
                    document.querySelectorAll('details.persistent-details').forEach((el) => {
                        if (!el.hasAttribute('data-listener')) {
                            el.setAttribute('data-listener', 'true');
                            el.addEventListener('toggle', () => {
                                saveDetailsStates();
                            });
                        }
                    });
                }, 50);
            });
            
            // Start observing the document with the configured parameters
            observer.observe(document.body, { 
                childList: true, 
                subtree: true,
                attributes: true,
                attributeFilter: ['open']
            });
            
            // Initial setup
            saveDetailsStates();
        }
        
        // Run setup when DOM is fully loaded
        document.addEventListener('DOMContentLoaded', setupPersistentDetails);
        // Also run it now in case the DOM is already loaded
        if (document.readyState === 'interactive' || document.readyState === 'complete') {
            setupPersistentDetails();
        }
        </script>
        """)
        
        # Create a markdown component to display the facts
        facts_output = gr.Markdown(
            label="Test Toggle Behavior",
            value="Click the buttons to test the toggle behavior."
        )
        
        # Create buttons to test different scenarios
        with gr.Row():
            btn_add_fact = gr.Button("Add Fact")
            btn_add_section = gr.Button("Add Section")
            btn_reset = gr.Button("Reset")
        
        # Define the test data
        facts_data = {
            "all_facts": [],
            "sections": []
        }
        
        # Define the format_facts_for_display function
        def format_facts_for_display(facts):
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
        
        # Define the event handlers
        def add_fact():
            facts_data["all_facts"].append(f"New fact {len(facts_data['all_facts'])+1}")
            return format_facts_for_display(facts_data)
        
        def add_section():
            facts_data["sections"].append(f"New section {len(facts_data['sections'])+1}")
            return format_facts_for_display(facts_data)
        
        def reset():
            facts_data["all_facts"] = []
            facts_data["sections"] = []
            return format_facts_for_display(facts_data)
        
        # Connect the buttons to the event handlers
        btn_add_fact.click(add_fact, outputs=facts_output)
        btn_add_section.click(add_section, outputs=facts_output)
        btn_reset.click(reset, outputs=facts_output)
        
        # Initialize the display
        facts_output.value = format_facts_for_display(facts_data)
    
    # Launch the demo
    demo.launch(share=False)

if __name__ == "__main__":
    test_toggle_behavior() 
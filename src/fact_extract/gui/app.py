"""
Gradio GUI for the Fact Extraction System.
This module provides a web interface for uploading documents and viewing fact extraction results.
"""

import os
import shutil
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

import asyncio
import gradio as gr
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional
from datetime import datetime

# Import document processing libraries
from pypdf import PdfReader
from docx import Document
import csv

from ..models.state import ProcessingState, create_initial_state
from ..utils.file_utils import (
    is_valid_file, 
    get_temp_path,
    cleanup_temp_files,
    ALLOWED_EXTENSIONS,
    MAX_FILE_SIZES,
    extract_text_from_file
)
from ..graph.nodes import create_workflow
from ..storage.chunk_repository import ChunkRepository
from ..storage.fact_repository import FactRepository

# Initialize repositories
chunk_repo = ChunkRepository()
fact_repo = FactRepository()

def format_file_types() -> str:
    """Format allowed file types for display."""
    types = sorted(list(ALLOWED_EXTENSIONS))
    return ", ".join(types)

def format_size_limits() -> str:
    """Format file size limits for display."""
    return "\n".join([
        f"- {ext.upper()} files: up to {size}MB"
        for ext, size in MAX_FILE_SIZES.items()
    ])

def create_message(content: str, is_user: bool = False) -> Dict[str, str]:
    """Create a properly formatted message for Gradio chatbot."""
    return {
        "role": "user" if is_user else "assistant",
        "content": content
    }

class FactExtractionGUI:
    def __init__(self):
        self.state = ProcessingState()
        self.processing = False
        self.theme = gr.themes.Soft(
            primary_hue="blue",
            secondary_hue="gray",
        )
        self.temp_files = []
        self.chat_history = []
        
        # Create workflow
        self.workflow, self.input_key = create_workflow(chunk_repo, fact_repo)
        
        # Store facts data for UI updates
        self.facts_data = {}

    def format_facts_summary(self, facts: Dict) -> str:
        """Format summary of extracted facts."""
        if not facts:
            return "No facts extracted yet"
            
        total_submitted = 0
        total_approved = 0
        total_rejected = 0
        
        for filename, file_facts in facts.items():
            # Track totals
            if "total_facts" in file_facts:
                total_submitted += file_facts["total_facts"]
                total_approved += file_facts.get("verified_count", 0)
                total_rejected += (file_facts["total_facts"] - file_facts.get("verified_count", 0))
        
        # Create summary text
        output = []
        output.append("## Progress")
        output.append(f"- Total submissions: {total_submitted}")
        output.append(f"- Facts approved: {total_approved}")
        output.append(f"- Submissions rejected: {total_rejected}")
        
        # Add approval rate at the bottom
        if total_submitted > 0:
            output.append(f"\nApproval rate: {(total_approved/total_submitted*100):.1f}%")
        
        return "\n".join(output)
        
    def create_fact_components(self, facts: Dict):
        """Create Gradio components for displaying facts."""
        # Store facts data for later use
        self.facts_data = facts
        
        # Create summary component
        summary = gr.Markdown(self.format_facts_summary(facts))
        
        components = [summary]
        
        # Create error accordion if there are errors
        if any(file_facts.get("errors") for file_facts in facts.values()):
            with gr.Accordion("🔻 Errors", open=True) as error_accordion:
                error_md = ""
                for filename, file_facts in facts.items():
                    if file_facts.get("errors"):
                        error_md += f"\n**{filename}:**\n"
                        for error in file_facts["errors"]:
                            error_md += f"- {error}\n"
                gr.Markdown(error_md)
            components.append(error_accordion)
        
        # Create all submissions accordion
        if any(file_facts.get("all_facts") for file_facts in facts.values()):
            with gr.Accordion("🔻 All Submissions", open=True) as all_facts_accordion:
                for filename, file_facts in facts.items():
                    if file_facts.get("all_facts"):
                        gr.Markdown(f"\n**{filename}:**")
                        
                        # Create nested accordions for each fact
                        for i, fact in enumerate(file_facts["all_facts"]):
                            status = "✅" if fact.get("verification_status") == "verified" else "❌"
                            fact_title = f"{status} {fact['statement']}"
                            
                            with gr.Accordion(fact_title, open=False) as fact_accordion:
                                if fact.get("verification_reason"):
                                    gr.Markdown(f"*Reasoning:*\n{fact['verification_reason']}")
            components.append(all_facts_accordion)
        
        # Create approved facts accordion
        if any(file_facts.get("verified_facts") for file_facts in facts.values()):
            with gr.Accordion("🔻 Approved Facts", open=True) as approved_facts_accordion:
                for filename, file_facts in facts.items():
                    if file_facts.get("verified_facts"):
                        gr.Markdown(f"\n**{filename}:**")
                        
                        # Create nested accordions for each verified fact
                        for i, fact in enumerate(file_facts["verified_facts"]):
                            with gr.Accordion(f"✅ {fact['statement']}", open=False) as fact_accordion:
                                if fact.get("verification_reason"):
                                    gr.Markdown(f"*Reasoning:*\n{fact['verification_reason']}")
            components.append(approved_facts_accordion)
        
        return components

    async def process_files(self, files):
        """Process uploaded files and extract facts."""
        if self.processing:
            self.chat_history.append(create_message("Processing already in progress"))
            yield self.chat_history, self.format_facts_summary({}), "No submissions yet.", "No approved facts yet.", "No rejected submissions yet.", "No errors."
            return

        self.processing = True
        facts = {}
        self.chat_history = []
        
        from langchain_text_splitters import RecursiveCharacterTextSplitter

        try:
            for file in files:
                if not file.name:
                    self.chat_history.append(create_message("⚠️ Invalid file detected"))
                    # Update tabs with current facts data
                    yield self.chat_history, self.format_facts_summary(facts), *self.format_tabs_content(facts)
                    continue

                self.chat_history.append(create_message(f"📄 Starting to process {file.name}..."))
                yield self.chat_history, self.format_facts_summary(facts), *self.format_tabs_content(facts)

                try:
                    self.chat_history.append(create_message("📖 Extracting text from file..."))
                    yield self.chat_history, self.format_facts_summary(facts), *self.format_tabs_content(facts)
                    
                    text = extract_text_from_file(file.name)
                    if not text:
                        self.chat_history.append(create_message(f"⚠️ No text could be extracted from {file.name}"))
                        yield self.chat_history, self.format_facts_summary(facts), *self.format_tabs_content(facts)
                        continue

                    self.chat_history.append(create_message("✅ Text extracted successfully"))
                    
                    # Create initial document
                    from langchain_core.documents import Document
                    initial_doc = Document(
                        page_content=text,
                        metadata={"source": file.name}
                    )
                    
                    # Split text into manageable chunks
                    text_splitter = RecursiveCharacterTextSplitter(
                        separators=["\n\n", "\n", ". ", " "],
                        chunk_size=750,
                        chunk_overlap=50,
                        length_function=lambda x: len(x.split()),  # Word-based length function
                    )
                    
                    # Split the document
                    try:
                        documents = text_splitter.split_documents([initial_doc])
                        
                        self.chat_history.append(create_message(f"📝 Split text into {len(documents)} chunks"))
                        yield self.chat_history, self.format_facts_summary(facts), *self.format_tabs_content(facts)
                        
                        # Initialize file facts structure
                        facts[file.name] = {
                            "all_facts": [],
                            "verified_facts": [],
                            "total_facts": 0,
                            "verified_count": 0,
                            "errors": []
                        }
                        
                        # Process each chunk
                        for i, doc in enumerate(documents, 1):
                            if not hasattr(doc, 'page_content'):
                                error_msg = f"Error in chunk {i}: Invalid document format"
                                facts[file.name]["errors"].append(error_msg)
                                self.chat_history.append(create_message(f"⚠️ {error_msg}"))
                                # Update tabs with current facts data
                                yield self.chat_history, self.format_facts_summary(facts), *self.format_tabs_content(facts)
                                continue
                                
                            # Get first 50 words as preview
                            preview = " ".join(doc.page_content.split()[:50]) + "..."
                            self.chat_history.append(create_message(f"🔄 Processing chunk {i} of {len(documents)}:\n{preview}"))
                            yield self.chat_history, self.format_facts_summary(facts), *self.format_tabs_content(facts)
                            
                            # Create workflow state for this chunk
                            workflow_state = create_initial_state(
                                input_text=doc.page_content,
                                document_name=f"{file.name} (chunk {i}/{len(documents)})",
                                source_url=""
                            )
                            
                            # Run workflow on chunk
                            result = await self.workflow.ainvoke(workflow_state)
                            
                            if result and result.get("extracted_facts"):
                                chunk_facts = result["extracted_facts"]
                                facts[file.name]["all_facts"].extend(chunk_facts)
                                verified_facts = [f for f in chunk_facts if f.get("verification_status") == "verified"]
                                facts[file.name]["verified_facts"].extend(verified_facts)
                                facts[file.name]["total_facts"] += len(chunk_facts)
                                facts[file.name]["verified_count"] += len(verified_facts)
                                
                                # Show chunk results with submitted and approved facts
                                self.chat_history.append(create_message(
                                    f"✓ Chunk {i}: {len(chunk_facts)} submissions, {len(verified_facts)} approved facts"
                                ))
                                
                                # Show the facts from this chunk
                                fact_list = []
                                for fact in chunk_facts:
                                    status = "✅" if fact.get("verification_status") == "verified" else "❌"
                                    fact_list.append(f"{status} {fact['statement']}")
                                if fact_list:
                                    self.chat_history.append(create_message("\n".join(fact_list)))
                                
                            if result and result.get("errors"):
                                facts[file.name]["errors"].extend(result["errors"])
                            
                            # Store facts data for display
                            self.facts_data = facts
                                
                            # Update tabs with current facts data
                            yield self.chat_history, self.format_facts_summary(facts), *self.format_tabs_content(facts)
                        
                    except Exception as e:
                        error_msg = f"Error splitting document: {str(e)}"
                        facts[file.name]["errors"].append(error_msg)
                        self.chat_history.append(create_message(f"⚠️ {error_msg}"))
                        yield self.chat_history, self.format_facts_summary(facts), *self.format_tabs_content(facts)

                    self.chat_history.append(create_message(
                        f"✅ Completed processing {file.name}\n" +
                        f"Total submissions: {facts[file.name]['total_facts']}\n" +
                        f"Total facts approved: {facts[file.name]['verified_count']}\n" +
                        f"Total submissions rejected: {facts[file.name]['total_facts'] - facts[file.name]['verified_count']}"
                    ))
                    yield self.chat_history, self.format_facts_summary(facts), *self.format_tabs_content(facts)

                except Exception as e:
                    self.chat_history.append(create_message(f"⚠️ Error processing {file.name}: {str(e)}"))
                    yield self.chat_history, self.format_facts_summary(facts), *self.format_tabs_content(facts)
                    continue

        except Exception as e:
            self.chat_history.append(create_message(f"⚠️ Error during processing: {str(e)}"))
            yield self.chat_history, self.format_facts_summary(facts), *self.format_tabs_content(facts)

        finally:
            self.processing = False
            if facts:
                total_submitted = sum(f["total_facts"] for f in facts.values())
                total_approved = sum(f["verified_count"] for f in facts.values())
                self.chat_history.append(create_message(
                    "✅ Processing complete\n" +
                    f"Total submissions: {total_submitted}\n" +
                    f"Total facts approved: {total_approved}\n" +
                    f"Total submissions rejected: {total_submitted - total_approved}\n" +
                    f"Overall approval rate: {(total_approved/total_submitted*100):.1f}%"
                ))
                
                # Store facts data for display
                self.facts_data = facts
                
                # Add debug information
                print(f"DEBUG: Facts data structure: {len(facts)} files with data")
                for filename, file_data in facts.items():
                    print(f"DEBUG: File {filename}: {file_data.get('total_facts', 0)} total facts, {file_data.get('verified_count', 0)} verified")
                    if file_data.get('all_facts'):
                        print(f"DEBUG: First fact: {file_data['all_facts'][0]['statement'] if file_data['all_facts'] else 'None'}")
            else:
                self.chat_history.append(create_message("⚠️ No facts were extracted"))
                # Clear facts data
                self.facts_data = {}
                print("DEBUG: No facts were extracted")
                
            yield self.chat_history, self.format_facts_summary(facts), *self.format_tabs_content(facts)
            
    def format_tabs_content(self, facts):
        """Format content for all tabs."""
        # Store facts data for later use
        self.facts_data = facts
        
        # Format all submissions
        all_submissions_md = ""
        for filename, file_facts in facts.items():
            if file_facts.get("all_facts"):
                all_submissions_md += f"\n## {filename}\n\n"
                for i, fact in enumerate(file_facts["all_facts"]):
                    status = "✅" if fact.get("verification_status") == "verified" else "❌"
                    all_submissions_md += f"{status} **Fact {i+1}:** {fact['statement']}\n\n"
                    if fact.get("verification_reason"):
                        all_submissions_md += f"*Reasoning:*\n{fact['verification_reason']}\n\n"
                    all_submissions_md += "---\n\n"
        
        # Format approved facts
        approved_facts_md = ""
        for filename, file_facts in facts.items():
            if file_facts.get("verified_facts"):
                approved_facts_md += f"\n## {filename}\n\n"
                for i, fact in enumerate(file_facts["verified_facts"]):
                    approved_facts_md += f"✅ **Fact {i+1}:** {fact['statement']}\n\n"
                    if fact.get("verification_reason"):
                        approved_facts_md += f"*Reasoning:*\n{fact['verification_reason']}\n\n"
                    approved_facts_md += "---\n\n"
        
        # Format rejected submissions
        rejected_facts_md = ""
        for filename, file_facts in facts.items():
            if file_facts.get("all_facts"):
                rejected_facts = [f for f in file_facts["all_facts"] if f.get("verification_status") != "verified"]
                if rejected_facts:
                    rejected_facts_md += f"\n## {filename}\n\n"
                    for i, fact in enumerate(rejected_facts):
                        rejected_facts_md += f"❌ **Submission {i+1}:** {fact['statement']}\n\n"
                        if fact.get("verification_reason"):
                            rejected_facts_md += f"*Reasoning:*\n{fact['verification_reason']}\n\n"
                        rejected_facts_md += "---\n\n"
        
        # Format errors
        errors_md = ""
        for filename, file_facts in facts.items():
            if file_facts.get("errors"):
                errors_md += f"\n## {filename}\n\n"
                for error in file_facts["errors"]:
                    errors_md += f"- {error}\n"
                errors_md += "\n"
        
        # Set default messages if no content
        if not all_submissions_md:
            all_submissions_md = "No submissions yet."
        if not approved_facts_md:
            approved_facts_md = "No approved facts yet."
        if not rejected_facts_md:
            rejected_facts_md = "No rejected submissions yet."
        if not errors_md:
            errors_md = "No errors."
        
        return all_submissions_md, approved_facts_md, rejected_facts_md, errors_md

    def build_interface(self) -> gr.Blocks:
        """Build the Gradio interface."""
        with gr.Blocks(title="Fact Extraction System", theme=self.theme) as interface:
            gr.Markdown("""
            # Fact Extraction System
            Upload documents to extract and verify facts using AI.
            """)
            
            # File format info
            with gr.Accordion("Supported Formats", open=False):
                gr.Markdown(f"""
                **Supported file types:**
                {format_file_types()}
                
                **Size limits:**
                {format_size_limits()}
                """)
            
            with gr.Row():
                with gr.Column(scale=2):
                    file_input = gr.File(
                        label="Upload Documents",
                        file_count="multiple",
                        file_types=list(ALLOWED_EXTENSIONS),
                        elem_id="file-upload"
                    )
                    
                    process_btn = gr.Button(
                        "Start Processing",
                        variant="primary",
                        interactive=True
                    )
                    
                with gr.Column(scale=3):
                    chat_display = gr.Chatbot(
                        label="Processing Status",
                        type="messages",
                        height=400
                    )
            
            # Facts output section
            with gr.Row():
                with gr.Column(elem_id="facts-container"):
                    gr.Markdown("## Extracted Facts", elem_id="facts-heading")
                    facts_summary = gr.Markdown(
                        value="Upload a document to see extracted facts here.",
                        elem_id="facts-summary"
                    )
                    
                    # Create tabs for different fact categories
                    with gr.Tabs(elem_id="facts-tabs") as facts_tabs:
                        with gr.TabItem("All Submissions", elem_id="all-submissions-tab"):
                            all_submissions = gr.Markdown("No submissions yet.")
                        
                        with gr.TabItem("Approved Facts", elem_id="approved-facts-tab"):
                            approved_facts = gr.Markdown("No approved facts yet.")
                        
                        with gr.TabItem("Rejected Submissions", elem_id="rejected-facts-tab"):
                            rejected_facts = gr.Markdown("No rejected submissions yet.")
                        
                        with gr.TabItem("Errors", elem_id="errors-tab"):
                            errors_display = gr.Markdown("No errors.")
            
            # Event handlers
            def update_facts_display(chat_history, facts_summary):
                """Update the facts display with the current facts data."""
                if not self.facts_data:
                    return chat_history, facts_summary, "No submissions yet.", "No approved facts yet.", "No rejected submissions yet.", "No errors."
                
                # Format all submissions
                all_submissions_md = ""
                for filename, file_facts in self.facts_data.items():
                    if file_facts.get("all_facts"):
                        all_submissions_md += f"\n## {filename}\n\n"
                        for i, fact in enumerate(file_facts["all_facts"]):
                            status = "✅" if fact.get("verification_status") == "verified" else "❌"
                            all_submissions_md += f"{status} **Fact {i+1}:** {fact['statement']}\n\n"
                            if fact.get("verification_reason"):
                                all_submissions_md += f"*Reasoning:*\n{fact['verification_reason']}\n\n"
                            all_submissions_md += "---\n\n"
                
                # Format approved facts
                approved_facts_md = ""
                for filename, file_facts in self.facts_data.items():
                    if file_facts.get("verified_facts"):
                        approved_facts_md += f"\n## {filename}\n\n"
                        for i, fact in enumerate(file_facts["verified_facts"]):
                            approved_facts_md += f"✅ **Fact {i+1}:** {fact['statement']}\n\n"
                            if fact.get("verification_reason"):
                                approved_facts_md += f"*Reasoning:*\n{fact['verification_reason']}\n\n"
                            approved_facts_md += "---\n\n"
                
                # Format rejected submissions
                rejected_facts_md = ""
                for filename, file_facts in self.facts_data.items():
                    if file_facts.get("all_facts"):
                        rejected_facts = [f for f in file_facts["all_facts"] if f.get("verification_status") != "verified"]
                        if rejected_facts:
                            rejected_facts_md += f"\n## {filename}\n\n"
                            for i, fact in enumerate(rejected_facts):
                                rejected_facts_md += f"❌ **Submission {i+1}:** {fact['statement']}\n\n"
                                if fact.get("verification_reason"):
                                    rejected_facts_md += f"*Reasoning:*\n{fact['verification_reason']}\n\n"
                                rejected_facts_md += "---\n\n"
                
                # Format errors
                errors_md = ""
                for filename, file_facts in self.facts_data.items():
                    if file_facts.get("errors"):
                        errors_md += f"\n## {filename}\n\n"
                        for error in file_facts["errors"]:
                            errors_md += f"- {error}\n"
                        errors_md += "\n"
                
                # Set default messages if no content
                if not all_submissions_md:
                    all_submissions_md = "No submissions yet."
                if not approved_facts_md:
                    approved_facts_md = "No approved facts yet."
                if not rejected_facts_md:
                    rejected_facts_md = "No rejected submissions yet."
                if not errors_md:
                    errors_md = "No errors."
                
                return chat_history, facts_summary, all_submissions_md, approved_facts_md, rejected_facts_md, errors_md
            
            process_btn.click(
                fn=self.process_files,
                inputs=[file_input],
                outputs=[chat_display, facts_summary, all_submissions, approved_facts, rejected_facts, errors_display],
                api_name="process",
                show_progress=True
            ).then(
                lambda: gr.update(interactive=True),
                None,
                [process_btn]
            )
            
            # Disable button during processing
            process_btn.click(
                lambda: gr.update(interactive=False),
                None,
                [process_btn],
                queue=False
            )
            
            # File drag-and-drop styling
            file_input.change(
                fn=lambda x: x,  # Simple identity function
                inputs=file_input,
                outputs=file_input
            )
            
        return interface

def create_app():
    """Create and configure the Gradio app."""
    gui = FactExtractionGUI()
    interface = gui.build_interface()
    return interface

if __name__ == "__main__":
    print("\nStarting Fact Extraction System GUI...")
    print("="*50)
    app = create_app()
    print("\nLaunching web interface...")
    
    # Try a range of ports if the default is in use
    for port in range(7860, 7870):
        try:
            app.launch(
                server_name="0.0.0.0",
                server_port=port,
                share=False,
                show_error=True,
                debug=True
            )
            print(f"\nServer running on port {port}")
            break
        except OSError as e:
            if "address already in use" in str(e).lower():
                print(f"Port {port} is in use, trying next port...")
                continue
            else:
                raise e
    else:
        print("\nError: Could not find an available port in range 7860-7869")
    
    print("\nServer stopped.") 
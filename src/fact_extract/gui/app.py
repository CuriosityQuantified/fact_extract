"""
Gradio GUI for the Fact Extraction System.
This module provides a web interface for uploading documents and viewing fact extraction results.
"""

import os
import shutil
import sys  # Added for stderr output
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
        
        # Debug mode
        self.debug = True
        print("DEBUG_INIT: FactExtractionGUI initialized")

    def debug_print(self, message):
        """Print debug message to stderr for visibility."""
        if self.debug:
            print(f"DEBUG: {message}", file=sys.stderr, flush=True)
            print(f"DEBUG: {message}")  # Also to stdout for redundancy

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
            yield self.chat_history, self.format_facts_summary({}), "No submissions yet.", "No approved facts yet.", "No rejected submissions yet.", "No errors.", []
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
                    yield self.chat_history, self.format_facts_summary(facts), *self.format_tabs_content(facts), []
                    continue

                self.chat_history.append(create_message(f"📄 Starting to process {file.name}..."))
                yield self.chat_history, self.format_facts_summary(facts), *self.format_tabs_content(facts), []

                try:
                    self.chat_history.append(create_message("📖 Extracting text from file..."))
                    yield self.chat_history, self.format_facts_summary(facts), *self.format_tabs_content(facts), []
                    
                    text = extract_text_from_file(file.name)
                    if not text:
                        self.chat_history.append(create_message(f"⚠️ No text could be extracted from {file.name}"))
                        yield self.chat_history, self.format_facts_summary(facts), *self.format_tabs_content(facts), []
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
                        yield self.chat_history, self.format_facts_summary(facts), *self.format_tabs_content(facts), []
                        
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
                                yield self.chat_history, self.format_facts_summary(facts), *self.format_tabs_content(facts), []
                                continue
                                
                            # Get first 50 words as preview
                            preview = " ".join(doc.page_content.split()[:50]) + "..."
                            self.chat_history.append(create_message(f"🔄 Processing chunk {i} of {len(documents)}:\n{preview}"))
                            yield self.chat_history, self.format_facts_summary(facts), *self.format_tabs_content(facts), []
                            
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
                                
                                # Add unique IDs to facts
                                for fact in chunk_facts:
                                    if "id" not in fact:
                                        fact["id"] = id(fact)  # Use object id as unique identifier
                                    fact["filename"] = file.name
                                
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
                            
                            # Get facts for review dropdown
                            _, fact_choices = self.get_facts_for_review()
                                
                            # Update tabs with current facts data
                            yield self.chat_history, self.format_facts_summary(facts), *self.format_tabs_content(facts), fact_choices
                        
                    except Exception as e:
                        error_msg = f"Error splitting document: {str(e)}"
                        facts[file.name]["errors"].append(error_msg)
                        self.chat_history.append(create_message(f"⚠️ {error_msg}"))
                        yield self.chat_history, self.format_facts_summary(facts), *self.format_tabs_content(facts), []

                    self.chat_history.append(create_message(
                        f"✅ Completed processing {file.name}\n" +
                        f"Total submissions: {facts[file.name]['total_facts']}\n" +
                        f"Total facts approved: {facts[file.name]['verified_count']}\n" +
                        f"Total submissions rejected: {facts[file.name]['total_facts'] - facts[file.name]['verified_count']}"
                    ))
                    
                    # Get facts for review dropdown after processing file
                    _, fact_choices = self.get_facts_for_review()
                    yield self.chat_history, self.format_facts_summary(facts), *self.format_tabs_content(facts), fact_choices

                except Exception as e:
                    self.chat_history.append(create_message(f"⚠️ Error processing {file.name}: {str(e)}"))
                    yield self.chat_history, self.format_facts_summary(facts), *self.format_tabs_content(facts), []
                    continue

        except Exception as e:
            self.chat_history.append(create_message(f"⚠️ Error during processing: {str(e)}"))
            yield self.chat_history, self.format_facts_summary(facts), *self.format_tabs_content(facts), []

        finally:
            self.processing = False
            if facts:
                total_submitted = sum(f["total_facts"] for f in facts.values())
                total_approved = sum(f["verified_count"] for f in facts.values())
                
                # Final summary message
                self.chat_history.append(create_message(
                    f"✅ Processing complete!\n" +
                    f"Total submissions: {total_submitted}\n" +
                    f"Total facts approved: {total_approved}\n" +
                    f"Total submissions rejected: {total_submitted - total_approved}\n\n" +
                    f"Approval rate: {(total_approved/total_submitted*100):.1f}%" if total_submitted > 0 else "0%"
                ))
                
                # Get facts for review dropdown after all processing
                _, fact_choices = self.get_facts_for_review()
                yield self.chat_history, self.format_facts_summary(facts), *self.format_tabs_content(facts), fact_choices
            else:
                self.chat_history.append(create_message("⚠️ No facts were extracted"))
                yield self.chat_history, self.format_facts_summary(facts), *self.format_tabs_content(facts), []
            
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
    
    def get_facts_for_review(self):
        """Get all facts available for review."""
        self.debug_print(f"get_facts_for_review called, facts_data has {len(self.facts_data)} files")
        
        all_facts = []
        fact_choices = []
        
        # Extract all facts from fact_data
        for filename, file_facts in self.facts_data.items():
            self.debug_print(f"Processing file: {filename}")
            if file_facts.get("all_facts"):
                self.debug_print(f"  File has {len(file_facts['all_facts'])} facts")
                for i, fact in enumerate(file_facts["all_facts"]):
                    # Add unique ID to fact if not present
                    if "id" not in fact:
                        fact["id"] = id(fact)  # Use object id as unique identifier
                        self.debug_print(f"  Assigned new ID {fact['id']} to fact {i}")
                    else:
                        self.debug_print(f"  Fact {i} already has ID {fact['id']}")
                    
                    # Add filename to fact for reference
                    fact["filename"] = filename
                    
                    # Add to all_facts list
                    all_facts.append(fact)
                    
                    # Format choice as "status | first 40 chars of statement"
                    status_emoji = "✅" if fact.get("verification_status") == "verified" else "❌" if fact.get("verification_status") == "rejected" else "⏳"
                    preview = fact["statement"][:40] + "..." if len(fact["statement"]) > 40 else fact["statement"]
                    choice_text = f"{status_emoji} {preview}"
                    fact_choices.append(choice_text)
                    self.debug_print(f"  Added choice: '{choice_text}'")
            else:
                self.debug_print(f"  File has no facts")
        
        # Debug information
        self.debug_print(f"Found {len(all_facts)} facts for review")
        for i, fact in enumerate(all_facts):
            self.debug_print(f"Fact {i}: ID={fact.get('id')}, Statement={fact.get('statement', '')[:30]}...")
        
        self.debug_print(f"Returning {len(fact_choices)} choices for dropdown")
        for i, choice in enumerate(fact_choices):
            self.debug_print(f"  Choice {i}: '{choice}'")
        
        return all_facts, fact_choices
    
    def load_fact_for_review(self, fact_index):
        """Load a fact into the review interface."""
        self.debug_print(f"load_fact_for_review called with index: {fact_index} (type: {type(fact_index)})")
        
        if fact_index is None or fact_index == "":
            self.debug_print("Empty fact_index, returning empty values")
            return "", "", "", "", "pending", ""
        
        all_facts, fact_choices = self.get_facts_for_review()
        self.debug_print(f"Got {len(all_facts)} facts and {len(fact_choices)} choices")
        
        # Convert string index to integer if needed
        if isinstance(fact_index, str):
            try:
                fact_index = int(fact_index)
                self.debug_print(f"Converted string index '{fact_index}' to integer")
            except ValueError:
                self.debug_print(f"Could not convert '{fact_index}' to integer - searching by value")
                # Try to find the index by matching the choice text
                for i, choice in enumerate(fact_choices):
                    if choice == fact_index:
                        fact_index = i
                        self.debug_print(f"Found matching choice at index {i}")
                        break
                else:
                    self.debug_print("No matching choice found - returning empty values")
                    return "", "", "", "", "pending", ""
        
        # Validate index range
        if not (0 <= fact_index < len(all_facts)):
            self.debug_print(f"Index {fact_index} out of range (0-{len(all_facts)-1}) - returning empty values")
            return "", "", "", "", "pending", ""
        
        # Get the selected fact
        fact = all_facts[fact_index]
        
        # Debug information
        self.debug_print(f"Loading fact with ID: {fact.get('id')}")
        self.debug_print(f"Fact statement: {fact.get('statement', '')[:50]}...")
        self.debug_print(f"Fact source: {fact.get('original_text', '')[:50]}...")
        self.debug_print(f"Fact status: {fact.get('verification_status', 'pending')}")
        
        # Ensure all values are strings to avoid UI errors
        fact_id_str = str(fact.get("id", ""))
        filename_str = str(fact.get("filename", ""))
        statement_str = str(fact.get("statement", ""))
        source_str = str(fact.get("original_text", ""))
        status_str = str(fact.get("verification_status", "pending"))
        reason_str = str(fact.get("verification_reason", ""))
        
        self.debug_print(f"Returning values:")
        self.debug_print(f"  ID: {fact_id_str}")
        self.debug_print(f"  Filename: {filename_str}")
        self.debug_print(f"  Statement: {statement_str[:50]}...")
        self.debug_print(f"  Source: {source_str[:50]}...")
        self.debug_print(f"  Status: {status_str}")
        self.debug_print(f"  Reason: {reason_str[:50]}...")
        
        return (
            fact_id_str,  # fact_id
            filename_str,  # filename
            statement_str,  # fact_statement
            source_str,  # fact_source
            status_str,  # fact_status
            reason_str  # fact_reason
        )
    
    def update_fact(self, fact_id, statement, status, reason):
        """Update a fact with new information."""
        self.debug_print(f"update_fact called with ID: {fact_id}")
        self.debug_print(f"  Statement: {statement[:50]}...")
        self.debug_print(f"  Status: {status}")
        self.debug_print(f"  Reason: {reason[:50]}...")
        
        if not fact_id:
            self.debug_print("No fact selected, returning error")
            return "No fact selected", self.facts_data
        
        try:
            # Convert fact_id back to integer (it comes as string from the UI)
            try:
                fact_id_int = int(fact_id)
                self.debug_print(f"Converted fact_id to integer: {fact_id_int}")
            except ValueError:
                self.debug_print(f"Could not convert fact_id to integer: {fact_id}")
                return f"Error: Invalid fact ID format: {fact_id}", self.facts_data
            
            # Find and update the fact in self.facts_data
            found = False
            for filename, file_facts in self.facts_data.items():
                self.debug_print(f"Searching in file: {filename}")
                if file_facts.get("all_facts"):
                    for i, fact in enumerate(file_facts["all_facts"]):
                        self.debug_print(f"  Checking fact {i} with ID: {fact.get('id')}")
                        if fact.get("id") == fact_id_int:
                            self.debug_print(f"  Found matching fact at index {i}")
                            found = True
                            
                            # Store original values for debugging
                            old_statement = fact.get("statement", "")
                            old_status = fact.get("verification_status", "pending")
                            old_reason = fact.get("verification_reason", "")
                            
                            # Update fact properties
                            fact["statement"] = statement
                            fact["verification_status"] = status
                            fact["verification_reason"] = reason
                            fact["human_reviewed"] = True
                            fact["review_timestamp"] = datetime.now().isoformat()
                            
                            self.debug_print(f"  Updated fact:")
                            self.debug_print(f"    Statement: {old_statement[:30]}... -> {statement[:30]}...")
                            self.debug_print(f"    Status: {old_status} -> {status}")
                            self.debug_print(f"    Reason: {old_reason[:30]}... -> {reason[:30]}...")
                            
                            # Update verified_facts list if applicable
                            if status == "verified":
                                # Remove from verified if already there (to avoid duplicates)
                                verified_before = len(file_facts.get("verified_facts", []))
                                file_facts["verified_facts"] = [f for f in file_facts.get("verified_facts", []) 
                                                               if f.get("id") != fact_id_int]
                                verified_after = len(file_facts["verified_facts"])
                                
                                self.debug_print(f"  Removed from verified_facts: {verified_before - verified_after} instances")
                                
                                # Add updated fact to verified list
                                file_facts["verified_facts"].append(fact)
                                self.debug_print(f"  Added to verified_facts, new count: {len(file_facts['verified_facts'])}")
                            else:
                                # Remove from verified if rejected or pending
                                verified_before = len(file_facts.get("verified_facts", []))
                                file_facts["verified_facts"] = [f for f in file_facts.get("verified_facts", []) 
                                                               if f.get("id") != fact_id_int]
                                verified_after = len(file_facts["verified_facts"])
                                
                                self.debug_print(f"  Removed from verified_facts: {verified_before - verified_after} instances")
                            
                            # Update counts
                            old_verified_count = file_facts.get("verified_count", 0)
                            verified_count = len([f for f in file_facts["all_facts"] 
                                                 if f.get("verification_status") == "verified"])
                            file_facts["verified_count"] = verified_count
                            
                            self.debug_print(f"  Updated verified count: {old_verified_count} -> {verified_count}")
                            
                            # Update fact choices for dropdown
                            _, fact_choices = self.get_facts_for_review()
                            self.debug_print(f"  Updated fact choices, now have {len(fact_choices)} choices")
                            
                            return f"Fact updated: {statement[:40]}...", self.facts_data
            
            if not found:
                self.debug_print(f"Fact with ID {fact_id_int} not found in any file")
                return f"Fact not found with ID: {fact_id}", self.facts_data
                
        except Exception as e:
            import traceback
            self.debug_print(f"Error updating fact: {str(e)}")
            self.debug_print(f"Traceback: {traceback.format_exc()}")
            return f"Error updating fact: {str(e)}", self.facts_data

    def approve_fact(self, fact_id, statement, reason):
        """Approve a fact with optional minor modifications."""
        return self.update_fact(fact_id, statement, "verified", reason)

    def reject_fact(self, fact_id, statement, reason):
        """Reject a fact with reasoning."""
        return self.update_fact(fact_id, statement, "rejected", reason)

    def build_interface(self) -> gr.Blocks:
        """Build the Gradio interface."""
        self.debug_print("Building Gradio interface")
        
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
            
            # Main tabs for different sections
            with gr.Tabs(elem_id="main-tabs") as main_tabs:
                # Facts output section
                with gr.TabItem("Extracted Facts", elem_id="facts-tab"):
                    with gr.Column(elem_id="facts-container"):
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
                
                # Fact Review section
                with gr.TabItem("Fact Review", elem_id="fact-review-tab"):
                    self.debug_print("Building Fact Review tab")
                    
                    # Debug display for troubleshooting
                    debug_display = gr.Markdown("Debug information will appear here", visible=True)
                    
                    with gr.Row():
                        # Left column for fact selection
                        with gr.Column(scale=1):
                            fact_selector = gr.Dropdown(
                                label="Select Fact to Review",
                                choices=[],
                                value=None,  # Set initial value to None
                                type="index",  # Changed to index type for more reliable selection
                                interactive=True,
                                allow_custom_value=False  # Don't allow custom values
                            )
                            self.debug_print("Created fact_selector dropdown")
                            
                            refresh_facts_btn = gr.Button("Refresh Facts List")
                            self.debug_print("Created refresh_facts_btn")
                                
                        # Right column for fact details
                        with gr.Column(scale=2):
                            # Current fact details
                            fact_id = gr.Textbox(label="Fact ID", visible=True)  # Made visible for debugging
                            self.debug_print("Created fact_id textbox")
                            
                            fact_filename = gr.Textbox(label="Source Document", interactive=False)
                            self.debug_print("Created fact_filename textbox")
                            
                            fact_statement = gr.Textbox(
                                label="Fact Statement", 
                                lines=3,
                                interactive=True
                            )
                            self.debug_print("Created fact_statement textbox")
                            
                            fact_source = gr.Textbox(
                                label="Source Text", 
                                lines=5,
                                interactive=False
                            )
                            self.debug_print("Created fact_source textbox")
                            
                            fact_status = gr.Radio(
                                choices=["verified", "rejected", "pending"],
                                label="Status",
                                value="pending",
                                interactive=True
                            )
                            self.debug_print("Created fact_status radio")
                            
                            fact_reason = gr.Textbox(
                                label="Reasoning", 
                                lines=3,
                                placeholder="Provide reasoning for your decision",
                                interactive=True
                            )
                            self.debug_print("Created fact_reason textbox")
                                
                    # Action buttons
                    with gr.Row():
                        approve_btn = gr.Button("Approve Fact", variant="primary")
                        reject_btn = gr.Button("Reject Fact", variant="secondary")
                        modify_btn = gr.Button("Save Modifications", variant="primary")
                    self.debug_print("Created action buttons")
                    
                    # Status message
                    review_status = gr.Markdown("")
                    self.debug_print("Created review_status markdown")
            
            # Event handlers
            def update_facts_display(chat_history, facts_summary):
                """Update the facts display with the current facts data."""
                self.debug_print("update_facts_display called")
                
                if not self.facts_data:
                    self.debug_print("No facts data available")
                    return chat_history, facts_summary, "No submissions yet.", "No approved facts yet.", "No rejected submissions yet.", "No errors.", []
                
                # Format all submissions
                all_submissions_md = ""
                for filename, file_facts in self.facts_data.items():
                    self.debug_print(f"Processing file: {filename}")
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
                
                # Get updated fact choices for the dropdown
                all_facts, fact_choices = self.get_facts_for_review()
                self.debug_print(f"Got {len(fact_choices)} fact choices for dropdown")
                
                # Return updated dropdown choices
                return (
                    chat_history, 
                    facts_summary, 
                    all_submissions_md, 
                    approved_facts_md, 
                    rejected_facts_md, 
                    errors_md, 
                    gr.update(choices=fact_choices)  # Use gr.update to update dropdown choices
                )
            
            # Process files function
            async def process_files_wrapper(files):
                """Wrapper for process_files that ensures dropdown is properly updated."""
                self.debug_print("process_files_wrapper called")
                
                # Call the original process_files function
                async for result in self.process_files(files):
                    chat_history, facts_summary, all_submissions_md, approved_facts_md, rejected_facts_md, errors_md, fact_choices = result
                    
                    # Get the current facts and choices
                    all_facts, choices = self.get_facts_for_review()
                    self.debug_print(f"After processing, got {len(all_facts)} facts and {len(choices)} choices")
                    
                    # Debug information about choices
                    debug_info = f"Updated dropdown with {len(choices)} choices:\n"
                    for i, choice in enumerate(choices):
                        debug_info += f"Choice {i}: '{choice}'\n"
                    
                    # Yield the result with updated dropdown
                    yield chat_history, facts_summary, all_submissions_md, approved_facts_md, rejected_facts_md, errors_md, gr.update(choices=choices, value=None), debug_info
            
            # Replace the original process_files with the wrapper
            process_btn.click(
                fn=process_files_wrapper,
                inputs=[file_input],
                outputs=[chat_display, facts_summary, all_submissions, approved_facts, rejected_facts, errors_display, fact_selector, debug_display],
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
            
            # Connect fact selector to display selected fact
            def on_fact_selected(selected_index):
                self.debug_print(f"on_fact_selected called with index: {selected_index} (type: {type(selected_index)})")
                
                # Get current facts and choices
                all_facts, fact_choices = self.get_facts_for_review()
                
                # Debug information about available facts and choices
                debug_info = [
                    f"Selected index: {selected_index} (type: {type(selected_index)})",
                    f"Number of facts: {len(all_facts)}",
                    f"Number of choices: {len(fact_choices)}",
                ]
                
                # Add information about each choice
                for i, choice in enumerate(fact_choices):
                    debug_info.append(f"Choice {i}: '{choice}'")
                
                # Handle invalid selection
                if selected_index is None or selected_index == "" or not isinstance(selected_index, (int, str)):
                    debug_info.append("Invalid selection - returning empty values")
                    return "", "", "", "", "pending", "", "\n".join(debug_info)
                
                # Convert string index to integer if needed
                if isinstance(selected_index, str):
                    try:
                        selected_index = int(selected_index)
                        debug_info.append(f"Converted string index '{selected_index}' to integer")
                    except ValueError:
                        debug_info.append(f"Could not convert '{selected_index}' to integer - searching by value")
                        # Try to find the index by matching the choice text
                        for i, choice in enumerate(fact_choices):
                            if choice == selected_index:
                                selected_index = i
                                debug_info.append(f"Found matching choice at index {i}")
                                break
                        else:
                            debug_info.append("No matching choice found - returning empty values")
                            return "", "", "", "", "pending", "", "\n".join(debug_info)
                
                # Validate index range
                if not (0 <= selected_index < len(all_facts)):
                    debug_info.append(f"Index {selected_index} out of range (0-{len(all_facts)-1}) - returning empty values")
                    return "", "", "", "", "pending", "", "\n".join(debug_info)
                
                # Get the selected fact
                fact = all_facts[selected_index]
                debug_info.append(f"Selected fact: ID={fact.get('id')}, Statement={fact.get('statement', '')[:30]}...")
                
                # Ensure all values are strings to avoid UI errors
                fact_id_str = str(fact.get("id", ""))
                filename_str = str(fact.get("filename", ""))
                statement_str = str(fact.get("statement", ""))
                source_str = str(fact.get("original_text", ""))
                status_str = str(fact.get("verification_status", "pending"))
                reason_str = str(fact.get("verification_reason", ""))
                
                debug_info.append(f"Returning values:")
                debug_info.append(f"  ID: {fact_id_str}")
                debug_info.append(f"  Filename: {filename_str}")
                debug_info.append(f"  Statement: {statement_str[:50]}...")
                debug_info.append(f"  Source: {source_str[:50]}...")
                debug_info.append(f"  Status: {status_str}")
                debug_info.append(f"  Reason: {reason_str[:50]}...")
                
                return (
                    fact_id_str,  # fact_id
                    filename_str,  # filename
                    statement_str,  # fact_statement
                    source_str,  # fact_source
                    status_str,  # fact_status
                    reason_str,  # fact_reason
                    "\n".join(debug_info)  # debug info
                )
            
            fact_selector.change(
                fn=on_fact_selected,
                inputs=[fact_selector],
                outputs=[fact_id, fact_filename, fact_statement, fact_source, fact_status, fact_reason, debug_display]
            )
            self.debug_print("Connected fact_selector.change event")

            # Connect refresh button
            def on_refresh_facts():
                self.debug_print("on_refresh_facts called")
                all_facts, choices = self.get_facts_for_review()
                
                # Debug information
                debug_info = [
                    f"Refreshed fact choices: {len(choices)} items",
                    f"Number of facts: {len(all_facts)}",
                ]
                
                # Add information about each choice
                for i, choice in enumerate(choices):
                    debug_info.append(f"Choice {i}: '{choice}'")
                
                return gr.update(choices=choices, value=None), "\n".join(debug_info)
                
            refresh_facts_btn.click(
                fn=on_refresh_facts,
                inputs=[],
                outputs=[fact_selector, debug_display]
            )
            self.debug_print("Connected refresh_facts_btn.click event")

            # Connect approve button
            approve_btn.click(
                fn=self.approve_fact,
                inputs=[fact_id, fact_statement, fact_reason],
                outputs=[review_status, facts_summary]
            ).then(
                fn=update_facts_display,
                inputs=[chat_display, facts_summary],
                outputs=[chat_display, facts_summary, all_submissions, approved_facts, rejected_facts, errors_display, fact_selector]
            )

            # Connect reject button
            reject_btn.click(
                fn=self.reject_fact,
                inputs=[fact_id, fact_statement, fact_reason],
                outputs=[review_status, facts_summary]
            ).then(
                fn=update_facts_display,
                inputs=[chat_display, facts_summary],
                outputs=[chat_display, facts_summary, all_submissions, approved_facts, rejected_facts, errors_display, fact_selector]
            )

            # Connect modify button
            modify_btn.click(
                fn=self.update_fact,
                inputs=[fact_id, fact_statement, fact_status, fact_reason],
                outputs=[review_status, facts_summary]
            ).then(
                fn=update_facts_display,
                inputs=[chat_display, facts_summary],
                outputs=[chat_display, facts_summary, all_submissions, approved_facts, rejected_facts, errors_display, fact_selector]
            )
            
        self.debug_print("Finished building interface")
        return interface

def create_app():
    """Create and configure the Gradio app."""
    print("Creating Fact Extraction GUI application")
    gui = FactExtractionGUI()
    interface = gui.build_interface()
    print("Interface built successfully")
    return interface

if __name__ == "__main__":
    print("\nStarting Fact Extraction System GUI...")
    print("="*50)
    app = create_app()
    print("\nLaunching web interface...")
    
    # Try a range of ports if the default is in use
    for port in range(7860, 7870):
        try:
            print(f"Attempting to launch on port {port}...")
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
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
import pandas as pd
import json

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
from ..storage.fact_repository import FactRepository, RejectedFactRepository

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
        
        # Initialize repositories
        self.chunk_repo = ChunkRepository()
        self.fact_repo = FactRepository()
        self.rejected_fact_repo = RejectedFactRepository()
        
        # Create workflow
        self.workflow, self.input_key = create_workflow(self.chunk_repo, self.fact_repo)
        
        # Store facts data for UI updates
        self.facts_data = {}
        
        # Debug mode
        self.debug = True
        print("DEBUG_INIT: FactExtractionGUI initialized")

    def debug_print(self, message):
        """Print a debug message and also log it to a file."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_message = f"DEBUG [{timestamp}]: {message}"
        print(log_message)
        
        # Also log to a file
        with open("app_debug.log", "a") as f:
            f.write(log_message + "\n")

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
        
        # First add facts from in-memory data
        for filename, file_facts in self.facts_data.items():
            self.debug_print(f"Processing file: {filename}")
            if file_facts.get("all_facts"):
                for i, fact in enumerate(file_facts["all_facts"]):
                    self.debug_print(f"  Processing fact {i} with status: {fact.get('verification_status', 'pending')}")
                    
                    # Add unique ID to fact if not present
                    if "id" not in fact or fact["id"] is None:
                        fact["id"] = i + 1  # Use sequential ID starting from 1
                        self.debug_print(f"  Assigned new ID {fact['id']} to fact {i}")
                    
                    # Add filename to fact for reference
                    fact["filename"] = filename
                    
                    # Add to all_facts list
                    all_facts.append(fact)
                    
                    # Format choice
                    statement = fact.get("statement", "")
                    if not isinstance(statement, str):
                        statement = str(statement) if statement is not None else ""
                    preview = statement[:40] + "..." if len(statement) > 40 else statement
                    status_icon = "✅" if fact.get("verification_status") == "verified" else "❌" if fact.get("verification_status") == "rejected" else "⏳"
                    choice_text = f"{status_icon} {preview} (Current Session)"
                    fact_choices.append(choice_text)
                    self.debug_print(f"  Added choice: '{choice_text}'")
        
        # Create sets to track statements we've already included
        included_statements = {(f.get('statement', ''), f.get('document_name', '')) for f in all_facts}
        
        # Add approved facts from repository
        repo_approved_facts = self.fact_repo.get_all_facts(verified_only=True)
        self.debug_print(f"Got {len(repo_approved_facts)} approved facts from repository")
        
        for i, fact in enumerate(repo_approved_facts):
            # Skip if we've already included this fact from in-memory data
            statement_key = (fact.get('statement', ''), fact.get('document_name', ''))
            if statement_key in included_statements:
                self.debug_print(f"  Skipping approved repo fact {i} as it's already in memory")
                continue
                
            # Add unique ID to fact if not present
            if "id" not in fact or fact["id"] is None:
                fact["id"] = len(all_facts) + i + 1  # Use sequential ID continuing from in-memory facts
                self.debug_print(f"  Assigned new ID {fact['id']} to approved repo fact {i}")
                
            # Add filename to fact for reference
            fact["filename"] = fact.get("document_name", "Unknown Document")
            
            # Add to all_facts list
            all_facts.append(fact)
            included_statements.add(statement_key)
            
            # Format choice
            statement = fact.get("statement", "")
            if not isinstance(statement, str):
                statement = str(statement) if statement is not None else ""
            preview = statement[:40] + "..." if len(statement) > 40 else statement
            choice_text = f"✅ {preview} (Repository)"
            fact_choices.append(choice_text)
            self.debug_print(f"  Added choice: '{choice_text}'")
        
        # Add rejected facts from repository
        repo_rejected_facts = self.rejected_fact_repo.get_all_rejected_facts()
        self.debug_print(f"Got {len(repo_rejected_facts)} rejected facts from repository")
        
        for i, fact in enumerate(repo_rejected_facts):
            # Skip if we've already included this fact from in-memory data or approved repo
            statement_key = (fact.get('statement', ''), fact.get('document_name', ''))
            if statement_key in included_statements:
                self.debug_print(f"  Skipping rejected repo fact {i} as it's already included")
                continue
                
            # Add unique ID to fact if not present
            if "id" not in fact or fact["id"] is None:
                fact["id"] = len(all_facts) + i + 1  # Use sequential ID continuing from previous facts
                self.debug_print(f"  Assigned new ID {fact['id']} to rejected repo fact {i}")
                
            # Add filename to fact for reference
            fact["filename"] = fact.get("document_name", "Unknown Document")
            
            # Add to all_facts list
            all_facts.append(fact)
            included_statements.add(statement_key)
            
            # Format choice
            statement = fact.get("statement", "")
            if not isinstance(statement, str):
                statement = str(statement) if statement is not None else ""
            preview = statement[:40] + "..." if len(statement) > 40 else statement
            choice_text = f"❌ {preview} (Repository)"
            fact_choices.append(choice_text)
            self.debug_print(f"  Added choice: '{choice_text}'")
        
        # Debug information
        self.debug_print(f"Found {len(all_facts)} total facts for review")
        for i, fact in enumerate(all_facts):
            statement = fact.get('statement', '')
            if not isinstance(statement, str):
                statement = str(statement) if statement is not None else ""
            self.debug_print(f"Fact {i}: ID={fact.get('id')}, Statement={statement[:30]}...")
        
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
        
        # Check if this is a repository fact (indicated by choice text)
        is_repo_fact = False
        if fact_index < len(fact_choices):
            choice_text = fact_choices[fact_index]
            is_repo_fact = "(Repository)" in choice_text
            self.debug_print(f"Fact is from repository: {is_repo_fact}")
        
        # Ensure all values are strings to avoid UI errors
        fact_id_str = str(fact.get("id", ""))
        filename_str = str(fact.get("filename", ""))
        statement_str = str(fact.get("statement", ""))
        source_str = str(fact.get("original_text", ""))
        status_str = str(fact.get("verification_status", "pending"))
        reason_str = str(fact.get("verification_reason", ""))
        
        # Add repository indicator to filename if from repository
        if is_repo_fact and not filename_str.endswith(" (Repository)"):
            filename_str = f"{filename_str} (Repository)"
            self.debug_print(f"Added repository indicator to filename: {filename_str}")
        
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
        self.debug_print(f"  Statement: {statement[:40]}...")
        self.debug_print(f"  Status: '{status}' (type: {type(status).__name__})")
        self.debug_print(f"  Reason: {reason[:40]}...")

        # Validate inputs
        if not statement or not statement.strip():
            return "Error: Statement cannot be empty", None

        # Validate status
        if status not in ["verified", "rejected", "pending"]:
            return "Invalid status. Must be 'verified', 'rejected', or 'pending'.", None

        if not fact_id:
            return "No fact ID provided.", None

        try:
            # Convert fact_id to integer if it's a string
            if isinstance(fact_id, str):
                fact_id = int(fact_id)
                self.debug_print(f"Converted fact_id to integer: {fact_id}")
        except ValueError:
            return f"Invalid fact ID: {fact_id}", None

        # Get all facts for review (includes in-memory and repository facts)
        all_facts, _ = self.get_facts_for_review()

        found_fact = None
        document_name = None

        # Find the fact with the matching ID
        for fact in all_facts:
            if "id" in fact and fact["id"] == fact_id:
                found_fact = fact
                self.debug_print(f"Found matching fact with ID {fact_id}")
                break

        if not found_fact:
            self.debug_print(f"No fact found with ID: {fact_id}")
            return f"Fact with ID {fact_id} not found.", None

        document_name = found_fact.get("document_name", "")
        
        # Check if this is an in-memory fact or from a repository
        is_repo_fact = "id" in found_fact and isinstance(found_fact["id"], (float, type(None)))
        self.debug_print(f"Fact is from repository: {is_repo_fact}")

        # Update the fact properties
        old_status = found_fact.get("verification_status", "pending")
        old_reason = found_fact.get("verification_reason", "")
        old_statement = found_fact.get("statement", "")

        # Make a copy to avoid modifying the original
        updated_fact = found_fact.copy()
        
        self.debug_print("Updated fact:")
        self.debug_print(f"  Statement: {old_statement[:40]}... -> {statement[:40]}...")
        self.debug_print(f"  Status: {old_status} -> {status}")
        self.debug_print(f"  Reason: {old_reason[:40]}... -> {reason[:40]}...")
        
        # Update all properties of the fact
        updated_fact["statement"] = statement
        updated_fact["fact"] = statement  # Also update the 'fact' field if it exists
        updated_fact["verification_status"] = status
        updated_fact["verification_reason"] = reason
        updated_fact["verification_reasoning"] = reason  # Ensure both fields are updated
        updated_fact["reviewed_date"] = datetime.now().isoformat()
        updated_fact["edited"] = True

        # Remove the fact from repositories to prevent duplicates
        self.debug_print("Removing fact from repositories to prevent duplicates")
        
        # Create a temporary fact to use for hash generation
        temp_fact = {
            "statement": old_statement,  # Use the old statement to find the existing fact
            "document_name": document_name,
        }
        
        # Clear facts with the same statement from both repositories
        self._remove_matching_facts_from_repositories(temp_fact)
        
        # Store the updated fact in the appropriate repository based on status
        if status == "verified":
            self.debug_print("Storing verified fact in fact repository")
            # Ensure the statement is set correctly before storing
            self.debug_print(f"Statement before storing: {updated_fact['statement'][:40]}...")
            
            # Create a new fact dictionary with the updated statement to ensure it's preserved
            fact_to_store = {
                "statement": statement,  # Explicitly set the statement
                "document_name": document_name,
                "verification_status": status,
                "verification_reason": reason,
                "verification_reasoning": reason,
                "reviewed_date": updated_fact["reviewed_date"],
                "edited": True
            }
            
            # Copy any other fields from the original fact
            for key, value in updated_fact.items():
                if key not in fact_to_store:
                    fact_to_store[key] = value
            
            self.fact_repo.store_fact(fact_to_store)
        elif status == "rejected":
            self.debug_print("Storing rejected fact in rejected fact repository")
            # Ensure the statement is set correctly before storing
            self.debug_print(f"Statement before storing: {updated_fact['statement'][:40]}...")
            
            # Create a new fact dictionary with the updated statement to ensure it's preserved
            fact_to_store = {
                "statement": statement,  # Explicitly set the statement
                "document_name": document_name,
                "verification_status": status,
                "verification_reason": reason,
                "verification_reasoning": reason,
                "reviewed_date": updated_fact["reviewed_date"],
                "edited": True
            }
            
            # Copy any other fields from the original fact
            for key, value in updated_fact.items():
                if key not in fact_to_store:
                    fact_to_store[key] = value
                    
            self.rejected_fact_repo.store_rejected_fact(fact_to_store)
        else:
            self.debug_print("Not storing pending fact in any repository")

        # Update the fact in the in-memory data structure if it exists there
        if document_name in self.facts_data:
            # Update all_facts
            found_in_memory = False
            for i, fact in enumerate(self.facts_data[document_name]["all_facts"]):
                if "id" in fact and fact["id"] == fact_id:
                    self.debug_print(f"Updating in-memory fact at index {i}")
                    self.facts_data[document_name]["all_facts"][i] = updated_fact
                    found_in_memory = True
                    break
            
            # Update verified_facts
            verified_facts = self.facts_data[document_name]["verified_facts"]
            # First remove from verified_facts if it exists
            removed_count = 0
            for i in range(len(verified_facts) - 1, -1, -1):
                if "id" in verified_facts[i] and verified_facts[i]["id"] == fact_id:
                    verified_facts.pop(i)
                    removed_count += 1
            
            self.debug_print(f"  Removed from verified_facts: {removed_count} instances")
            
            # Add back to verified_facts if status is "verified"
            if status == "verified":
                verified_facts.append(updated_fact)
                self.debug_print(f"  Added to verified_facts, new count: {len(verified_facts)}")
            
            # Update verified count
            self.facts_data[document_name]["verified_count"] = len(verified_facts)
            self.debug_print(f"  Updated verified count: {self.facts_data[document_name]['verified_count']}")
        else:
            self.debug_print(f"Document {document_name} not found in facts_data")

        # Update fact choices for dropdowns
        _, facts_summary = self.get_facts_for_review()
        self.debug_print(f"Updated fact choices, now have {len(facts_summary)} choices")

        return f"Fact updated: {statement[:40]}...", facts_summary

    def _remove_matching_facts_from_repositories(self, fact):
        """Remove all facts with the same statement from both fact repositories."""
        # Use the instance repository references
        statement = fact.get("statement", "")
        document_name = fact.get("document_name", "")
        
        self.debug_print(f"Removing facts with statement: {statement[:40]}... from document: {document_name}")
        
        # Remove from main fact repository if it exists
        if document_name in self.fact_repo.facts:
            facts = self.fact_repo.facts[document_name]
            removed_count = 0
            for i in range(len(facts) - 1, -1, -1):
                if facts[i].get("statement", "") == statement:
                    self.debug_print(f"  Removing fact from fact repository at index {i}")
                    facts.pop(i)
                    removed_count += 1
            
            self.debug_print(f"  Removed {removed_count} facts from fact repository")
            # Save changes
            self.fact_repo._save_to_excel()
        
        # Remove from rejected fact repository if it exists
        if document_name in self.rejected_fact_repo.rejected_facts:
            rejected_facts = self.rejected_fact_repo.rejected_facts[document_name]
            removed_count = 0
            for i in range(len(rejected_facts) - 1, -1, -1):
                if rejected_facts[i].get("statement", "") == statement:
                    self.debug_print(f"  Removing fact from rejected fact repository at index {i}")
                    rejected_facts.pop(i)
                    removed_count += 1
            
            self.debug_print(f"  Removed {removed_count} facts from rejected fact repository")
            # Save changes
            self.rejected_fact_repo._save_to_excel()

    def approve_fact(self, fact_id, statement, reason):
        """Approve a fact with optional minor modifications."""
        try:
            self.debug_print(f"Approving fact with ID: {fact_id}")
            self.debug_print(f"  Statement: {statement[:50]}...")
            self.debug_print(f"  Reason: {reason[:50]}...")
            
            if not fact_id or not statement:
                self.debug_print("Error: Missing fact ID or statement")
                return "Error: Missing fact ID or statement", self.format_facts_summary(self.facts_data)
            
            result, facts_data = self.update_fact(fact_id, statement, "verified", reason)
            self.debug_print(f"Approval result: {result}")
            return result, self.format_facts_summary(self.facts_data)
        except Exception as e:
            import traceback
            self.debug_print(f"Error approving fact: {str(e)}")
            self.debug_print(f"Traceback: {traceback.format_exc()}")
            return f"Error approving fact: {str(e)}", self.format_facts_summary(self.facts_data)

    def reject_fact(self, fact_id, statement, reason):
        """Reject a fact with reasoning."""
        try:
            self.debug_print(f"Rejecting fact with ID: {fact_id}")
            self.debug_print(f"  Statement: {statement[:50]}...")
            self.debug_print(f"  Reason: {reason[:50]}...")
            
            if not fact_id or not statement:
                self.debug_print("Error: Missing fact ID or statement")
                return "Error: Missing fact ID or statement", self.format_facts_summary(self.facts_data)
                
            result, facts_data = self.update_fact(fact_id, statement, "rejected", reason)
            self.debug_print(f"Rejection result: {result}")
            return result, self.format_facts_summary(self.facts_data)
        except Exception as e:
            import traceback
            self.debug_print(f"Error rejecting fact: {str(e)}")
            self.debug_print(f"Traceback: {traceback.format_exc()}")
            return f"Error rejecting fact: {str(e)}", self.format_facts_summary(self.facts_data)

    def export_facts_to_csv(self, output_path):
        """Export verified facts to CSV format.
        
        Args:
            output_path: Path to save the CSV file
            
        Returns:
            str: Status message with the export result
        """
        self.debug_print(f"Exporting facts to CSV: {output_path}")
        facts = self.fact_repo.get_all_facts(verified_only=True)
        
        try:
            df = pd.DataFrame(facts)
            df.to_csv(output_path, index=False)
            return f"Exported {len(facts)} facts to {output_path}"
        except Exception as e:
            self.debug_print(f"Error exporting to CSV: {str(e)}")
            return f"Error exporting facts: {str(e)}"

    def export_facts_to_json(self, output_path):
        """Export verified facts to JSON format.
        
        Args:
            output_path: Path to save the JSON file
            
        Returns:
            str: Status message with the export result
        """
        self.debug_print(f"Exporting facts to JSON: {output_path}")
        facts = self.fact_repo.get_all_facts(verified_only=True)
        
        try:
            with open(output_path, 'w') as f:
                json.dump(facts, f, indent=2)
            return f"Exported {len(facts)} facts to {output_path}"
        except Exception as e:
            self.debug_print(f"Error exporting to JSON: {str(e)}")
            return f"Error exporting facts: {str(e)}"

    def export_facts_to_markdown(self, output_path):
        """Export verified facts to Markdown format.
        
        Args:
            output_path: Path to save the Markdown file
            
        Returns:
            str: Status message with the export result
        """
        self.debug_print(f"Exporting facts to Markdown: {output_path}")
        facts = self.fact_repo.get_all_facts(verified_only=True)
        
        try:
            # Group facts by document
            grouped_facts = {}
            for fact in facts:
                doc_name = fact.get("document_name", "Unknown Document")
                if doc_name not in grouped_facts:
                    grouped_facts[doc_name] = []
                grouped_facts[doc_name].append(fact)
            
            with open(output_path, 'w') as f:
                f.write("# Verified Facts Report\n\n")
                f.write(f"Total Facts: {len(facts)}\n\n")
                
                for doc_name, doc_facts in grouped_facts.items():
                    f.write(f"## {doc_name}\n\n")
                    for i, fact in enumerate(doc_facts):
                        f.write(f"### Fact {i+1}\n\n")
                        f.write(f"**Statement:** {fact['statement']}\n\n")
                        if fact.get("verification_reason"):
                            f.write(f"**Reasoning:** {fact['verification_reason']}\n\n")
                        f.write("---\n\n")
            
            return f"Exported {len(facts)} facts to {output_path}"
        except Exception as e:
            self.debug_print(f"Error exporting to Markdown: {str(e)}")
            return f"Error exporting facts: {str(e)}"

    def generate_statistics(self):
        """Generate statistics about extracted facts.
        
        Returns:
            tuple: (overall_stats, doc_stats) where overall_stats is a dict of overall statistics
                   and doc_stats is a dict of per-document statistics
        """
        self.debug_print("Generating fact statistics")
        
        # Get data from repositories
        all_chunks = self.chunk_repo.get_all_chunks()
        all_facts = self.fact_repo.get_all_facts(verified_only=False)
        approved_facts = self.fact_repo.get_all_facts(verified_only=True)
        rejected_facts = self.rejected_fact_repo.get_all_rejected_facts()
        
        # Calculate overall statistics
        stats = {
            "total_documents": len(set(chunk["document_name"] for chunk in all_chunks)),
            "total_chunks": len(all_chunks),
            "total_submissions": len(all_facts) + len(rejected_facts),
            "approved_facts": len(approved_facts),
            "rejected_facts": len(rejected_facts),
            "approval_rate": round(len(approved_facts) / (len(approved_facts) + len(rejected_facts)) * 100, 1) if (len(approved_facts) + len(rejected_facts)) > 0 else 0,
        }
        
        # Calculate per-document statistics
        doc_stats = {}
        for doc_name in set(chunk["document_name"] for chunk in all_chunks):
            doc_chunks = [c for c in all_chunks if c["document_name"] == doc_name]
            doc_approved_facts = [f for f in approved_facts if f["document_name"] == doc_name]
            doc_rejected_facts = [f for f in rejected_facts if f["document_name"] == doc_name]
            
            doc_stats[doc_name] = {
                "chunks": len(doc_chunks),
                "approved_facts": len(doc_approved_facts),
                "rejected_facts": len(doc_rejected_facts),
                "total_submissions": len(doc_approved_facts) + len(doc_rejected_facts),
                "facts_per_chunk": round(len(doc_approved_facts) / len(doc_chunks), 2) if len(doc_chunks) > 0 else 0
            }
        
        return stats, doc_stats

    def format_statistics_markdown(self, stats, doc_stats):
        """Format statistics as markdown.
        
        Args:
            stats: Dict of overall statistics
            doc_stats: Dict of per-document statistics
            
        Returns:
            str: Markdown formatted statistics
        """
        self.debug_print("Formatting statistics as markdown")
        
        md = "# Fact Extraction Statistics\n\n"
        
        # Overall statistics section
        md += "## Overall Statistics\n\n"
        md += f"- **Total Documents:** {stats['total_documents']}\n"
        md += f"- **Total Chunks:** {stats['total_chunks']}\n"
        md += f"- **Total Submissions:** {stats['total_submissions']}\n"
        md += f"- **Approved Facts:** {stats['approved_facts']}\n"
        md += f"- **Rejected Facts:** {stats['rejected_facts']}\n"
        md += f"- **Approval Rate:** {stats['approval_rate']}%\n\n"
        
        # Per-document statistics section
        md += "## Document Statistics\n\n"
        
        for doc_name, doc_stat in doc_stats.items():
            md += f"### {doc_name}\n\n"
            md += f"- **Chunks:** {doc_stat['chunks']}\n"
            md += f"- **Approved Facts:** {doc_stat['approved_facts']}\n"
            md += f"- **Rejected Facts:** {doc_stat['rejected_facts']}\n"
            md += f"- **Total Submissions:** {doc_stat['total_submissions']}\n"
            md += f"- **Facts per Chunk:** {doc_stat['facts_per_chunk']}\n\n"
        
        return md

    async def update_statistics_tab(self, statistics_tab):
        """Update the statistics tab with current statistics.
        
        Args:
            statistics_tab: Gradio Markdown component to update
            
        Returns:
            str: Markdown content that was used to update the tab
        """
        self.debug_print("Updating statistics tab")
        
        try:
            # Generate statistics
            stats, doc_stats = self.generate_statistics()
            
            # Format as markdown
            markdown_stats = self.format_statistics_markdown(stats, doc_stats)
            
            # Update the tab content
            await statistics_tab.update(value=markdown_stats)
            
            return markdown_stats
        except Exception as e:
            self.debug_print(f"Error updating statistics tab: {str(e)}")
            error_message = f"# Error Generating Statistics\n\nAn error occurred while generating statistics: {str(e)}"
            await statistics_tab.update(value=error_message)
            return error_message

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
            
            # Statistics Tab
            with gr.TabItem("Statistics", elem_id="statistics-tab"):
                with gr.Column():
                    gr.Markdown("# Fact Extraction Statistics")
                    statistics_content = gr.Markdown("Process documents to see statistics.")
                    update_stats_btn = gr.Button("Update Statistics")
            
            # Export Tab
            with gr.TabItem("Export", elem_id="export-tab"):
                with gr.Column():
                    gr.Markdown("# Export Verified Facts")
                    
                    with gr.Row():
                        export_format = gr.Dropdown(
                            label="Export Format",
                            choices=["CSV", "JSON", "Markdown"],
                            value="CSV"
                        )
                        
                        export_path = gr.Textbox(
                            label="Export Path",
                            placeholder="e.g., /path/to/facts_export.csv",
                            value="exported_facts"
                        )
                    
                    export_btn = gr.Button("Export Facts", variant="primary")
                    export_status = gr.Markdown("Select a format and click Export to download verified facts.")
            
            # Event handlers
            def update_facts_display(chat_history, facts_summary):
                """Update the facts display with the current facts data."""
                self.debug_print("update_facts_display called")
                
                try:
                    # Initialize content for each tab
                    all_submissions_md = ""
                    approved_facts_md = ""
                    rejected_facts_md = ""
                    errors_md = ""
                    
                    # Fetch facts from repositories
                    approved_facts_from_repo = self.fact_repo.get_all_facts(verified_only=True)
                    rejected_facts_from_repo = self.rejected_fact_repo.get_all_rejected_facts()
                    
                    self.debug_print(f"Got {len(approved_facts_from_repo)} approved facts from repository")
                    self.debug_print(f"Got {len(rejected_facts_from_repo)} rejected facts from repository")
                    
                    # Group facts by document for better display
                    grouped_approved_facts = {}
                    for fact in approved_facts_from_repo:
                        doc_name = fact.get("document_name", "Unknown Document")
                        if doc_name not in grouped_approved_facts:
                            grouped_approved_facts[doc_name] = []
                        grouped_approved_facts[doc_name].append(fact)
                    
                    grouped_rejected_facts = {}
                    for fact in rejected_facts_from_repo:
                        doc_name = fact.get("document_name", "Unknown Document")
                        if doc_name not in grouped_rejected_facts:
                            grouped_rejected_facts[doc_name] = []
                        grouped_rejected_facts[doc_name].append(fact)
                    
                    # Process in-memory facts if available
                    if self.facts_data:
                        # Format all submissions
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
                        
                        # Format in-memory verified facts
                        for filename, file_facts in self.facts_data.items():
                            if file_facts.get("verified_facts"):
                                approved_facts_md += f"\n## {filename} (Current Session)\n\n"
                                for i, fact in enumerate(file_facts["verified_facts"]):
                                    approved_facts_md += f"✅ **Fact {i+1}:** {fact['statement']}\n\n"
                                    if fact.get("verification_reason"):
                                        approved_facts_md += f"*Reasoning:*\n{fact['verification_reason']}\n\n"
                                    approved_facts_md += "---\n\n"
                        
                        # Format in-memory rejected facts
                        for filename, file_facts in self.facts_data.items():
                            if file_facts.get("all_facts"):
                                rejected_facts = [f for f in file_facts["all_facts"] if f.get("verification_status") == "rejected"]
                                if rejected_facts:
                                    rejected_facts_md += f"\n## {filename} (Current Session)\n\n"
                                    for i, fact in enumerate(rejected_facts):
                                        rejected_facts_md += f"❌ **Submission {i+1}:** {fact['statement']}\n\n"
                                        if fact.get("verification_reason"):
                                            rejected_facts_md += f"*Reasoning:*\n{fact['verification_reason']}\n\n"
                                        rejected_facts_md += "---\n\n"
                        
                        # Format errors
                        for filename, file_facts in self.facts_data.items():
                            if file_facts.get("errors"):
                                errors_md += f"\n## {filename}\n\n"
                                for error in file_facts["errors"]:
                                    errors_md += f"- {error}\n"
                                errors_md += "\n"
                    
                    # Add repository approved facts
                    if grouped_approved_facts:
                        for doc_name, facts in grouped_approved_facts.items():
                            approved_facts_md += f"\n## {doc_name} (Repository)\n\n"
                            for i, fact in enumerate(facts):
                                approved_facts_md += f"✅ **Fact {i+1}:** {fact.get('statement', 'No statement')}\n\n"
                                if fact.get("verification_reason"):
                                    approved_facts_md += f"*Reasoning:*\n{fact['verification_reason']}\n\n"
                                approved_facts_md += "---\n\n"
                    
                    # Add repository rejected facts
                    if grouped_rejected_facts:
                        for doc_name, facts in grouped_rejected_facts.items():
                            rejected_facts_md += f"\n## {doc_name} (Repository)\n\n"
                            for i, fact in enumerate(facts):
                                rejected_facts_md += f"❌ **Submission {i+1}:** {fact.get('statement', 'No statement')}\n\n"
                                if fact.get("verification_reason"):
                                    rejected_facts_md += f"*Reasoning:*\n{fact['verification_reason']}\n\n"
                                rejected_facts_md += "---\n\n"
                    
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
                        gr.update(choices=fact_choices, value=None)  # Use gr.update to update dropdown choices
                    )
                except Exception as e:
                    import traceback
                    error_msg = f"Error in update_facts_display: {str(e)}\n{traceback.format_exc()}"
                    self.debug_print(error_msg)
                    return (
                        chat_history, 
                        facts_summary, 
                        f"Error updating display: {str(e)}", 
                        "No approved facts yet.", 
                        "No rejected submissions yet.", 
                        error_msg, 
                        gr.update(choices=[], value=None)
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
                
                try:
                    # Initialize debug information
                    debug_info = [f"on_fact_selected called with index: {selected_index} (type: {type(selected_index)})"]
                    
                    # Handle invalid selection
                    if selected_index is None or selected_index == "":
                        debug_info.append("Empty selection - returning empty values")
                        return "", "", "", "", "pending", "", "\n".join(debug_info)
                    
                    # Get current facts and choices
                    all_facts, fact_choices = self.get_facts_for_review()
                    debug_info.append(f"Retrieved {len(all_facts)} facts and {len(fact_choices)} choices")
                    
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
                        debug_info.append(f"Index {selected_index} out of range (0-{len(all_facts)-1 if all_facts else 0}) - returning empty values")
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
                except Exception as e:
                    import traceback
                    error_msg = f"Error in on_fact_selected: {str(e)}\n{traceback.format_exc()}"
                    self.debug_print(error_msg)
                    # Return empty values with error message to avoid UI errors
                    return "", "", "", "", "pending", "", error_msg
            
            fact_selector.change(
                fn=on_fact_selected,
                inputs=[fact_selector],
                outputs=[fact_id, fact_filename, fact_statement, fact_source, fact_status, fact_reason, debug_display]
            )
            self.debug_print("Connected fact_selector.change event")

            # Connect refresh button
            def on_refresh_facts():
                self.debug_print("on_refresh_facts called")
                try:
                    # Get facts and choices
                    all_facts, choices = self.get_facts_for_review()
                    
                    # Debug information
                    debug_info = [
                        f"Refreshed fact choices: {len(choices)} items",
                        f"Number of facts: {len(all_facts)}",
                    ]
                    
                    # Add information about each choice (limit to first 10 for large lists)
                    max_choices_to_display = 10
                    for i, choice in enumerate(choices[:max_choices_to_display]):
                        debug_info.append(f"Choice {i}: '{choice}'")
                    
                    if len(choices) > max_choices_to_display:
                        debug_info.append(f"... and {len(choices) - max_choices_to_display} more choices")
                    
                    # Return updated dropdown and debug info
                    return gr.update(choices=choices, value=None), "\n".join(debug_info)
                except Exception as e:
                    import traceback
                    error_msg = f"Error in on_refresh_facts: {str(e)}\n{traceback.format_exc()}"
                    self.debug_print(error_msg)
                    # Return empty choices with error message
                    return gr.update(choices=[], value=None), error_msg
                
            refresh_facts_btn.click(
                fn=on_refresh_facts,
                inputs=[],
                outputs=[fact_selector, debug_display]
            )
            self.debug_print("Connected refresh_facts_btn.click event")

            # Connect approve button
            approve_btn.click(
                fn=lambda fact_id, statement, reason: self.approve_fact(fact_id, statement, reason) if fact_id and statement else ("Please select a fact first", self.format_facts_summary(self.facts_data)),
                inputs=[fact_id, fact_statement, fact_reason],
                outputs=[review_status, facts_summary],
                api_name="approve_fact",
                queue=True  # Ensure queuing is enabled
            ).then(
                fn=update_facts_display,
                inputs=[chat_display, facts_summary],
                outputs=[chat_display, facts_summary, all_submissions, approved_facts, rejected_facts, errors_display, fact_selector],
                queue=True  # Ensure queuing is enabled
            ).then(
                # Clear the fact selection after approval
                lambda: (None, "", "", "", "pending", "", "Fact approved. Select another fact to review.", ""),
                None,
                [fact_selector, fact_id, fact_filename, fact_statement, fact_source, fact_status, fact_reason, debug_display],
                queue=True  # Ensure queuing is enabled
            )

            # Connect reject button
            reject_btn.click(
                fn=lambda fact_id, statement, reason: self.reject_fact(fact_id, statement, reason) if fact_id and statement else ("Please select a fact first", self.format_facts_summary(self.facts_data)),
                inputs=[fact_id, fact_statement, fact_reason],
                outputs=[review_status, facts_summary],
                api_name="reject_fact",
                queue=True  # Ensure queuing is enabled
            ).then(
                fn=update_facts_display,
                inputs=[chat_display, facts_summary],
                outputs=[chat_display, facts_summary, all_submissions, approved_facts, rejected_facts, errors_display, fact_selector],
                queue=True  # Ensure queuing is enabled
            ).then(
                # Clear the fact selection after rejection
                lambda: (None, "", "", "", "pending", "", "Fact rejected. Select another fact to review.", ""),
                None,
                [fact_selector, fact_id, fact_filename, fact_statement, fact_source, fact_status, fact_reason, debug_display],
                queue=True  # Ensure queuing is enabled
            )

            # Connect modify button
            modify_btn.click(
                fn=lambda fact_id, statement, status, reason: self.update_fact(fact_id, statement, status, reason) if fact_id and statement else ("Please select a fact first", self.format_facts_summary(self.facts_data)),
                inputs=[fact_id, fact_statement, fact_status, fact_reason],
                outputs=[review_status, facts_summary],
                api_name="update_fact",
                queue=True  # Ensure queuing is enabled
            ).then(
                fn=update_facts_display,
                inputs=[chat_display, facts_summary],
                outputs=[chat_display, facts_summary, all_submissions, approved_facts, rejected_facts, errors_display, fact_selector],
                queue=True  # Ensure queuing is enabled
            ).then(
                # Clear the fact selection after modification
                lambda: (None, "", "", "", "pending", "", "Fact modified. Select another fact to review.", ""),
                None,
                [fact_selector, fact_id, fact_filename, fact_statement, fact_source, fact_status, fact_reason, debug_display],
                queue=True  # Ensure queuing is enabled
            )
            
            # Add button state management
            def disable_buttons():
                """Disable all action buttons during processing."""
                return [
                    gr.update(interactive=False),
                    gr.update(interactive=False),
                    gr.update(interactive=False)
                ]
                
            def enable_buttons():
                """Enable all action buttons after processing."""
                return [
                    gr.update(interactive=True),
                    gr.update(interactive=True),
                    gr.update(interactive=True)
                ]
            
            # Disable buttons during processing
            approve_btn.click(
                fn=disable_buttons,
                inputs=None,
                outputs=[approve_btn, reject_btn, modify_btn],
                queue=False
            )
            
            reject_btn.click(
                fn=disable_buttons,
                inputs=None,
                outputs=[approve_btn, reject_btn, modify_btn],
                queue=False
            )
            
            modify_btn.click(
                fn=disable_buttons,
                inputs=None,
                outputs=[approve_btn, reject_btn, modify_btn],
                queue=False
            )
            
            # Re-enable buttons after processing
            approve_btn.click(
                fn=enable_buttons,
                inputs=None,
                outputs=[approve_btn, reject_btn, modify_btn]
            )
            
            reject_btn.click(
                fn=enable_buttons,
                inputs=None,
                outputs=[approve_btn, reject_btn, modify_btn]
            )
            
            modify_btn.click(
                fn=enable_buttons,
                inputs=None,
                outputs=[approve_btn, reject_btn, modify_btn]
            )
            
            # Statistics tab event handler
            update_stats_btn.click(
                fn=lambda: asyncio.create_task(self.update_statistics_tab(statistics_content)),
                inputs=[],
                outputs=[statistics_content]
            )
            
            # Export tab event handlers
            def on_export_facts(format_choice, base_path):
                """Handle fact export based on selected format."""
                self.debug_print(f"Exporting facts in {format_choice} format to {base_path}")
                
                try:
                    # Add extension if not present
                    if format_choice == "CSV" and not base_path.lower().endswith(".csv"):
                        base_path += ".csv"
                    elif format_choice == "JSON" and not base_path.lower().endswith(".json"):
                        base_path += ".json"
                    elif format_choice == "Markdown" and not base_path.lower().endswith((".md", ".markdown")):
                        base_path += ".md"
                    
                    # Export based on format
                    if format_choice == "CSV":
                        result = self.export_facts_to_csv(base_path)
                    elif format_choice == "JSON":
                        result = self.export_facts_to_json(base_path)
                    elif format_choice == "Markdown":
                        result = self.export_facts_to_markdown(base_path)
                    else:
                        return "Error: Unknown export format selected."
                    
                    return result
                except Exception as e:
                    self.debug_print(f"Error exporting facts: {str(e)}")
                    return f"Error exporting facts: {str(e)}"
            
            export_btn.click(
                fn=on_export_facts,
                inputs=[export_format, export_path],
                outputs=[export_status]
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
                debug=True,
                inbrowser=True  # Try to open in browser automatically
            )
            print(f"\nServer running on port {port}")
            print(f"\nAccess the application at: http://127.0.0.1:{port}")
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
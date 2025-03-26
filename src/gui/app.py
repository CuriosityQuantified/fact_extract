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
import time

from src.models.state import ProcessingState, create_initial_state
from src.utils.file_utils import (
    is_valid_file, 
    get_temp_path,
    cleanup_temp_files,
    ALLOWED_EXTENSIONS,
    MAX_FILE_SIZES,
    extract_text_from_file
)
from src.graph.nodes import create_workflow
from src.storage.chunk_repository import ChunkRepository
from src.storage.fact_repository import FactRepository, RejectedFactRepository

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

    def _snapshot_current_state(self):
        """
        Create a snapshot of the current state for transaction support.
        Returns a deep copy of the current state for rollback if needed.
        """
        import copy
        import json
        
        self.debug_print("Creating state snapshot for transaction")
        
        try:
            # Create a deep copy of the in-memory facts data
            facts_data_copy = copy.deepcopy(self.facts_data)
            
            # Create snapshots of both repositories
            fact_repo_snapshot = {}
            for doc_name, facts in self.fact_repo.facts.items():
                fact_repo_snapshot[doc_name] = copy.deepcopy(facts)
                
            rejected_fact_repo_snapshot = {}
            for doc_name, facts in self.rejected_fact_repo.rejected_facts.items():
                rejected_fact_repo_snapshot[doc_name] = copy.deepcopy(facts)
            
            # Create Excel backup files
            fact_excel_path = self.fact_repo.excel_path
            fact_backup_path = f"{fact_excel_path}.backup"
            if os.path.exists(fact_excel_path):
                shutil.copy2(fact_excel_path, fact_backup_path)
                self.debug_print(f"Created backup of fact repository: {fact_backup_path}")
            
            rejected_excel_path = self.rejected_fact_repo.excel_path
            rejected_backup_path = f"{rejected_excel_path}.backup"
            if os.path.exists(rejected_excel_path):
                shutil.copy2(rejected_excel_path, rejected_backup_path)
                self.debug_print(f"Created backup of rejected fact repository: {rejected_backup_path}")
            
            # Return the complete snapshot
            return {
                "facts_data": facts_data_copy,
                "fact_repo": fact_repo_snapshot,
                "rejected_fact_repo": rejected_fact_repo_snapshot,
                "fact_excel_path": fact_excel_path,
                "fact_backup_path": fact_backup_path,
                "rejected_excel_path": rejected_excel_path,
                "rejected_backup_path": rejected_backup_path,
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            import traceback
            self.debug_print(f"Error creating state snapshot: {str(e)}")
            self.debug_print(traceback.format_exc())
            return None
            
    def _restore_state(self, snapshot):
        """
        Restore state from a snapshot for transaction rollback.
        """
        if not snapshot:
            self.debug_print("No snapshot provided for state restoration")
            return False
            
        self.debug_print(f"Restoring state from snapshot (timestamp: {snapshot.get('timestamp')})")
        
        try:
            # Restore in-memory facts data
            if "facts_data" in snapshot:
                self.facts_data = snapshot["facts_data"]
                self.debug_print("Restored in-memory facts data")
            
            # Restore repository data
            if "fact_repo" in snapshot and "rejected_fact_repo" in snapshot:
                self.fact_repo.facts = snapshot["fact_repo"]
                self.rejected_fact_repo.rejected_facts = snapshot["rejected_fact_repo"]
                self.debug_print("Restored repository in-memory data")
            
            # Restore Excel files from backups
            fact_backup_path = snapshot.get("fact_backup_path")
            fact_excel_path = snapshot.get("fact_excel_path")
            if fact_backup_path and fact_excel_path and os.path.exists(fact_backup_path):
                shutil.copy2(fact_backup_path, fact_excel_path)
                self.debug_print(f"Restored fact repository from backup: {fact_backup_path}")
                # Clean up backup
                os.remove(fact_backup_path)
            
            rejected_backup_path = snapshot.get("rejected_backup_path")
            rejected_excel_path = snapshot.get("rejected_excel_path")
            if rejected_backup_path and rejected_excel_path and os.path.exists(rejected_backup_path):
                shutil.copy2(rejected_backup_path, rejected_excel_path)
                self.debug_print(f"Restored rejected fact repository from backup: {rejected_backup_path}")
                # Clean up backup
                os.remove(rejected_backup_path)
            
            # Force repositories to reload from Excel
            self.fact_repo._reload_facts_from_excel()
            self.rejected_fact_repo._reload_facts_from_excel()
            self.debug_print("Reloaded facts from Excel files after restoration")
            
            return True
        except Exception as e:
            import traceback
            self.debug_print(f"Error restoring state from snapshot: {str(e)}")
            self.debug_print(traceback.format_exc())
            return False
            
    def _verify_data_consistency(self):
        """
        Verify that data is consistent between in-memory and Excel storage.
        """
        self.debug_print("Verifying data consistency")
        
        try:
            # Check if Excel files exist
            fact_excel_exists = os.path.exists(self.fact_repo.excel_path)
            rejected_excel_exists = os.path.exists(self.rejected_fact_repo.excel_path)
            
            # Reload facts from Excel to in-memory
            temp_fact_repo = FactRepository(self.fact_repo.excel_path)
            temp_rejected_repo = RejectedFactRepository(self.rejected_fact_repo.excel_path)
            
            # Compare fact counts between repositories
            fact_count_match = True
            for doc_name, facts in self.fact_repo.facts.items():
                excel_count = len(temp_fact_repo.facts.get(doc_name, []))
                memory_count = len(facts)
                if excel_count != memory_count:
                    self.debug_print(f"Inconsistency detected: {doc_name} has {memory_count} facts in memory but {excel_count} in Excel")
                    fact_count_match = False
                    break
            
            # Compare rejected fact counts
            rejected_count_match = True
            for doc_name, facts in self.rejected_fact_repo.rejected_facts.items():
                excel_count = len(temp_rejected_repo.rejected_facts.get(doc_name, []))
                memory_count = len(facts)
                if excel_count != memory_count:
                    self.debug_print(f"Inconsistency detected: {doc_name} has {memory_count} rejected facts in memory but {excel_count} in Excel")
                    rejected_count_match = False
                    break
            
            # Report consistency
            is_consistent = fact_count_match and rejected_count_match and fact_excel_exists and rejected_excel_exists
            self.debug_print(f"Data consistency verification result: {is_consistent}")
            
            return is_consistent
        except Exception as e:
            import traceback
            self.debug_print(f"Error verifying data consistency: {str(e)}")
            self.debug_print(traceback.format_exc())
            return False

    def update_fact_with_transaction(self, fact_id, statement, status, reason):
        """Update a fact using a transaction-like pattern to ensure consistency."""
        # Create a backup of the current state
        self.debug_print(f"Starting fact update transaction for fact ID: {fact_id}")
        current_state = self._snapshot_current_state()
        
        try:
            # IMPORTANT: Create a copy of the repositories BEFORE any operations
            # This helps avoid in-place modifications that might affect our rollback state
            import copy
            original_fact_repo = copy.deepcopy(self.fact_repo.facts)
            original_rejected_repo = copy.deepcopy(self.rejected_fact_repo.rejected_facts)
            
            # Perform the update operation
            result, facts_summary = self.update_fact(fact_id, statement, status, reason)
            
            # Force a save of Excel files
            self.debug_print("Forcing Excel file save after update")
            self.fact_repo._save_to_excel()
            self.rejected_fact_repo._save_to_excel()
            
            # Verify data consistency
            if self._verify_data_consistency():
                self.debug_print(f"Fact update transaction completed successfully: {result}")
                # Force synchronization to ensure all changes are saved and UI is refreshed
                self.synchronize_repositories()
                # Explicitly reload facts for review to update dropdown
                all_facts, fact_choices = self.get_facts_for_review()
                self.debug_print(f"Refreshed fact choices, now have {len(fact_choices)} choices")
                return result, fact_choices
            else:
                # If inconsistent, roll back and report error
                self.debug_print("Data consistency check failed - rolling back transaction")
                # Direct restoration of original data (skipping Excel which may be locked)
                self.fact_repo.facts = original_fact_repo
                self.rejected_fact_repo.rejected_facts = original_rejected_repo
                # Ensure a complete restore of the state
                success = self._restore_state(current_state)
                self.debug_print(f"Restore state result: {success}")
                return "Error: Data consistency check failed after update. Changes rolled back.", None
        except Exception as e:
            # Roll back on error
            import traceback
            self.debug_print(f"Error during fact update transaction: {str(e)}")
            self.debug_print(traceback.format_exc())
            self._restore_state(current_state)
            return f"Error during update: {str(e)}. Changes rolled back.", None

    def synchronize_repositories(self):
        """
        Force synchronization between in-memory state and Excel files.
        This ensures all changes are properly persisted and loaded.
        """
        self.debug_print("Synchronizing repositories")
        
        try:
            # Clean up any existing backup files
            fact_excel_path = self.fact_repo.excel_path
            fact_backup_path = f"{fact_excel_path}.backup"
            if os.path.exists(fact_backup_path):
                os.remove(fact_backup_path)
                self.debug_print(f"Removed stale backup file: {fact_backup_path}")
                
            rejected_excel_path = self.rejected_fact_repo.excel_path
            rejected_backup_path = f"{rejected_excel_path}.backup"
            if os.path.exists(rejected_backup_path):
                os.remove(rejected_backup_path)
                self.debug_print(f"Removed stale backup file: {rejected_backup_path}")
            
            # Flush changes to Excel - using separate try blocks to ensure both operations run
            try:
                self.fact_repo._save_to_excel()
                self.debug_print("Fact repository saved to Excel")
            except Exception as e:
                self.debug_print(f"Error saving fact repository: {str(e)}")
                
            try:
                self.rejected_fact_repo._save_to_excel()
                self.debug_print("Rejected fact repository saved to Excel")
            except Exception as e:
                self.debug_print(f"Error saving rejected fact repository: {str(e)}")
            
            # Reload data from Excel with a small delay to ensure file operations complete
            time.sleep(0.5)  # Short delay to ensure file operations complete
            
            self.fact_repo._reload_facts_from_excel()
            self.rejected_fact_repo._reload_facts_from_excel()
            
            # Refresh in-memory facts data by re-fetching
            all_facts, _ = self.get_facts_for_review()
            
            # Verify consistency
            consistent = self._verify_data_consistency()
            self.debug_print(f"Repository synchronization complete. Consistency: {consistent}")
            
            return consistent
        except Exception as e:
            import traceback
            self.debug_print(f"Error synchronizing repositories: {str(e)}")
            self.debug_print(traceback.format_exc())
            return False
            
    def _generate_persistent_id(self, fact_data):
        """
        Generate a truly unique ID that persists across operations.
        
        Args:
            fact_data: Dictionary containing fact data like statement, document name, etc.
            
        Returns:
            str: A UUID-based unique identifier
        """
        import uuid
        import hashlib
        
        # Use content hash + document + timestamp + random component
        content = fact_data.get("statement", "")
        document = fact_data.get("document_name", "")
        source = fact_data.get("original_text", "")
        timestamp = fact_data.get("timestamp", datetime.now().isoformat())
        
        # Create a consistent string to hash
        id_string = f"{content}|{document}|{source}|{timestamp}"
        
        # Generate a hash to use as the namespace
        hash_input = id_string.encode('utf-8')
        namespace_hex = hashlib.md5(hash_input).hexdigest()
        namespace = uuid.UUID(namespace_hex[:32])  # Use first 32 chars of hash as UUID
        
        # Generate a UUID using the namespace and the content
        fact_uuid = uuid.uuid5(namespace, content)
        
        # Return a formatted ID string
        return f"fact-{fact_uuid}"

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

        # Check if this is a persistent ID (UUID-based)
        is_persistent_id = isinstance(fact_id, str) and fact_id.startswith("fact-")
        self.debug_print(f"Using persistent ID: {is_persistent_id}")

        # Get all facts for review (includes in-memory and repository facts)
        all_facts, _ = self.get_facts_for_review()

        found_fact = None
        document_name = None

        # Find the fact with the matching ID
        for fact in all_facts:
            # Check both persistent ID and legacy ID
            if (is_persistent_id and fact.get("persistent_id") == fact_id) or \
               (not is_persistent_id and "id" in fact and str(fact["id"]) == str(fact_id)):
                found_fact = fact
                self.debug_print(f"Found matching fact with ID {fact_id}")
                break

        if not found_fact:
            self.debug_print(f"No fact found with ID: {fact_id}")
            return f"Fact with ID {fact_id} not found.", None

        document_name = found_fact.get("document_name", "")
        
        # Generate a persistent ID if not already present
        if not found_fact.get("persistent_id"):
            found_fact["persistent_id"] = self._generate_persistent_id(found_fact)
            self.debug_print(f"Generated persistent ID: {found_fact['persistent_id']}")
        
        # Important: Store the persistent ID to ensure it's preserved throughout operations
        persistent_id = found_fact.get("persistent_id")
        self.debug_print(f"Using persistent ID for operations: {persistent_id}")
        
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
        
        # Ensure persistent ID is preserved
        updated_fact["persistent_id"] = persistent_id

        # Remove the fact from repositories to prevent duplicates
        self.debug_print("Removing fact from repositories to prevent duplicates")
        
        # Create a temporary fact to use for hash generation - using persistent ID now
        temp_fact = {
            "statement": old_statement,  # Use the old statement to find the existing fact
            "document_name": document_name,
            "persistent_id": persistent_id  # Use persistent ID for more reliable matching
        }
        
        # Clear facts with the same persistent ID from both repositories
        removed_count = self._remove_matching_facts_from_repositories(temp_fact)
        self.debug_print(f"Removed {removed_count} matching facts from repositories")
        
        # Prepare the fact data to store, preserving all important metadata
        fact_to_store = {
            # Essential fields
            "statement": statement,  # Updated statement
            "fact": statement,  # Duplicate in fact field for compatibility
            "document_name": document_name,
            "verification_status": status,
            "verification_reason": reason,
            "verification_reasoning": reason,
            "reviewed_date": updated_fact["reviewed_date"],
            "persistent_id": persistent_id,  # Preserve the persistent ID
            "edited": True
        }
        
        # Copy any other fields from the original fact to preserve metadata
        for key, value in updated_fact.items():
            if key not in fact_to_store and value is not None:
                fact_to_store[key] = value
        
        # Store the updated fact in the appropriate repository based on status
        if status == "verified":
            self.debug_print("Storing verified fact in fact repository")
            self.debug_print(f"Statement before storing: {fact_to_store['statement'][:40]}...")
            self.debug_print(f"Persistent ID being stored: {fact_to_store['persistent_id']}")
            
            # Store in verified fact repository
            self.fact_repo.store_fact(fact_to_store)
            
        elif status == "rejected":
            self.debug_print("Storing rejected fact in rejected fact repository")
            self.debug_print(f"Statement before storing: {fact_to_store['statement'][:40]}...")
            self.debug_print(f"Persistent ID being stored: {fact_to_store['persistent_id']}")
            
            # Add rejection reason field for compatibility
            fact_to_store["rejection_reason"] = reason
            
            # Store in rejected fact repository
            self.rejected_fact_repo.store_rejected_fact(fact_to_store)
            
        else:
            self.debug_print("Not storing pending fact in any repository")

        # Update the fact in the in-memory data structure if it exists there
        if document_name in self.facts_data:
            # Update all_facts
            found_in_memory = False
            for i, fact in enumerate(self.facts_data[document_name]["all_facts"]):
                # Match by persistent ID if available, otherwise fall back to legacy ID
                if (persistent_id and fact.get("persistent_id") == persistent_id) or \
                   (not persistent_id and "id" in fact and str(fact["id"]) == str(fact_id)):
                    self.debug_print(f"Updating in-memory fact at index {i}")
                    self.facts_data[document_name]["all_facts"][i] = fact_to_store.copy()
                    found_in_memory = True
                    break
            
            # Update verified_facts
            verified_facts = self.facts_data[document_name]["verified_facts"]
            # First remove from verified_facts if it exists
            removed_count = 0
            for i in range(len(verified_facts) - 1, -1, -1):
                # Match by persistent ID if available, otherwise fall back to legacy ID
                if (persistent_id and verified_facts[i].get("persistent_id") == persistent_id) or \
                   (not persistent_id and "id" in verified_facts[i] and str(verified_facts[i]["id"]) == str(fact_id)):
                    verified_facts.pop(i)
                    removed_count += 1
            
            self.debug_print(f"  Removed from verified_facts: {removed_count} instances")
            
            # Add back to verified_facts if status is "verified"
            if status == "verified":
                verified_facts.append(fact_to_store.copy())
                self.debug_print(f"  Added to verified_facts, new count: {len(verified_facts)}")
            
            # Update verified count
            self.facts_data[document_name]["verified_count"] = len(verified_facts)
            self.debug_print(f"  Updated verified count: {self.facts_data[document_name]['verified_count']}")
        else:
            self.debug_print(f"Document {document_name} not found in facts_data")

        # Force synchronization to ensure Excel files are updated
        self.debug_print("Forcing repository synchronization after update")
        self.synchronize_repositories()
        
        # Update fact choices for dropdowns - get fresh data
        all_facts, fact_choices = self.get_facts_for_review()
        self.debug_print(f"Updated fact choices, now have {len(fact_choices)} choices")

        return f"Fact updated: {statement[:40]}...", fact_choices

    def _remove_matching_facts_from_repositories(self, fact):
        """Remove all facts with the same persistent ID from both fact repositories."""
        # Use the instance repository references
        statement = fact.get("statement", "")
        document_name = fact.get("document_name", "")
        persistent_id = fact.get("persistent_id", "")
        
        self.debug_print(f"Removing facts matching: document={document_name}, id={persistent_id}, statement={statement[:40]}...")
        
        try:
            # Track if any changes were made to either repository
            changes_made = False
            
            # First remove from fact repository
            facts_removed = 0
            for doc_name, facts_list in list(self.fact_repo.facts.items()):
                removed_count = 0
                for i in range(len(facts_list) - 1, -1, -1):
                    # Match based on persistent ID first, then fall back to statement if no ID
                    fact_matches = False
                    if persistent_id and facts_list[i].get("persistent_id") == persistent_id:
                        self.debug_print(f"  Matched fact by persistent ID in {doc_name} at index {i}")
                        fact_matches = True
                    elif not persistent_id and document_name == doc_name and facts_list[i].get("statement", "") == statement:
                        self.debug_print(f"  Matched fact by statement in {doc_name} at index {i}")
                        fact_matches = True
                        
                    if fact_matches:
                        facts_list.pop(i)
                        removed_count += 1
                        facts_removed += 1
                        changes_made = True
                        
                if removed_count > 0:
                    self.debug_print(f"  Removed {removed_count} facts from {doc_name} in fact repository")
            
            # Then remove from rejected fact repository
            rejected_removed = 0
            for doc_name, facts_list in list(self.rejected_fact_repo.rejected_facts.items()):
                removed_count = 0
                for i in range(len(facts_list) - 1, -1, -1):
                    # Match based on persistent ID first, then fall back to statement if no ID
                    fact_matches = False
                    if persistent_id and facts_list[i].get("persistent_id") == persistent_id:
                        self.debug_print(f"  Matched rejected fact by persistent ID in {doc_name} at index {i}")
                        fact_matches = True
                    elif not persistent_id and document_name == doc_name and facts_list[i].get("statement", "") == statement:
                        self.debug_print(f"  Matched rejected fact by statement in {doc_name} at index {i}")
                        fact_matches = True
                        
                    if fact_matches:
                        facts_list.pop(i)
                        removed_count += 1
                        rejected_removed += 1
                        changes_made = True
                        
                if removed_count > 0:
                    self.debug_print(f"  Removed {removed_count} facts from {doc_name} in rejected fact repository")
            
            # Save changes if any removals were made
            if changes_made:
                self.debug_print(f"Saving changes after removing {facts_removed} facts and {rejected_removed} rejected facts")
                
                # Save changes to Excel with separate try blocks
                try:
                    self.fact_repo._save_to_excel()
                    self.debug_print("Fact repository saved to Excel after removals")
                except Exception as e:
                    self.debug_print(f"Error saving fact repository after removals: {str(e)}")
                
                try:
                    self.rejected_fact_repo._save_to_excel()
                    self.debug_print("Rejected fact repository saved to Excel after removals")
                except Exception as e:
                    self.debug_print(f"Error saving rejected fact repository after removals: {str(e)}")
                    
                # Reload from Excel to ensure consistency
                self.fact_repo._reload_facts_from_excel()
                self.rejected_fact_repo._reload_facts_from_excel()
                self.debug_print("Repositories reloaded after removals")
            
            return facts_removed + rejected_removed
            
        except Exception as e:
            import traceback
            self.debug_print(f"Error removing matching facts from repositories: {str(e)}")
            self.debug_print(traceback.format_exc())
            return 0

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
            
    def approve_fact_with_transaction(self, fact_id, statement, reason):
        """
        Approve a fact using the transaction system for data consistency.
        This wraps the standard approve_fact method with transaction support.
        """
        self.debug_print(f"Starting approve fact transaction for ID: {fact_id}")
        current_state = self._snapshot_current_state()
        
        try:
            # Perform the update with verification status set to "verified"
            result, facts_summary = self.update_fact(fact_id, statement, "verified", reason)
            
            # Verify data consistency
            if self._verify_data_consistency():
                self.debug_print(f"Approve fact transaction completed successfully: {result}")
                # Force synchronization
                self.synchronize_repositories()
                return result, facts_summary
            else:
                # Roll back if data is inconsistent
                self.debug_print("Data consistency check failed - rolling back transaction")
                self._restore_state(current_state)
                return "Error: Data consistency check failed after approval. Changes rolled back.", None
        except Exception as e:
            # Roll back on any exception
            import traceback
            self.debug_print(f"Error during approve_fact transaction: {str(e)}")
            self.debug_print(traceback.format_exc())
            self._restore_state(current_state)
            return f"Error approving fact: {str(e)}. Changes rolled back.", None

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
            
    def reject_fact_with_transaction(self, fact_id, statement, reason):
        """
        Reject a fact using the transaction system for data consistency.
        This wraps the standard reject_fact method with transaction support.
        """
        self.debug_print(f"Starting reject fact transaction for ID: {fact_id}")
        current_state = self._snapshot_current_state()
        
        try:
            # Perform the update with verification status set to "rejected"
            result, facts_summary = self.update_fact(fact_id, statement, "rejected", reason)
            
            # Verify data consistency
            if self._verify_data_consistency():
                self.debug_print(f"Reject fact transaction completed successfully: {result}")
                # Force synchronization
                self.synchronize_repositories()
                return result, facts_summary
            else:
                # Roll back if data is inconsistent
                self.debug_print("Data consistency check failed - rolling back transaction")
                self._restore_state(current_state)
                return "Error: Data consistency check failed after rejection. Changes rolled back.", None
        except Exception as e:
            # Roll back on any exception
            import traceback
            self.debug_print(f"Error during reject_fact transaction: {str(e)}")
            self.debug_print(traceback.format_exc())
            self._restore_state(current_state)
            return f"Error rejecting fact: {str(e)}. Changes rolled back.", None

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
        """Export verified facts to a Markdown file."""
        try:
            self.debug_print(f"Exporting facts to Markdown file: {output_path}")
            
            # Create the output directory if it doesn't exist
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            # Append .md extension if missing
            if not output_path.endswith(".md"):
                output_path += ".md"
            
            # Get all verified facts from the repository
            verified_facts = self.fact_repo.get_all_facts(verified_only=True)
            self.debug_print(f"Found {len(verified_facts)} verified facts to export")
            
            # Group facts by document
            facts_by_document = {}
            for fact in verified_facts:
                doc_name = fact.get("document_name", "Unknown Document")
                if doc_name not in facts_by_document:
                    facts_by_document[doc_name] = []
                facts_by_document[doc_name].append(fact)
            
            # Create Markdown content
            markdown_content = "# Extracted and Verified Facts\n\n"
            markdown_content += f"*Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n\n"
            
            # Add facts for each document
            for doc_name, facts in facts_by_document.items():
                markdown_content += f"## {doc_name}\n\n"
                
                for i, fact in enumerate(facts, 1):
                    statement = fact.get("statement", "No statement")
                    reason = fact.get("verification_reason", "No reasoning provided")
                    
                    markdown_content += f"### Fact {i}\n\n"
                    markdown_content += f"**Statement:** {statement}\n\n"
                    markdown_content += f"**Verification Reasoning:** {reason}\n\n"
                    markdown_content += "---\n\n"
            
            # Write to file
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(markdown_content)
            
            self.debug_print(f"Successfully exported {len(verified_facts)} facts to {output_path}")
            return f"Successfully exported {len(verified_facts)} facts to {output_path}"
        except Exception as e:
            error_msg = f"Error exporting facts to Markdown: {str(e)}"
            self.debug_print(error_msg)
            return error_msg
    
    def search_facts(self, query: str, n_results: int = 5) -> Tuple[str, str]:
        """
        Search for facts semantically similar to the query.
        
        Args:
            query: The search query text
            n_results: Number of results to return
            
        Returns:
            Tuple of (results_markdown, stats_markdown)
        """
        self.debug_print(f"Searching for facts with query: '{query}', n_results={n_results}")
        
        try:
            # Search for facts using the repository's search method
            results = self.fact_repo.search_facts(query=query, n_results=n_results)
            
            # Get vector store stats
            stats = self.fact_repo.get_vector_store_stats()
            
            # Format the search statistics
            stats_markdown = f"📊 **Search Statistics**\n"
            stats_markdown += f"* Found {len(results)} results for query: '{query}'\n"
            stats_markdown += f"* Total facts in vector store: {stats.get('fact_count', 0)}\n"
            
            # If no results, return early
            if not results:
                results_markdown = "No results found. Try a different search query or check if facts have been added to the vector store."
                return results_markdown, stats_markdown
            
            # Format the search results
            results_markdown = f"## 🔍 Search Results for '{query}'\n\n"
            
            for i, fact in enumerate(results, 1):
                # Format the similarity score as a percentage
                similarity = f"{fact.get('similarity', 0) * 100:.1f}%"
                
                results_markdown += f"### Result {i} (Relevance: {similarity})\n\n"
                results_markdown += f"**Statement:** {fact.get('statement', '')}\n\n"
                results_markdown += f"**Source:** {fact.get('document_name', '')}, Chunk: {fact.get('chunk_index', 0)}\n\n"
                
                if fact.get('extracted_at'):
                    results_markdown += f"**Extracted:** {fact.get('extracted_at', '')}\n\n"
                
                results_markdown += "---\n\n"
            
            self.debug_print(f"Found {len(results)} search results for query: '{query}'")
            return results_markdown, stats_markdown
            
        except Exception as e:
            error_message = f"Error searching facts: {str(e)}"
            self.debug_print(error_message)
            return f"Error: {error_message}", "Error occurred during search"
    
    def format_search_results(self, results: List[Dict[str, Any]]) -> str:
        """
        Format search results as Markdown.
        
        Args:
            results: List of search result dictionaries
            
        Returns:
            Markdown formatted results
        """
        if not results:
            return "No results found."
        
        markdown = ""
        
        for i, result in enumerate(results, 1):
            similarity = f"{result.get('similarity', 0) * 100:.1f}%"
            statement = result.get('statement', 'No statement available')
            document = result.get('document_name', 'Unknown document')
            chunk_index = result.get('chunk_index', 0)
            
            markdown += f"### Result {i} (Relevance: {similarity})\n\n"
            markdown += f"**Statement:** {statement}\n\n"
            markdown += f"**Source:** {document}, Chunk: {chunk_index}\n\n"
            markdown += "---\n\n"
        
        return markdown

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
                            
                            fact_status_display = gr.Markdown(label="Status", value="")
                            # Add a hidden field to store the status value
                            fact_status = gr.Textbox(visible=False)
                            self.debug_print("Created fact_status textbox")
                            
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
                
                # Fact Search section
                with gr.TabItem("Fact Search", elem_id="fact-search-tab"):
                    self.debug_print("Building Fact Search tab")
                    
                    with gr.Row():
                        # Left column for search input
                        with gr.Column(scale=1):
                            search_query = gr.Textbox(
                                label="Search Query",
                                placeholder="Enter a search query to find relevant facts",
                                lines=2,
                                interactive=True
                            )
                            self.debug_print("Created search_query textbox")
                            
                            num_results = gr.Slider(
                                label="Number of Results",
                                minimum=1,
                                maximum=20,
                                value=5,
                                step=1,
                                interactive=True
                            )
                            self.debug_print("Created num_results slider")
                            
                            search_btn = gr.Button("Search Facts", variant="primary")
                            self.debug_print("Created search_btn button")
                            
                            search_stats = gr.Markdown("")
                            self.debug_print("Created search_stats markdown")
                        
                        # Right column for search results
                        with gr.Column(scale=2):
                            search_results = gr.Markdown(
                                value="Enter a search query and click Search to find relevant facts.",
                                elem_id="search-results"
                            )
                            self.debug_print("Created search_results markdown")
            
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
                    # Refresh data from repositories first
                    self.refresh_facts_data()
                    self.debug_print(f"Refreshed facts data, found {len(self.facts_data)} documents")
                    
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
                    
                    # Display repository facts even if in-memory data is missing
                    if approved_facts_from_repo:
                        approved_facts_md += "\n## From Repository\n\n"
                        for i, fact in enumerate(approved_facts_from_repo):
                            doc_name = fact.get("document_name", "Unknown Document")
                            approved_facts_md += f"**Document:** {doc_name}\n\n"
                            approved_facts_md += f"✅ **Fact {i+1}:** {fact.get('statement', 'No statement')}\n\n"
                            if fact.get("verification_reason"):
                                approved_facts_md += f"*Reasoning:*\n{fact.get('verification_reason', '')}\n\n"
                            approved_facts_md += "---\n\n"
                    
                    if rejected_facts_from_repo:
                        rejected_facts_md += "\n## From Repository\n\n"
                        for i, fact in enumerate(rejected_facts_from_repo):
                            doc_name = fact.get("document_name", "Unknown Document")
                            rejected_facts_md += f"**Document:** {doc_name}\n\n"
                            rejected_facts_md += f"❌ **Fact {i+1}:** {fact.get('statement', 'No statement')}\n\n"
                            reason = ""
                            if fact.get("rejection_reason"):
                                reason = fact.get("rejection_reason")
                            elif fact.get("verification_reason"):
                                reason = fact.get("verification_reason")
                            
                            if reason:
                                rejected_facts_md += f"*Reasoning:*\n{reason}\n\n"
                            rejected_facts_md += "---\n\n"
                    
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
                    
                    # Continue with in-memory facts processing
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
            def on_fact_selected(evt):
                """Handle fact selection events with robust error handling."""
                self.debug_print(f"on_fact_selected called with selection: {evt}")
                
                try:
                    # Initialize debug information
                    debug_info = []
                    
                    # Handle empty or None selection
                    if evt is None or evt == "" or (hasattr(evt, 'index') and evt.index is None):
                        # This is an expected case after approving, rejecting, or modifying a fact
                        debug_info.append("Empty selection - form cleared and ready for next fact selection")
                        return "", "", "", "", "", "", "\n".join(debug_info)
                    
                    # Get all facts and choices
                    all_facts, fact_choices = self.get_facts_for_review()
                    # Add extensive logging for debugging
                    debug_info.append(f"Retrieved {len(all_facts)} facts and {len(fact_choices)} choices")
                    if not all_facts:
                        self.debug_print("Warning: No facts available for review")
                        return "", "", "", "", "", "", "No facts available for review"
                    
                    # Extract index from evt object or convert string to int
                    selected_index = None
                    if hasattr(evt, 'index'):
                        selected_index = evt.index
                        debug_info.append(f"Using SelectData index: {selected_index}")
                    elif isinstance(evt, (int, float)):
                        selected_index = int(evt)
                        debug_info.append(f"Using numeric index: {selected_index}")
                    elif isinstance(evt, str) and evt.isdigit():
                        selected_index = int(evt)
                        debug_info.append(f"Converted string index '{evt}' to int: {selected_index}")
                    else:
                        debug_info.append(f"Unrecognized selection format: {type(evt)}")
                        # Try to find the index by matching the choice text
                        for i, choice in enumerate(fact_choices):
                            if choice == evt:
                                selected_index = i
                                debug_info.append(f"Found matching choice at index {i}")
                                break
                        else:
                            debug_info.append("No matching choice found - returning empty values")
                            return "", "", "", "", "", "", "\n".join(debug_info)
                    
                    # Validate index is in range
                    if not all_facts or selected_index is None or selected_index < 0 or selected_index >= len(all_facts):
                        debug_info.append(f"Index {selected_index} out of range (valid range: 0-{len(all_facts)-1 if all_facts else 0})")
                        return "", "", "", "", "", "", "\n".join(debug_info)
                    
                    # Get the selected fact
                    fact = all_facts[selected_index]
                    debug_info.append(f"Selected fact at index {selected_index}: {fact.get('statement', '')[:50]}...")
                    
                    # Ensure the fact has a persistent ID
                    if not fact.get("persistent_id"):
                        fact["persistent_id"] = self._generate_persistent_id(fact)
                        debug_info.append(f"Generated new persistent ID: {fact['persistent_id']}")
                    
                    # Extract all required values with safe defaults
                    fact_id = fact.get("persistent_id", "") or str(fact.get("id", ""))
                    document_name = str(fact.get("document_name", "")) or str(fact.get("filename", ""))
                    statement = str(fact.get("statement", ""))
                    source = str(fact.get("original_text", "")) or str(fact.get("chunk", ""))
                    status = str(fact.get("verification_status", "pending"))
                    reason = str(fact.get("verification_reason", ""))
                    
                    debug_info.append(f"Returning values: ID={fact_id}, Document={document_name}, Status={status}")
                    
                    return (
                        fact_id,
                        document_name,
                        statement,
                        source,
                        status,
                        reason,
                        "\n".join(debug_info)
                    )
                except Exception as e:
                    import traceback
                    error_msg = f"Error in on_fact_selected: {str(e)}\n{traceback.format_exc()}"
                    self.debug_print(error_msg)
                    return "", "", "", "", "", "", error_msg
            
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
            approve_result = approve_btn.click(
                fn=lambda fact_id, statement, reason: self.approve_fact_with_transaction(fact_id, statement, reason) if fact_id and statement else ("Please select a fact first", self.format_facts_summary(self.facts_data)),
                inputs=[fact_id, fact_statement, fact_reason],
                outputs=[review_status, facts_summary],
                api_name="approve_fact",
                queue=True  # Ensure queuing is enabled
            )
            
            approve_update = approve_result.then(
                fn=update_facts_display,
                inputs=[chat_display, facts_summary],
                outputs=[chat_display, facts_summary, all_submissions, approved_facts, rejected_facts, errors_display, fact_selector],
                queue=True  # Ensure queuing is enabled
            )
            
            approve_clear = approve_update.then(
                fn=lambda: (None, "", "", "", "", "", "Fact approved. Select another fact to review.", "Selection cleared after approval - this is expected behavior"),
                inputs=None,
                outputs=[fact_selector, fact_id, fact_filename, fact_statement, fact_source, fact_status, fact_reason, debug_display],
                queue=True  # Ensure queuing is enabled
            )
            
            # Fix: separate the final .then() to fix the multiple values for argument 'fn' error
            approve_clear.then(
                fn=lambda: self.synchronize_repositories(),
                inputs=None,
                outputs=None,
                queue=True
            )
            
            # Connect reject button
            reject_result = reject_btn.click(
                fn=lambda fact_id, statement, reason: self.reject_fact_with_transaction(fact_id, statement, reason) if fact_id and statement else ("Please select a fact first", self.format_facts_summary(self.facts_data)),
                inputs=[fact_id, fact_statement, fact_reason],
                outputs=[review_status, facts_summary],
                api_name="reject_fact",
                queue=True  # Ensure queuing is enabled
            )
            
            reject_update = reject_result.then(
                fn=update_facts_display,
                inputs=[chat_display, facts_summary],
                outputs=[chat_display, facts_summary, all_submissions, approved_facts, rejected_facts, errors_display, fact_selector],
                queue=True  # Ensure queuing is enabled
            )
            
            # Fix: add explicit fn parameter
            reject_update.then(
                fn=lambda: (None, "", "", "", "pending", "", "Fact rejected. Select another fact to review.", "Selection cleared after rejection - this is expected behavior"),
                inputs=None,
                outputs=[fact_selector, fact_id, fact_filename, fact_statement, fact_source, fact_status, fact_reason, debug_display],
                queue=True  # Ensure queuing is enabled
            )

            # Connect modify button
            modify_result = modify_btn.click(
                fn=lambda fact_id, statement, status, reason: self.update_fact_with_transaction(fact_id, statement, status, reason) if fact_id and statement else ("Please select a fact first", self.format_facts_summary(self.facts_data)),
                inputs=[fact_id, fact_statement, fact_status, fact_reason],
                outputs=[review_status, facts_summary],
                api_name="update_fact",
                queue=True  # Ensure queuing is enabled
            )
            
            modify_update = modify_result.then(
                fn=update_facts_display,
                inputs=[chat_display, facts_summary],
                outputs=[chat_display, facts_summary, all_submissions, approved_facts, rejected_facts, errors_display, fact_selector],
                queue=True  # Ensure queuing is enabled
            )
            
            # Fix: add explicit fn parameter
            modify_update.then(
                fn=lambda: (None, "", "", "", "pending", "", "Fact modified. Select another fact to review.", "Selection cleared after modification - this is expected behavior"),
                inputs=None,
                outputs=[fact_selector, fact_id, fact_filename, fact_statement, fact_source, fact_status, fact_reason, debug_display],
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
            
            # Search tab event handler
            def on_search_facts(query, num_results):
                """Handle searching for facts based on semantic search."""
                self.debug_print(f"Search button clicked with query: '{query}', num_results: {num_results}")
                
                if not query:
                    return "Please enter a search query", "No search performed"
                
                # Search for facts
                results_markdown, stats_markdown = self.search_facts(
                    query=query,
                    n_results=int(num_results)
                )
                
                return results_markdown, stats_markdown
            
            # Connect search button to the search handler
            search_btn.click(
                fn=on_search_facts,
                inputs=[search_query, num_results],
                outputs=[search_results, search_stats]
            )
            
            self.debug_print("Connected all event handlers")
            
        self.debug_print("Finished building interface")
        return interface
    
    def refresh_facts_data(self):
        """Refresh the facts data from repositories."""
        self.debug_print("refresh_facts_data called")
        
        # First, force repositories to reload fresh data from Excel files
        self.fact_repo._reload_facts_from_excel()
        self.rejected_fact_repo._reload_facts_from_excel()
        
        # Clear existing facts data
        self.facts_data = {}
        
        # Load all facts from the repository
        verified_facts = self.fact_repo.get_all_facts(verified_only=True)
        all_facts = self.fact_repo.get_all_facts(verified_only=False)
        rejected_facts = self.rejected_fact_repo.get_all_rejected_facts()
        
        self.debug_print(f"Loaded {len(verified_facts)} verified facts")
        self.debug_print(f"Loaded {len(all_facts)} total facts")
        self.debug_print(f"Loaded {len(rejected_facts)} rejected facts")
        
        # Group facts by document name
        documents = set()
        for fact in all_facts + rejected_facts:
            doc_name = fact.get("document_name", "Unknown Document")
            documents.add(doc_name)
        
        # Create facts data structure
        for doc_name in documents:
            doc_verified = [f for f in verified_facts if f.get("document_name") == doc_name]
            doc_all = [f for f in all_facts if f.get("document_name") == doc_name]
            doc_rejected = [f for f in rejected_facts if f.get("document_name") == doc_name]
            
            # Filter out any facts with NaN or empty statements
            doc_verified = [f for f in doc_verified if f.get("statement") and not pd.isna(f.get("statement"))]
            doc_all = [f for f in doc_all if f.get("statement") and not pd.isna(f.get("statement"))]
            doc_rejected = [f for f in doc_rejected if f.get("statement") and not pd.isna(f.get("statement"))]
            
            self.facts_data[doc_name] = {
                "all_facts": doc_all + doc_rejected,
                "verified_facts": doc_verified,
                "total_facts": len(doc_all) + len(doc_rejected),
                "verified_count": len(doc_verified),
                "errors": []
            }
        
        self.debug_print(f"Refreshed facts data for {len(self.facts_data)} documents")
        
        return self.facts_data

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
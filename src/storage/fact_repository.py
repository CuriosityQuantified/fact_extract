"""
Repository for storing and managing extracted facts.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
import os
import pandas as pd
import hashlib
import traceback
import logging
import time
import threading
import shutil
import copy

# Set up logging configuration
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("fact_repository.log"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger("fact_repository")

# Lock to prevent concurrent file access
fact_repo_lock = threading.RLock()
rejected_fact_repo_lock = threading.RLock()

# Import vector store
from search.vector_store import ChromaFactStore

class FactRepository:
    """Repository for storing and managing facts with Excel persistence."""
    
    def __init__(self, excel_path: str = "data/all_facts.xlsx", 
                 vector_store_dir: str = "src/data/embeddings",
                 collection_name: str = "fact_embeddings"):
        """
        Initialize the FactRepository with both Excel and vector store capabilities.
        
        Args:
            excel_path: Path to the Excel file for storing facts
            vector_store_dir: Directory to store ChromaDB files
            collection_name: Name of the ChromaDB collection to use
        """
        self.facts: Dict[str, List[Dict[str, Any]]] = {}
        self.excel_path = excel_path
        # Valid status values
        self.valid_statuses = ["verified", "rejected", "pending"]
        
        # Create data directory if it doesn't exist
        os.makedirs(os.path.dirname(self.excel_path), exist_ok=True)
        
        # Initialize the vector store for semantic search
        self.vector_store = ChromaFactStore(
            persist_directory=vector_store_dir,
            collection_name="fact_embeddings_new"  # Use the new collection created by populate_vector_store.py
        )
        
        # Load existing facts from Excel if file exists
        self._load_from_excel()
        
        logger.info(f"Initialized FactRepository with Excel path: {self.excel_path} and vector store in {vector_store_dir}")
        
    def _load_from_excel(self) -> None:
        """Load facts from Excel file if it exists."""
        if os.path.exists(self.excel_path):
            try:
                logger.info(f"Loading facts from {self.excel_path}")
                # Read the Excel file and drop any completely empty rows
                df = pd.read_excel(self.excel_path)
                # Remove rows where document_name or statement is NaN or empty
                df = df.dropna(subset=['document_name', 'statement'], how='any')
                logger.info(f"Loaded {len(df)} facts from {self.excel_path} after removing empty rows")
                
                # Convert DataFrame to dictionary structure
                for _, row in df.iterrows():
                    document_name = row["document_name"]
                    
                    if document_name not in self.facts:
                        self.facts[document_name] = []
                    
                    # Convert row to dictionary
                    fact_data = row.to_dict()
                    
                    # Handle metadata columns
                    metadata = {}
                    for col in df.columns:
                        if col.startswith("metadata_"):
                            metadata_key = col[len("metadata_"):]
                            # Convert NaN values to None
                            value = fact_data.pop(col, None)
                            if not pd.isna(value):
                                metadata[metadata_key] = value
                    
                    fact_data["metadata"] = metadata
                    
                    # Clean NaN values
                    for key, value in list(fact_data.items()):
                        if pd.isna(value):
                            fact_data[key] = None
                    
                    # Fix: Ensure the statement field is properly set
                    if "fact" in fact_data and (not fact_data.get("statement") or pd.isna(fact_data.get("statement"))):
                        fact_data["statement"] = fact_data.get("fact", "")
                        
                    # Fix: Ensure verification fields are properly set
                    if "verification_status" not in fact_data or pd.isna(fact_data.get("verification_status")):
                        fact_data["verification_status"] = "pending"
                        
                    if "verification_reason" not in fact_data or pd.isna(fact_data.get("verification_reason")):
                        fact_data["verification_reason"] = ""
                    
                    # Only add the fact if it has valid statement
                    if fact_data.get("statement") and not pd.isna(fact_data.get("statement")):
                        self.facts[document_name].append(fact_data)
                    else:
                        logger.warning(f"Skipping fact with empty statement for document: {document_name}")
                        
            except Exception as e:
                logger.error(f"Error loading facts from Excel: {e}")
                logger.error(traceback.format_exc())
    
    def _save_to_excel(self) -> None:
        """Save facts to Excel file."""
        with fact_repo_lock:  # Use lock to prevent concurrent modifications
            try:
                start_time = time.time()
                
                # Ensure the directory exists
                if not os.path.exists(os.path.dirname(self.excel_path)):
                    os.makedirs(os.path.dirname(self.excel_path), exist_ok=True)
                    logger.info(f"Created directory: {os.path.dirname(self.excel_path)}")
                
                # Flatten facts for storage in Excel
                rows = []
                required_columns = [
                    "date_uploaded", "document_name", "source_name", "url", 
                    "fact", "statement", "chunk", "chunk_id", "verification_status", 
                    "verification_reason", "verification_reasoning", "persistent_id"
                ]
                
                for document_name, facts_list in self.facts.items():
                    for fact_data in facts_list:
                        # Create a deep copy of the fact data to avoid modifying the original
                        row_data = fact_data.copy()
                        
                        # Extract metadata and flatten it with prefix
                        if "metadata" in row_data and isinstance(row_data["metadata"], dict):
                            metadata = row_data.pop("metadata", {})
                            for key, value in metadata.items():
                                row_data[f"metadata_{key}"] = value
                        
                        # Preserve the original statement
                        original_statement = row_data.get("statement", "")
                        
                        # Ensure all required columns are present
                        row_data["date_uploaded"] = row_data.get("timestamp", datetime.now().isoformat())
                        row_data["source_name"] = row_data.get("source_name", "")
                        row_data["url"] = row_data.get("source_url", "")
                        row_data["document_name"] = document_name
                        
                        # Use the statement field directly instead of creating a new "fact" field
                        if "statement" in row_data:
                            row_data["fact"] = row_data["statement"]
                        else:
                            row_data["fact"] = ""
                            row_data["statement"] = ""
                        
                        row_data["chunk"] = row_data.get("original_text", "")
                        row_data["chunk_id"] = row_data.get("source_chunk", "")
                        
                        # Fix: Ensure verification status and reason are correctly set
                        row_data["verification_status"] = row_data.get("verification_status", "pending")
                        row_data["verification_reason"] = row_data.get("verification_reason", "")
                        row_data["verification_reasoning"] = row_data.get("verification_reasoning", row_data.get("verification_reason", ""))
                        
                        # Ensure persistent_id is preserved
                        if "persistent_id" not in row_data or not row_data["persistent_id"]:
                            # Generate a unique ID based on content to ensure consistency
                            import hashlib
                            import uuid
                            content = row_data.get("statement", "")
                            hash_input = f"{content}|{document_name}".encode('utf-8')
                            namespace = uuid.UUID(hashlib.md5(hash_input).hexdigest()[:32])
                            row_data["persistent_id"] = f"fact-{uuid.uuid5(namespace, content)}"
                            logger.debug(f"Generated new persistent_id for fact: {row_data['persistent_id']}")
                        
                        # Add the row data to the list
                        rows.append(row_data)
                
                if rows:
                    # Create DataFrame from the rows
                    df = pd.DataFrame(rows)
                    
                    # Reorder columns so required columns come first
                    all_columns = list(df.columns)
                    for col in reversed(required_columns):
                        if col in all_columns:
                            all_columns.remove(col)
                            all_columns.insert(0, col)
                    
                    df = df[all_columns]
                    
                    # Generate a temporary file name with timestamp to prevent conflicts
                    temp_dir = os.path.dirname(self.excel_path)
                    base_name = os.path.basename(self.excel_path)
                    timestamp = int(time.time() * 1000)  # Millisecond timestamp
                    temp_file = os.path.join(temp_dir, f"{os.path.splitext(base_name)[0]}.{timestamp}.xlsx")
                    
                    # Save to the temporary file first
                    logger.info(f"Saving {len(rows)} facts to temporary file: {temp_file}")
                    df.to_excel(temp_file, index=False)
                    
                    # Check if the temp file was created successfully
                    if not os.path.exists(temp_file):
                        logger.error(f"ERROR: Temporary file {temp_file} was not created!")
                        return
                    
                    # Create a backup of the existing file if it exists
                    backup_file = None
                    if os.path.exists(self.excel_path):
                        backup_file = f"{self.excel_path}.backup"
                        try:
                            shutil.copy2(self.excel_path, backup_file)
                            logger.info(f"Created backup of existing file: {backup_file}")
                        except Exception as e:
                            logger.error(f"Error creating backup file: {e}")
                    
                    # Move the temp file to the target file
                    try:
                        logger.info(f"Moving temporary file to target: {self.excel_path}")
                        shutil.move(temp_file, self.excel_path)
                    except Exception as e:
                        logger.error(f"Error moving temporary file: {e}")
                        # Try to restore from backup if available
                        if backup_file and os.path.exists(backup_file):
                            try:
                                shutil.copy2(backup_file, self.excel_path)
                                logger.info(f"Restored from backup after failed move")
                            except Exception as restore_error:
                                logger.error(f"Error restoring from backup: {restore_error}")
                        return
                    
                    # Verify the file was written successfully
                    if os.path.exists(self.excel_path):
                        logger.info(f"Successfully saved {len(rows)} facts to {self.excel_path} in {time.time() - start_time:.2f} seconds")
                        # Verify file content by reading it back
                        try:
                            check_df = pd.read_excel(self.excel_path)
                            logger.info(f"Verified file saved with {len(check_df)} rows")
                            
                            # Clean up backup if everything is successful
                            if backup_file and os.path.exists(backup_file):
                                try:
                                    os.remove(backup_file)
                                    logger.debug(f"Removed backup file: {backup_file}")
                                except Exception as e:
                                    logger.warning(f"Could not remove backup file: {e}")
                        except Exception as e:
                            logger.error(f"Error verifying saved file: {e}")
                    else:
                        logger.error(f"ERROR: File {self.excel_path} was not created!")
                    
                else:
                    # If there are no facts, create an empty Excel file
                    logger.info(f"No facts to save, creating empty Excel file: {self.excel_path}")
                    empty_df = pd.DataFrame(columns=required_columns)
                    empty_df.to_excel(self.excel_path, index=False)
                    
            except Exception as e:
                logger.error(f"Error saving facts to Excel: {e}")
                logger.error(traceback.format_exc())
                # If an error occurred, don't attempt to reload from Excel
                return
                
            # After successful save, force a reload to ensure consistency
            self._reload_facts_from_excel()
    
    def _generate_fact_hash(self, fact_data: Dict[str, Any]) -> str:
        """
        Generate a hash for a fact to identify duplicates.
        
        Args:
            fact_data: Dictionary containing fact information
            
        Returns:
            str: Hash of the fact
        """
        # Use only the statement to create a unique hash
        fact_text = fact_data.get("statement", "").strip()
        
        # Create a hash of the fact text to identify duplicates
        hash_input = fact_text.encode('utf-8')
        return hashlib.md5(hash_input).hexdigest()
    
    def is_duplicate_fact(self, fact_data: Dict[str, Any]) -> bool:
        """
        Check if a fact is a duplicate.
        
        Args:
            fact_data: Dictionary containing fact information
            
        Returns:
            bool: True if the fact is a duplicate
        """
        fact_hash = self._generate_fact_hash(fact_data)
        
        # Check all facts in all documents
        for document_name, facts_list in self.facts.items():
            for existing_fact in facts_list:
                existing_hash = self._generate_fact_hash(existing_fact)
                if existing_hash == fact_hash:
                    return True
        
        return False
        
    def store_fact(self, fact_data: Dict[str, Any]) -> str:
        """
        Store a fact in both Excel and the vector database.
        
        Args:
            fact_data: Dictionary containing fact data
            
        Returns:
            String ID of the stored fact
        """
        # Generate a unique ID for the fact
        fact_id = self._generate_fact_id(fact_data)
        
        # Check for duplicates
        fact_hash = self._generate_fact_hash(fact_data)
        if self._is_duplicate_fact(fact_hash):
            logger.info(f"Duplicate fact detected, skipping: {fact_data.get('statement', '')[:30]}...")
            return fact_id
        
        # Store in Excel (existing implementation)
        document_name = fact_data.get("document_name", "")
        if document_name not in self.facts:
            self.facts[document_name] = []
            
        self.facts[document_name].append(fact_data)
        
        # Save to Excel
        self._save_to_excel()
        
        # Additionally, store in vector database
        try:
            # Create metadata for the vector store
            metadata = {
                "document_name": fact_data.get("document_name", ""),
                "chunk_index": fact_data.get("chunk_index", 0),
                "source": fact_data.get("source_name", ""),
                "extracted_at": str(datetime.now()),
                "fact_hash": fact_hash,
                "verification_status": fact_data.get("verification_status", "pending")
            }
            
            # Add any additional metadata fields
            if "metadata" in fact_data and isinstance(fact_data["metadata"], dict):
                for key, value in fact_data["metadata"].items():
                    if key not in metadata:  # Don't overwrite existing fields
                        metadata[key] = value
            
            # Add to vector store
            self.vector_store.add_fact(
                fact_id=fact_id,
                statement=fact_data.get("statement", ""),
                metadata=metadata
            )
            logger.info(f"Fact {fact_id} added to vector store")
        except Exception as e:
            logger.error(f"Error adding fact to vector store: {e}")
            logger.error(traceback.format_exc())
            # Still return the ID since it was stored in Excel
        
        return fact_id
    
    def get_facts(
        self,
        document_name: str,
        verified_only: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Get facts for a document.
        
        Args:
            document_name: Name of the document
            verified_only: Only return verified facts
            
        Returns:
            List[Dict]: List of facts
        """
        if document_name not in self.facts:
            return []
            
        facts = self.facts[document_name]
        if verified_only:
            return [
                fact for fact in facts
                if fact.get("verification_status") == "verified"
            ]
        return facts
    
    def get_all_facts(self, verified_only: bool = True) -> List[Dict[str, Any]]:
        """
        Get all facts as a flat list.
        
        Args:
            verified_only: Only return verified facts
            
        Returns:
            List[Dict]: All facts
        """
        all_facts = []
        for document_name, facts_list in self.facts.items():
            if verified_only:
                all_facts.extend([
                    fact for fact in facts_list
                    if fact.get("verification_status") == "verified"
                ])
            else:
                all_facts.extend(facts_list)
        return all_facts
    
    def get_fact_count(
        self,
        document_name: str,
        verified_only: bool = True
    ) -> int:
        """
        Get count of facts for a document.
        
        Args:
            document_name: Name of the document
            verified_only: Only count verified facts
            
        Returns:
            int: Number of facts
        """
        return len(self.get_facts(document_name, verified_only))
    
    def get_facts_for_document(
        self,
        document_name: str,
        verified_only: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Get facts for a document. Alias for get_facts for backward compatibility.
        
        Args:
            document_name: Name of the document
            verified_only: Only return verified facts
            
        Returns:
            List[Dict]: List of facts
        """
        return self.get_facts(document_name, verified_only)
    
    def remove_fact(self, document_name: str, statement: str, remove_all: bool = False) -> bool:
        """
        Remove a fact from both Excel and vector store.
        
        Args:
            document_name: The name of the document containing the fact
            statement: The statement text to remove
            remove_all: If True, remove all instances of the statement, otherwise just the first
            
        Returns:
            True if the fact was removed, False otherwise
        """
        with fact_repo_lock:
            try:
                # Remove from Excel (existing implementation)
                if document_name not in self.facts:
                    logger.warning(f"Document {document_name} not found in repository")
                    return False
                
                # First, generate fact IDs for facts to be removed
                facts_to_remove = []
                indices_to_remove = []
                
                for i, fact in enumerate(self.facts[document_name]):
                    if fact.get("statement", "") == statement:
                        # Generate the fact ID
                        fact_id = self._generate_fact_id(fact)
                        facts_to_remove.append(fact_id)
                        indices_to_remove.append(i)
                        
                        # If not removing all, just remove the first one
                        if not remove_all:
                            break
                
                # If no facts found with this statement
                if not indices_to_remove:
                    logger.warning(f"No facts found with statement: {statement}")
                    return False
                
                # Remove from the list in reverse order to maintain correct indices
                for index in sorted(indices_to_remove, reverse=True):
                    self.facts[document_name].pop(index)
                
                # Save changes to Excel
                self._save_to_excel()
                
                # Remove from vector store
                for fact_id in facts_to_remove:
                    try:
                        self.vector_store.delete_fact(fact_id)
                        logger.info(f"Removed fact {fact_id} from vector store")
                    except Exception as e:
                        logger.error(f"Error removing fact {fact_id} from vector store: {e}")
                
                return True
            except Exception as e:
                logger.error(f"Error removing fact: {e}")
                logger.error(traceback.format_exc())
                return False
            
    def update_fact(self, document_name: str, old_statement: str, new_data: Dict[str, Any]) -> bool:
        """
        Update a fact in both Excel and vector store.
        
        Args:
            document_name: The name of the document containing the fact
            old_statement: The current statement text to update
            new_data: New data for the fact
            
        Returns:
            True if the fact was updated, False otherwise
        """
        with fact_repo_lock:
            try:
                # First, find the fact to update
                if document_name not in self.facts:
                    logger.warning(f"Document {document_name} not found in repository")
                    return False
                
                fact_found = False
                old_fact = None
                
                for i, fact in enumerate(self.facts[document_name]):
                    if fact.get("statement", "") == old_statement:
                        # Generate the old fact ID for vector store removal
                        old_fact_id = self._generate_fact_id(fact)
                        old_fact = copy.deepcopy(fact)  # Keep a copy of the old fact
                        
                        # Update the fact in Excel storage
                        for key, value in new_data.items():
                            self.facts[document_name][i][key] = value
                        
                        fact_found = True
                        break
                
                if not fact_found:
                    logger.warning(f"No fact found with statement: {old_statement}")
                    return False
                
                # Save changes to Excel
                self._save_to_excel()
                
                # Update in vector store (delete old, add new)
                try:
                    # Delete the old fact from vector store
                    self.vector_store.delete_fact(old_fact_id)
                    
                    # Create a new fact with updated data for vector store
                    updated_fact = old_fact.copy()
                    for key, value in new_data.items():
                        updated_fact[key] = value
                    
                    # Generate new fact ID
                    new_fact_id = self._generate_fact_id(updated_fact)
                    
                    # Create metadata for the vector store
                    metadata = {
                        "document_name": updated_fact.get("document_name", ""),
                        "chunk_index": updated_fact.get("chunk_index", 0),
                        "source": updated_fact.get("source_name", ""),
                        "extracted_at": str(datetime.now()),
                        "fact_hash": self._generate_fact_hash(updated_fact),
                        "verification_status": updated_fact.get("verification_status", "pending")
                    }
                    
                    # Add to vector store
                    self.vector_store.add_fact(
                        fact_id=new_fact_id,
                        statement=updated_fact.get("statement", ""),
                        metadata=metadata
                    )
                    logger.info(f"Updated fact {old_fact_id} to {new_fact_id} in vector store")
                except Exception as e:
                    logger.error(f"Error updating fact in vector store: {e}")
                    logger.error(traceback.format_exc())
                
                return True
            except Exception as e:
                logger.error(f"Error updating fact: {e}")
                logger.error(traceback.format_exc())
                return False
    
    def _generate_fact_id(self, fact_data: Dict[str, Any]) -> str:
        """
        Generate a unique identifier for a fact.
        
        Args:
            fact_data: Fact data dictionary
            
        Returns:
            String ID for the fact
        """
        # Use document name and chunk index for consistency
        document_name = fact_data.get("document_name", "")
        chunk_index = fact_data.get("chunk_index", 0)
        
        # Add a hash of the statement for uniqueness
        statement = fact_data.get("statement", "")
        statement_hash = hash(statement) % 10000  # Simple hash to keep ID short
        
        return f"{document_name}_{chunk_index}_{statement_hash}"

    def _is_duplicate_fact(self, fact_hash: str) -> bool:
        """
        Check if a fact is a duplicate.
        
        Args:
            fact_hash: Hash of the fact
            
        Returns:
            bool: True if the fact is a duplicate
        """
        # Check all facts in all documents
        for document_name, facts_list in self.facts.items():
            for existing_fact in facts_list:
                existing_hash = self._generate_fact_hash(existing_fact)
                if existing_hash == fact_hash:
                    return True
        
        return False
    
    def _reload_facts_from_excel(self) -> None:
        """Reload facts from Excel file to ensure they're stored correctly."""
        if os.path.exists(self.excel_path):
            try:
                # Create a backup of the current facts data in case loading fails
                facts_backup = copy.deepcopy(self.facts)
                
                # Clear existing facts
                self.facts = {}
                
                # Load fresh data from Excel
                logger.info(f"Reloading facts from {self.excel_path}")
                df = pd.read_excel(self.excel_path)
                
                # Remove rows where document_name or statement is NaN or empty
                df = df.dropna(subset=['document_name', 'statement'], how='any')
                logger.info(f"Reloaded {len(df)} facts from {self.excel_path} after removing empty rows")
                
                # Convert DataFrame to dictionary structure
                for _, row in df.iterrows():
                    document_name = row["document_name"]
                    
                    if document_name not in self.facts:
                        self.facts[document_name] = []
                    
                    # Convert row to dictionary
                    fact_data = row.to_dict()
                    
                    # Clean NaN values
                    for key, value in list(fact_data.items()):
                        if pd.isna(value):
                            fact_data[key] = None
                    
                    # Handle metadata columns
                    metadata = {}
                    for col in df.columns:
                        if col.startswith("metadata_"):
                            metadata_key = col[len("metadata_"):]
                            value = fact_data.pop(col, None)
                            if value is not None and not pd.isna(value):
                                metadata[metadata_key] = value
                    
                    fact_data["metadata"] = metadata
                    
                    # Fix: Ensure statement field is set from fact field if needed
                    if "fact" in fact_data and ("statement" not in fact_data or fact_data["statement"] is None):
                        fact_data["statement"] = fact_data["fact"]
                            
                    # Fix: Ensure verification status is set
                    if "verification_status" not in fact_data or fact_data["verification_status"] is None:
                        fact_data["verification_status"] = "pending"
                    
                    # Debug log to check statement
                    logger.debug(f"Reloaded fact with statement: {fact_data.get('statement', '')[:40]}... status: {fact_data.get('verification_status', 'unknown')}")
                    
                    # Only add if statement is not empty
                    if fact_data.get("statement") and not pd.isna(fact_data.get("statement")):
                        self.facts[document_name].append(fact_data)
                    else:
                        logger.warning(f"Skipping fact with empty statement during reload for document: {document_name}")
                        
            except Exception as e:
                logger.error(f"Error reloading facts from Excel: {e}")
                logger.error(traceback.format_exc())
                # Restore backup if loading fails
                self.facts = facts_backup
                return False
                
            return True
        return False

    def clear_facts(self, document_name: str) -> bool:
        """
        Clear all facts for a document.
        
        Args:
            document_name: Name of the document
            
        Returns:
            bool: True if the document existed and facts were cleared
        """
        with fact_repo_lock:  # Use lock to prevent concurrent modifications
            if document_name in self.facts:
                del self.facts[document_name]
                # Save changes to Excel
                self._save_to_excel()
                logger.info(f"Cleared all facts for document: {document_name}")
                return True
            return False

    def search_facts(self, query: str, n_results: int = 5, 
                     filter_criteria: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Search for facts semantically similar to the query.
        
        Args:
            query: The search query text
            n_results: Number of results to return
            filter_criteria: Optional filter for metadata fields
            
        Returns:
            List of fact dictionaries matching the query
        """
        try:
            # Search the vector store
            results = self.vector_store.search_facts(
                query=query,
                n_results=n_results,
                filter_criteria=filter_criteria
            )
            
            # Format the results
            formatted_results = []
            
            # Check if we have search results
            if results and "ids" in results and len(results["ids"]) > 0:
                for i, fact_id in enumerate(results["ids"][0]):
                    # Get the similarity score (convert from distance)
                    similarity = 1 - results["distances"][0][i] if "distances" in results else 0
                    
                    # Get the document text
                    statement = results["documents"][0][i] if "documents" in results else ""
                    
                    # Get the metadata
                    metadata = results["metadatas"][0][i] if "metadatas" in results else {}
                    
                    # Create a complete fact record
                    fact = {
                        "id": fact_id,
                        "statement": statement,
                        "similarity": similarity,
                        "document_name": metadata.get("document_name", ""),
                        "chunk_index": metadata.get("chunk_index", 0),
                        "source": metadata.get("source", ""),
                        "extracted_at": metadata.get("extracted_at", "")
                    }
                    
                    formatted_results.append(fact)
            
            logger.info(f"Search for '{query}' returned {len(formatted_results)} results")
            return formatted_results
        except Exception as e:
            logger.error(f"Error searching facts: {e}")
            logger.error(traceback.format_exc())
            return []

    def get_vector_store_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the vector store.
        
        Returns:
            Dictionary with vector store statistics
        """
        try:
            # Get fact count from vector store
            fact_count = self.vector_store.get_fact_count()
            
            return {
                "fact_count": fact_count,
                "collection_name": self.vector_store.collection.name,
                # Use simpler approach to avoid relying on internal API that might change
                "embeddings_directory": self.vector_store.client.get_settings().persist_directory
            }
        except Exception as e:
            logger.error(f"Error getting vector store stats: {e}")
            logger.error(traceback.format_exc())
            return {
                "error": str(e),
                "fact_count": 0
            }

class RejectedFactRepository:
    """Repository for storing and managing rejected facts with Excel persistence."""
    
    def __init__(self, excel_path: str = "data/rejected_facts.xlsx"):
        self.rejected_facts: Dict[str, List[Dict[str, Any]]] = {}
        self.excel_path = excel_path
        # Valid verification statuses
        self.valid_statuses = ["rejected", "pending"]
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(excel_path), exist_ok=True)
        
        # Try to load from Excel
        self._load_from_excel()
        
        logger.info(f"Initialized RejectedFactRepository with path: {self.excel_path}")
        
    def _load_from_excel(self) -> None:
        """Load rejected facts from Excel file if it exists."""
        if os.path.exists(self.excel_path):
            try:
                logger.info(f"Loading rejected facts from {self.excel_path}")
                # Read the Excel file and drop any completely empty rows
                df = pd.read_excel(self.excel_path)
                # Remove rows where document_name or statement is NaN or empty
                df = df.dropna(subset=['document_name', 'statement'], how='any')
                logger.info(f"Loaded {len(df)} rejected facts from {self.excel_path} after removing empty rows")
                
                # Convert DataFrame to dictionary structure
                for _, row in df.iterrows():
                    document_name = row["document_name"]
                    
                    if document_name not in self.rejected_facts:
                        self.rejected_facts[document_name] = []
                    
                    # Convert row to dictionary
                    fact_data = row.to_dict()
                    
                    # Clean NaN values
                    for key, value in list(fact_data.items()):
                        if pd.isna(value):
                            fact_data[key] = None
                    
                    # Handle metadata columns
                    metadata = {}
                    for col in df.columns:
                        if col.startswith("metadata_"):
                            metadata_key = col[len("metadata_"):]
                            value = fact_data.pop(col, None)
                            if value is not None and not pd.isna(value):
                                metadata[metadata_key] = value
                    
                    fact_data["metadata"] = metadata
                    
                    # Fix: Ensure statement is set properly
                    if "fact" in fact_data and (not fact_data.get("statement") or fact_data["statement"] is None):
                        fact_data["statement"] = fact_data.get("fact", "")
                        
                    # Map rejection_reason to verification_reason for consistency
                    if "rejection_reason" in fact_data and (not fact_data.get("verification_reason") or fact_data["verification_reason"] is None):
                        fact_data["verification_reason"] = fact_data.get("rejection_reason", "")
                        
                    # Fix: Ensure verification status is rejected
                    fact_data["verification_status"] = "rejected"
                    
                    # Only add if statement is not empty
                    if fact_data.get("statement") and not pd.isna(fact_data.get("statement")):
                        self.rejected_facts[document_name].append(fact_data)
                    else:
                        logger.warning(f"Skipping rejected fact with empty statement for document: {document_name}")
                        
            except Exception as e:
                logger.error(f"Error loading rejected facts from Excel: {e}")
                logger.error(traceback.format_exc())
    
    def _save_to_excel(self) -> None:
        """Save rejected facts to Excel file."""
        with rejected_fact_repo_lock:  # Use lock to prevent concurrent modifications
            try:
                start_time = time.time()
                
                # Ensure the directory exists
                if not os.path.exists(os.path.dirname(self.excel_path)):
                    os.makedirs(os.path.dirname(self.excel_path), exist_ok=True)
                    logger.info(f"Created directory: {os.path.dirname(self.excel_path)}")
                
                # Flatten facts for storage in Excel
                rows = []
                required_columns = [
                    "date_uploaded", "document_name", "source_name", "url", 
                    "fact", "statement", "chunk", "chunk_id", "verification_status", 
                    "rejection_reason", "verification_reasoning", "persistent_id"
                ]
                
                for document_name, facts_list in self.rejected_facts.items():
                    for fact_data in facts_list:
                        # Create a deep copy of the fact data to avoid modifying the original
                        row_data = fact_data.copy()
                        
                        # Extract metadata and flatten it with prefix
                        if "metadata" in row_data and isinstance(row_data["metadata"], dict):
                            metadata = row_data.pop("metadata", {})
                            for key, value in metadata.items():
                                row_data[f"metadata_{key}"] = value
                        
                        # Preserve the original statement
                        original_statement = row_data.get("statement", "")
                        
                        # Ensure all required columns are present
                        row_data["date_uploaded"] = row_data.get("timestamp", datetime.now().isoformat())
                        row_data["source_name"] = row_data.get("source_name", "")
                        row_data["url"] = row_data.get("source_url", "")
                        row_data["document_name"] = document_name
                        
                        # Use the statement field directly instead of creating a new "fact" field
                        if "statement" in row_data:
                            row_data["fact"] = row_data["statement"]
                        else:
                            row_data["fact"] = ""
                            row_data["statement"] = ""
                        
                        row_data["chunk"] = row_data.get("original_text", "")
                        row_data["chunk_id"] = row_data.get("source_chunk", "")
                        
                        # Fix: Ensure verification/rejection fields are correctly set
                        row_data["verification_status"] = "rejected"  # Always rejected in this repository
                        
                        # Make sure the rejection reason is properly set
                        if "rejection_reason" not in row_data or pd.isna(row_data["rejection_reason"]):
                            # Use verification_reason as a fallback if available
                            if "verification_reason" in row_data and not pd.isna(row_data["verification_reason"]):
                                row_data["rejection_reason"] = row_data["verification_reason"]
                            else:
                                row_data["rejection_reason"] = ""
                                
                        # Make sure verification_reasoning is set for compatibility
                        row_data["verification_reasoning"] = row_data.get("rejection_reason", "")
                        
                        # Ensure persistent_id is preserved
                        if "persistent_id" not in row_data or not row_data["persistent_id"]:
                            # Generate a unique ID based on content to ensure consistency
                            import hashlib
                            import uuid
                            content = row_data.get("statement", "")
                            hash_input = f"{content}|{document_name}".encode('utf-8')
                            namespace = uuid.UUID(hashlib.md5(hash_input).hexdigest()[:32])
                            row_data["persistent_id"] = f"fact-{uuid.uuid5(namespace, content)}"
                            logger.debug(f"Generated new persistent_id for rejected fact: {row_data['persistent_id']}")
                        
                        # Add the row data to the list
                        rows.append(row_data)
                
                if rows:
                    # Create DataFrame from the rows
                    df = pd.DataFrame(rows)
                    
                    # Reorder columns so required columns come first
                    all_columns = list(df.columns)
                    for col in reversed(required_columns):
                        if col in all_columns:
                            all_columns.remove(col)
                            all_columns.insert(0, col)
                    
                    df = df[all_columns]
                    
                    # Generate a temporary file name with timestamp to prevent conflicts
                    temp_dir = os.path.dirname(self.excel_path)
                    base_name = os.path.basename(self.excel_path)
                    timestamp = int(time.time() * 1000)  # Millisecond timestamp
                    temp_file = os.path.join(temp_dir, f"{os.path.splitext(base_name)[0]}.{timestamp}.xlsx")
                    
                    # Save to the temporary file first
                    logger.info(f"Saving {len(rows)} rejected facts to temporary file: {temp_file}")
                    df.to_excel(temp_file, index=False)
                    
                    # Check if the temp file was created successfully
                    if not os.path.exists(temp_file):
                        logger.error(f"ERROR: Temporary file {temp_file} was not created!")
                        return
                    
                    # Create a backup of the existing file if it exists
                    backup_file = None
                    if os.path.exists(self.excel_path):
                        backup_file = f"{self.excel_path}.backup"
                        try:
                            shutil.copy2(self.excel_path, backup_file)
                            logger.info(f"Created backup of existing rejected facts file: {backup_file}")
                        except Exception as e:
                            logger.error(f"Error creating backup file: {e}")
                    
                    # Move the temp file to the target file
                    try:
                        logger.info(f"Moving temporary file to target: {self.excel_path}")
                        shutil.move(temp_file, self.excel_path)
                    except Exception as e:
                        logger.error(f"Error moving temporary file: {e}")
                        # Try to restore from backup if available
                        if backup_file and os.path.exists(backup_file):
                            try:
                                shutil.copy2(backup_file, self.excel_path)
                                logger.info(f"Restored from backup after failed move")
                            except Exception as restore_error:
                                logger.error(f"Error restoring from backup: {restore_error}")
                        return
                    
                    # Verify the file was written successfully
                    if os.path.exists(self.excel_path):
                        logger.info(f"Successfully saved {len(rows)} rejected facts to {self.excel_path} in {time.time() - start_time:.2f} seconds")
                        # Verify file content by reading it back
                        try:
                            check_df = pd.read_excel(self.excel_path)
                            logger.info(f"Verified file saved with {len(check_df)} rows")
                            
                            # Clean up backup if everything is successful
                            if backup_file and os.path.exists(backup_file):
                                try:
                                    os.remove(backup_file)
                                    logger.debug(f"Removed backup file: {backup_file}")
                                except Exception as e:
                                    logger.warning(f"Could not remove backup file: {e}")
                        except Exception as e:
                            logger.error(f"Error verifying saved file: {e}")
                    else:
                        logger.error(f"ERROR: File {self.excel_path} was not created!")
                    
                else:
                    # If there are no facts, create an empty Excel file
                    logger.info(f"No rejected facts to save, creating empty Excel file: {self.excel_path}")
                    empty_df = pd.DataFrame(columns=required_columns)
                    empty_df.to_excel(self.excel_path, index=False)
                    
            except Exception as e:
                logger.error(f"Error saving rejected facts to Excel: {e}")
                logger.error(traceback.format_exc())
                # If an error occurred, don't attempt to reload from Excel
                return
                
            # After successful save, force a reload to ensure consistency
            self._reload_facts_from_excel()
    
    def _generate_fact_hash(self, fact_data: Dict[str, Any]) -> str:
        """
        Generate a hash for a fact to identify duplicates.
        
        Args:
            fact_data: Dictionary containing fact information
            
        Returns:
            str: Hash of the fact
        """
        # Use only the statement to create a unique hash
        fact_text = fact_data.get("statement", "").strip()
        
        # Create a hash of the fact text to identify duplicates
        hash_input = fact_text.encode('utf-8')
        return hashlib.md5(hash_input).hexdigest()
    
    def is_duplicate_fact(self, fact_data: Dict[str, Any]) -> bool:
        """
        Check if a fact is a duplicate.
        
        Args:
            fact_data: Dictionary containing fact information
            
        Returns:
            bool: True if the fact is a duplicate
        """
        fact_hash = self._generate_fact_hash(fact_data)
        
        # Check all facts in all documents
        for document_name, facts_list in self.rejected_facts.items():
            for existing_fact in facts_list:
                existing_hash = self._generate_fact_hash(existing_fact)
                if existing_hash == fact_hash:
                    return True
        
        return False
        
    def store_rejected_fact(self, fact_data: Dict[str, Any]) -> None:
        """
        Store a rejected fact with its metadata if it's not a duplicate.
        
        Args:
            fact_data: Dictionary containing rejected fact information
        """
        logger.info(f"store_rejected_fact called with statement: {fact_data.get('statement', '')[:40]}...")
        logger.info(f"Status: {fact_data.get('verification_status', 'None')}")
        logger.info(f"Rejection reason: {fact_data.get('rejection_reason', fact_data.get('verification_reason', 'None'))[:40]}...")
        
        with rejected_fact_repo_lock:  # Use lock to prevent concurrent modifications
            document_name = fact_data["document_name"]
            
            # Validate the verification status
            if "verification_status" in fact_data:
                status = fact_data["verification_status"]
                if status not in self.valid_statuses:
                    logger.warning(f"Warning: Invalid verification status '{status}'. Setting to 'rejected'.")
                    fact_data["verification_status"] = "rejected"
            else:
                fact_data["verification_status"] = "rejected"
                
            # Check if this is a duplicate fact - skip if it's explicitly marked as edited
            if not fact_data.get("edited", False) and self.is_duplicate_fact(fact_data):
                logger.info(f"Duplicate rejected fact detected, not storing: {fact_data.get('statement', '')[:40]}...")
                return
                
            if document_name not in self.rejected_facts:
                self.rejected_facts[document_name] = []
                logger.info(f"Created new document entry in rejected facts: {document_name}")
                
            # Add timestamp if not present
            if "timestamp" not in fact_data:
                fact_data["timestamp"] = datetime.now().isoformat()
                
            # Ensure the rejection reason is set
            if "rejection_reason" not in fact_data and "verification_reason" in fact_data:
                fact_data["rejection_reason"] = fact_data["verification_reason"]
                logger.info(f"Using verification_reason as rejection_reason: {fact_data['rejection_reason'][:40]}...")
                
            # Store the rejected fact
            self.rejected_facts[document_name].append(fact_data)
            
            logger.info(f"Stored rejected fact: {fact_data.get('statement', '')[:40]}... in document: {document_name}")
            logger.info(f"Current rejected fact count for document {document_name}: {len(self.rejected_facts[document_name])}")
            
            # Save changes to Excel immediately
            self._save_to_excel()
    
    def get_rejected_facts(
        self,
        document_name: str
    ) -> List[Dict[str, Any]]:
        """
        Get rejected facts for a document.
        
        Args:
            document_name: Name of the document
            
        Returns:
            List[Dict]: List of rejected facts
        """
        if document_name not in self.rejected_facts:
            return []
            
        return self.rejected_facts[document_name]
    
    def get_rejected_facts_for_document(
        self,
        document_name: str
    ) -> List[Dict[str, Any]]:
        """
        Get rejected facts for a document. Alias for get_rejected_facts for backward compatibility.
        
        Args:
            document_name: Name of the document
            
        Returns:
            List[Dict]: List of rejected facts
        """
        return self.get_rejected_facts(document_name)
    
    def get_all_rejected_facts(self) -> List[Dict[str, Any]]:
        """
        Get all rejected facts as a flat list.
        
        Returns:
            List[Dict]: All rejected facts
        """
        all_rejected_facts = []
        for document_name, facts_list in self.rejected_facts.items():
            all_rejected_facts.extend(facts_list)
        return all_rejected_facts
    
    def get_rejected_fact_count(self, document_name: str) -> int:
        """
        Get count of rejected facts for a document.
        
        Args:
            document_name: Name of the document
            
        Returns:
            int: Number of rejected facts
        """
        return len(self.get_rejected_facts(document_name))
    
    def clear_rejected_facts(self, document_name: str) -> bool:
        """
        Clear all rejected facts for a document.
        
        Args:
            document_name: Name of the document
            
        Returns:
            bool: True if the document existed and rejected facts were cleared
        """
        with rejected_fact_repo_lock:  # Use lock to prevent concurrent modifications
            if document_name in self.rejected_facts:
                del self.rejected_facts[document_name]
                # Save changes to Excel
                self._save_to_excel()
                logger.info(f"Cleared all rejected facts for document: {document_name}")
                return True
            return False
            
    def remove_rejected_fact(
        self, 
        document_name: str, 
        statement: str, 
        remove_all: bool = False
    ) -> bool:
        """
        Remove a rejected fact from the repository.
        
        Args:
            document_name: Name of the document
            statement: The statement to remove
            remove_all: Remove all instances of the statement
            
        Returns:
            bool: True if any facts were removed
        """
        if document_name not in self.rejected_facts:
            return False
            
        found = False
        for i in range(len(self.rejected_facts[document_name]) - 1, -1, -1):
            fact = self.rejected_facts[document_name][i]
            if fact.get("statement", "") == statement:
                self.rejected_facts[document_name].pop(i)
                found = True
                print(f"Removed rejected fact: {statement[:40]}...")
                if not remove_all:
                    break
                    
        if found:
            # Save changes to Excel
            self._save_to_excel()
        
        return found
            
    def _reload_facts_from_excel(self) -> None:
        """Reload rejected facts from Excel file to ensure they're stored correctly."""
        if os.path.exists(self.excel_path):
            try:
                # Create a backup of the current facts data in case loading fails
                facts_backup = copy.deepcopy(self.rejected_facts)
                
                # Clear existing facts
                self.rejected_facts = {}
                
                # Load fresh data from Excel
                logger.info(f"Reloading rejected facts from {self.excel_path}")
                df = pd.read_excel(self.excel_path)
                
                # Remove rows where document_name or statement is NaN or empty
                df = df.dropna(subset=['document_name', 'statement'], how='any')
                logger.info(f"Reloaded {len(df)} rejected facts from {self.excel_path} after removing empty rows")
                
                # Convert DataFrame to dictionary structure
                for _, row in df.iterrows():
                    document_name = row["document_name"]
                    
                    if document_name not in self.rejected_facts:
                        self.rejected_facts[document_name] = []
                    
                    # Convert row to dictionary
                    fact_data = row.to_dict()
                    
                    # Clean NaN values
                    for key, value in list(fact_data.items()):
                        if pd.isna(value):
                            fact_data[key] = None
                    
                    # Handle metadata columns
                    metadata = {}
                    for col in df.columns:
                        if col.startswith("metadata_"):
                            metadata_key = col[len("metadata_"):]
                            value = fact_data.pop(col, None)
                            if value is not None and not pd.isna(value):
                                metadata[metadata_key] = value
                    
                    fact_data["metadata"] = metadata
                    
                    # Fix: Ensure statement field is set from fact field if needed
                    if "fact" in fact_data and ("statement" not in fact_data or fact_data["statement"] is None):
                        fact_data["statement"] = fact_data["fact"]
                            
                    # Map rejection_reason to verification_reason for consistency
                    if "rejection_reason" in fact_data and (not fact_data.get("verification_reason") or fact_data["verification_reason"] is None):
                        fact_data["verification_reason"] = fact_data.get("rejection_reason", "")
                            
                    # Fix: Ensure verification status is rejected
                    fact_data["verification_status"] = "rejected"
                    
                    # Debug log to check statement
                    logger.debug(f"Reloaded rejected fact with statement: {fact_data.get('statement', '')[:40]}...")
                    
                    # Only add if statement is not empty
                    if fact_data.get("statement") and not pd.isna(fact_data.get("statement")):
                        self.rejected_facts[document_name].append(fact_data)
                    else:
                        logger.warning(f"Skipping rejected fact with empty statement during reload for document: {document_name}")
                        
            except Exception as e:
                logger.error(f"Error reloading rejected facts from Excel: {e}")
                logger.error(traceback.format_exc())
                # Restore backup if loading fails
                self.rejected_facts = facts_backup
                return False
                
            return True
        return False 
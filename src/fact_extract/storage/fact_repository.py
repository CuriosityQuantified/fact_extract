"""
Repository for storing and managing extracted facts.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
import os
import pandas as pd
import hashlib

class FactRepository:
    """Repository for storing and managing facts with Excel persistence."""
    
    def __init__(self, excel_path: str = "src/fact_extract/data/all_facts.xlsx"):
        self.facts: Dict[str, List[Dict[str, Any]]] = {}
        self.excel_path = excel_path
        # Valid status values
        self.valid_statuses = ["verified", "rejected", "pending"]
        
        # Create data directory if it doesn't exist
        os.makedirs(os.path.dirname(self.excel_path), exist_ok=True)
        
        # Load existing facts from Excel if file exists
        self._load_from_excel()
        
    def _load_from_excel(self) -> None:
        """Load facts from Excel file if it exists."""
        if os.path.exists(self.excel_path):
            try:
                df = pd.read_excel(self.excel_path)
                
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
                            metadata[metadata_key] = fact_data.pop(col, None)
                    
                    fact_data["metadata"] = metadata
                    self.facts[document_name].append(fact_data)
                    
            except Exception as e:
                print(f"Error loading facts from Excel: {e}")
    
    def _save_to_excel(self) -> None:
        """Save all facts to Excel file."""
        try:
            # Flatten the nested dictionary structure
            rows = []
            for document_name, facts_list in self.facts.items():
                for fact_data in facts_list:
                    # Create a copy of the fact data
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
                    
                    # Debug print to check statement
                    if original_statement != row_data.get("statement", ""):
                        print(f"WARNING: Statement changed during Excel preparation!")
                        print(f"  Original: {original_statement[:40]}...")
                        print(f"  Row data: {row_data.get('statement', '')[:40]}...")
                        # Fix the statement if it was changed
                        row_data["statement"] = original_statement
                        row_data["fact"] = original_statement
                    
                    rows.append(row_data)
            
            # Create DataFrame and save to Excel
            if rows:
                df = pd.DataFrame(rows)
                
                # Ensure required columns are first in the DataFrame
                required_columns = [
                    "date_uploaded", "source_name", "url", "document_name", 
                    "fact", "statement", "chunk", "chunk_id", "verification_status"
                ]
                
                # Reorder columns to put required columns first
                all_columns = list(df.columns)
                for col in reversed(required_columns):
                    if col in all_columns:
                        all_columns.remove(col)
                        all_columns.insert(0, col)
                
                df = df[all_columns]
                
                # Debug print to check statement in DataFrame
                if "statement" in df.columns:
                    for i, row in df.iterrows():
                        if i < 5:  # Only print first 5 rows to avoid flooding logs
                            print(f"DEBUG: DataFrame row {i} statement: {row.get('statement', '')[:40]}...")
                
                df.to_excel(self.excel_path, index=False)
                
                # After saving, reload the facts to ensure they're stored correctly
                self._reload_facts_from_excel()
        except Exception as e:
            print(f"Error saving facts to Excel: {e}")
    
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
        
    def store_fact(self, fact_data_or_statement, document_name=None, chunk_index=None, 
                   verification_status=None, verification_reasoning=None, timestamp=None, edited=None) -> None:
        """
        Store a fact with its metadata if it's not a duplicate.
        
        Args:
            fact_data_or_statement: Either a dictionary containing all fact information or the fact statement string
            document_name: Name of the document (required if first arg is a statement)
            chunk_index: Index of the chunk (required if first arg is a statement)
            verification_status: Status of verification (optional if first arg is a statement)
            verification_reasoning: Reasoning for verification (optional if first arg is a statement)
            timestamp: Timestamp of fact creation (optional)
            edited: Whether the fact has been edited (optional)
        """
        # Check if the first argument is a dictionary or a statement string
        if isinstance(fact_data_or_statement, dict):
            fact_data = fact_data_or_statement.copy()  # Make a copy to avoid modifying the original
            print(f"DEBUG: Storing fact with statement: {fact_data.get('statement', '')[:40]}...")
        else:
            # Create a fact dictionary from individual parameters
            fact_data = {
                "statement": fact_data_or_statement,
                "document_name": document_name,
                "chunk_index": chunk_index,
                "verification_status": verification_status or "pending",
                "verification_reasoning": verification_reasoning or ""
            }
            print(f"DEBUG: Created fact with statement: {fact_data.get('statement', '')[:40]}...")
            
            # Add optional parameters if provided
            if timestamp:
                fact_data["timestamp"] = timestamp
            if edited is not None:
                fact_data["edited"] = edited
            
        document_name = fact_data["document_name"]
        
        # Validate the verification status
        if "verification_status" in fact_data:
            status = fact_data["verification_status"]
            if status not in self.valid_statuses:
                print(f"Warning: Invalid verification status '{status}'. Setting to 'pending'.")
                fact_data["verification_status"] = "pending"
        else:
            # Default to pending if not provided
            fact_data["verification_status"] = "pending"
        
        # Check if this fact is a duplicate
        if self.is_duplicate_fact(fact_data):
            print(f"Duplicate fact detected, not storing: {fact_data.get('statement', '')}")
            return
        
        if document_name not in self.facts:
            self.facts[document_name] = []
            
        # Add timestamp if not present
        if "timestamp" not in fact_data:
            fact_data["timestamp"] = datetime.now().isoformat()
            
        # Ensure the statement is preserved
        original_statement = fact_data.get("statement", "")
        
        # Add the fact to the repository
        self.facts[document_name].append(fact_data)
        
        # Verify the statement wasn't changed
        stored_fact = self.facts[document_name][-1]
        if stored_fact.get("statement", "") != original_statement:
            print(f"WARNING: Statement changed during storage!")
            print(f"  Original: {original_statement[:40]}...")
            print(f"  Stored: {stored_fact.get('statement', '')[:40]}...")
            # Fix the statement if it was changed
            stored_fact["statement"] = original_statement
        
        # Save to Excel after each update
        self._save_to_excel()
    
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
                if fact["verification_status"] == "verified"
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
                    if fact["verification_status"] == "verified"
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
    
    def clear_facts(self, document_name: str) -> None:
        """
        Clear all facts for a document.
        
        Args:
            document_name: Name of the document
        """
        if document_name in self.facts:
            del self.facts[document_name]
            
            # Save to Excel after each update
            self._save_to_excel()
    
    def _reload_facts_from_excel(self) -> None:
        """Reload facts from Excel file to ensure they're stored correctly."""
        if os.path.exists(self.excel_path):
            try:
                # Create a backup of the current facts
                facts_backup = self.facts.copy()
                
                # Clear current facts
                self.facts = {}
                
                # Load facts from Excel
                df = pd.read_excel(self.excel_path)
                
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
                            metadata[metadata_key] = fact_data.pop(col, None)
                    
                    fact_data["metadata"] = metadata
                    
                    # Ensure statement field is set from fact field if needed
                    if "fact" in fact_data and ("statement" not in fact_data or pd.isna(fact_data["statement"])):
                        fact_data["statement"] = fact_data["fact"]
                    
                    # Debug print to check statement
                    print(f"DEBUG: Reloaded fact with statement: {fact_data.get('statement', '')[:40]}...")
                    
                    self.facts[document_name].append(fact_data)
                    
            except Exception as e:
                print(f"Error reloading facts from Excel: {e}")
                # Restore backup if loading fails
                self.facts = facts_backup


class RejectedFactRepository:
    """Repository for storing and managing rejected facts with Excel persistence."""
    
    def __init__(self, excel_path: str = "src/fact_extract/data/rejected_facts.xlsx"):
        self.rejected_facts: Dict[str, List[Dict[str, Any]]] = {}
        self.excel_path = excel_path
        # Valid status values
        self.valid_statuses = ["verified", "rejected", "pending"]
        
        # Create data directory if it doesn't exist
        os.makedirs(os.path.dirname(self.excel_path), exist_ok=True)
        
        # Load existing rejected facts from Excel if file exists
        self._load_from_excel()
        
    def _load_from_excel(self) -> None:
        """Load rejected facts from Excel file if it exists."""
        if os.path.exists(self.excel_path):
            try:
                df = pd.read_excel(self.excel_path)
                
                # Convert DataFrame to dictionary structure
                for _, row in df.iterrows():
                    document_name = row["document_name"]
                    
                    if document_name not in self.rejected_facts:
                        self.rejected_facts[document_name] = []
                    
                    # Convert row to dictionary
                    fact_data = row.to_dict()
                    
                    # Handle metadata columns
                    metadata = {}
                    for col in df.columns:
                        if col.startswith("metadata_"):
                            metadata_key = col[len("metadata_"):]
                            metadata[metadata_key] = fact_data.pop(col, None)
                    
                    fact_data["metadata"] = metadata
                    self.rejected_facts[document_name].append(fact_data)
                    
            except Exception as e:
                print(f"Error loading rejected facts from Excel: {e}")
    
    def _save_to_excel(self) -> None:
        """Save all rejected facts to Excel file."""
        try:
            # Flatten the nested dictionary structure
            rows = []
            for document_name, facts_list in self.rejected_facts.items():
                for fact_data in facts_list:
                    # Create a copy of the fact data
                    row_data = fact_data.copy()
                    
                    # Extract metadata and flatten it with prefix
                    if "metadata" in row_data and isinstance(row_data["metadata"], dict):
                        metadata = row_data.pop("metadata", {})
                        for key, value in metadata.items():
                            row_data[f"metadata_{key}"] = value
                    
                    # Ensure all required columns are present
                    row_data["date_uploaded"] = row_data.get("timestamp", datetime.now().isoformat())
                    row_data["source_name"] = row_data.get("source_name", "")
                    row_data["url"] = row_data.get("source_url", "")
                    row_data["document_name"] = document_name
                    row_data["fact"] = row_data.get("statement", "")
                    row_data["chunk"] = row_data.get("original_text", "")
                    row_data["chunk_id"] = row_data.get("source_chunk", "")
                    row_data["rejection_reason"] = row_data.get("verification_reason", "")
                    
                    rows.append(row_data)
            
            # Create DataFrame and save to Excel
            if rows:
                df = pd.DataFrame(rows)
                
                # Ensure required columns are first in the DataFrame
                required_columns = [
                    "date_uploaded", "source_name", "url", "document_name", 
                    "fact", "chunk", "chunk_id", "verification_status", "rejection_reason"
                ]
                
                # Reorder columns to put required columns first
                all_columns = list(df.columns)
                for col in reversed(required_columns):
                    if col in all_columns:
                        all_columns.remove(col)
                        all_columns.insert(0, col)
                
                df = df[all_columns]
                df.to_excel(self.excel_path, index=False)
        except Exception as e:
            print(f"Error saving rejected facts to Excel: {e}")
    
    def _generate_fact_hash(self, fact_data: Dict[str, Any]) -> str:
        """
        Generate a hash for a fact to identify duplicates.
        
        Args:
            fact_data: Dictionary containing fact information
            
        Returns:
            str: Hash of the fact
        """
        # Use only the statement to create a unique hash
        statement = fact_data.get("statement", "")
        # Convert to string if it's not already
        if not isinstance(statement, str):
            statement = str(statement) if statement is not None else ""
        fact_text = statement.strip()
        
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
        document_name = fact_data["document_name"]
        
        # Validate the verification status
        if "verification_status" in fact_data:
            status = fact_data["verification_status"]
            if status not in self.valid_statuses:
                print(f"Warning: Invalid verification status '{status}'. Setting to 'rejected'.")
                fact_data["verification_status"] = "rejected"
        else:
            # Default to rejected if not provided
            fact_data["verification_status"] = "rejected"
            
        # Check if this fact is a duplicate
        if self.is_duplicate_fact(fact_data):
            print(f"Duplicate rejected fact detected, not storing: {fact_data.get('statement', '')}")
            return
        
        if document_name not in self.rejected_facts:
            self.rejected_facts[document_name] = []
            
        # Add timestamp if not present
        if "timestamp" not in fact_data:
            fact_data["timestamp"] = datetime.now().isoformat()
            
        self.rejected_facts[document_name].append(fact_data)
        
        # Save to Excel after each update
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
    
    def clear_rejected_facts(self, document_name: str) -> None:
        """
        Clear all rejected facts for a document.
        
        Args:
            document_name: Name of the document
        """
        if document_name in self.rejected_facts:
            del self.rejected_facts[document_name]
            
            # Save to Excel after each update
            self._save_to_excel() 
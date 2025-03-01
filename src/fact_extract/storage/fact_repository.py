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
                    
                    # Ensure all required columns are present
                    row_data["date_uploaded"] = row_data.get("timestamp", datetime.now().isoformat())
                    row_data["source_name"] = row_data.get("source_name", "")
                    row_data["url"] = row_data.get("source_url", "")
                    row_data["document_name"] = document_name
                    row_data["fact"] = row_data.get("statement", "")
                    row_data["chunk"] = row_data.get("original_text", "")
                    row_data["chunk_id"] = row_data.get("source_chunk", "")
                    
                    rows.append(row_data)
            
            # Create DataFrame and save to Excel
            if rows:
                df = pd.DataFrame(rows)
                
                # Ensure required columns are first in the DataFrame
                required_columns = [
                    "date_uploaded", "source_name", "url", "document_name", 
                    "fact", "chunk", "chunk_id", "verification_status"
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
        
    def store_fact(self, fact_data: Dict[str, Any]) -> None:
        """
        Store a fact with its metadata if it's not a duplicate.
        
        Args:
            fact_data: Dictionary containing fact information
        """
        document_name = fact_data["document_name"]
        
        # Check if this fact is a duplicate
        if self.is_duplicate_fact(fact_data):
            print(f"Duplicate fact detected, not storing: {fact_data.get('statement', '')}")
            return
        
        if document_name not in self.facts:
            self.facts[document_name] = []
            
        # Add timestamp if not present
        if "timestamp" not in fact_data:
            fact_data["timestamp"] = datetime.now().isoformat()
            
        self.facts[document_name].append(fact_data)
        
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
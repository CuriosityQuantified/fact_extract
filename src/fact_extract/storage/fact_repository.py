"""
Repository for storing and managing extracted facts.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime

class FactRepository:
    """In-memory repository for storing and managing facts."""
    
    def __init__(self):
        self.facts: Dict[str, List[Dict[str, Any]]] = {}
        
    def store_fact(self, fact_data: Dict[str, Any]) -> None:
        """
        Store a fact with its metadata.
        
        Args:
            fact_data: Dictionary containing fact information
        """
        document_name = fact_data["document_name"]
        
        if document_name not in self.facts:
            self.facts[document_name] = []
            
        # Add timestamp if not present
        if "timestamp" not in fact_data:
            fact_data["timestamp"] = datetime.now().isoformat()
            
        self.facts[document_name].append(fact_data)
    
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
"""
Configuration settings for the fact extraction system.
"""

import os
import logging
from typing import Dict, Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("fact_extract.log"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

# Default parallelism settings
DEFAULT_SETTINGS = {
    # Maximum number of chunks to process concurrently
    "max_concurrent_chunks": 5,
    
    # Rate limiting for API calls (requests per minute)
    "max_requests_per_minute": 60,
    
    # Chunk size settings (in characters)
    "chunk_size": 3000,
    "chunk_overlap": 200,
    
    # Error retry settings
    "max_retries": 3,
    "retry_delay": 5,  # seconds
    
    # Repository paths
    "chunks_excel_path": "src/data/all_chunks.xlsx",
    "facts_excel_path": "src/data/all_facts.xlsx",
    "rejected_facts_excel_path": "src/data/rejected_facts.xlsx"
}

def load_config() -> Dict[str, Any]:
    """
    Load configuration from environment variables, 
    falling back to defaults if not specified.
    
    Returns:
        Dict containing configuration settings
    """
    config = DEFAULT_SETTINGS.copy()
    
    # Override with environment variables if set
    try:
        if "MAX_CONCURRENT_CHUNKS" in os.environ:
            config["max_concurrent_chunks"] = int(os.environ["MAX_CONCURRENT_CHUNKS"])
            
        if "MAX_REQUESTS_PER_MINUTE" in os.environ:
            config["max_requests_per_minute"] = int(os.environ["MAX_REQUESTS_PER_MINUTE"])
            
        if "CHUNK_SIZE" in os.environ:
            config["chunk_size"] = int(os.environ["CHUNK_SIZE"])
            
        if "CHUNK_OVERLAP" in os.environ:
            config["chunk_overlap"] = int(os.environ["CHUNK_OVERLAP"])
            
        if "MAX_RETRIES" in os.environ:
            config["max_retries"] = int(os.environ["MAX_RETRIES"])
            
        if "RETRY_DELAY" in os.environ:
            config["retry_delay"] = float(os.environ["RETRY_DELAY"])
            
        if "CHUNKS_EXCEL_PATH" in os.environ:
            config["chunks_excel_path"] = os.environ["CHUNKS_EXCEL_PATH"]
            
        if "FACTS_EXCEL_PATH" in os.environ:
            config["facts_excel_path"] = os.environ["FACTS_EXCEL_PATH"]
            
        if "REJECTED_FACTS_EXCEL_PATH" in os.environ:
            config["rejected_facts_excel_path"] = os.environ["REJECTED_FACTS_EXCEL_PATH"]
    
    except (ValueError, TypeError) as e:
        logger.warning(f"Error parsing environment variables: {e}")
    
    # Validate settings
    if config["max_concurrent_chunks"] < 1:
        logger.warning(f"Invalid max_concurrent_chunks ({config['max_concurrent_chunks']}), setting to 1")
        config["max_concurrent_chunks"] = 1
    elif config["max_concurrent_chunks"] > 20:
        logger.warning(f"max_concurrent_chunks value ({config['max_concurrent_chunks']}) is very high. This might cause performance issues.")
    
    logger.info(f"Loaded configuration: max_concurrent_chunks={config['max_concurrent_chunks']}")
    
    return config

# Export the configuration
config = load_config() 
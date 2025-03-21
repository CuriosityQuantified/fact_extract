"""
Configuration utilities for the fact extraction system.
"""

import os
from dotenv import load_dotenv

def load_config():
    """Load configuration from environment variables."""
    load_dotenv()
    
    # Required configs
    required_vars = ["OPENAI_API_KEY"]
    missing = [var for var in required_vars if not os.getenv(var)]
    if missing:
        raise ValueError(f"Missing required environment variables: {', '.join(missing)}")
    
    return {
        "openai_api_key": os.getenv("OPENAI_API_KEY"),
        # Add other config variables as needed
    } 
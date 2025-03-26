"""
Launch the GUI for the fact extraction system.
"""

import sys
import logging
import os
import asyncio
from pathlib import Path

# Add the parent directory to the Python path
parent_dir = str(Path(__file__).parent.parent.absolute())
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# Setup logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# Import and explicitly initialize the LLM to ensure it's loaded into RAM 
print("Initializing LLM model (loading into RAM)...")
from src.llm_config import preload_model, default_llm
print("LLM initialization complete.")

from src.gui.app import create_app

def main():
    """Run the Fact Extraction GUI."""
    print("Starting Fact Extraction GUI...")
    app = create_app()
    app.launch(share=False)

if __name__ == "__main__":
    main() 
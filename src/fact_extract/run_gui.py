"""
Script to run the Fact Extraction GUI.
"""

import os
import asyncio
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables from .env file
dotenv_path = Path(__file__).parents[2] / '.env'
load_dotenv(dotenv_path)

from fact_extract.gui.app import create_app

def main():
    """Run the Fact Extraction GUI."""
    print("Starting Fact Extraction GUI...")
    app = create_app()
    app.launch(share=False)

if __name__ == "__main__":
    main() 
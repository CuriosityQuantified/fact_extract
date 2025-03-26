# Fact Extraction System

A robust document processing system that extracts factual statements from various document formats using vector search and LLM technologies.

## Overview

This system allows you to:
- Upload documents in various formats (PDF, DOCX, TXT)
- Extract factual statements from the text
- Validate facts using LLM technology
- Search for facts using semantic vector search with ChromaDB
- Export verified facts in various formats

## Quick Start

### Fork and Clone the Repository

1. **Fork the Repository**
   - Visit https://github.com/CuriosityQuantified/fact_extract
   - Click the "Fork" button in the upper-right corner
   - Follow the prompts to create a fork in your GitHub account

2. **Clone Your Fork**
   ```bash
   git clone https://github.com/YOUR-USERNAME/fact_extract.git
   cd fact_extract
   ```

### Set Up Local Environment

1. **Create a Virtual Environment**
   ```bash
   # Create virtual environment
   python -m venv venv

   # Activate virtual environment
   # On macOS/Linux:
   source venv/bin/activate
   # On Windows:
   # venv\Scripts\activate
   ```

2. **Install Dependencies**
   ```bash
   # If pip is missing from the virtual environment, install it
   curl https://bootstrap.pypa.io/get-pip.py -o get-pip.py
   venv/bin/python get-pip.py

   # Install dependencies
   venv/bin/python -m pip install -r requirements.txt
   ```

### Configure for Local Model (Ollama)

1. **Install Ollama**
   - Visit https://ollama.com/ and follow installation instructions for your OS
   - Or use the terminal (macOS/Linux):
     ```bash
     curl -fsSL https://ollama.com/install.sh | sh
     ```

2. **Pull a Compatible Model**
   ```bash
   # Pull a model like llama3 (8B or 70B based on your hardware)
   ollama pull llama3
   # For smaller hardware requirements:
   # ollama pull mistral
   # ollama pull phi
   ```

3. **Configure the Model in the Project**
   Create a `.env` file in the project root with:
   ```
   # Use local Ollama model instead of OpenAI
   USE_LOCAL_MODEL=true
   LOCAL_MODEL_NAME=llama3
   ```

### Run the Application

1. **Start the Application**
   ```bash
   # With virtual environment activated
   python -m src.fact_extract.gui.app
   ```

2. **Access the Web Interface**
   - Open your browser and go to: http://localhost:7860

## Usage Guide

### Document Processing

1. **Upload Documents**
   - Navigate to the "Document Processing" tab
   - Click "Upload Document" and select a file (PDF, DOCX, TXT)
   - Click "Process" to extract facts

2. **Review and Validate Facts**
   - Navigate to the "Fact Validation" tab
   - Review extracted facts and mark them as valid or invalid
   - Edit facts as needed

### Searching Facts

1. **Search for Facts**
   - Navigate to the "Fact Search" tab
   - Enter a search query in the text field
   - Click "Search" to find relevant facts

2. **Export Facts**
   - Navigate to the "Export" tab
   - Choose an export format (CSV, JSON, Markdown)
   - Click "Export" to save the verified facts

## Initializing Vector Search

If you need to populate the vector database with existing facts:

```bash
# With virtual environment activated
python -m src.fact_extract.scripts.populate_vector_store
```

## Troubleshooting

- **Missing facts in search results?** Run the populate_vector_store script to ensure all facts are indexed in ChromaDB.
- **Model errors?** Ensure your .env file is properly configured and the specified Ollama model is installed.
- **Dependencies issues?** Make sure you have activated the virtual environment before installing dependencies or running commands.


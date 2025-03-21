"""
Unit tests for the Fact Extraction GUI components.
"""

import os
import sys
import pytest
import tempfile
import gradio as gr
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock
from dotenv import load_dotenv


# Ensure the src directory is in the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Ensure the src directory is in the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))
# Load environment variables
load_dotenv()

# Add mock modules to sys.modules to prevent actual imports
from src.tests.mocks import mock_llm, mock_submission, mock_nodes

# Configure OpenAI API key
os.environ['OPENAI_API_KEY'] = os.getenv('OPENAI_API_KEY', '')

mock_modules = {
    'openai': Mock(),
    'langchain_openai': Mock(),
    'langchain_openai.chat_models': Mock(),
    'langchain_core.language_models.chat_models': Mock(),
    'fact_extract.tools.submission': mock_submission,
    'fact_extract.graph.nodes': mock_nodes
}

for mod_name, mock_mod in mock_modules.items():
    sys.modules[mod_name] = mock_mod

# Now import the modules that use these dependencies
from gui.app import FactExtractionGUI, format_file_types, format_size_limits
from utils.file_utils import ALLOWED_EXTENSIONS, MAX_FILE_SIZES
from models.state import ProcessingState

@pytest.fixture
def gui():
    """Create a GUI instance for testing."""
    return FactExtractionGUI()

@pytest.fixture
def mock_file():
    """Create a mock file for testing."""
    class MockFile:
        def __init__(self, name, content=b"test content"):
            self.name = name
            self._content = content
            
        def save(self, path):
            Path(path).write_bytes(self._content)
    return MockFile

def test_format_file_types():
    """Test file type formatting."""
    result = format_file_types()
    assert isinstance(result, str)
    for ext in ALLOWED_EXTENSIONS:
        assert ext in result

def test_format_size_limits():
    """Test size limit formatting."""
    result = format_size_limits()
    assert isinstance(result, str)
    for format_type in MAX_FILE_SIZES:
        assert str(MAX_FILE_SIZES[format_type]) in result
        assert format_type.upper() in result

def test_gui_initialization(gui):
    """Test GUI instance initialization."""
    assert isinstance(gui.state, ProcessingState)
    assert gui.processing is False
    assert isinstance(gui.theme, gr.themes.Soft)
    assert gui.temp_files == []

def test_build_interface(gui):
    """Test interface building."""
    interface = gui.build_interface()
    assert isinstance(interface, gr.Blocks)

@pytest.mark.asyncio
async def test_process_files_empty(gui):
    """Test processing with no files."""
    # process_files is an async generator, so we need to iterate over it
    results = []
    async for result in gui.process_files([]):
        results.append(result)
    
    # Check that we got at least one result
    assert len(results) > 0
    
    # Check the structure of the first result
    first_result = results[0]
    assert isinstance(first_result, tuple)
    assert len(first_result) >= 2
    assert isinstance(first_result[0], list)  # chat_history

@pytest.mark.asyncio
async def test_process_files_invalid(gui, mock_file):
    """Test processing invalid files."""
    # Create a temporary invalid file
    invalid_file = mock_file("test.invalid")
    
    # process_files is an async generator, so we need to iterate over it
    results = []
    async for result in gui.process_files([invalid_file]):
        results.append(result)
    
    # Check that we got at least one result
    assert len(results) > 0
    
    # Check the structure of the first result
    first_result = results[0]
    assert isinstance(first_result, tuple)
    assert len(first_result) >= 2
    assert isinstance(first_result[0], list)  # chat_history
    
    # Check that the chat history contains an error message
    # The actual message might be "⚠️ Invalid file detected" or similar
    chat_history = first_result[0]
    assert any("invalid" in str(msg).lower() for msg in chat_history)

@pytest.mark.asyncio
async def test_process_files_valid(gui, mock_file):
    """Test processing valid files."""
    # Create a mock valid file
    valid_file = mock_file("test.txt")
    
    # process_files is an async generator, so we need to iterate over it
    results = []
    async for result in gui.process_files([valid_file]):
        results.append(result)
    
    # Check that we got at least one result
    assert len(results) > 0
    
    # Check the structure of the first result
    first_result = results[0]
    assert isinstance(first_result, tuple)
    assert len(first_result) >= 2
    assert isinstance(first_result[0], list)  # chat_history
    
    # Check that the chat history contains a processing message
    chat_history = first_result[0]
    assert any("Starting to process" in str(msg) for msg in chat_history)

@pytest.mark.asyncio
async def test_process_files_error(gui, mock_file):
    """Test handling processing errors."""
    valid_file = mock_file("test.txt")

    # Skip the test that requires mocking process_document since it's not directly imported in app.py
    # Instead, we'll simulate an error by raising an exception in the file processing
    gui.processing = False  # Reset processing flag
    
    # Create a mock file that raises an exception when saved
    class ErrorFile:
        name = "error.txt"
        def save(self, path):
            raise Exception("Test error during file save")
    
    # process_files is an async generator, so we need to iterate over it
    results = []
    async for result in gui.process_files([ErrorFile()]):
        results.append(result)
    
    # Check that we got at least one result
    assert len(results) > 0
    
    # Check the structure of the last result
    last_result = results[-1]
    assert isinstance(last_result, tuple)
    assert len(last_result) >= 2
    assert isinstance(last_result[0], list)  # chat_history
    
    # Check that the chat history contains an error message
    chat_history = last_result[0]
    assert any("error" in str(msg).lower() for msg in chat_history)

@pytest.mark.asyncio
async def test_concurrent_processing_prevention(gui, mock_file):
    """Test prevention of concurrent processing."""
    valid_file = mock_file("test.txt")

    # Start first processing
    gui.processing = True
    
    # process_files is an async generator, so we need to iterate over it
    results = []
    async for result in gui.process_files([valid_file]):
        results.append(result)
    
    # Check that we got at least one result
    assert len(results) > 0
    
    # Check the structure of the first result
    first_result = results[0]
    assert isinstance(first_result, tuple)
    assert len(first_result) >= 2
    assert isinstance(first_result[0], list)  # chat_history
    
    # Check that the chat history contains a message about processing already in progress
    chat_history = first_result[0]
    assert any("Processing already in progress" in str(msg) for msg in chat_history)

@pytest.mark.asyncio
async def test_temp_file_cleanup(gui, mock_file):
    """Test temporary file cleanup."""
    valid_file = mock_file("test.txt")

    # process_files is an async generator, so we need to iterate over it
    results = []
    async for result in gui.process_files([valid_file]):
        results.append(result)
    
    # Check that the temp directory is empty after processing
    temp_dir = Path(tempfile.gettempdir()) / "fact_extract"
    if temp_dir.exists():
        assert len(list(temp_dir.glob("*"))) == 0

@pytest.mark.asyncio
async def test_multiple_file_processing(gui, mock_file):
    """Test processing multiple files."""
    files = [
        mock_file("test1.txt"),
        mock_file("test2.pdf"),
        mock_file("test3.docx")  # Use a valid extension
    ]

    # process_files is an async generator, so we need to iterate over it
    results = []
    async for result in gui.process_files(files):
        results.append(result)
    
    # Check that we got at least one result
    assert len(results) > 0
    
    # Check the structure of the first result
    first_result = results[0]
    assert isinstance(first_result, tuple)
    assert len(first_result) >= 2
    assert isinstance(first_result[0], list)  # chat_history
    
    # Check that the chat history contains processing messages for each file
    chat_history = results[-1][0]  # Get the chat history from the last result
    assert any("test1.txt" in str(msg) for msg in chat_history)
    assert any("test2.pdf" in str(msg) for msg in chat_history)
    assert any("test3.docx" in str(msg) for msg in chat_history)

def find_components(interface, component_type):
    """Find all components of a specific type in the interface."""
    components = []
    
    def search_components(block):
        if isinstance(block, component_type):
            components.append(block)
        if hasattr(block, 'children'):
            for child in block.children:
                search_components(child)
    
    search_components(interface)
    return components

def test_file_type_validation(gui, mock_file):
    """Test file type validation through the interface."""
    interface = gui.build_interface()
    
    # Find file input component
    file_inputs = find_components(interface, gr.File)
    assert len(file_inputs) > 0, "File input component not found"
    
    file_input = file_inputs[0]
    assert all(ext in file_input.file_types for ext in ALLOWED_EXTENSIONS)

def test_interface_components(gui):
    """Test presence and configuration of interface components."""
    interface = gui.build_interface()
    
    # Find components by type
    file_inputs = find_components(interface, gr.File)
    buttons = find_components(interface, gr.Button)
    chatbots = find_components(interface, gr.Chatbot)
    markdowns = find_components(interface, gr.Markdown)
    
    assert len(file_inputs) > 0, "File input component not found"
    assert len(buttons) > 0, "Process button not found"
    assert len(chatbots) > 0, "Chat display not found"
    assert len(markdowns) > 0, "Markdown components not found" 
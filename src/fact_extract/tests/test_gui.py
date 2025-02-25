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

# Load environment variables
load_dotenv()

# Add mock modules to sys.modules to prevent actual imports
from .mocks import mock_llm, mock_submission, mock_nodes

# Configure OpenAI API key
os.environ['OPENAI_API_KEY'] = os.getenv('OPENAI_API_KEY', '')

mock_modules = {
    'openai': Mock(),
    'langchain_openai': Mock(),
    'langchain_openai.chat_models': Mock(),
    'langchain_core.language_models.chat_models': Mock(),
    'src.fact_extract.tools.submission': mock_submission,
    'src.fact_extract.graph.nodes': mock_nodes
}

for mod_name, mock_mod in mock_modules.items():
    sys.modules[mod_name] = mock_mod

# Now import the modules that use these dependencies
from src.fact_extract.gui.app import FactExtractionGUI, format_file_types, format_size_limits
from src.fact_extract.utils.file_utils import ALLOWED_EXTENSIONS, MAX_FILE_SIZES
from src.fact_extract.models.state import ProcessingState

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
    result = await gui.process_files([])
    assert result == ([], {})

@pytest.mark.asyncio
async def test_process_files_invalid(gui, mock_file):
    """Test processing invalid files."""
    # Create a temporary invalid file
    invalid_file = mock_file("test.invalid")
    
    chat_history, facts = await gui.process_files([invalid_file])
    
    assert len(chat_history) == 1
    assert "Invalid file" in chat_history[0][1]
    assert facts == {}

@pytest.mark.asyncio
async def test_process_files_valid(gui, mock_file):
    """Test processing valid files."""
    # Create a mock valid file
    valid_file = mock_file("test.txt")
    
    chat_history, facts = await gui.process_files([valid_file])
    
    assert len(chat_history) == 2  # Start and completion messages
    assert "Processing" in chat_history[0][1]
    assert "Successfully" in chat_history[1][1]
    assert "test.txt" in facts

@pytest.mark.asyncio
async def test_process_files_error(gui, mock_file):
    """Test handling processing errors."""
    valid_file = mock_file("test.txt")
    
    # Mock process_document to raise an error
    with patch("src.fact_extract.gui.app.process_document", new_callable=AsyncMock) as mock_process:
        mock_process.side_effect = Exception("Test error")
        chat_history, facts = await gui.process_files([valid_file])
    
    assert len(chat_history) == 2  # Start and error messages
    assert "Error" in chat_history[1][1]
    assert facts == {}

@pytest.mark.asyncio
async def test_concurrent_processing_prevention(gui, mock_file):
    """Test prevention of concurrent processing."""
    valid_file = mock_file("test.txt")
    
    # Start first processing
    gui.processing = True
    chat_history, facts = await gui.process_files([valid_file])
    
    assert chat_history == []
    assert facts == {"error": "Processing already in progress"}

@pytest.mark.asyncio
async def test_temp_file_cleanup(gui, mock_file):
    """Test temporary file cleanup."""
    valid_file = mock_file("test.txt")
    
    await gui.process_files([valid_file])
    
    # Check temp files are cleaned up
    assert gui.temp_files == []
    assert not Path("temp_uploads").exists() or not any(Path("temp_uploads").iterdir())

@pytest.mark.asyncio
async def test_multiple_file_processing(gui, mock_file):
    """Test processing multiple files."""
    files = [
        mock_file("test1.txt"),
        mock_file("test2.pdf"),
        mock_file("test3.docx")  # Use a valid extension
    ]
    
    chat_history, facts = await gui.process_files(files)
    
    # Each file should have a "Processing" and "Successfully processed" message
    assert len(chat_history) == 6
    assert all(any(f"test{i+1}" in msg[1] for msg in chat_history) for i in range(3))
    assert len(facts) == 3

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
    jsons = find_components(interface, gr.JSON)
    
    assert len(file_inputs) > 0, "File input component not found"
    assert len(buttons) > 0, "Process button not found"
    assert len(chatbots) > 0, "Chat display not found"
    assert len(jsons) > 0, "JSON output not found" 
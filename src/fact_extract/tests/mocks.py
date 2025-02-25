"""
Mock objects for testing.
"""

from unittest.mock import Mock, AsyncMock

class MockLLM:
    """Mock LLM for testing."""
    async def invoke(self, *args, **kwargs):
        return "test response"

class MockSubmission:
    """Mock submission module for testing."""
    async def submit_fact(*args, **kwargs):
        return {"status": "success", "fact": "test fact"}

class MockNodes:
    """Mock nodes module for testing."""
    async def process_document(*args, **kwargs):
        return {"facts": ["test fact"]}

# Create mock instances
mock_llm = MockLLM()
mock_submission = MockSubmission()
mock_nodes = MockNodes() 
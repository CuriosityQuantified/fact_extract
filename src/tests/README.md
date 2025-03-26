# Tests Directory

This directory contains all test files for the fact extraction system. The test files were consolidated from multiple locations:

- Tests originally in `src/unit_tests/`
- Tests originally directly in the `src/` directory

## Running Tests

Tests can be run using pytest:

```bash
# Activate the virtual environment first
source venv/bin/activate

# Run all tests
python -m pytest

# Run specific test file
python -m pytest src/tests/test_name.py

# Run tests with verbose output
python -m pytest -v
```

## Test Configuration

The pytest configuration is defined in the `pyproject.toml` file at the root of the project:

```toml
[tool.pytest.ini_options]
testpaths = ["src/tests"]
python_files = "test_*.py"
python_functions = "test_*"
asyncio_mode = "strict"
asyncio_default_fixture_loop_scope = "function"
```

## Notes

- Some test files were merged to consolidate duplicate functionality
- The `unit_tests` directory has been removed to simplify the project structure
- All tests should be maintained in this single location going forward 
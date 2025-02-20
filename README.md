# Fact Extract

A Python-based fact extraction system using LangChain and LangGraph for extracting and storing facts from text and documents.

## Features

- Extract facts from various document types (text, PDF, etc.)
- Flexible storage options for extracted facts
- Configurable extraction pipelines using LangGraph
- Easy integration with various LLM providers
- Structured fact schema management

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/fact_extract.git
cd fact_extract
```

2. Create and activate a virtual environment:
```bash
python3.10 -m venv venv
source venv/bin/activate  # On Windows: .\venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements/requirements.txt
pip install -r requirements/requirements-dev.txt  # For development
```

4. Copy the example environment file and configure it:
```bash
cp .env.example .env
```

## Project Structure

```
fact_extract/
├── src/
│   └── fact_extract/
│       ├── extractors/    # Fact extraction implementations
│       ├── storage/       # Storage implementations
│       ├── schemas/       # Data models and schemas
│       ├── pipelines/     # LangGraph pipelines
│       └── utils/         # Helper functions
├── tests/                 # Test suite
├── docs/                  # Documentation
├── examples/              # Usage examples
└── requirements/          # Dependency files
```

## Usage

[Documentation to be added]

## Development

1. Install development dependencies:
```bash
pip install -r requirements/requirements-dev.txt
```

2. Install pre-commit hooks:
```bash
pre-commit install
```

3. Run tests:
```bash
pytest
```

## License

[License to be added] 
from setuptools import setup, find_packages

setup(
    name="fact_extract",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "langchain>=0.1.0",
        "langchain-core>=0.1.0",
        "langchain-community>=0.0.10",
        "langchain-openai>=0.0.3",
        "langchain-text-splitters>=0.0.1",
        "openai>=1.0.0",
        "pandas>=2.0.0",
        "openpyxl>=3.1.0",
        "pydantic>=2.0.0",
        "python-dotenv>=1.0.0",
        "typing-extensions>=4.5.0",
        "tiktoken>=0.5.2",
        "gradio>=4.12.0",
        "pypdf>=4.0.0",
        "python-docx>=0.8.11",
        "langgraph>=0.3.18"
    ],
    python_requires=">=3.8",
    author="Your Name",
    author_email="your.email@example.com",
    description="A simple fact extraction system using LLMs",
    keywords="nlp, fact-extraction, llm",
) 
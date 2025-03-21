"""
Central configuration module for LLM settings.
Configures Gemma 3 4B through Ollama using the ChatOpenAI wrapper.
"""

import os
import logging
import time
import subprocess
from langchain_openai import ChatOpenAI

logger = logging.getLogger(__name__)

# Ollama base URL - configurable via environment variable
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")

# Model configuration
MODEL_NAME = "gemma3:4b"
DEFAULT_TEMPERATURE = 0.1
DEFAULT_TIMEOUT = 300  # Increased timeout to 5 minutes
MAX_RETRIES = 3
RETRY_DELAY = 2  # Initial delay in seconds

# Dummy API key for ChatOpenAI when using Ollama
DUMMY_API_KEY = "dummy-key-for-ollama"

def preload_model(model_name=MODEL_NAME):
    """
    Preload the model into RAM by making a call to Ollama directly.
    This function should be called at application start to warm up the model.
    
    Args:
        model_name: Name of the model to preload
    """
    logger.info(f"Preloading model {model_name} into RAM...")
    
    try:
        # First ensure the model is pulled with optimized settings
        env_vars = {
            "OLLAMA_CPU_LAYERS": "0",  # Force CPU layers to 0 to keep everything in GPU if possible
            "OLLAMA_FLASH_ATTENTION": "1"  # Enable Flash Attention for better memory usage
        }
        
        # Set environment variables
        old_env = {}
        for key, value in env_vars.items():
            old_env[key] = os.environ.get(key)
            os.environ[key] = value
        
        # Run a small inference to ensure the model is loaded into RAM
        # Using subprocess for direct Ollama communication
        logger.info("Running warm-up inference to load model into RAM...")
        warm_up_cmd = [
            "curl", "-s", 
            OLLAMA_BASE_URL.replace("/v1", "") + "/api/generate",
            "-d", f'{{"model": "{model_name}", "prompt": "Hello", "stream": false, "options": {{"num_gpu": 99999, "num_thread": 8}}}}'
        ]
        
        subprocess.run(warm_up_cmd, check=True, capture_output=True)
        logger.info(f"Successfully preloaded model {model_name} into RAM")
        
        # Restore environment variables
        for key, value in old_env.items():
            if value is None:
                del os.environ[key]
            else:
                os.environ[key] = value
                
        return True
    except Exception as e:
        logger.error(f"Error preloading model {model_name}: {str(e)}")
        return False

def get_llm(temperature=DEFAULT_TEMPERATURE, timeout=DEFAULT_TIMEOUT):
    """
    Get a configured LLM instance using ChatOpenAI wrapper pointing to Ollama.
    
    Args:
        temperature: Temperature for response generation (0.0-1.0)
        timeout: Timeout in seconds
        
    Returns:
        ChatOpenAI: Configured LLM instance
    """
    for attempt in range(MAX_RETRIES):
        try:
            # Configure ChatOpenAI to use Ollama
            llm = ChatOpenAI(
                model=MODEL_NAME,
                temperature=temperature,
                openai_api_base=OLLAMA_BASE_URL,  # Point to Ollama API
                openai_api_key=DUMMY_API_KEY,     # Dummy API key for ChatOpenAI
                timeout=timeout,
                streaming=True,
                max_retries=3,                    # Built-in retries
                request_timeout=timeout,          # Explicit request timeout
            )
            
            # Test the connection to Ollama
            logger.info(f"Testing connection to Ollama with model: {MODEL_NAME}...")
            try:
                test_response = llm.invoke("Test")
                logger.info(f"Successfully connected to Ollama with model: {MODEL_NAME}")
            except Exception as e:
                logger.warning(f"Connection test failed: {str(e)}")
                
            logger.info(f"Initialized LLM with model: {MODEL_NAME}, temperature: {temperature}")
            return llm
            
        except Exception as e:
            delay = RETRY_DELAY * (2 ** attempt)  # Exponential backoff
            logger.error(f"Attempt {attempt+1}/{MAX_RETRIES} failed to initialize LLM: {str(e)}")
            logger.info(f"Retrying in {delay} seconds...")
            
            if attempt < MAX_RETRIES - 1:
                time.sleep(delay)
            else:
                logger.error(f"All {MAX_RETRIES} attempts to initialize LLM failed")
                raise

# Preload the model into RAM
preload_success = preload_model()
if not preload_success:
    logger.warning("Model preloading failed, continuing without preloading")

# Default singleton LLM instance with standard settings
default_llm = get_llm() 
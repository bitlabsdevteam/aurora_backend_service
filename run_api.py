#!/usr/bin/env python
"""
Runner script for starting the Aurora API Service.

This script starts the FastAPI service for Aurora LLM backend.
"""

import os
import sys
import uvicorn
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("api_runner")

def main():
    """
    Main entry point for starting the API service.
    """
    logger.info("Starting Aurora API Service")
    
    # Add src to the Python path if it's not already there
    current_path = os.path.dirname(os.path.abspath(__file__))
    src_path = os.path.join(current_path, "src")
    if src_path not in sys.path:
        sys.path.insert(0, src_path)
        logger.info(f"Added {src_path} to Python path")

    try:
        # Start the API service
        uvicorn.run(
            "aurora_backend_llm.api.api_service:app",
            host="0.0.0.0",
            port=3001,
            reload=False,
            workers=4,
            log_level="info"
        )
    except Exception as e:
        logger.error(f"Error starting API service: {str(e)}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main() 
import logging
import time
import uuid
import os
from contextlib import asynccontextmanager
from typing import Dict, Any, List, Optional
import asyncio  # Added for running sync code in executor
import argparse

import uvicorn
from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel # Added for request body validation

# Import the crew
from aurora_backend_llm.crew import AuroraBackendLlm

# Ensure logs directory exists
os.makedirs(os.path.join(os.path.dirname(__file__), "../../../logs"), exist_ok=True)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join(os.path.dirname(__file__), "../../../logs/api_service.log")),
    ],
)
logger = logging.getLogger("aurora_api_service")

# Define the request body models
class AnalyzeRequest(BaseModel):
    topic: str
    current_year: int | None = None # Make current_year optional or provide a default

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Add any startup code here
    logger.info("Aurora API Service is starting up")
    
    yield
    
    # Shutdown: Add any cleanup code here
    logger.info("Aurora API Service is shutting down")

# Initialize FastAPI app
app = FastAPI(
    title="Aurora API Service",
    description="API Service for Aurora LLM applications using CrewAI",
    version="1.0.0",
    lifespan=lifespan,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify the actual origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Middleware for request logging and timing
@app.middleware("http")
async def log_requests(request: Request, call_next):
    request_id = str(uuid.uuid4())
    logger.info(f"Request {request_id} started: {request.method} {request.url.path}")
    
    start_time = time.time()
    try:
        response = await call_next(request)
        process_time = time.time() - start_time
        logger.info(f"Request {request_id} completed: {response.status_code} ({process_time:.4f}s)")
        response.headers["X-Process-Time"] = f"{process_time:.4f}"
        response.headers["X-Request-ID"] = request_id
        return response
    except Exception as e:
        process_time = time.time() - start_time
        logger.error(f"Request {request_id} failed: {str(e)} ({process_time:.4f}s)")
        raise

# Root endpoint
@app.get("/")
async def root():
    """Root endpoint providing basic API information"""
    logger.info("Root endpoint called")
    return {
        "message": "Welcome to Aurora API Service",
        "version": "1.0.0",
        "documentation": "/docs"
    }

# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring"""
    logger.info("Health check endpoint called")
    return {
        "status": "healthy",
        "timestamp": time.time(),
        "service": "Aurora API Service"
    }

# Example CrewAI integration endpoint
@app.post("/api/v1/analyze")
async def analyze_data(request_data: AnalyzeRequest):
    """
    Analyze data using the AuroraBackendLlm CrewAI crew.

    Accepts a 'topic' and optional 'current_year' to kick off the crew.
    """
    request_id = str(uuid.uuid4()) # Generate request ID here for logging
    logger.info(f"Analyze data endpoint called (Request ID: {request_id}) with topic: {request_data.topic}")

    # Prepare inputs for the crew
    inputs = {
        'topic': request_data.topic
    }
    # Add current_year if provided, otherwise CrewAI might use a default if configured
    if request_data.current_year:
        inputs['current_year'] = str(request_data.current_year) # Ensure it's a string if needed by config

    # Define the synchronous function to run the crew
    def run_crew_sync(crew_inputs: Dict[str, Any], task_id: str):
        try:
            # Change directory to the crew's root to find config files
            original_cwd = os.getcwd()
            crew_root_dir = os.path.join(os.path.dirname(__file__), "..") # Assumes api_service.py is in src/aurora_backend_llm/api
            os.chdir(crew_root_dir)
            logger.info(f"Changed working directory to: {crew_root_dir} for crew execution")

            aurora_crew = AuroraBackendLlm()
            logger.info(f"Kicking off AuroraBackendLlm crew (Request ID: {task_id}) with inputs: {crew_inputs}")
            result = aurora_crew.crew().kickoff(inputs=crew_inputs)
            logger.info(f"AuroraBackendLlm crew finished successfully (Request ID: {task_id})")
            
            return result
        except Exception as e:
            logger.error(f"Error running AuroraBackendLlm crew (Request ID: {task_id}): {str(e)}", exc_info=True)
            # Reraise the exception so it can be caught by the main try/except block
            raise
        finally:
            # Change back to the original directory
            os.chdir(original_cwd)
            logger.info(f"Restored working directory to: {original_cwd}")

    try:
        # Run the synchronous crew kickoff in a thread pool executor
        loop = asyncio.get_event_loop()
        crew_result = await loop.run_in_executor(None, run_crew_sync, inputs, request_id)

        return {
            "request_id": request_id,
            "status": "processed",
            "results": crew_result # Return the direct result from the crew
        }
    except Exception as e:
        # Log the specific error from run_crew_sync if it occurred
        logger.error(f"Error processing analysis request (Request ID: {request_id}): {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error processing analysis request: {str(e)}")

if __name__ == "__main__":
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Aurora API Service")
    parser.add_argument("--host", default="0.0.0.0", help="Host to listen on")
    parser.add_argument("--port", type=int, default=3001, help="Port to listen on")
    parser.add_argument("--workers", type=int, default=4, help="Number of worker processes")
    parser.add_argument("--log-level", default="info", help="Logging level")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload")
    
    args = parser.parse_args()
    
    logger.info(f"Starting Aurora API Service on port {args.port} with {args.workers} workers")
    uvicorn.run(
        "aurora_backend_llm.api.api_service:app", 
        host=args.host, 
        port=args.port, 
        reload=args.reload, 
        workers=args.workers, 
        log_level=args.log_level
    ) 
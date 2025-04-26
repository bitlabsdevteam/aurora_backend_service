import logging
import time
import uuid
import os
from contextlib import asynccontextmanager
from typing import Dict, Any

import uvicorn
from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.middleware.cors import CORSMiddleware

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

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Add any startup code here (DB connections, etc.)
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
async def analyze_data(data: Dict[str, Any]):
    """
    Analyze data using CrewAI agents
    
    This endpoint accepts data for analysis and processes it using CrewAI agents.
    Replace the mock implementation with actual CrewAI integration.
    """
    logger.info(f"Analyze data endpoint called with data type: {type(data).__name__}")
    
    try:
        # Mock implementation - replace with actual CrewAI integration
        # Example:
        # from your_crewai_module import analyze_with_crew
        # result = analyze_with_crew(data)
        
        # Simulated processing time
        time.sleep(0.5)
        
        return {
            "request_id": str(uuid.uuid4()),
            "status": "processed",
            "results": {
                "summary": "This is a mock analysis result. Replace with actual CrewAI output.",
                "confidence": 0.92,
                "processed_at": time.time()
            }
        }
    except Exception as e:
        logger.error(f"Error analyzing data: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error processing analysis request")

# Task management endpoints
@app.get("/api/v1/tasks")
async def get_tasks():
    """Get list of running or completed tasks"""
    logger.info("Get tasks endpoint called")
    # Mock response - replace with actual implementation
    return {
        "tasks": [
            {"id": "task-123", "status": "completed", "type": "analysis"},
            {"id": "task-456", "status": "running", "type": "research"}
        ]
    }

@app.get("/api/v1/tasks/{task_id}")
async def get_task(task_id: str):
    """Get details of a specific task"""
    logger.info(f"Get task endpoint called for task_id: {task_id}")
    # Mock response - replace with actual implementation
    return {
        "id": task_id,
        "status": "completed",
        "type": "analysis",
        "started_at": time.time() - 3600,
        "completed_at": time.time() - 1800,
        "results": {
            "summary": "This is a mock result for a specific task."
        }
    }

if __name__ == "__main__":
    logger.info("Starting Aurora API Service on port 3001")
    uvicorn.run("aurora_backend_llm.api.api_service:app", host="0.0.0.0", port=3001, reload=False, workers=4, log_level="info") 
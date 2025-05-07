import logging
import time
import uuid
import os
from contextlib import asynccontextmanager
from typing import Dict, Any, List, Optional
import asyncio  # Added for running sync code in executor
import argparse
from datetime import datetime, timedelta

import uvicorn
from fastapi import FastAPI, Request, Response, HTTPException, Depends, Body, Query, Path
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.wsgi import WSGIMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List

# Import the crew
from aurora_backend_llm.crew import AuroraBackendLlm
# Import Flask app for authentication routes
from aurora_backend_llm.app import create_app as create_flask_app

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

# User Models
class UserBase(BaseModel):
    username: str = Field(..., min_length=3, max_length=80, examples=["johndoe"])
    email: EmailStr = Field(..., examples=["john@example.com"])
    first_name: Optional[str] = Field(None, max_length=50, examples=["John"])
    last_name: Optional[str] = Field(None, max_length=50, examples=["Doe"])
    is_active: bool = True
    is_admin: bool = False

class UserCreate(UserBase):
    password: str = Field(..., min_length=8, examples=["password123"])

class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    first_name: Optional[str] = Field(None, max_length=50)
    last_name: Optional[str] = Field(None, max_length=50)
    is_active: Optional[bool] = None
    is_admin: Optional[bool] = None
    password: Optional[str] = Field(None, min_length=8)

class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    is_active: bool
    is_admin: bool
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    last_login_at: Optional[str] = None

    class Config:
        from_attributes = True

class LoginRequest(BaseModel):
    username: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserResponse

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

# Create Flask app for authentication
flask_app = create_flask_app()

# Mount Flask app for authentication routes
app.mount("/api/auth/flask", WSGIMiddleware(flask_app))

# Include POS fetch routes
from aurora_backend_llm.api.pos_routes import router as pos_router
app.include_router(pos_router)

# Include SKUs fetch routes
from aurora_backend_llm.api.skus_routes import router as skus_router
app.include_router(skus_router)

# Include Main routes for Langflow API
from aurora_backend_llm.api.main_routes import router as main_router
app.include_router(main_router)

# OAuth2 setup
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

# Helper function to get flask app context
def get_flask_context():
    return flask_app.app_context()

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
        error_message = str(e)
        if len(error_message) > 500:
            error_message = error_message[:500] + "..."
        logger.error(f"Request {request_id} failed: {error_message} ({process_time:.4f}s)")
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
    # Check database connection
    try:
        with flask_app.app_context():
            from aurora_backend_llm.db import db
            db.session.execute("SELECT 1")
        db_status = "healthy"
    except Exception as e:
        db_status = f"unhealthy: {str(e)}"
    
    return {
        "status": "healthy",
        "database": db_status,
        "timestamp": time.time(),
        "service": "Aurora API Service"
    }

# User endpoints

@app.get("/api/users", response_model=List[UserResponse], tags=["Users"])
async def get_users(
    skip: int = Query(0, description="Number of users to skip"),
    limit: int = Query(100, description="Maximum number of users to return")
):
    """
    Get all users
    """
    with flask_app.app_context():
        from aurora_backend_llm.db.models import User
        users = User.query.offset(skip).limit(limit).all()
        
        # Convert datetimes to strings
        result = []
        for user in users:
            user_dict = {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "is_active": user.is_active,
                "is_admin": user.is_admin,
                "created_at": user.created_at.isoformat() if user.created_at else None,
                "updated_at": user.updated_at.isoformat() if user.updated_at else None,
                "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None
            }
            result.append(user_dict)
        
        return result

@app.get("/api/users/{user_id}", response_model=UserResponse, tags=["Users"])
async def get_user(
    user_id: int = Path(..., description="The ID of the user to get")
):
    """
    Get a specific user
    """
    with flask_app.app_context():
        from aurora_backend_llm.db.models import User
        user = User.query.get(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        user_dict = {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "is_active": user.is_active,
            "is_admin": user.is_admin,
            "created_at": user.created_at.isoformat() if user.created_at else None,
            "updated_at": user.updated_at.isoformat() if user.updated_at else None,
            "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None
        }
        
        return user_dict

@app.post("/api/users", response_model=UserResponse, tags=["Users"])
async def create_user(
    user: UserCreate
):
    """
    Create a new user
    """
    with flask_app.app_context():
        from aurora_backend_llm.db.models import User
        from aurora_backend_llm.db.database import db
        
        # Check if user already exists
        if User.get_by_username(user.username):
            raise HTTPException(status_code=400, detail="Username already exists")
        
        if User.get_by_email(user.email):
            raise HTTPException(status_code=400, detail="Email already exists")
        
        # Create new user
        new_user = User(
            username=user.username,
            email=user.email,
            first_name=user.first_name,
            last_name=user.last_name,
            is_active=user.is_active,
            is_admin=user.is_admin
        )
        new_user.password = user.password
        
        db.session.add(new_user)
        db.session.commit()
        
        # Load the data back from the database
        db.session.refresh(new_user)
        
        user_dict = {
            "id": new_user.id,
            "username": new_user.username,
            "email": new_user.email,
            "first_name": new_user.first_name,
            "last_name": new_user.last_name,
            "is_active": new_user.is_active,
            "is_admin": new_user.is_admin,
            "created_at": new_user.created_at.isoformat() if new_user.created_at else None,
            "updated_at": new_user.updated_at.isoformat() if new_user.updated_at else None,
            "last_login_at": new_user.last_login_at.isoformat() if new_user.last_login_at else None
        }
        
        return user_dict

@app.put("/api/users/{user_id}", response_model=UserResponse, tags=["Users"])
async def update_user(
    user: UserUpdate,
    user_id: int = Path(..., description="The ID of the user to update")
):
    """
    Update a user
    """
    with flask_app.app_context():
        from aurora_backend_llm.db.models import User
        from aurora_backend_llm.db.database import db
        
        db_user = User.query.get(user_id)
        if not db_user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Update user fields
        if user.email is not None:
            # Check if email exists and belongs to another user
            existing_user = User.get_by_email(user.email)
            if existing_user and existing_user.id != user_id:
                raise HTTPException(status_code=400, detail="Email already exists")
            db_user.email = user.email
        
        if user.first_name is not None:
            db_user.first_name = user.first_name
            
        if user.last_name is not None:
            db_user.last_name = user.last_name
            
        if user.password is not None:
            db_user.password = user.password
        
        if user.is_active is not None:
            db_user.is_active = user.is_active
                
        if user.is_admin is not None:
            db_user.is_admin = user.is_admin
        
        db_user.updated_at = datetime.utcnow()
        db.session.commit()
        db.session.refresh(db_user)
        
        user_dict = {
            "id": db_user.id,
            "username": db_user.username,
            "email": db_user.email,
            "first_name": db_user.first_name,
            "last_name": db_user.last_name,
            "is_active": db_user.is_active,
            "is_admin": db_user.is_admin,
            "created_at": db_user.created_at.isoformat() if db_user.created_at else None,
            "updated_at": db_user.updated_at.isoformat() if db_user.updated_at else None,
            "last_login_at": db_user.last_login_at.isoformat() if db_user.last_login_at else None
        }
        
        return user_dict

@app.delete("/api/users/{user_id}", tags=["Users"])
async def delete_user(
    user_id: int = Path(..., description="The ID of the user to delete")
):
    """
    Delete a user
    """
    with flask_app.app_context():
        from aurora_backend_llm.db.models import User
        from aurora_backend_llm.db.database import db
        
        user = User.query.get(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        username = user.username
        db.session.delete(user)
        db.session.commit()
        
        return {"message": f"User {username} deleted successfully"}

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
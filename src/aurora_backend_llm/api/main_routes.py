from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel
from typing import Dict, Any, Optional
import os
from dotenv import load_dotenv
import requests
import logging

# Configure logging
logger = logging.getLogger("aurora_main_routes")

# Create router
router = APIRouter(prefix="/api/main", tags=["Main"])

# Define request model
class LangflowRequest(BaseModel):
    input_value: str
    output_type: str = "chat"
    input_type: str = "chat"
    custom_fields: Optional[Dict[str, Any]] = None

# Define response model
class LangflowResponse(BaseModel):
    result: Any
    status: str

@router.post("/main_entry", response_model=LangflowResponse)
async def main_entry(request_data: LangflowRequest = Body(...)):
    """
    Make a call to Langflow API with the provided input.
    """
    # Load environment variables
    load_dotenv()
    
    # Get API token from environment variable
    api_token = os.getenv("LANGFLOW_API_TOKEN")
    if not api_token:
        raise HTTPException(status_code=500, detail="LANGFLOW_API_TOKEN environment variable not set")
    
    # The complete API endpoint URL for this flow
    url = "https://api.langflow.astra.datastax.com/lf/d41445b6-878c-4f7f-b90e-7c3d26e3036f/api/v1/run/435fcb42-3030-4f84-9006-aaf334d36902"
    
    # Prepare request payload
    payload = {
        "input_value": request_data.input_value,
        "output_type": request_data.output_type,
        "input_type": request_data.input_type
    }
    
    # Add any custom fields if provided
    if request_data.custom_fields:
        payload.update(request_data.custom_fields)
    
    # Request headers
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_token}"
    }
    
    try:
        # Send API request
        response = requests.request("POST", url, json=payload, headers=headers)
        response.raise_for_status()  # Raise exception for bad status codes
        
        # Return response
        return {
            "result": response.json(),
            "status": "success"
        }
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Error making API request to Langflow: {e}")
        raise HTTPException(status_code=500, detail=f"Error making API request to Langflow: {str(e)}")
    except ValueError as e:
        logger.error(f"Error parsing Langflow response: {e}")
        raise HTTPException(status_code=500, detail=f"Error parsing Langflow response: {str(e)}") 
from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel, Field, field_validator
from typing import List, Dict, Any, Optional, Union
import os
from dotenv import load_dotenv
from astrapy import DataAPIClient
import logging
from datetime import date

# Configure logging
logger = logging.getLogger("aurora_skus_routes")

# Create router
router = APIRouter(prefix="/api/skus", tags=["SKUs"])

# Define SKU data model
class SKUData(BaseModel):
    id: Optional[str] = Field(None, description="Unique identifier for the SKU record")
    sku_id: Optional[str] = Field(None, description="SKU identifier")
    name: Optional[str] = Field(None, description="Product name")
    description: Optional[str] = Field(None, description="Product description")
    category: Optional[str] = Field(None, description="Product category")
    price: Optional[Union[float, str]] = Field(None, description="Price per unit")
    cost: Optional[Union[float, str]] = Field(None, description="Cost per unit")
    stock_quantity: Optional[Union[int, str]] = Field(None, description="Available stock quantity")
    supplier_id: Optional[str] = Field(None, description="Supplier identifier")
    brand: Optional[str] = Field(None, description="Product brand")
    upc: Optional[str] = Field(None, description="Universal Product Code")
    created_at: Optional[str] = Field(None, description="Creation date")
    updated_at: Optional[str] = Field(None, description="Last update date")
    
    class Config:
        from_attributes = True
        populate_by_name = True
        # Allow extra fields from AstraDB
        extra = "allow"
        json_schema_extra = {"examples": [
            {
                "_id": "86a77d18-5d89-4bfd-a77d-185d890bfd3a",
                "sku_id": "SKU001",
                "name": "Premium T-Shirt",
                "description": "High quality cotton t-shirt",
                "category": "Apparel",
                "price": "29.99",
                "cost": "12.50",
                "stock_quantity": "150",
                "supplier_id": "SUP123",
                "brand": "Fashion Brand",
                "upc": "123456789012",
                "created_at": "2024-01-15",
                "updated_at": "2024-06-01"
            }
        ]}
        
    # Add model validators to convert string to numeric types if needed
    @field_validator('stock_quantity', mode='before')
    @classmethod
    def validate_quantity(cls, v):
        if isinstance(v, str) and v.isdigit():
            return int(v)
        return v
        
    @field_validator('price', 'cost', mode='before')
    @classmethod
    def validate_price(cls, v):
        if isinstance(v, str):
            try:
                return float(v)
            except ValueError:
                pass
        return v

@router.post("/fetch", response_model=List[SKUData])
async def fetch_skus_data(payload: Dict[str, Any] = Body(...)):
    """
    Fetch SKUs data from AstraDB Data API via POST.
    Request body should be:
    {
      "find": { ... },           # filter spec
      "options": {              # optional pagination
        "limit": <int>,
        "skip": <int>
      }
    }
    """
    # Load environment variables
    load_dotenv()
    token = os.getenv("ASTRA_DB_TOKEN")
    endpoint = "https://78448361-64f9-4771-a1a4-74e8f06c6259-us-east-2.apps.astra.datastax.com"
    if not token or not endpoint:
        raise HTTPException(status_code=500, detail="ASTRA_DB_TOKEN and ASTRA_DB_ENDPOINT must be set")

    try:
        # Initialize the AstraDB client and connect
        client = DataAPIClient(token)
        db = client.get_database_by_api_endpoint(endpoint)
        collection_name = os.getenv("ASTRA_SKU_COLLECTION", "sku_data")
        collection = db.get_collection(collection_name)

        # Build find filter and pagination options
        find_filter = payload.get("find", {}) or {}
        options = payload.get("options", {}) or {}
        limit = int(options.get("limit", 100))
        skip = int(options.get("skip", 0))

        # Execute query
        if skip > 0:
            cursor = collection.find(find_filter, limit=limit, skip=skip, sort={"_id": 1})
        else:
            cursor = collection.find(find_filter, limit=limit)

        # Convert cursor to list and transform data
        results = list(cursor)
        logger.info(f"Found {len(results)} SKU records")
        
        # Transform data to ensure _id is mapped to id for validation
        transformed_results = []
        for item in results:
            # Create a copy to avoid modifying the original
            new_item = dict(item)
            
            # Ensure id field exists
            if '_id' in new_item and 'id' not in new_item:
                new_item['id'] = new_item['_id']
                
            transformed_results.append(new_item)
        
        return transformed_results
    except Exception as e:
        logger.error(f"Error fetching SKUs data: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}") 
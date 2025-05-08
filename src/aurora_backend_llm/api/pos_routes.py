from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel, Field, field_validator
from typing import List, Dict, Any, Optional, Union
import os
from dotenv import load_dotenv
from astrapy import DataAPIClient
import logging
from datetime import date

# Configure logging
logger = logging.getLogger("aurora_pos_routes")

# Create router
router = APIRouter(prefix="/api/pos", tags=["POS"])

# Define POS sales data model
class POSSaleData(BaseModel):
    id: Optional[str] = Field(None, alias="_id", description="Unique identifier for the sale record")
    Transaction_ID: Optional[str] = Field(None, description="Transaction identifier")
    Date: Optional[str] = Field(None, description="Date of transaction")
    SKU_ID: Optional[str] = Field(None, description="Product SKU identifier")
    Store_ID: Optional[str] = Field(None, description="Store identifier")
    Store_Name: Optional[str] = Field(None, description="Name of the store")
    Teller_ID: Optional[str] = Field(None, description="Teller identifier who processed the sale")
    Teller_Name: Optional[str] = Field(None, description="Name of the teller")
    Original_Cost: Optional[Union[float, str]] = Field(None, description="Original cost per unit")
    Sold_Cost: Optional[Union[float, str]] = Field(None, description="Sold cost per unit")
    Quantity_Sold: Optional[Union[int, str]] = Field(None, description="Quantity of items sold")
    Payment_Method: Optional[str] = Field(None, description="Method of payment")
    
    class Config:
        from_attributes = True
        populate_by_name = True
        # Allow extra fields from AstraDB
        extra = "allow"
        json_schema_extra = {"examples": [
            {
                "_id": "20bcc578-c09e-43ea-bcc5-78c09ef3ea4e",
                "Transaction_ID": "120037",
                "Date": "2025-09-04",
                "SKU_ID": "M-JN-32-BLK-SLD-COT-25A",
                "Store_ID": "S001",
                "Store_Name": "Tokyo Main",
                "Teller_ID": "T104",
                "Teller_Name": "Kobayashi Ryo",
                "Original_Cost": "82.00",
                "Sold_Cost": "98.40",
                "Quantity_Sold": "2",
                "Payment_Method": "E-money"
            }
        ]}
        
    # Add model validators to convert string to numeric types if needed
    @field_validator('Quantity_Sold', mode='before')
    @classmethod
    def validate_quantity(cls, v):
        if isinstance(v, str) and v.isdigit():
            return int(v)
        return v
        
    @field_validator('Original_Cost', 'Sold_Cost', mode='before')
    @classmethod
    def validate_price(cls, v):
        if isinstance(v, str):
            try:
                return float(v)
            except ValueError:
                pass
        return v

@router.post("/sales/fetch", response_model=List[POSSaleData])
async def fetch_pos_sales_data(payload: Dict[str, Any] = Body(...)):
    """
    Fetch POS sales data from AstraDB Data API via POST.
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
        collection_name = os.getenv("ASTRA_POS_COLLECTION", "pos_sales_data")
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
        logger.info(f"Found {len(results)} POS sales records")
        
        # No need to transform _id field anymore as we're using it directly in the model
        return results
    except Exception as e:
        logger.error(f"Error fetching POS sales data: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.get("/sales/sku_sales_by_skuid/{sku_id}", response_model=List[POSSaleData])
async def get_sku_sales_by_skuid(sku_id: str):
    """
    Fetch POS sales data for a specific SKU_ID.
    
    Args:
        sku_id: The SKU identifier to filter sales data
        
    Returns:
        List of sales data records for the specified SKU
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
        collection_name = os.getenv("ASTRA_POS_COLLECTION", "pos_sales_data")
        collection = db.get_collection(collection_name)

        # Set filter to find records with the specified SKU_ID
        find_filter = {"SKU_ID": sku_id}
        
        # Execute query with a reasonable limit
        cursor = collection.find(find_filter, limit=100)

        # Convert cursor to list
        results = list(cursor)
        logger.info(f"Found {len(results)} sales records for SKU_ID: {sku_id}")
        
        return results
    except Exception as e:
        logger.error(f"Error fetching sales data for SKU_ID {sku_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}") 
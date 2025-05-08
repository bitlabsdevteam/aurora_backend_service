import strawberry
from typing import List, Optional
from strawberry.fastapi import GraphQLRouter
import os
from dotenv import load_dotenv
from astrapy import DataAPIClient
import logging

# Configure logging
logger = logging.getLogger("aurora_graphql")

# Define GraphQL SKU type with camelCase field names
@strawberry.type
class SKU:
    id: Optional[str] = strawberry.field(description="Unique identifier for the SKU record")
    sku: Optional[str] = strawberry.field(description="SKU identifier")
    productName: Optional[str] = strawberry.field(description="Product name")
    brand: Optional[str] = strawberry.field(description="Product brand")
    category: Optional[str] = strawberry.field(description="Product category")
    size: Optional[str] = strawberry.field(description="Product size")
    color: Optional[str] = strawberry.field(description="Product color")
    sex: Optional[str] = strawberry.field(description="Product gender")
    pattern: Optional[str] = strawberry.field(description="Product pattern")
    fabric: Optional[str] = strawberry.field(description="Product fabric")
    fit: Optional[str] = strawberry.field(description="Product fit type")
    season: Optional[str] = strawberry.field(description="Seasonal classification")
    price: Optional[float] = strawberry.field(description="Price per unit")
    stock: Optional[int] = strawberry.field(description="Available stock quantity")
    launchDate: Optional[str] = strawberry.field(description="Product launch date")
    ecoTag: Optional[str] = strawberry.field(description="Environmental classification")
    countryOrigin: Optional[str] = strawberry.field(description="Country of origin")
    upc: Optional[str] = strawberry.field(description="Universal Product Code")
    styleCollection: Optional[str] = strawberry.field(description="Style collection name")
    supplier: Optional[str] = strawberry.field(description="Supplier name")
    careInstructions: Optional[str] = strawberry.field(description="Product care instructions")
    imageUrl: Optional[str] = strawberry.field(description="Product image URL")

# Field name mapping from GraphQL camelCase to AstraDB formats
field_map = {
    "sku": "SKU",
    "productName": "Product_Name",
    "brand": "Brand",
    "category": "Category",
    "size": "Size",
    "color": "Color",
    "sex": "Sex",
    "pattern": "Pattern",
    "fabric": "Fabric",
    "fit": "Fit",
    "season": "Season",
    "price": "Price",
    "stock": "Stock",
    "launchDate": "Launch_Date",
    "ecoTag": "Eco_Tag",
    "countryOrigin": "Country_Origin",
    "upc": "UPC",
    "styleCollection": "Style_Collection",
    "supplier": "Supplier",
    "careInstructions": "Care_Instructions",
    "imageUrl": "Image_URL"
}

# Reverse mapping to convert AstraDB fields to GraphQL fields
reverse_field_map = {v: k for k, v in field_map.items()}

# Define GraphQL queries
@strawberry.type
class Query:
    @strawberry.field(description="Get a single SKU by SKU ID")
    async def sku(self, sku_id: str) -> Optional[SKU]:
        # Load environment variables
        load_dotenv()
        token = os.getenv("ASTRA_DB_TOKEN")
        endpoint = "https://78448361-64f9-4771-a1a4-74e8f06c6259-us-east-2.apps.astra.datastax.com"
        if not token or not endpoint:
            raise Exception("ASTRA_DB_TOKEN and ASTRA_DB_ENDPOINT must be set")

        try:
            # Initialize the AstraDB client and connect
            client = DataAPIClient(token)
            db = client.get_database_by_api_endpoint(endpoint)
            collection_name = os.getenv("ASTRA_SKU_COLLECTION", "sku_data")
            collection = db.get_collection(collection_name)

            # Query for the specific SKU
            result = collection.find_one({"SKU": sku_id})
            
            if not result:
                return None
                
            # Ensure id field is populated
            if '_id' in result and 'id' not in result:
                result['id'] = result['_id']
                
            # Convert numeric strings to proper types
            if 'Stock' in result and isinstance(result['Stock'], str) and result['Stock'].isdigit():
                result['Stock'] = int(result['Stock'])
                
            if 'Price' in result and isinstance(result['Price'], str):
                try:
                    result['Price'] = float(result['Price'])
                except ValueError:
                    pass
            
            # Convert AstraDB field names to GraphQL camelCase
            transformed_result = {}
            for key, value in result.items():
                if key == 'id' or key == '_id':
                    transformed_result['id'] = value
                elif key in reverse_field_map:
                    transformed_result[reverse_field_map[key]] = value
                else:
                    # Keep fields that don't have a mapping as is
                    transformed_result[key] = value
                    
            # Convert dict to SKU object
            return SKU(**transformed_result)
        except Exception as e:
            logger.error(f"Error fetching SKU data: {e}")
            raise Exception(f"Error fetching SKU: {str(e)}")

    @strawberry.field(description="Get all SKUs with optional limit")
    async def skus(self, limit: Optional[int] = 100) -> List[SKU]:
        # Load environment variables
        load_dotenv()
        token = os.getenv("ASTRA_DB_TOKEN")
        endpoint = "https://78448361-64f9-4771-a1a4-74e8f06c6259-us-east-2.apps.astra.datastax.com"
        if not token or not endpoint:
            raise Exception("ASTRA_DB_TOKEN and ASTRA_DB_ENDPOINT must be set")

        try:
            # Initialize the AstraDB client and connect
            client = DataAPIClient(token)
            db = client.get_database_by_api_endpoint(endpoint)
            collection_name = os.getenv("ASTRA_SKU_COLLECTION", "sku_data")
            collection = db.get_collection(collection_name)

            # Query for all SKUs with a limit
            cursor = collection.find({}, limit=limit)
            results = list(cursor)
            
            logger.info(f"Found {len(results)} SKU records")
            
            # Transform data
            sku_objects = []
            for item in results:
                # Ensure id field exists
                if '_id' in item and 'id' not in item:
                    item['id'] = item['_id']
                    
                # Convert numeric strings to proper types
                if 'Stock' in item and isinstance(item['Stock'], str) and item['Stock'].isdigit():
                    item['Stock'] = int(item['Stock'])
                    
                if 'Price' in item and isinstance(item['Price'], str):
                    try:
                        item['Price'] = float(item['Price'])
                    except ValueError:
                        pass
                
                # Convert AstraDB field names to GraphQL camelCase
                transformed_item = {}
                for key, value in item.items():
                    if key == 'id' or key == '_id':
                        transformed_item['id'] = value
                    elif key in reverse_field_map:
                        transformed_item[reverse_field_map[key]] = value
                    else:
                        # Keep fields that don't have a mapping as is
                        transformed_item[key] = value
                        
                # Create SKU object
                sku_objects.append(SKU(**transformed_item))
                
            return sku_objects
        except Exception as e:
            logger.error(f"Error fetching SKUs data: {e}")
            raise Exception(f"Error fetching SKUs: {str(e)}")

    @strawberry.field(description="Search SKUs by any field")
    async def search_skus(self, field: str, value: str, limit: Optional[int] = 100) -> List[SKU]:
        # Load environment variables
        load_dotenv()
        token = os.getenv("ASTRA_DB_TOKEN")
        endpoint = "https://78448361-64f9-4771-a1a4-74e8f06c6259-us-east-2.apps.astra.datastax.com"
        if not token or not endpoint:
            raise Exception("ASTRA_DB_TOKEN and ASTRA_DB_ENDPOINT must be set")

        try:
            # Initialize the AstraDB client and connect
            client = DataAPIClient(token)
            db = client.get_database_by_api_endpoint(endpoint)
            collection_name = os.getenv("ASTRA_SKU_COLLECTION", "sku_data")
            collection = db.get_collection(collection_name)

            # Map GraphQL field to AstraDB field if needed
            astra_field = field_map.get(field, field)
            
            # Query for SKUs matching the field and value
            cursor = collection.find({astra_field: value}, limit=limit)
            results = list(cursor)
            
            logger.info(f"Found {len(results)} SKU records matching {astra_field}={value}")
            
            # Transform data
            sku_objects = []
            for item in results:
                # Ensure id field exists
                if '_id' in item and 'id' not in item:
                    item['id'] = item['_id']
                    
                # Convert numeric strings to proper types
                if 'Stock' in item and isinstance(item['Stock'], str) and item['Stock'].isdigit():
                    item['Stock'] = int(item['Stock'])
                    
                if 'Price' in item and isinstance(item['Price'], str):
                    try:
                        item['Price'] = float(item['Price'])
                    except ValueError:
                        pass
                
                # Convert AstraDB field names to GraphQL camelCase
                transformed_item = {}
                for key, value in item.items():
                    if key == 'id' or key == '_id':
                        transformed_item['id'] = value
                    elif key in reverse_field_map:
                        transformed_item[reverse_field_map[key]] = value
                    else:
                        # Keep fields that don't have a mapping as is
                        transformed_item[key] = value
                        
                # Create SKU object
                sku_objects.append(SKU(**transformed_item))
                
            return sku_objects
        except Exception as e:
            logger.error(f"Error searching SKUs data: {e}")
            raise Exception(f"Error searching SKUs: {str(e)}")

# Create the GraphQL schema
schema = strawberry.Schema(query=Query)

# Create the GraphQL router
graphql_router = GraphQLRouter(schema) 
"""
Trend Forecasting Lambda Function

This Lambda function processes images from an S3 bucket when new images arrive,
analyzing them for fashion trends (colors, patterns, fabrics, silhouettes)
and generating trend forecasts with confidence scores.

Author: Manus AI
Date: May 17, 2025
"""

import json
import os
import boto3
import logging
from datetime import datetime
import numpy as np
from io import BytesIO
from PIL import Image
import re
import uuid
import colorsys

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize AWS clients
s3 = boto3.client('s3')
dynamodb = boto3.resource('dynamodb')

# Configuration - REPLACE WITH YOUR ACTUAL VALUES
S3_BUCKET_IMAGES = 'fashion-trend-images'
S3_BUCKET_METADATA = 'fashion-trend-metadata'
S3_BUCKET_RESULTS = 'fashion-trend-results'
DYNAMODB_TABLE = 'fashion-trends'
AWS_REGION = 'ap-northeast-1'  # Tokyo region

# Define trend categories
TREND_CATEGORIES = {
    'colors': [
        'red', 'orange', 'yellow', 'green', 'blue', 'purple', 'pink', 
        'brown', 'black', 'white', 'gray', 'beige', 'navy', 'teal', 
        'lavender', 'mint', 'coral', 'burgundy', 'olive', 'mustard'
    ],
    'patterns': [
        'solid', 'striped', 'plaid', 'checkered', 'floral', 'polka_dot', 
        'geometric', 'animal_print', 'camouflage', 'tie_dye', 'paisley', 
        'herringbone', 'houndstooth', 'argyle', 'abstract', 'graphic'
    ],
    'fabrics': [
        'cotton', 'polyester', 'silk', 'wool', 'linen', 'denim', 'leather', 
        'suede', 'velvet', 'satin', 'chiffon', 'lace', 'tweed', 'fleece', 
        'jersey', 'corduroy', 'canvas', 'nylon', 'spandex', 'cashmere'
    ],
    'silhouettes': [
        'fitted', 'loose', 'oversized', 'slim', 'straight', 'a_line', 
        'bodycon', 'boxy', 'flared', 'pleated', 'peplum', 'empire', 
        'mermaid', 'pencil', 'balloon', 'bell_shaped', 'wrap', 'shift', 
        'trapeze', 'asymmetric'
    ]
}

def lambda_handler(event, context):
    """
    Main Lambda handler function.
    
    Args:
        event (dict): Lambda event data
        context (object): Lambda context
        
    Returns:
        dict: Response with status and details
    """
    try:
        logger.info("Received event: " + json.dumps(event))
        
        # Process S3 event notifications
        if 'Records' in event:
            processed_items = []
            
            for record in event['Records']:
                # Check if this is an S3 event
                if 'eventSource' in record and record['eventSource'] == 'aws:s3':
                    bucket = record['s3']['bucket']['name']
                    key = record['s3']['object']['key']
                    
                    logger.info(f"Processing new object: s3://{bucket}/{key}")
                    
                    # Check if this is an image or metadata file
                    if bucket == S3_BUCKET_IMAGES and (key.endswith('.jpg') or key.endswith('.jpeg') or key.endswith('.png')):
                        # Process image directly
                        result = process_image(bucket, key)
                        processed_items.append(result)
                    
                    elif bucket == S3_BUCKET_METADATA and key.endswith('_metadata.json'):
                        # Process metadata file
                        result = process_metadata(bucket, key)
                        processed_items.append(result)
            
            # After processing all records, update trend aggregates
            update_trend_aggregates()
            
            return {
                'statusCode': 200,
                'body': json.dumps({
                    'message': 'Successfully processed S3 events',
                    'processed_items': len(processed_items)
                })
            }
        
        # Manual invocation with specific parameters
        elif 'bucket' in event and 'key' in event:
            bucket = event['bucket']
            key = event['key']
            
            logger.info(f"Processing specified object: s3://{bucket}/{key}")
            
            if bucket == S3_BUCKET_IMAGES and (key.endswith('.jpg') or key.endswith('.jpeg') or key.endswith('.png')):
                result = process_image(bucket, key)
            elif bucket == S3_BUCKET_METADATA and key.endswith('_metadata.json'):
                result = process_metadata(bucket, key)
            else:
                return {
                    'statusCode': 400,
                    'body': json.dumps({
                        'error': 'Unsupported file type or bucket'
                    })
                }
            
            # Update trend aggregates
            update_trend_aggregates()
            
            return {
                'statusCode': 200,
                'body': json.dumps({
                    'message': 'Successfully processed specified object',
                    'result': result
                })
            }
        
        # Periodic trend analysis (e.g., triggered by EventBridge)
        elif event.get('detail-type') == 'Scheduled Event':
            # Update trend aggregates and generate reports
            update_trend_aggregates()
            generate_trend_report()
            
            return {
                'statusCode': 200,
                'body': json.dumps({
                    'message': 'Successfully generated trend report'
                })
            }
        
        else:
            return {
                'statusCode': 400,
                'body': json.dumps({
                    'error': 'Invalid event format'
                })
            }
    
    except Exception as e:
        logger.error(f"Error in lambda_handler: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e)
            })
        }

def process_image(bucket, key):
    """
    Process an image from S3 for trend analysis.
    
    Args:
        bucket (str): S3 bucket name
        key (str): S3 object key
        
    Returns:
        dict: Processing result
    """
    try:
        logger.info(f"Processing image: s3://{bucket}/{key}")
        
        # Get image from S3
        response = s3.get_object(Bucket=bucket, Key=key)
        image_data = response['Body'].read()
        
        # Open image with PIL
        image = Image.open(BytesIO(image_data))
        
        # Analyze image for fashion trends
        trends = analyze_image_for_trends(image)
        
        # Generate a unique ID for this analysis
        analysis_id = str(uuid.uuid4())
        timestamp = datetime.now().isoformat()
        
        # Create result object
        result = {
            'analysis_id': analysis_id,
            'image_bucket': bucket,
            'image_key': key,
            'timestamp': timestamp,
            'trends': trends
        }
        
        # Save result to S3
        result_key = f"image_analysis/{analysis_id}.json"
        s3.put_object(
            Bucket=S3_BUCKET_RESULTS,
            Key=result_key,
            Body=json.dumps(result, indent=2),
            ContentType='application/json'
        )
        
        # Store trend data in DynamoDB for aggregation
        store_trend_data(result)
        
        logger.info(f"Successfully processed image: {key}")
        return {
            'analysis_id': analysis_id,
            'result_key': result_key
        }
    
    except Exception as e:
        logger.error(f"Error processing image {key}: {str(e)}")
        return {
            'error': str(e),
            'image_key': key
        }

def process_metadata(bucket, key):
    """
    Process a metadata file from S3 for trend analysis.
    
    Args:
        bucket (str): S3 bucket name
        key (str): S3 object key
        
    Returns:
        dict: Processing result
    """
    try:
        logger.info(f"Processing metadata: s3://{bucket}/{key}")
        
        # Get metadata from S3
        response = s3.get_object(Bucket=bucket, Key=key)
        metadata = json.loads(response['Body'].read().decode('utf-8'))
        
        # Extract image features if available
        image_features = metadata.get('image_features', {})
        
        # Extract text content for analysis
        text_content = ''
        if 'caption' in metadata:
            text_content += metadata['caption'] + ' '
        elif 'text_content' in metadata:
            text_content += metadata['text_content'] + ' '
        
        if 'hashtags' in metadata and metadata['hashtags']:
            text_content += ' '.join(['#' + tag for tag in metadata['hashtags']])
        
        # Analyze text for fashion trends
        text_trends = analyze_text_for_trends(text_content)
        
        # Analyze image features for fashion trends
        image_trends = analyze_features_for_trends(image_features)
        
        # Combine text and image trends
        combined_trends = combine_trend_analyses(text_trends, image_trends)
        
        # Generate a unique ID for this analysis
        analysis_id = str(uuid.uuid4())
        timestamp = datetime.now().isoformat()
        
        # Create result object
        result = {
            'analysis_id': analysis_id,
            'metadata_bucket': bucket,
            'metadata_key': key,
            'timestamp': timestamp,
            'platform': metadata.get('platform', ''),
            'post_id': metadata.get('post_id', ''),
            'post_url': metadata.get('post_url', ''),
            'image_s3_key': metadata.get('image_s3_key', ''),
            'trends': combined_trends
        }
        
        # Save result to S3
        result_key = f"metadata_analysis/{analysis_id}.json"
        s3.put_object(
            Bucket=S3_BUCKET_RESULTS,
            Key=result_key,
            Body=json.dumps(result, indent=2),
            ContentType='application/json'
        )
        
        # Store trend data in DynamoDB for aggregation
        store_trend_data(result)
        
        logger.info(f"Successfully processed metadata: {key}")
        return {
            'analysis_id': analysis_id,
            'result_key': result_key
        }
    
    except Exception as e:
        logger.error(f"Error processing metadata {key}: {str(e)}")
        return {
            'error': str(e),
            'metadata_key': key
        }

def analyze_image_for_trends(image):
    """
    Analyze an image for fashion trends.
    
    Args:
        image (PIL.Image): Image object
        
    Returns:
        dict: Detected trends with confidence scores
    """
    # This is a simplified implementation
    # In a production environment, you would use more sophisticated computer vision models
    
    # Resize for consistent processing
    image = image.resize((300, 300))
    
    # Convert to RGB if not already
    if image.mode != 'RGB':
        image = image.convert('RGB')
    
    # Extract dominant colors
    colors = extract_dominant_colors(image)
    
    # Map dominant colors to color trends
    color_trends = map_colors_to_trends(colors)
    
    # For this simplified implementation, we'll use dummy values for other trend categories
    # In a real implementation, you would use computer vision models to detect patterns, fabrics, and silhouettes
    
    # Dummy pattern detection (in reality, this would use a trained model)
    pattern_trends = {
        'solid': 0.7,
        'striped': 0.2,
        'floral': 0.1
    }
    
    # Dummy fabric detection (in reality, this would use a trained model)
    fabric_trends = {
        'cotton': 0.6,
        'denim': 0.3,
        'polyester': 0.1
    }
    
    # Dummy silhouette detection (in reality, this would use a trained model)
    silhouette_trends = {
        'fitted': 0.4,
        'loose': 0.3,
        'oversized': 0.3
    }
    
    return {
        'colors': color_trends,
        'patterns': pattern_trends,
        'fabrics': fabric_trends,
        'silhouettes': silhouette_trends
    }

def extract_dominant_colors(image, num_colors=5):
    """
    Extract dominant colors from an image.
    
    Args:
        image (PIL.Image): Image object
        num_colors (int): Number of dominant colors to extract
        
    Returns:
        list: List of dominant colors with RGB values and percentages
    """
    # This is a simplified implementation
    # In a production environment, you would use k-means clustering or similar algorithms
    
    # Reduce colors for faster processing
    image = image.quantize(colors=64)
    image = image.convert('RGB')
    
    # Sample pixels
    pixels = list(image.getdata())
    pixel_count = len(pixels)
    
    # Count occurrences of each color
    color_counts = {}
    for pixel in pixels:
        # Simplify colors by rounding to nearest 10
        simplified = (round(pixel[0], -1), round(pixel[1], -1), round(pixel[2], -1))
        if simplified in color_counts:
            color_counts[simplified] += 1
        else:
            color_counts[simplified] = 1
    
    # Sort colors by frequency
    sorted_colors = sorted(color_counts.items(), key=lambda x: x[1], reverse=True)
    
    # Return top colors with their percentage
    dominant_colors = []
    for color, count in sorted_colors[:num_colors]:
        percentage = (count / pixel_count) * 100
        dominant_colors.append({
            'rgb': color,
            'hex': '#{:02x}{:02x}{:02x}'.format(int(color[0]), int(color[1]), int(color[2])),
            'percentage': round(percentage, 2)
        })
    
    return dominant_colors

def map_colors_to_trends(dominant_colors):
    """
    Map dominant colors to color trend categories.
    
    Args:
        dominant_colors (list): List of dominant colors
        
    Returns:
        dict: Color trends with confidence scores
    """
    color_trends = {}
    
    # Define color ranges (simplified)
    color_ranges = {
        'red': ((340, 360), (0, 10), (50, 100), (50, 100)),  # (hue range, saturation range, value range)
        'orange': ((10, 40), (50, 100), (50, 100)),
        'yellow': ((40, 70), (50, 100), (50, 100)),
        'green': ((70, 170), (30, 100), (30, 100)),
        'blue': ((170, 260), (30, 100), (30, 100)),
        'purple': ((260, 340), (30, 100), (30, 100)),
        'pink': ((300, 340), (30, 100), (70, 100)),
        'brown': ((0, 30), (30, 80), (20, 60)),
        'black': ((0, 360), (0, 100), (0, 15)),
        'white': ((0, 360), (0, 10), (90, 100)),
        'gray': ((0, 360), (0, 10), (20, 80)),
        'beige': ((20, 50), (10, 30), (70, 100)),
        'navy': ((210, 240), (50, 100), (10, 40)),
        'teal': ((170, 200), (50, 100), (30, 70)),
        'lavender': ((260, 290), (20, 40), (70, 100)),
        'mint': ((120, 160), (20, 40), (70, 100)),
        'coral': ((0, 20), (40, 70), (70, 100)),
        'burgundy': ((340, 360), (50, 100), (20, 40)),
        'olive': ((60, 90), (50, 100), (20, 50)),
        'mustard': ((40, 60), (70, 100), (50, 70))
    }
    
    for color in dominant_colors:
        rgb = color['rgb']
        percentage = color['percentage']
        
        # Convert RGB to HSV
        r, g, b = rgb[0] / 255.0, rgb[1] / 255.0, rgb[2] / 255.0
        h, s, v = colorsys.rgb_to_hsv(r, g, b)
        h = h * 360  # Convert to degrees
        s = s * 100  # Convert to percentage
        v = v * 100  # Convert to percentage
        
        # Match color to trend categories
        for trend_color, ranges in color_ranges.items():
            hue_range = ranges[0]
            sat_range = ranges[1]
            val_range = ranges[2]
            
            # Check if color is in range
            hue_match = False
            if hue_range[0] <= hue_range[1]:
                hue_match = hue_range[0] <= h <= hue_range[1]
            else:  # Handle wrap-around (e.g., red spans 340-360 and 0-10)
                hue_match = h >= hue_range[0] or h <= hue_range[1]
            
            sat_match = sat_range[0] <= s <= sat_range[1]
            val_match = val_range[0] <= v <= val_range[1]
            
            if hue_match and sat_match and val_match:
                # Calculate confidence based on percentage and match quality
                confidence = percentage / 100.0
                
                # Add to trends or update if higher confidence
                if trend_color in color_trends:
                    color_trends[trend_color] = max(color_trends[trend_color], confidence)
                else:
                    color_trends[trend_color] = confidence
    
    # Normalize confidence scores
    total = sum(color_trends.values())
    if total > 0:
        for color in color_trends:
            color_trends[color] = round(color_trends[color] / total, 2)
    
    return color_trends

def analyze_text_for_trends(text):
    """
    Analyze text content for fashion trends.
    
    Args:
        text (str): Text content to analyze
        
    Returns:
        dict: Detected trends with confidence scores
    """
    # This is a simplified implementation
    # In a production environment, you would use NLP models for more sophisticated analysis
    
    text = text.lower()
    
    # Initialize trend dictionaries
    color_trends = {}
    pattern_trends = {}
    fabric_trends = {}
    silhouette_trends = {}
    
    # Check for trend keywords in text
    for category, keywords in TREND_CATEGORIES.items():
        for keyword in keywords:
            # Create regex pattern to match whole word
            pattern = r'\b' + re.escape(keyword.replace('_', ' ')) + r'\b'
            matches = re.findall(pattern, text)
            
            if matches:
                # Calculate confidence based on frequency
                confidence = min(1.0, len(matches) * 0.2)
                
                # Add to appropriate trend category
                if category == 'colors':
                    color_trends[keyword] = confidence
                elif category == 'patterns':
                    pattern_trends[keyword] = confidence
                elif category == 'fabrics':
                    fabric_trends[keyword] = confidence
                elif category == 'silhouettes':
                    silhouette_trends[keyword] = confidence
    
    # Normalize confidence scores for each category
    for trends in [color_trends, pattern_trends, fabric_trends, silhouette_trends]:
        total = sum(trends.values())
        if total > 0:
            for trend in trends:
                trends[trend] = round(trends[trend] / total, 2)
    
    return {
        'colors': color_trends,
        'patterns': pattern_trends,
        'fabrics': fabric_trends,
        'silhouettes': silhouette_trends
    }

def analyze_features_for_trends(image_features):
    """
    Analyze image features for fashion trends.
    
    Args:
        image_features (dict): Image features from metadata
        
    Returns:
        dict: Detected trends with confidence scores
    """
    # Initialize trend dictionaries
    color_trends = {}
    pattern_trends = {}
    fabric_trends = {}
    silhouette_trends = {}
    
    # Extract color trends from dominant colors if available
    if 'dominant_colors' in image_features:
        dominant_colors = image_features['dominant_colors']
        color_trends = map_colors_to_trends(dominant_colors)
    
    # In a real implementation, you would extract pattern, fabric, and silhouette trends
    # from more sophisticated image features
    
    return {
        'colors': color_trends,
        'patterns': pattern_trends,
        'fabrics': fabric_trends,
        'silhouettes': silhouette_trends
    }

def combine_trend_analyses(text_trends, image_trends):
    """
    Combine text and image trend analyses.
    
    Args:
        text_trends (dict): Trends detected from text
        image_trends (dict): Trends detected from image
        
    Returns:
        dict: Combined trends with confidence scores
    """
    combined_trends = {}
    
    # Combine each trend category
    for category in ['colors', 'patterns', 'fabrics', 'silhouettes']:
        text_category = text_trends.get(category, {})
        image_category = image_trends.get(category, {})
        
        # Merge dictionaries, giving more weight to image trends for colors and patterns,
        # and more weight to text trends for fabrics and silhouettes
        combined_category = {}
        
        # Get all unique trend keys
        all_trends = set(list(text_category.keys()) + list(image_category.keys()))
        
        for trend in all_trends:
            text_confidence = text_category.get(trend, 0)
            image_confidence = image_category.get(trend, 0)
            
            # Weight factors (can be adjusted)
            if category in ['colors', 'patterns']:
                text_weight = 0.3
                image_weight = 0.7
            else:  # fabrics, silhouettes
                text_weight = 0.7
                image_weight = 0.3
            
            # Calculate weighted average
            combined_confidence = (text_confidence * text_weight) + (image_confidence * image_weight)
            
            if combined_confidence > 0:
                combined_category[trend] = round(combined_confidence, 2)
        
        combined_trends[category] = combined_category
    
    return combined_trends

def store_trend_data(result):
    """
    Store trend data in DynamoDB for aggregation.
    
    Args:
        result (dict): Analysis result
        
    Returns:
        None
    """
    try:
        # Get the DynamoDB table
        table = dynamodb.Table(DYNAMODB_TABLE)
        
        # Extract trends
        trends = result.get('trends', {})
        timestamp = result.get('timestamp', datetime.now().isoformat())
        
        # Store each trend as a separate item
        for category, category_trends in trends.items():
            for trend, confidence in category_trends.items():
                if confidence > 0:
                    item = {
                        'trend_id': f"{category}#{trend}",
                        'timestamp': timestamp,
                        'category': category,
                        'trend': trend,
                        'confidence': confidence,
                        'analysis_id': result.get('analysis_id', ''),
                        'platform': result.get('platform', ''),
                        'post_id': result.get('post_id', ''),
                        'image_key': result.get('image_key', '') or result.get('image_s3_key', '')
                    }
                    
                    # Add item to DynamoDB
                    table.put_item(Item=item)
        
        logger.info(f"Stored trend data for analysis {result.get('analysis_id', '')}")
    
    except Exception as e:
        logger.error(f"Error storing trend data: {str(e)}")

def update_trend_aggregates():
    """
    Update trend aggregates in DynamoDB.
    
    Returns:
        None
    """
    try:
        # Get the DynamoDB table
        table = dynamodb.Table(DYNAMODB_TABLE)
        
        # Get current timestamp
        now = datetime.now()
        
        # Define time windows for aggregation
        time_windows = {
            'daily': now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat(),
            'weekly': (now - datetime.timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0).isoformat(),
            'monthly': now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).isoformat()
        }
        
        # Aggregate trends for each category and time window
        for category in TREND_CATEGORIES.keys():
            for window_name, start_time in time_windows.items():
                # Query trends for this category and time window
                response = table.query(
                    KeyConditionExpression='trend_id = :tid AND timestamp >= :ts',
                    ExpressionAttributeValues={
                        ':tid': f"{category}#",
                        ':ts': start_time
                    }
                )
                
                # Aggregate trends
                trend_aggregates = {}
                for item in response.get('Items', []):
                    trend = item.get('trend', '')
                    confidence = item.get('confidence', 0)
                    
                    if trend in trend_aggregates:
                        trend_aggregates[trend]['count'] += 1
                        trend_aggregates[trend]['total_confidence'] += confidence
                    else:
                        trend_aggregates[trend] = {
                            'count': 1,
                            'total_confidence': confidence
                        }
                
                # Calculate average confidence and sort by count
                for trend, data in trend_aggregates.items():
                    data['avg_confidence'] = round(data['total_confidence'] / data['count'], 2)
                
                sorted_trends = sorted(trend_aggregates.items(), key=lambda x: x[1]['count'], reverse=True)
                
                # Store aggregate in S3
                aggregate_data = {
                    'category': category,
                    'time_window': window_name,
                    'start_time': start_time,
                    'end_time': now.isoformat(),
                    'trends': [{
                        'trend': trend,
                        'count': data['count'],
                        'avg_confidence': data['avg_confidence']
                    } for trend, data in sorted_trends]
                }
                
                # Save to S3
                s3.put_object(
                    Bucket=S3_BUCKET_RESULTS,
                    Key=f"aggregates/{category}_{window_name}_{now.strftime('%Y%m%d_%H%M%S')}.json",
                    Body=json.dumps(aggregate_data, indent=2),
                    ContentType='application/json'
                )
                
                logger.info(f"Updated {window_name} aggregates for {category}")
        
        logger.info("Successfully updated all trend aggregates")
    
    except Exception as e:
        logger.error(f"Error updating trend aggregates: {str(e)}")

def generate_trend_report():
    """
    Generate a comprehensive trend report.
    
    Returns:
        None
    """
    try:
        # Get current timestamp
        now = datetime.now()
        
        # Define time windows for reporting
        time_windows = {
            'daily': now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat(),
            'weekly': (now - datetime.timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0).isoformat(),
            'monthly': now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).isoformat()
        }
        
        # Initialize report data
        report_data = {
            'report_id': str(uuid.uuid4()),
            'timestamp': now.isoformat(),
            'time_windows': time_windows,
            'trends': {}
        }
        
        # Get latest aggregates for each category and time window
        for category in TREND_CATEGORIES.keys():
            report_data['trends'][category] = {}
            
            for window_name in time_windows.keys():
                # List objects in the aggregates folder
                response = s3.list_objects_v2(
                    Bucket=S3_BUCKET_RESULTS,
                    Prefix=f"aggregates/{category}_{window_name}_"
                )
                
                # Get the latest aggregate file
                if 'Contents' in response and response['Contents']:
                    latest_key = sorted(response['Contents'], key=lambda x: x['LastModified'], reverse=True)[0]['Key']
                    
                    # Get the aggregate data
                    aggregate_response = s3.get_object(Bucket=S3_BUCKET_RESULTS, Key=latest_key)
                    aggregate_data = json.loads(aggregate_response['Body'].read().decode('utf-8'))
                    
                    # Add to report
                    report_data['trends'][category][window_name] = aggregate_data.get('trends', [])
        
        # Generate trend forecasts
        report_data['forecasts'] = generate_trend_forecasts(report_data['trends'])
        
        # Save report to S3
        report_key = f"reports/trend_report_{now.strftime('%Y%m%d_%H%M%S')}.json"
        s3.put_object(
            Bucket=S3_BUCKET_RESULTS,
            Key=report_key,
            Body=json.dumps(report_data, indent=2),
            ContentType='application/json'
        )
        
        # Generate a more user-friendly HTML report
        html_report = generate_html_report(report_data)
        html_report_key = f"reports/trend_report_{now.strftime('%Y%m%d_%H%M%S')}.html"
        s3.put_object(
            Bucket=S3_BUCKET_RESULTS,
            Key=html_report_key,
            Body=html_report,
            ContentType='text/html'
        )
        
        logger.info(f"Successfully generated trend report: {report_key}")
    
    except Exception as e:
        logger.error(f"Error generating trend report: {str(e)}")

def generate_trend_forecasts(trend_data):
    """
    Generate trend forecasts based on historical data.
    
    Args:
        trend_data (dict): Historical trend data
        
    Returns:
        dict: Trend forecasts
    """
    # This is a simplified implementation
    # In a production environment, you would use more sophisticated forecasting models
    
    forecasts = {}
    
    for category, windows in trend_data.items():
        forecasts[category] = []
        
        # Use weekly data for forecasting
        weekly_trends = windows.get('weekly', [])
        
        for trend_item in weekly_trends[:10]:  # Top 10 trends
            trend = trend_item.get('trend', '')
            count = trend_item.get('count', 0)
            confidence = trend_item.get('avg_confidence', 0)
            
            # Simple forecasting logic (in reality, this would be much more sophisticated)
            # For demonstration, we'll use a combination of count and confidence
            trend_strength = count * confidence
            
            # Determine trend direction (simplified)
            if trend_strength > 10:
                direction = 'rising'
                forecast_confidence = 0.8
            elif trend_strength > 5:
                direction = 'stable'
                forecast_confidence = 0.6
            else:
                direction = 'declining'
                forecast_confidence = 0.4
            
            forecasts[category].append({
                'trend': trend,
                'current_count': count,
                'current_confidence': confidence,
                'forecast_direction': direction,
                'forecast_confidence': forecast_confidence,
                'forecast_description': f"This {category} trend is {direction} with {forecast_confidence:.0%} confidence."
            })
    
    return forecasts

def generate_html_report(report_data):
    """
    Generate an HTML report from the report data.
    
    Args:
        report_data (dict): Report data
        
    Returns:
        str: HTML report
    """
    # This is a simplified implementation
    # In a production environment, you would use a template engine
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Fashion Trend Report - {report_data['timestamp']}</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 20px; }}
            h1, h2, h3 {{ color: #333; }}
            .report-header {{ margin-bottom: 30px; }}
            .trend-section {{ margin-bottom: 40px; }}
            .trend-category {{ margin-bottom: 30px; }}
            table {{ border-collapse: collapse; width: 100%; margin-bottom: 20px; }}
            th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
            th {{ background-color: #f2f2f2; }}
            tr:nth-child(even) {{ background-color: #f9f9f9; }}
            .confidence {{ width: 100px; background-color: #eee; border-radius: 4px; }}
            .confidence-fill {{ background-color: #4CAF50; height: 20px; border-radius: 4px; }}
            .rising {{ color: green; }}
            .stable {{ color: blue; }}
            .declining {{ color: red; }}
        </style>
    </head>
    <body>
        <div class="report-header">
            <h1>Fashion Trend Report</h1>
            <p>Generated on: {report_data['timestamp']}</p>
            <p>Report ID: {report_data['report_id']}</p>
        </div>
        
        <div class="trend-section">
            <h2>Trend Forecasts</h2>
    """
    
    # Add forecasts for each category
    for category, trends in report_data['forecasts'].items():
        html += f"""
            <div class="trend-category">
                <h3>{category.capitalize()}</h3>
                <table>
                    <tr>
                        <th>Trend</th>
                        <th>Current Popularity</th>
                        <th>Confidence</th>
                        <th>Forecast</th>
                    </tr>
        """
        
        for trend in trends:
            direction_class = trend['forecast_direction']
            confidence_width = int(trend['forecast_confidence'] * 100)
            
            html += f"""
                    <tr>
                        <td>{trend['trend'].replace('_', ' ').capitalize()}</td>
                        <td>{trend['current_count']} mentions</td>
                        <td>
                            <div class="confidence">
                                <div class="confidence-fill" style="width: {confidence_width}%;"></div>
                            </div>
                            {trend['forecast_confidence']:.0%}
                        </td>
                        <td class="{direction_class}">{trend['forecast_direction'].capitalize()} ({trend['forecast_confidence']:.0%} confidence)</td>
                    </tr>
            """
        
        html += """
                </table>
            </div>
        """
    
    # Add current trends for each category and time window
    html += """
        <div class="trend-section">
            <h2>Current Trends</h2>
    """
    
    for category, windows in report_data['trends'].items():
        html += f"""
            <div class="trend-category">
                <h3>{category.capitalize()}</h3>
        """
        
        for window_name, trends in windows.items():
            html += f"""
                <h4>{window_name.capitalize()} Trends</h4>
                <table>
                    <tr>
                        <th>Trend</th>
                        <th>Count</th>
                        <th>Average Confidence</th>
                    </tr>
            """
            
            for trend in trends[:10]:  # Top 10 trends
                confidence_width = int(trend['avg_confidence'] * 100)
                
                html += f"""
                    <tr>
                        <td>{trend['trend'].replace('_', ' ').capitalize()}</td>
                        <td>{trend['count']} mentions</td>
                        <td>
                            <div class="confidence">
                                <div class="confidence-fill" style="width: {confidence_width}%;"></div>
                            </div>
                            {trend['avg_confidence']:.0%}
                        </td>
                    </tr>
                """
            
            html += """
                </table>
            """
        
        html += """
            </div>
        """
    
    html += """
        </div>
    </body>
    </html>
    """
    
    return html

# For local testing (not used in Lambda)
if __name__ == "__main__":
    # Test event
    test_event = {
        'Records': [
            {
                'eventSource': 'aws:s3',
                's3': {
                    'bucket': {
                        'name': 'fashion-trend-images'
                    },
                    'object': {
                        'key': 'test/sample_image.jpg'
                    }
                }
            }
        ]
    }
    
    # Call the handler
    result = lambda_handler(test_event, None)
    print(json.dumps(result, indent=2))

import os
import json
import boto3
import pandas as pd
import requests
import logging
from datetime import datetime
from urllib.parse import urlparse, quote
import base64
from botocore.exceptions import ClientError
from io import StringIO

# Initialize logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize AWS services
s3_client = boto3.client('s3')
ssm = boto3.client('ssm')

# Configuration - stored in SSM Parameter Store for security
def get_parameter(name):
    try:
        response = ssm.get_parameter(Name=name, WithDecryption=True)
        return response['Parameter']['Value']
    except Exception as e:
        logger.error(f"Error retrieving parameter {name}: {str(e)}")
        raise

# Target social media platforms and their endpoints
PLATFORMS = {
    'instagram': {
        'hashtag_url': 'https://api.instagram.com/v1/tags/{}/media/recent',
        'trending_url': 'https://api.instagram.com/v1/tags/search'
    },
    'twitter': {
        'hashtag_url': 'https://api.twitter.com/2/tweets/search/recent',
    },
    'pinterest': {
        'search_url': 'https://api.pinterest.com/v5/pins/search',
    }
}

# Apparel-related keywords to search for
SEARCH_KEYWORDS = [
    'fashion', 'outfit', 'style', 'clothes', 'apparel', 
    'dress', 'jacket', 'jeans', 'sneakers', 'shoes',
    'streetwear', 'luxury', 'vintage', 'sustainable fashion',
    'summer outfit', 'winter fashion', 'fall look'
]

def lambda_handler(event, context):
    """
    Main Lambda handler function that orchestrates the crawling process
    """
    try:
        # Get configuration from SSM Parameter Store
        bucket_name = get_parameter('/trend-forecasting/s3-bucket')
        openai_api_key = get_parameter('/trend-forecasting/openai-api-key')
        # Optional use of GROQ instead of OpenAI
        # groq_api_key = get_parameter('/trend-forecasting/groq-api-key')
        
        # Get social media API keys/tokens
        instagram_token = get_parameter('/trend-forecasting/instagram-token')
        twitter_bearer_token = get_parameter('/trend-forecasting/twitter-token')
        pinterest_token = get_parameter('/trend-forecasting/pinterest-token')
        
        # Create a timestamp for the crawl
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Create lists to store collected data
        all_posts = []
        image_urls = []
        
        # Crawl data from each platform
        logger.info("Starting social media crawl")
        
        # Instagram crawl
        instagram_data = crawl_instagram(instagram_token)
        all_posts.extend(instagram_data['posts'])
        image_urls.extend(instagram_data['images'])
        
        # Twitter crawl
        twitter_data = crawl_twitter(twitter_bearer_token)
        all_posts.extend(twitter_data['posts'])
        image_urls.extend(twitter_data['images'])
        
        # Pinterest crawl
        pinterest_data = crawl_pinterest(pinterest_token)
        all_posts.extend(pinterest_data['posts'])
        image_urls.extend(pinterest_data['images'])
        
        # Process the collected data using an LLM
        logger.info(f"Processing {len(all_posts)} posts with LLM")
        processed_data = process_with_llm(all_posts, openai_api_key)
        
        # Convert to DataFrame
        df = pd.DataFrame(processed_data)
        
        # Save data to S3
        save_to_s3(df, image_urls, bucket_name, timestamp)
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Crawl completed successfully',
                'posts_collected': len(all_posts),
                'images_collected': len(image_urls),
                'timestamp': timestamp
            })
        }
        
    except Exception as e:
        logger.error(f"Error in lambda_handler: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'message': f'Error occurred: {str(e)}'
            })
        }

def crawl_instagram(token):
    """
    Crawl Instagram for fashion-related posts
    """
    logger.info("Crawling Instagram")
    posts = []
    images = []
    
    try:
        for keyword in SEARCH_KEYWORDS:
            url = PLATFORMS['instagram']['hashtag_url'].format(keyword)
            headers = {
                'Authorization': f'Bearer {token}'
            }
            
            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                data = response.json()
                
                # Extract relevant information from each post
                for item in data.get('data', []):
                    post = {
                        'platform': 'instagram',
                        'post_id': item.get('id'),
                        'user_id': item.get('user', {}).get('id'),
                        'username': item.get('user', {}).get('username'),
                        'caption': item.get('caption', {}).get('text', ''),
                        'hashtags': extract_hashtags(item.get('caption', {}).get('text', '')),
                        'likes': item.get('likes', {}).get('count', 0),
                        'comments': item.get('comments', {}).get('count', 0),
                        'created_at': item.get('created_time'),
                        'url': item.get('link'),
                        'timestamp': datetime.now().isoformat()
                    }
                    posts.append(post)
                    
                    # Get image URLs
                    if 'images' in item:
                        image_url = item['images']['standard_resolution']['url']
                        images.append({
                            'url': image_url,
                            'post_id': item.get('id'),
                            'platform': 'instagram'
                        })
            else:
                logger.warning(f"Instagram API error: {response.status_code} - {response.text}")
                
    except Exception as e:
        logger.error(f"Error crawling Instagram: {str(e)}")
    
    return {'posts': posts, 'images': images}

def crawl_twitter(bearer_token):
    """
    Crawl Twitter for fashion-related posts
    """
    logger.info("Crawling Twitter")
    posts = []
    images = []
    
    try:
        headers = {
            'Authorization': f'Bearer {bearer_token}'
        }
        
        for keyword in SEARCH_KEYWORDS:
            params = {
                'query': f'{keyword} -is:retweet has:images',
                'tweet.fields': 'created_at,public_metrics,entities',
                'expansions': 'author_id,attachments.media_keys',
                'media.fields': 'url,preview_image_url',
                'max_results': 100
            }
            
            url = PLATFORMS['twitter']['hashtag_url']
            response = requests.get(url, headers=headers, params=params)
            
            if response.status_code == 200:
                data = response.json()
                
                # Create lookup dictionaries for users and media
                users = {user['id']: user for user in data.get('includes', {}).get('users', [])}
                media = {m['media_key']: m for m in data.get('includes', {}).get('media', [])}
                
                # Extract relevant information from each tweet
                for tweet in data.get('data', []):
                    # Get user information
                    user = users.get(tweet.get('author_id', ''), {})
                    
                    post = {
                        'platform': 'twitter',
                        'post_id': tweet.get('id'),
                        'user_id': tweet.get('author_id'),
                        'username': user.get('username', ''),
                        'text': tweet.get('text', ''),
                        'hashtags': [h['tag'] for h in tweet.get('entities', {}).get('hashtags', [])],
                        'likes': tweet.get('public_metrics', {}).get('like_count', 0),
                        'retweets': tweet.get('public_metrics', {}).get('retweet_count', 0),
                        'replies': tweet.get('public_metrics', {}).get('reply_count', 0),
                        'created_at': tweet.get('created_at'),
                        'url': f"https://twitter.com/i/web/status/{tweet.get('id')}",
                        'timestamp': datetime.now().isoformat()
                    }
                    posts.append(post)
                    
                    # Get image URLs
                    if 'attachments' in tweet and 'media_keys' in tweet['attachments']:
                        for media_key in tweet['attachments']['media_keys']:
                            if media_key in media:
                                media_item = media[media_key]
                                if 'url' in media_item or 'preview_image_url' in media_item:
                                    image_url = media_item.get('url', media_item.get('preview_image_url'))
                                    images.append({
                                        'url': image_url,
                                        'post_id': tweet.get('id'),
                                        'platform': 'twitter'
                                    })
            else:
                logger.warning(f"Twitter API error: {response.status_code} - {response.text}")
    
    except Exception as e:
        logger.error(f"Error crawling Twitter: {str(e)}")
    
    return {'posts': posts, 'images': images}

def crawl_pinterest(token):
    """
    Crawl Pinterest for fashion-related pins
    """
    logger.info("Crawling Pinterest")
    posts = []
    images = []
    
    try:
        headers = {
            'Authorization': f'Bearer {token}'
        }
        
        for keyword in SEARCH_KEYWORDS:
            params = {
                'query': keyword,
                'bookmark': '',
                'page_size': 50
            }
            
            url = PLATFORMS['pinterest']['search_url']
            response = requests.get(url, headers=headers, params=params)
            
            if response.status_code == 200:
                data = response.json()
                
                # Extract relevant information from each pin
                for item in data.get('items', []):
                    pin = item.get('pin', {})
                    
                    post = {
                        'platform': 'pinterest',
                        'post_id': pin.get('id'),
                        'user_id': pin.get('pinner', {}).get('id'),
                        'username': pin.get('pinner', {}).get('username', ''),
                        'description': pin.get('description', ''),
                        'hashtags': extract_hashtags(pin.get('description', '')),
                        'saves': pin.get('save_count', 0),
                        'created_at': pin.get('created_at', ''),
                        'url': f"https://www.pinterest.com/pin/{pin.get('id')}/",
                        'timestamp': datetime.now().isoformat()
                    }
                    posts.append(post)
                    
                    # Get image URL
                    if 'images' in pin and 'original' in pin['images']:
                        image_url = pin['images']['original']['url']
                        images.append({
                            'url': image_url,
                            'post_id': pin.get('id'),
                            'platform': 'pinterest'
                        })
            else:
                logger.warning(f"Pinterest API error: {response.status_code} - {response.text}")
    
    except Exception as e:
        logger.error(f"Error crawling Pinterest: {str(e)}")
    
    return {'posts': posts, 'images': images}

def extract_hashtags(text):
    """
    Extract hashtags from text
    """
    if not text:
        return []
        
    words = text.split()
    return [word[1:] for word in words if word.startswith('#')]

def process_with_llm(posts, api_key):
    """
    Process collected posts with an LLM to extract trend information
    """
    logger.info("Processing data with OpenAI")
    processed_data = []
    
    # Process in batches to avoid token limits
    batch_size = 10
    for i in range(0, len(posts), batch_size):
        batch = posts[i:i+batch_size]
        
        # Prepare the prompt for the LLM
        prompt = """
        Please analyze the following social media posts related to fashion and apparel. 
        For each post, extract:
        1. Primary apparel category (e.g., dress, jeans, coat, etc.)
        2. Style/trend name (e.g., Y2K, minimalist, vintage, etc.)
        3. Colors mentioned or implied
        4. Seasons relevant to the post (spring, summer, fall, winter)
        5. Sentiment score (0-100, where 100 is extremely positive)
        
        Posts data:
        """
        
        # Add the batch data to the prompt
        for post in batch:
            prompt += f"\n\nPlatform: {post.get('platform')}\n"
            prompt += f"Text: {post.get('text', post.get('caption', post.get('description', '')))}\n"
            prompt += f"Hashtags: {', '.join(post.get('hashtags', []))}\n"
            prompt += f"Engagement: Likes/Saves: {post.get('likes', post.get('saves', 0))}\n"
        
        # Call OpenAI API
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {api_key}'
        }
        
        payload = {
            'model': 'gpt-3.5-turbo',  # Using GPT-3.5 for cost efficiency
            'messages': [
                {'role': 'system', 'content': 'You are a fashion trend analyzer. Extract structured fashion trend data from social media posts.'},
                {'role': 'user', 'content': prompt}
            ],
            'temperature': 0.2,
            'max_tokens': 500
        }
        
        try:
            response = requests.post('https://api.openai.com/v1/chat/completions', headers=headers, json=payload)
            
            if response.status_code == 200:
                llm_response = response.json()
                result_text = llm_response['choices'][0]['message']['content']
                
                # Parse the response for each post
                # This is a simplified parsing approach - in production, you might want to use a more robust method
                sections = result_text.split('\n\n')
                for j, section in enumerate(sections):
                    if i+j < len(posts):
                        post = posts[i+j]
                        trend_data = {
                            'post_id': post.get('post_id'),
                            'platform': post.get('platform'),
                            'user_id': post.get('user_id'),
                            'username': post.get('username'),
                            'text': post.get('text', post.get('caption', post.get('description', ''))),
                            'hashtags': post.get('hashtags', []),
                            'likes': post.get('likes', post.get('saves', 0)),
                            'url': post.get('url'),
                            'created_at': post.get('created_at'),
                            'timestamp': post.get('timestamp')
                        }
                        
                        # Extract the LLM analysis
                        lines = section.strip().split('\n')
                        for line in lines:
                            if ':' in line:
                                key, value = line.split(':', 1)
                                key = key.strip().lower().replace(' ', '_')
                                trend_data[key] = value.strip()
                        
                        processed_data.append(trend_data)
            else:
                logger.warning(f"OpenAI API error: {response.status_code} - {response.text}")
                
        except Exception as e:
            logger.error(f"Error processing with LLM: {str(e)}")
    
    return processed_data

def download_image(url, post_id, platform):
    """
    Download an image from URL
    """
    try:
        response = requests.get(url, stream=True)
        if response.status_code == 200:
            # Extract file extension from URL
            parsed_url = urlparse(url)
            path = parsed_url.path
            ext = os.path.splitext(path)[1]
            if not ext:
                ext = '.jpg'  # Default to jpg if no extension
            
            return {
                'content': response.content,
                'extension': ext,
                'post_id': post_id,
                'platform': platform
            }
        else:
            logger.warning(f"Failed to download image: {url} - Status code: {response.status_code}")
            return None
    except Exception as e:
        logger.error(f"Error downloading image {url}: {str(e)}")
        return None

def save_to_s3(df, image_urls, bucket_name, timestamp):
    """
    Save data and images to S3
    """
    logger.info(f"Saving data to S3 bucket: {bucket_name}")
    
    try:
        # Save DataFrame to CSV
        csv_buffer = StringIO()
        df.to_csv(csv_buffer, index=False)
        
        # Upload CSV to S3
        s3_csv_key = f"trend_data/{timestamp}/trend_data.csv"
        s3_client.put_object(
            Body=csv_buffer.getvalue(),
            Bucket=bucket_name,
            Key=s3_csv_key
        )
        logger.info(f"Saved trend data CSV to s3://{bucket_name}/{s3_csv_key}")
        
        # Process images
        for i, img_info in enumerate(image_urls):
            # Download image
            image_data = download_image(img_info['url'], img_info['post_id'], img_info['platform'])
            
            if image_data:
                # Create a unique file name for the image
                file_name = f"{image_data['platform']}_{image_data['post_id']}{image_data['extension']}"
                s3_key = f"trend_data/{timestamp}/images/{file_name}"
                
                # Upload image to S3
                s3_client.put_object(
                    Body=image_data['content'],
                    Bucket=bucket_name,
                    Key=s3_key,
                    ContentType=f"image/{image_data['extension'][1:]}"  # Set the content type
                )
                
                # Add the S3 path to the DataFrame
                for index, row in df.iterrows():
                    if row['post_id'] == image_data['post_id'] and row['platform'] == image_data['platform']:
                        df.at[index, 'image_s3_path'] = f"s3://{bucket_name}/{s3_key}"
        
        # Save the updated DataFrame with image paths
        csv_buffer = StringIO()
        df.to_csv(csv_buffer, index=False)
        
        # Upload updated CSV to S3
        s3_client.put_object(
            Body=csv_buffer.getvalue(),
            Bucket=bucket_name,
            Key=s3_csv_key
        )
        
    except Exception as e:
        logger.error(f"Error saving data to S3: {str(e)}")
        raise

# Helper function for setting up the scheduled crawling
def set_up_scheduled_crawling():
    """
    Set up EventBridge rule to trigger Lambda on a schedule
    This function is not part of the Lambda execution but is provided as a guide
    """
    # Create EventBridge client
    event_client = boto3.client('events')
    
    # Define the rule
    rule_name = 'TrendForecastingCrawlSchedule'
    schedule_expression = 'rate(12 hours)'  # Run every 12 hours
    
    # Create the rule
    response = event_client.put_rule(
        Name=rule_name,
        ScheduleExpression=schedule_expression,
        State='ENABLED',
        Description='Schedule for running apparel trend forecasting crawl'
    )
    
    # Define target for the rule (the Lambda function)
    lambda_client = boto3.client('lambda')
    lambda_function_name = 'Apparel_Trend_Forecasting_Crawler'
    
    # Get Lambda function ARN
    lambda_response = lambda_client.get_function(
        FunctionName=lambda_function_name
    )
    lambda_arn = lambda_response['Configuration']['FunctionArn']
    
    # Add Lambda as target for the rule
    event_client.put_targets(
        Rule=rule_name,
        Targets=[
            {
                'Id': '1',
                'Arn': lambda_arn
            }
        ]
    )
    
    # Add permissions for EventBridge to invoke Lambda
    lambda_client.add_permission(
        FunctionName=lambda_function_name,
        StatementId=f'{rule_name}-Event',
        Action='lambda:InvokeFunction',
        Principal='events.amazonaws.com',
        SourceArn=response['RuleArn']
    )
    
    return {
        'RuleName': rule_name,
        'ScheduleExpression': schedule_expression,
        'LambdaFunction': lambda_function_name
    }

# For local testing - this will not be executed in Lambda
if __name__ == "__main__":
    test_event = {}
    test_context = {}
    print(lambda_handler(test_event, test_context))

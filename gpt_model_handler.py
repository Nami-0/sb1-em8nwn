import os
import openai
import logging
from datetime import datetime, timedelta
from functools import wraps
import time
from flask_login import current_user
from openai import OpenAI
import redis
import json

# Configure logging
logger = logging.getLogger(__name__)

def retry_with_backoff(func):
    """Decorator for exponential backoff retry logic"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        max_retries = 3
        retry_delay = 1  # initial delay in seconds

        for attempt in range(max_retries):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                if attempt == max_retries - 1:  # Last attempt
                    raise e

                wait_time = (2 ** attempt) * retry_delay
                logger.warning(f"Attempt {attempt + 1} failed. Waiting {wait_time} seconds...")
                time.sleep(wait_time)
        return None
    return wrapper

class GPTModelHandler:
    # Rate limiting settings
    MAX_CALLS_PER_MINUTE = 50
    call_history = []
    _redis_client = None

    # Model mapping based on subscription tiers
    MODEL_MAPPING = {
        'solo_backpacker': 'gpt-3.5-turbo',    # Free tier: GPT-3.5
        'tandem_trekker': 'gpt-3.5-turbo',     # $4.99 tier: GPT-3.5
        'gold_wanderer': 'gpt-4',              # $14.99 tier: GPT-4
        'business': 'gpt-4'                    # Business tier: GPT-4
    }

    # Token limits per model
    TOKEN_LIMITS = {
        'gpt-3.5-turbo': 16385,
        'gpt-4': 8192
    }

    # Cache configuration
    CACHE_EXPIRY = 3600  # 1 hour in seconds
    CACHE_PREFIX = 'gpt_model:'

    @classmethod
    def get_redis(cls):
        """Get or create Redis connection using Replit secrets"""
        if cls._redis_client is None:
            try:
                redis_url = os.environ.get('UPSTASH_REDIS_URL')
                redis_token = os.environ.get('UPSTASH_REDIS_TOKEN')

                if not redis_url or not redis_token:
                    logger.warning("Upstash Redis credentials not found")
                    return None

                cls._redis_client = redis.from_url(
                    redis_url,
                    username="default",
                    password=redis_token,
                    decode_responses=True,
                    socket_timeout=5,
                    retry_on_timeout=True
                )
                # Test connection
                cls._redis_client.ping()
                logger.info("Successfully connected to Upstash Redis")
            except Exception as e:
                logger.error(f"Failed to connect to Redis: {str(e)}")
                cls._redis_client = None

        return cls._redis_client

    @classmethod
    def get_cached_response(cls, prompt_hash):
        """Get cached response from Redis"""
        try:
            redis_client = cls.get_redis()
            if not redis_client:
                return None

            cache_key = f"{cls.CACHE_PREFIX}{prompt_hash}"
            cached_data = redis_client.get(cache_key)

            if cached_data:
                logger.info("Cache hit for prompt")
                return json.loads(cached_data)

        except Exception as e:
            logger.warning(f"Error getting cached response: {str(e)}")

        return None

    @classmethod
    def cache_response(cls, prompt_hash, response_data):
        """Cache response in Redis"""
        try:
            redis_client = cls.get_redis()
            if not redis_client:
                return

            cache_key = f"{cls.CACHE_PREFIX}{prompt_hash}"
            redis_client.setex(
                cache_key,
                cls.CACHE_EXPIRY,
                json.dumps(response_data)
            )
            logger.info("Successfully cached response")

        except Exception as e:
            logger.warning(f"Error caching response: {str(e)}")

    @classmethod
    def is_api_available(cls):
        """Check if OpenAI API is available and configured."""
        return bool(os.getenv('OPENAI_API_KEY'))

    @classmethod
    def get_model_for_user(cls):
        """Determine which GPT model to use based on user's subscription tier"""
        if not current_user.is_authenticated:
            return 'gpt-3.5-turbo'

        return cls.MODEL_MAPPING.get(
            current_user.subscription_tier, 
            'gpt-3.5-turbo'  # Default fallback
        )

    @classmethod
    def _rate_limit_check(cls):
        """Check if we've exceeded our rate limit"""
        now = datetime.now()
        cls.call_history = [t for t in cls.call_history if (now - t).seconds < 60]
        if len(cls.call_history) >= cls.MAX_CALLS_PER_MINUTE:
            return False
        cls.call_history.append(now)
        return True

    @classmethod
    def validate_api_key(cls):
        """Validate OpenAI API key format"""
        api_key = os.getenv('OPENAI_API_KEY')
        if not isinstance(api_key, str) or len(api_key) < 20:
            raise ValueError("Invalid API key format")
        return api_key

    @classmethod
    @retry_with_backoff
    def generate_itinerary(cls, system_prompt, user_prompt, temperature=0.7):
        """Generate itinerary using appropriate GPT model based on user's subscription"""
        try:
            if not cls._rate_limit_check():
                raise Exception("Rate limit exceeded. Please try again later.")

            # Generate a unique hash for the prompt combination
            prompt_hash = hash(f"{system_prompt}{user_prompt}{temperature}")

            # Check cache first
            cached_response = cls.get_cached_response(prompt_hash)
            if cached_response:
                logger.info("Using cached response")
                return cached_response

            model = cls.get_model_for_user()
            logger.info(f"Using model {model} for user {current_user.id} with subscription {current_user.subscription_tier}")

            api_key = cls.validate_api_key()
            client = OpenAI(api_key=api_key)

            # Log token usage for cost tracking
            system_tokens = len(system_prompt.split())
            user_tokens = len(user_prompt.split())
            estimated_tokens = system_tokens + user_tokens
            logger.info(f"Estimated input tokens: {estimated_tokens}")

            response = client.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "system",
                        "content": system_prompt
                    },
                    {
                        "role": "user",
                        "content": user_prompt
                    }
                ],
                temperature=temperature,
                max_tokens=cls.TOKEN_LIMITS[model] - estimated_tokens,
                top_p=0.95
            )

            # Get response content
            response_content = response.choices[0].message.content

            # Log completion for cost tracking
            completion_tokens = len(response_content.split())
            logger.info(f"Completion tokens: {completion_tokens}")
            logger.info(f"Total estimated tokens: {estimated_tokens + completion_tokens}")

            # Cache the response
            cls.cache_response(prompt_hash, response_content)

            return response_content

        except Exception as e:
            logger.error(f"Error generating itinerary: {str(e)}")
            error_message = f"""
            Error generating itinerary. Details: {str(e)}
            Model: {model}
            Subscription: {current_user.subscription_tier}
            """
            raise Exception(error_message)

    @classmethod
    def get_model_features(cls, subscription_tier):
        """Get features available for the subscription tier"""
        features = {
            'solo_backpacker': {
                'model': 'gpt-3.5-turbo',
                'max_tokens': 16385,
                'features': ['Basic itinerary generation', 'Standard recommendations']
            },
            'tandem_trekker': {
                'model': 'gpt-3.5-turbo',
                'max_tokens': 16385,
                'features': ['Detailed itinerary generation', 'Custom recommendations', 'Priority support']
            },
            'gold_wanderer': {
                'model': 'gpt-4',
                'max_tokens': 8192,
                'features': ['Advanced AI itinerary generation', 'Premium recommendations', 'Priority support', 'Custom features']
            },
            'business': {
                'model': 'gpt-4',
                'max_tokens': 8192,
                'features': ['Enterprise AI solutions', 'Custom development', 'Dedicated support', 'API access']
            }
        }
        return features.get(subscription_tier, features['solo_backpacker'])
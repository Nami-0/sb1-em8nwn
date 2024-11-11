import os
import redis
import logging
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

def get_redis_connection():
    """Get Redis connection using Upstash credentials."""
    try:
        # Get credentials from environment variables
        redis_host = os.getenv('PGHOST', 'verified-kid-26523.upstash.io')  # Your Upstash host
        redis_password = os.getenv('UPSTASH_REDIS_TOKEN')  # Your Upstash password

        if not redis_host or not redis_password:
            logger.warning("Redis credentials not found in environment variables")
            return None

        # Create Redis connection
        redis_client = redis.Redis(
            host=redis_host,
            port=6379,
            password=redis_password,
            ssl=True,
            socket_timeout=5,
            retry_on_timeout=True,
            socket_connect_timeout=5,
            socket_keepalive=True,
            charset="utf-8",
            decode_responses=False,  # Important: Set to False for session data
            health_check_interval=30,
            max_connections=10,
            encoding='utf-8'
        )

        # Test connection
        redis_client.ping()
        logger.info("Successfully connected to Redis")
        return redis_client

    except Exception as e:
        logger.error(f"Failed to connect to Redis: {str(e)}")
        return None

def parse_redis_url():
    """Parse Redis URL, handling both standard Redis URLs and Upstash HTTPS URLs."""
    try:
        redis_url = os.getenv('UPSTASH_REDIS_URL')
        if not redis_url:
            logger.warning("No Redis URL provided")
            return None

        # If it's already a redis:// or rediss:// URL, return as is
        if redis_url.startswith(('redis://', 'rediss://')):
            return redis_url

        # Handle Upstash URL format
        if redis_url.startswith('https://'):
            parsed = urlparse(redis_url)
            auth = f"{parsed.username}:{parsed.password}" if parsed.username and parsed.password else None
            host = parsed.hostname

            if not auth or not host:
                logger.warning("Invalid Upstash URL format")
                return None

            # Construct Redis URL (using rediss:// for SSL)
            redis_url = f"rediss://{auth}@{host}:6379"
            logger.info("Successfully parsed Upstash URL to Redis format")
            return redis_url

        logger.warning(f"Unrecognized Redis URL format")
        return None

    except Exception as e:
        logger.error(f"Error parsing Redis URL: {str(e)}")
        return None

def get_redis_url():
    """Get Redis URL in the correct format for Flask-SQLAlchemy."""
    try:
        redis_host = os.getenv('PGHOST', 'verified-kid-26523.upstash.io')
        redis_password = os.getenv('UPSTASH_REDIS_TOKEN')

        if not redis_host or not redis_password:
            return None

        # Construct Redis URL in the correct format
        redis_url = f"rediss://:{redis_password}@{redis_host}:6379"
        return redis_url

    except Exception as e:
        logger.error(f"Error constructing Redis URL: {str(e)}")
        return None

def init_redis_cache(app):
    """Initialize Redis cache for Flask application."""
    try:
        redis_url = get_redis_url()
        if redis_url:
            cache_config = {
                'CACHE_TYPE': 'redis',
                'CACHE_REDIS_URL': redis_url,
                'CACHE_DEFAULT_TIMEOUT': 300,
                'CACHE_OPTIONS': {
                    'ssl': True,
                    'socket_timeout': 5,
                    'retry_on_timeout': True,
                    'decode_responses': False,  # Important: Set to False for binary data
                    'charset': 'utf-8',
                    'encoding': 'utf-8',
                    'health_check_interval': 30,
                    'max_connections': 10
                }
            }
            app.config.update(cache_config)
            logger.info("Redis cache configured successfully")
            return True
        return False

    except Exception as e:
        logger.error(f"Failed to initialize Redis cache: {str(e)}")
        return False

def clear_redis_session():
    """Clear all Redis session data."""
    try:
        redis_client = get_redis_connection()
        if redis_client:
            # Clear session data
            session_keys = redis_client.keys('session:*')
            if session_keys:
                redis_client.delete(*session_keys)

            # Clear any other temporary keys
            temp_keys = redis_client.keys('temp:*')
            if temp_keys:
                redis_client.delete(*temp_keys)

            logger.info("Successfully cleared Redis session data")
            return True
        return False
    except Exception as e:
        logger.error(f"Failed to clear Redis sessions: {str(e)}")
        return False

def test_redis_connection():
    """Test Redis connection by setting and getting a value."""
    try:
        redis_client = get_redis_connection()
        if not redis_client:
            print("Failed to get Redis connection")
            return False

        # Test set and get operations
        test_key = "test_connection"
        test_value = "working"
        redis_client.set(test_key, test_value)
        retrieved_value = redis_client.get(test_key)

        if isinstance(retrieved_value, bytes):
            retrieved_value = retrieved_value.decode('utf-8')

        if retrieved_value == test_value:
            print("Redis connection test successful!")
            # Clean up test key
            redis_client.delete(test_key)
            return True
        else:
            print("Redis test failed: Value mismatch")
            return False

    except Exception as e:
        print(f"Redis test failed with error: {str(e)}")
        return False

if __name__ == "__main__":
    # Set up logging
    logging.basicConfig(level=logging.INFO)

    # Test the connection
    test_redis_connection()
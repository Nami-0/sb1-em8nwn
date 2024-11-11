import redis
import os
from datetime import timedelta
import logging
import urllib.parse

logger = logging.getLogger(__name__)

# Cache timeouts
CACHE_TIMEOUTS = {
    'openai_response': timedelta(hours=24),  # Cache OpenAI responses for 24 hours
    'user_data': timedelta(minutes=30),      # Cache user data for 30 minutes
    'landmarks': timedelta(hours=12),        # Cache landmarks for 12 hours
}

# Cache key patterns
CACHE_KEYS = {
    'openai_response': 'openai:response:{}',  # Format with request hash
    'user_data': 'user:{}',                   # Format with user_id
    'landmarks': 'landmarks:{}',              # Format with destination
}

def parse_redis_url(url):
    """Parse Redis URL, handling both standard Redis URLs and Upstash HTTPS URLs."""
    try:
        if not url:
            logger.warning("No Redis URL provided, using default localhost")
            return "redis://localhost:6380"

        if url.startswith('https://'):
            # Parse Upstash URL format
            parsed = urllib.parse.urlparse(url)

            # Extract auth and host
            if '@' in parsed.netloc:
                auth = parsed.netloc.split('@')[0]
                host = parsed.netloc.split('@')[1]
            else:
                auth = parsed.username + ':' + parsed.password if parsed.username and parsed.password else None
                host = parsed.hostname

            if not auth or not host:
                logger.error("Invalid Upstash URL format")
                return "redis://localhost:6380"

            # Construct Redis URL
            redis_url = f"rediss://{auth}@{host}"
            logger.info("Successfully parsed Upstash URL to Redis format")
            return redis_url

        elif url.startswith(('redis://', 'rediss://')):
            return url

        else:
            logger.warning(f"Unrecognized Redis URL format: {url}")
            return "redis://localhost:6380"

    except Exception as e:
        logger.error(f"Error parsing Redis URL: {str(e)}")
        return "redis://localhost:6380"

def configure_redis_fallback(app):
    """Configure Redis with fallback to simple cache."""
    try:
        redis_host = os.getenv('PGHOST', 'verified-kid-26523.upstash.io')
        redis_password = os.getenv('UPSTASH_REDIS_TOKEN')

        if not redis_host or not redis_password:
            logger.warning("Redis credentials not found, using simple cache")
            app.config['CACHE_TYPE'] = 'simple'
            return False

        # Configure Redis
        redis_client = redis.Redis(
            host=redis_host,
            port=6379,
            password=redis_password,
            ssl=True,
            decode_responses=False,
            socket_timeout=5,
            retry_on_timeout=True,
            socket_connect_timeout=5,
            socket_keepalive=True,
            charset="utf-8",
            encoding='utf-8',
            health_check_interval=30
        )

        # Test connection
        redis_client.ping()

        # Configure cache with Redis
        app.config['CACHE_TYPE'] = 'redis'
        app.config['CACHE_REDIS_HOST'] = redis_host
        app.config['CACHE_REDIS_PORT'] = 6379
        app.config['CACHE_REDIS_PASSWORD'] = redis_password
        app.config['CACHE_REDIS_SSL'] = True
        app.config['CACHE_REDIS_DECODE_RESPONSES'] = False
        app.config['CACHE_DEFAULT_TIMEOUT'] = 300
        app.config['CACHE_OPTIONS'] = {
            'socket_timeout': 5,
            'socket_connect_timeout': 5,
            'retry_on_timeout': True,
            'decode_responses': False,
            'charset': 'utf-8',
            'health_check_interval': 30
        }

        logger.info("Redis cache configured successfully")
        return True

    except Exception as e:
        logger.warning(f"Failed to configure Redis, using simple cache: {str(e)}")
        app.config['CACHE_TYPE'] = 'simple'
        return False

# Base connection pool settings
POOL_CONFIG = {
    'max_connections': 10,
    'socket_timeout': 5,
    'socket_connect_timeout': 5,
    'socket_keepalive': True,
    'retry_on_timeout': True,
    'retry_on_error': [redis.exceptions.ConnectionError],
    'max_retries': 3,
    'decode_responses': True
}

# SSL configuration for secure connections
SSL_CONFIG = {
    'ssl': True,
    'ssl_cert_reqs': None
}

# Parse Redis URL
REDIS_URL = parse_redis_url(os.getenv('UPSTASH_REDIS_URL', 'redis://localhost:6380'))

try:
    # Create a copy of POOL_CONFIG to avoid modifying the original
    connection_config = POOL_CONFIG.copy()

    # Update connection config with SSL settings only for secure connections
    if REDIS_URL.startswith('rediss://'):
        logger.info("Using SSL configuration for secure Redis connection")
        connection_config.update(SSL_CONFIG)
    else:
        logger.info("Using standard Redis connection without SSL")

    # Create connection pool with appropriate configuration
    REDIS_CONNECTION_POOL = redis.ConnectionPool.from_url(
        url=REDIS_URL,
        **connection_config
    )
    logger.info("Successfully created Redis connection pool")

except Exception as e:
    logger.error(f"Failed to create Redis connection pool: {str(e)}")
    REDIS_CONNECTION_POOL = None

# Final Redis configuration
REDIS_CONFIG = {
    'connection_pool': REDIS_CONNECTION_POOL,
    'decode_responses': True
}

def get_redis_client():
    """Get a Redis client with the current configuration."""
    try:
        if REDIS_CONNECTION_POOL:
            return redis.Redis(connection_pool=REDIS_CONNECTION_POOL)
        return None
    except Exception as e:
        logger.error(f"Failed to create Redis client: {str(e)}")
        return None

logger.info(f"Redis configuration initialized with URL type: {'SSL' if REDIS_URL.startswith('rediss://') else 'Standard'}")
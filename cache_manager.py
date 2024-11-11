# Part 1: Imports and setup code
# Part 1: Imports and Initial Setup
import os
import json
import redis
import logging
import time
from functools import wraps
from urllib.parse import urlparse
from datetime import datetime

# Configure logger
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def cache_enabled(func):
    """Decorator to handle cache operations safely"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except redis.RedisError as e:
            logger.error(f"Redis error in {func.__name__}: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error in {func.__name__}: {str(e)}")
            return None
    return wrapper

def parse_redis_url(url):
    """Parse Redis URL, handling both standard Redis URLs and Upstash HTTPS URLs."""
    try:
        if not url:
            logger.warning("No Redis URL provided, using default localhost")
            return "redis://localhost:6380"

        if url.startswith('https://'):
            # Parse Upstash URL format
            parsed = urlparse(url)

            # Extract auth from netloc or username/password from path
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
            return f"rediss://{auth}@{host}"

        elif url.startswith('redis://') or url.startswith('rediss://'):
            return url

        else:
            logger.warning(f"Unrecognized Redis URL format: {url}")
            return "redis://localhost:6380"

    except Exception as e:
        logger.error(f"Error parsing Redis URL: {str(e)}")
        return "redis://localhost:6380"

# Part 2: Class definition and core methods
class CacheManager:
    _instance = None
    _connection_attempts = 0
    MAX_RETRIES = 3
    RETRY_DELAY = 1  # seconds

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(CacheManager, cls).__new__(cls)
            cls._instance._init_connection()
        return cls._instance

    def _init_connection(self):
        """Initialize Redis connection with retries"""
        self.redis = None
        retry_count = 0
        # Get and parse Redis URL
        redis_url = parse_redis_url(os.getenv('UPSTASH_REDIS_URL', 'redis://localhost:6380'))
        logger.debug(f"Attempting to connect to Redis at {redis_url}")
        connection_config = {
            'decode_responses': True,
            'socket_timeout': 5,
            'socket_connect_timeout': 5,
            'socket_keepalive': True,
            'retry_on_timeout': True
        }

        # Add SSL config for secure connections
        if redis_url.startswith('rediss://'):
            connection_config.update({
                'ssl': True,
                'ssl_cert_reqs': None
            })

        while retry_count < self.MAX_RETRIES:
            try:
                self.redis = redis.from_url(
                    url=redis_url,
                    **connection_config
                )
                self.redis.ping()
                logger.info(f"Successfully connected to Redis at {redis_url}")
                break
            except redis.RedisError as e:
                retry_count += 1
                logger.warning(f"Redis connection attempt {retry_count} failed: {str(e)}")
                if retry_count < self.MAX_RETRIES:
                    time.sleep(self.RETRY_DELAY)
                else:
                    logger.error("Failed to connect to Redis after maximum retries")
                    self.redis = None

    # Basic Cache Operations
    @cache_enabled
    def set(self, key, value, timeout=None):
        """Set value in cache with optional timeout"""
        if not self.redis:
            return None

        if isinstance(value, (dict, list)):
            value = json.dumps(value)

        self.redis.set(key, value, ex=timeout)

    @cache_enabled
    def get(self, key):
        """Get value from cache"""
        if not self.redis:
            return None
        try:
            value = self.redis.get(key)
            if value:
                try:
                    return json.loads(value)
                except json.JSONDecodeError:
                    return value  # Return raw string if not JSON
            return None
        except Exception as e:
            logger.error(f"Error getting value from cache: {str(e)}")
            return None

    @cache_enabled
    def delete(self, key):
        """Delete value from cache"""
        if not self.redis:
            return None
        self.redis.delete(key)

    @cache_enabled
    def exists(self, key):
        """Check if key exists in cache"""
        if not self.redis:
            return False
        return self.redis.exists(key)

    @cache_enabled
    def expire(self, key, seconds):
        """Set expiration time for a key"""
        if not self.redis:
            return None
        return self.redis.expire(key, seconds)

    @cache_enabled
    def increment(self, key):
        """Increment a value in cache"""
        if not self.redis:
            return None
        return self.redis.incr(key)

    # Part 3: Currency operations methods
    # Currency Operations
    def get_currency_rates(self):
        """Get all currency rates from cache"""
        if not self.redis:
            return None
        try:
            rates = self.redis.get('currency:rates')
            if rates:
                return json.loads(rates)
            return None
        except Exception as e:
            logger.error(f"Error getting currency rates: {str(e)}")
            return None

    def set_currency_rates(self, rates, timeout=86400):  # 24 hours
        """Cache currency rates for all users"""
        if not self.redis:
            return False
        try:
            # Ensure all rates are strings
            string_rates = {k: str(v) for k, v in rates.items()}
            self.redis.setex('currency:rates', timeout, json.dumps(string_rates))
            self.redis.set('rates_last_update', datetime.now().isoformat())
            return True
        except Exception as e:
            logger.error(f"Error setting currency rates: {str(e)}")
            return False

    @cache_enabled
    def set_currency_rate(self, from_currency, to_currency, rate, timeout=3600):
        """Cache currency conversion rate as string"""
        if not self.redis:
            return None

        key = f"rate:{from_currency}:{to_currency}"
        # Ensure rate is stored as string
        rate_str = str(rate)
        if self.redis:
            try:
                self.redis.set(key, rate_str, ex=timeout)
                return True
            except Exception as e:
                logger.error(f"Error setting currency rate: {str(e)}")
                return False
        return False

    @cache_enabled
    def get_currency_rate(self, from_currency, to_currency):
        """Get currency conversion rate as string"""
        if not self.redis:
            return None

        key = f"rate:{from_currency}:{to_currency}"
        try:
            value = self.redis.get(key)
            return value  # Return raw string value
        except Exception as e:
            logger.error(f"Error getting currency rate: {str(e)}")
            return None

    def needs_rate_update(self):
        """Check if rates need updating (older than 24 hours)"""
        if not self.redis:
            return True
        try:
            last_update = self.redis.get('rates_last_update')
            if not last_update:
                return True

            last_update_time = datetime.fromisoformat(last_update)
            time_since_update = datetime.now() - last_update_time
            return time_since_update.days >= 1
        except Exception as e:
            logger.error(f"Error checking rate update: {str(e)}")
            return True

    def clear_currency_cache(self):
        """Clear all currency-related cache"""
        if not self.redis:
            return False
        try:
            keys = self.redis.keys('currency:*')
            if keys:
                self.redis.delete(*keys)
            return True
        except Exception as e:
            logger.error(f"Error clearing currency cache: {str(e)}")
            return False

    def get_many_currency_rates(self, currency_pairs):
        """Get multiple currency rates at once"""
        if not self.redis:
            return {}
        try:
            pipeline = self.redis.pipeline()
            keys = [f"rate:{from_curr}:{to_curr}" for from_curr, to_curr in currency_pairs]
            for key in keys:
                pipeline.get(key)
            values = pipeline.execute()
            return dict(zip(currency_pairs, values))
        except Exception as e:
            logger.error(f"Error getting multiple rates: {str(e)}")
            return {}

    # Part 4: Batch and user operations methods
    # Batch Operations
    @cache_enabled
    def get_many(self, keys):
        """Get multiple values by their keys"""
        if not self.redis:
            return None

        values = self.redis.mget(keys)
        result = {}
        for key, value in zip(keys, values):
            if value:
                try:
                    result[key] = json.loads(value)
                except json.JSONDecodeError:
                    result[key] = value
            else:
                result[key] = None
        return result

    @cache_enabled
    def set_many(self, mapping, timeout=None):
        """Set multiple key-value pairs with optional timeout"""
        if not self.redis:
            return None

        pipeline = self.redis.pipeline()
        for key, value in mapping.items():
            if isinstance(value, (dict, list)):
                value = json.dumps(value)
            pipeline.set(key, value, ex=timeout)
        return pipeline.execute()

    # User Data Operations
    def cache_user_data(self, user_id, data, timeout=1800):
        """Cache user data with timeout"""
        key = f"user:{user_id}"
        self.set(key, data, timeout)

    def get_user_data(self, user_id):
        """Get cached user data"""
        key = f"user:{user_id}"
        return self.get(key)

    def clear_user_cache(self, user_id):
        """Clear user cache"""
        key = f"user:{user_id}"
        self.delete(key)

    # Part 5: Utility methods
    # Pipeline Operations
    def get_pipeline(self):
        """Get a Redis pipeline for batch operations"""
        if not self.redis:
            return None
        return self.redis.pipeline()

    def execute_pipeline(self, pipeline_func):
        """Execute a series of operations in a pipeline"""
        if not self.redis:
            return None
        try:
            with self.redis.pipeline() as pipe:
                pipeline_func(pipe)
                return pipe.execute()
        except Exception as e:
            logger.error(f"Pipeline execution error: {str(e)}")
            return None

    # Utility Methods
    def get_with_fallback(self, key, fallback_function, timeout=3600):
        """Get cached value with automatic fallback"""
        value = self.get(key)
        if value is None:
            value = fallback_function()
            if value is not None:
                self.set(key, value, timeout=timeout)
        return value

    def get_status(self):
        """Get Redis connection status"""
        if not self.redis:
            return False
        try:
            return self.redis.ping()
        except:
            return False

    def reconnect(self):
        """Force a reconnection to Redis"""
        self._init_connection()
        return self.get_status()

    def clear_all(self):
        """Clear all cache data (use with caution)"""
        if self.redis:
            self.redis.flushdb()
            logger.warning("Cache cleared entirely")

    def ensure_connection(self):
        """Ensure Redis connection is active, reconnect if needed"""
        if not self.get_status():
            logger.warning("Redis connection lost, attempting to reconnect")
            return self.reconnect()
        return True

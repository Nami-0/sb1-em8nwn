import os
import redis
import logging

logger = logging.getLogger(__name__)

def get_redis_client():
    """Get Redis client with fallback options"""
    try:
        # Try Upstash Redis first
        redis_url = os.getenv('UPSTASH_REDIS_URL')
        if redis_url:
            client = redis.from_url(
                redis_url,
                decode_responses=False,
                socket_timeout=5,
                retry_on_timeout=True,
                socket_connect_timeout=5,
                socket_keepalive=True
            )
            # Test connection
            client.ping()
            logger.info("Successfully connected to Upstash Redis")
            return client

        # Try local Redis as fallback
        client = redis.Redis(
            host='localhost',
            port=6380,
            decode_responses=False,
            socket_timeout=5,
            retry_on_timeout=True
        )
        client.ping()
        logger.info("Successfully connected to local Redis")
        return client

    except redis.ConnectionError as e:
        logger.warning(f"Redis connection failed: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error connecting to Redis: {str(e)}")
        return None
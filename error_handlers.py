from flask import jsonify
import redis
import logging
from functools import wraps
from time import time
import os

logger = logging.getLogger(__name__)

# Rate limiting configuration
RATE_LIMIT = {
    'DEFAULT': {'calls': 100, 'period': 3600},  # 100 calls per hour
    'CURRENCY': {'calls': 50, 'period': 3600},  # 50 currency calls per hour
}

# Store rate limiting data
rate_limit_store = {}

def rate_limit(limit_type='DEFAULT'):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            # Get client identifier (can be IP or user ID)
            client = str(kwargs.get('user_id', request.remote_addr))

            # Get rate limit settings
            settings = RATE_LIMIT.get(limit_type, RATE_LIMIT['DEFAULT'])

            # Create key for this client and endpoint
            key = f"{client}:{f.__name__}"

            current = time()
            client_history = rate_limit_store.get(key, [])

            # Remove old timestamps
            client_history = [t for t in client_history if current - t < settings['period']]

            if len(client_history) >= settings['calls']:
                logger.warning(f"Rate limit exceeded for {client}")
                return jsonify({
                    'error': 'Rate limit exceeded',
                    'retry_after': int(client_history[0] + settings['period'] - current)
                }), 429

            client_history.append(current)
            rate_limit_store[key] = client_history

            return f(*args, **kwargs)
        return wrapper
    return decorator

def handle_redis_error(e):
    """Handle Redis-specific errors"""
    logger.error(f"Redis error: {str(e)}")
    return jsonify({
        'error': 'Cache service temporarily unavailable',
        'message': str(e)
    }), 503

def handle_cache_miss(cache_key, fetch_function, timeout=3600):
    """Handle cache misses with automatic refresh"""
    try:
        # Try to get from cache first
        cached_data = cache_manager.get(cache_key)
        if cached_data:
            return cached_data

        # If cache miss, fetch fresh data
        fresh_data = fetch_function()

        # Cache the fresh data
        cache_manager.set(cache_key, fresh_data, timeout=timeout)

        return fresh_data
    except Exception as e:
        logger.error(f"Cache miss handler error: {str(e)}")
        return None

def register_error_handlers(app):
    """Register all error handlers with the app"""

    @app.errorhandler(redis.RedisError)
    def redis_error(e):
        return handle_redis_error(e)

    @app.errorhandler(redis.ConnectionError)
    def redis_connection_error(e):
        return handle_redis_error(e)

    @app.errorhandler(429)
    def too_many_requests(e):
        return jsonify({
            'error': 'Too many requests',
            'message': 'Rate limit exceeded'
        }), 429
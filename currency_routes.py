from flask import Blueprint, jsonify, request, current_app
from flask_login import login_required, current_user
from cache_manager import CacheManager
from currency_data import (
    get_currency_info, 
    format_currency, 
    CURRENCY_DATA,
    get_default_currency
)
import logging
import json
from decimal import Decimal
import os
import redis
from functools import wraps

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Initialize blueprint
currency_routes = Blueprint('currency_routes', __name__)

# Initialize cache manager
cache_manager = CacheManager()

def get_redis():
    """Get Redis connection using Replit secrets"""
    try:
        redis_url = os.environ.get('UPSTASH_REDIS_URL')
        redis_token = os.environ.get('UPSTASH_REDIS_TOKEN')

        if not redis_url or not redis_token:
            logger.warning("Upstash Redis credentials not found")
            return None

        redis_client = redis.from_url(
            redis_url,
            username="default",
            password=redis_token,
            decode_responses=True,
            socket_timeout=5,
            retry_on_timeout=True
        )

        # Test connection
        redis_client.ping()
        logger.info("Successfully connected to Upstash Redis")
        return redis_client

    except Exception as e:
        logger.error(f"Failed to connect to Redis: {str(e)}")
        return None

def cache_enabled(f):
    """Decorator to handle Redis cache operations"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except redis.RedisError as e:
            logger.error(f"Redis error in {f.__name__}: {str(e)}")
            return jsonify({'error': 'Cache service temporarily unavailable'}), 503
        except Exception as e:
            logger.error(f"Unexpected error in {f.__name__}: {str(e)}")
            return jsonify({'error': 'Internal server error'}), 500
    return decorated_function

@currency_routes.route('/api/currencies/supported', methods=['GET'])
@cache_enabled
def get_supported_currencies():
    """Get list of supported currencies"""
    try:
        # Try to get from cache first
        cache_key = 'supported_currencies'
        cached_data = cache_manager.get(cache_key)

        if cached_data:
            return jsonify(json.loads(cached_data))

        # If not in cache, prepare fresh data
        currencies = {
            code: {
                'name': info.name,
                'symbol': info.symbol,
                'decimal_places': info.decimal_places,
                'flag': info.flag
            }
            for code, info in CURRENCY_DATA.items()
        }

        # Cache for 24 hours
        cache_manager.set(cache_key, json.dumps(currencies), timeout=86400)

        return jsonify(currencies)

    except Exception as e:
        logger.error(f"Error getting supported currencies: {str(e)}")
        return jsonify({'error': 'Failed to get currency list'}), 500

@currency_routes.route('/api/currencies/rates', methods=['GET'])
@cache_enabled
def get_exchange_rates():
    """Get current exchange rates"""
    try:
        redis_client = get_redis()
        if redis_client:
            # Try to get from Redis cache
            cached_rates = redis_client.get('currency:rates')
            if cached_rates:
                return jsonify({'rates': json.loads(cached_rates)})

        # If not in Redis or no Redis connection, try backup cache
        cached_rates = cache_manager.get('exchange_rates')
        if cached_rates:
            return jsonify({'rates': json.loads(cached_rates)})

        # If no cache hit, fetch fresh rates (implement your rate fetching logic)
        rates = fetch_fresh_rates()  # You'll need to implement this

        # Cache in Redis if available
        if redis_client:
            redis_client.setex('currency:rates', 3600, json.dumps(rates))  # 1 hour cache

        # Backup cache
        cache_manager.set('exchange_rates', json.dumps(rates), timeout=3600)

        return jsonify({'rates': rates})

    except Exception as e:
        logger.error(f"Error getting exchange rates: {str(e)}")
        return jsonify({'error': 'Failed to get exchange rates'}), 500

@currency_routes.route('/api/currencies/convert', methods=['GET'])
@cache_enabled
def convert_currency():
    """Convert amount between currencies"""
    try:
        amount = request.args.get('amount', type=float)
        from_currency = request.args.get('from', default='MYR')
        to_currency = request.args.get('to', default='MYR')

        if not amount:
            return jsonify({'error': 'Amount is required'}), 400

        # Validate currencies
        if not all(currency in CURRENCY_DATA for currency in [from_currency, to_currency]):
            return jsonify({'error': 'Invalid currency code'}), 400

        # Try to get conversion rate from cache
        cache_key = f'rate:{from_currency}:{to_currency}'
        rate = cache_manager.get(cache_key)

        if not rate:
            # Get fresh rate and cache it
            rate = get_conversion_rate(from_currency, to_currency)  # Implement this
            cache_manager.set(cache_key, str(rate), timeout=3600)  # 1 hour cache

        converted_amount = Decimal(str(amount)) * Decimal(str(rate))

        return jsonify({
            'from': from_currency,
            'to': to_currency,
            'amount': amount,
            'rate': float(rate),
            'result': float(converted_amount),
            'formatted': format_currency(converted_amount, to_currency)
        })

    except Exception as e:
        logger.error(f"Error converting currency: {str(e)}")
        return jsonify({'error': 'Currency conversion failed'}), 500

@currency_routes.route('/api/currencies/preferences', methods=['GET', 'POST'])
@login_required
def user_currency_preferences():
    """Get or update user's currency preferences"""
    try:
        if request.method == 'GET':
            return jsonify({
                'preferred_currency': current_user.preferred_currency,
                'last_update': current_user.last_currency_update.isoformat() 
                    if current_user.last_currency_update else None
            })

        # Handle POST request
        data = request.get_json()
        currency = data.get('currency')

        if not currency or currency not in CURRENCY_DATA:
            return jsonify({'error': 'Invalid currency code'}), 400

        current_user.preferred_currency = currency
        current_user.last_currency_update = datetime.utcnow()
        db.session.commit()

        return jsonify({
            'message': 'Currency preference updated',
            'preferred_currency': currency
        })

    except Exception as e:
        logger.error(f"Error handling currency preferences: {str(e)}")
        return jsonify({'error': 'Failed to process currency preferences'}), 500

# Add these utility functions at the bottom of the file
def fetch_fresh_rates():
    """
    Implement your exchange rate API call here
    For example, using ExchangeRate-API or similar service
    """
    # This is a placeholder - implement your actual rate fetching logic
    return {
        'MYR': 1.0,
        'USD': 0.24,
        'SGD': 0.32,
        'JPY': 26.39,
        'EUR': 0.22,
        'GBP': 0.19
    }

def get_conversion_rate(from_currency, to_currency):
    """Get conversion rate between two currencies"""
    rates = fetch_fresh_rates()
    if from_currency == to_currency:
        return Decimal('1.0')

    # Convert through base currency (MYR)
    from_rate = Decimal(str(rates.get(from_currency, 1)))
    to_rate = Decimal(str(rates.get(to_currency, 1)))

    return to_rate / from_rate
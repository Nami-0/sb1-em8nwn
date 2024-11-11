from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_session import Session
from flask_caching import Cache
from redis_helper import get_redis_connection, init_redis_cache, clear_redis_session
import redis
import os
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create single instances of all extensions
db = SQLAlchemy()
login_manager = LoginManager()
cache = Cache()
sess = Session()

def init_extensions(app):
    """Initialize all Flask extensions"""
    try:
        # Initialize SQLAlchemy
        db.init_app(app)

        # Create tables if they don't exist
        with app.app_context():
            db.create_all()
            logger.info("Database tables created successfully")

        # Configure login manager with correct endpoint
        login_manager.init_app(app)
        login_manager.login_view = 'google_auth.login'  # This line fixes the BuildError
        login_manager.login_message = 'Please log in to access this page.'
        login_manager.login_message_category = 'info'

        # Initialize Redis session interface
        redis_url = os.getenv('UPSTASH_REDIS_URL')
        if redis_url:
            try:
                # Configure Redis for session handling
                app.config['SESSION_TYPE'] = 'redis'
                app.config['SESSION_REDIS'] = redis.from_url(
                    redis_url,
                    encoding="utf-8",
                    decode_responses=False,  # Important for session data
                    socket_timeout=5,
                    retry_on_timeout=True,
                    socket_connect_timeout=5,
                    socket_keepalive=True,
                    health_check_interval=30
                )
                app.config['SESSION_PERMANENT'] = False
                app.config['PERMANENT_SESSION_LIFETIME'] = 3600  # 1 hour
                app.config['SESSION_KEY_PREFIX'] = 'session:'
                app.config['SESSION_USE_SIGNER'] = True
                app.config['SESSION_REDIS_ENCODE_KEYS'] = False
                logger.info("Redis session configured successfully")
            except Exception as e:
                logger.error(f"Failed to configure Redis: {str(e)}")
                # Fallback to filesystem session
                app.config['SESSION_TYPE'] = 'filesystem'
                logger.info("Falling back to filesystem session")

        # Try to get Redis connection using helper
        redis_client = get_redis_connection()
        if redis_client:
            # Configure Redis session using new helper
            app.config['SESSION_REDIS'] = redis_client
            logger.info("Redis session configured successfully using helper")

            # Clear any existing session data
            clear_redis_session()
            logger.info("Cleared existing Redis session data")

        # Initialize caching with Redis if available
        if redis_url:
            cache_config = {
                'CACHE_TYPE': 'redis',
                'CACHE_REDIS_URL': redis_url,
                'CACHE_DEFAULT_TIMEOUT': 300,
                'CACHE_OPTIONS': {
                    'socket_timeout': 5,
                    'socket_connect_timeout': 5,
                    'retry_on_timeout': True,
                    'decode_responses': False,
                    'charset': 'utf-8',
                    'health_check_interval': 30
                }
            }
            app.config.update(cache_config)
        else:
            # Try new Redis helper for cache if URL method failed
            if init_redis_cache(app):
                logger.info("Redis cache initialized successfully using helper")
            else:
                app.config['CACHE_TYPE'] = 'simple'
                logger.info("Using simple cache (Redis not available)")

        cache.init_app(app)

        # Initialize session handling
        sess.init_app(app)

        # User loader callback for Flask-Login
        @login_manager.user_loader
        def load_user(user_id):
            from models import User
            try:
                return User.query.get(int(user_id))
            except Exception as e:
                logger.error(f"Error loading user {user_id}: {str(e)}")
                return None

        # Redis connection error handler
        @app.errorhandler(redis.RedisError)
        def handle_redis_error(error):
            logger.error(f"Redis error: {str(error)}")
            return {'error': 'Cache service temporarily unavailable'}, 503

        logger.info("Successfully initialized all extensions")
        return db

    except Exception as e:
        logger.error(f"Error initializing extensions: {str(e)}")
        raise e

def get_redis():
    """Get Redis connection using environment variables"""
    try:
        redis_url = os.environ.get('UPSTASH_REDIS_URL')
        redis_token = os.environ.get('UPSTASH_REDIS_TOKEN')

        if not redis_url or not redis_token:
            logger.warning("Redis credentials not found")
            return None

        redis_client = redis.from_url(
            redis_url,
            username="default",
            password=redis_token,
            decode_responses=False,  # Important: Set to False for session data
            socket_timeout=5,
            retry_on_timeout=True,
            socket_connect_timeout=5,
            socket_keepalive=True,
            charset='utf-8',
            encoding='utf-8',
            health_check_interval=30
        )

        # Test connection
        redis_client.ping()
        logger.info("Successfully connected to Redis")
        return redis_client

    except Exception as e:
        logger.error(f"Failed to connect to Redis: {str(e)}")
        return None

def get_db():
    """Get database instance."""
    return db

def get_cache():
    """Get cache instance."""
    return cache

def get_session():
    """Get session instance."""
    return sess

def get_login_manager():
    """Get login manager instance."""
    return login_manager
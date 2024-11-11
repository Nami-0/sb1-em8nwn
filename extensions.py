from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_session import Session
from flask_caching import Cache
import redis
import os
import logging
from datetime import timedelta

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize extensions
db = SQLAlchemy()
login_manager = LoginManager()
cache = Cache()
session = Session()

def get_redis_client():
    """Get Redis client with fallback options"""
    try:
        redis_url = os.getenv('UPSTASH_REDIS_URL')
        if not redis_url:
            logger.warning("No Redis URL provided, using filesystem session")
            return None

        # Configure Redis client with robust settings
        client = redis.from_url(
            redis_url,
            decode_responses=False,  # Important for session data
            socket_timeout=5,
            retry_on_timeout=True,
            retry_on_error=[redis.ConnectionError],
            socket_connect_timeout=5,
            socket_keepalive=True,
            health_check_interval=30,
            max_connections=10
        )

        # Test connection
        client.ping()
        logger.info("Successfully connected to Redis")
        return client

    except (redis.ConnectionError, redis.RedisError) as e:
        logger.error(f"Redis connection error: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error connecting to Redis: {str(e)}")
        return None

def init_app(app):
    """Initialize all Flask extensions"""
    try:
        # Initialize SQLAlchemy
        db.init_app(app)

        # Create tables if they don't exist
        with app.app_context():
            db.create_all()
            logger.info("Database tables created successfully")

        # Configure login manager
        login_manager.init_app(app)
        login_manager.login_view = 'google_auth.login'
        login_manager.login_message = 'Please log in to access this page.'
        login_manager.login_message_category = 'info'

        # Configure session handling
        app.config['SESSION_TYPE'] = 'filesystem'  # Default to filesystem
        app.config['SESSION_FILE_DIR'] = '.flask_session/'  # Specify session directory
        app.config['SESSION_FILE_THRESHOLD'] = 500  # Maximum number of sessions
        app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=1)
        app.config['SESSION_USE_SIGNER'] = True
        app.config['SESSION_KEY_PREFIX'] = 'session:'

        # Try to set up Redis
        redis_client = get_redis_client()
        if redis_client:
            try:
                app.config.update({
                    'SESSION_TYPE': 'redis',
                    'SESSION_REDIS': redis_client,
                    'CACHE_TYPE': 'redis',
                    'CACHE_REDIS': redis_client,
                    'CACHE_DEFAULT_TIMEOUT': 300
                })
                logger.info("Using Redis for sessions and cache")
            except Exception as e:
                logger.warning(f"Failed to configure Redis, falling back to filesystem: {str(e)}")
        else:
            logger.info("Using filesystem for sessions and simple cache")
            app.config['CACHE_TYPE'] = 'simple'

        # Initialize caching
        cache.init_app(app)

        # Initialize session handling
        session.init_app(app)

        # User loader callback
        @login_manager.user_loader
        def load_user(user_id):
            from models import User
            try:
                return User.query.get(int(user_id))
            except Exception as e:
                logger.error(f"Error loading user {user_id}: {str(e)}")
                return None

        # Redis error handler
        @app.errorhandler(redis.RedisError)
        def handle_redis_error(error):
            logger.error(f"Redis error: {str(error)}")
            return {'error': 'Cache service temporarily unavailable'}, 503

        # Session cleanup on app shutdown
        @app.teardown_appcontext
        def cleanup_session(exception=None):
            try:
                if 'redis' in app.config.get('SESSION_TYPE', ''):
                    redis_client = app.config.get('SESSION_REDIS')
                    if redis_client:
                        redis_client.close()
            except Exception as e:
                logger.error(f"Error during session cleanup: {str(e)}")

        logger.info("Successfully initialized all extensions")
        return True

    except Exception as e:
        logger.error(f"Error initializing extensions: {str(e)}")
        return False
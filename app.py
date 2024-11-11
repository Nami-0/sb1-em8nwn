from flask import Flask, request, jsonify
from config import Config
from extensions import init_app, db
import logging
import os
import redis
from redis import Redis, RedisError
from werkzeug.middleware.proxy_fix import ProxyFix

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_app():
    """Create and configure the Flask application"""
    try:
        # Initialize Flask app
        app = Flask(__name__, 
                   static_url_path='/static', 
                   static_folder='static')

        # Load configuration
        app.config.from_object(Config())

        # Add ProxyFix middleware for Cloudflare
        app.wsgi_app = ProxyFix(
            app.wsgi_app,
            x_for=1,
            x_proto=1,
            x_host=1,
            x_port=1,
            x_prefix=1
        )

        # Initialize extensions
        init_app(app)

        # Register blueprints
        from auth import google_auth
        app.register_blueprint(google_auth)

        from views import main_views
        app.register_blueprint(main_views)

        from currency_routes import currency_routes
        app.register_blueprint(currency_routes)

        # Error handlers
        from error_handlers import register_error_handlers
        register_error_handlers(app)

        # Add cache headers for static files
        @app.after_request
        def add_cache_headers(response):
            if 'static' in request.path:
                # Cache static files for 1 year
                response.cache_control.max_age = 31536000
                response.cache_control.public = True
                response.headers['Vary'] = 'Accept-Encoding'

                # Add security headers
                response.headers['X-Content-Type-Options'] = 'nosniff'
                response.headers['X-Frame-Options'] = 'SAMEORIGIN'
                response.headers['X-XSS-Protection'] = '1; mode=block'

                # Cache different file types appropriately
                if request.path.endswith(('.css', '.js')):
                    response.headers['Cache-Control'] = 'public, max-age=31536000'
                elif request.path.endswith(('.jpg', '.jpeg', '.png', '.gif', '.ico')):
                    response.headers['Cache-Control'] = 'public, max-age=31536000'
                elif request.path.endswith(('.woff', '.woff2', '.ttf', '.eot')):
                    response.headers['Cache-Control'] = 'public, max-age=31536000'
            else:
                # For non-static files, no caching by default
                response.cache_control.no_cache = True
                response.cache_control.no_store = True
                response.cache_control.must_revalidate = True
            return response

        # Enable CORS for static assets
        @app.after_request
        def add_cors_headers(response):
            if 'static' in request.path:
                response.headers['Access-Control-Allow-Origin'] = '*'
                response.headers['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
                response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
            return response

        # Compression configuration
        @app.after_request
        def add_compression_headers(response):
            if 'static' in request.path:
                response.headers['Content-Encoding'] = 'br'  # Use Brotli compression
            return response

        # Redis error handlers
        @app.errorhandler(redis.RedisError)
        def handle_redis_error(error):
            logger.error(f"Redis error: {str(error)}")
            return jsonify({'error': 'Cache service temporarily unavailable'}), 503

        @app.errorhandler(redis.ConnectionError)
        def handle_redis_connection_error(error):
            logger.error(f"Redis connection error: {str(error)}")
            return jsonify({'error': 'Cache service unavailable'}), 503

        # Set development mode for OAuth if in Replit environment
        if os.getenv('REPLIT_ENVIRONMENT'):
            os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
            logger.info("Development mode enabled for OAuth")

        # Initialize SQLAlchemy with app context
        with app.app_context():
            try:
                db.create_all()
                logger.info("Database tables created successfully")
            except Exception as e:
                logger.error(f"Error creating database tables: {str(e)}")

        logger.info("Travel Buddy startup completed")
        return app

    except Exception as e:
        logger.error(f"Error creating application: {str(e)}")
        raise

if __name__ == '__main__':
    app = create_app()
    # Use Replit's environment variables for host and port if available
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
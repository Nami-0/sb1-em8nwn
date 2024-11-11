import os
from datetime import timedelta
import logging
import redis
import urllib.parse
from werkzeug.middleware.proxy_fix import ProxyFix

# Configure logger
logger = logging.getLogger(__name__)

def parse_redis_url(url):
  """Parse Redis URL, handling both standard Redis URLs and Upstash HTTPS URLs."""
  try:
      if not url:
          logger.warning("No Redis URL provided, using default localhost")
          return "redis://localhost:6380"

      if url.startswith('https://'):
          # Parse Upstash URL format
          parsed = urllib.parse.urlparse(url)

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
          redis_url = f"rediss://{auth}@{host}"
          logger.info("Successfully parsed Upstash URL to Redis format")
          return redis_url

      elif url.startswith('redis://') or url.startswith('rediss://'):
          return url

      else:
          logger.warning(f"Unrecognized Redis URL format: {url}")
          return "redis://localhost:6380"

  except Exception as e:
      logger.error(f"Error parsing Redis URL: {str(e)}")
      return "redis://localhost:6380"


class Config:
  # Basic Flask Configuration
  SECRET_KEY = os.urandom(24)
  SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', 'sqlite:///app.db')
  SQLALCHEMY_TRACK_MODIFICATIONS = False

  # Cloudflare configuration
  PREFERRED_URL_SCHEME = 'https'
  PROXY_FIX_SETTINGS = {
      'x_for': 1,        # Number of proxy servers
      'x_proto': 1,      # Trust X-Forwarded-Proto
      'x_host': 1,       # Trust X-Forwarded-Host
      'x_port': 1,       # Trust X-Forwarded-Port
      'x_prefix': 1      # Trust X-Forwarded-Prefix
  }
  # Trust Cloudflare IPs (you can update this list as needed)
  CLOUDFLARE_NETWORKS = [
      '173.245.48.0/20',
      '103.21.244.0/22',
      '103.22.200.0/22',
      '103.31.4.0/22',
      '141.101.64.0/18',
      '108.162.192.0/18',
      '190.93.240.0/20',
      '188.114.96.0/20',
      '197.234.240.0/22',
      '198.41.128.0/17',
      '162.158.0.0/15',
      '104.16.0.0/13',
      '104.24.0.0/14',
      '172.64.0.0/13',
      '131.0.72.0/22'
  ]

  # Redis configuration
  REDIS_URL = parse_redis_url(os.getenv('UPSTASH_REDIS_URL', 'redis://localhost:6380'))

  # Currency configuration
  CURRENCY_CACHE_TTL = 86400  # 24 hours
  DEFAULT_CURRENCY = 'MYR'
  EXCHANGE_RATE_API_KEY = os.getenv('EXCHANGERATE_API_KEY')
  CURRENCY_UPDATE_INTERVAL = 86400  # 24 hours

  # Redis currency cache settings
  REDIS_CURRENCY_PREFIX = 'currency:'
  REDIS_CURRENCY_RATE_PREFIX = 'rate:'
  REDIS_CURRENCY_CONFIG = {
      'socket_timeout': 5,
      'socket_connect_timeout': 5,
      'retry_on_timeout': True,
      'decode_responses': True,
      'key_prefix': REDIS_CURRENCY_PREFIX
  }

  # Update Redis SSL config for currency service
  if REDIS_URL.startswith('rediss://'):
      REDIS_CURRENCY_CONFIG.update({
          'ssl': True,
          'ssl_cert_reqs': None
      })

  # Redis SSL Configuration (for production Upstash)
  REDIS_SSL_CONFIG = {
      'socket_timeout': 5,
      'socket_connect_timeout': 5,
      'socket_keepalive': True,
      'retry_on_timeout': True,
      'decode_responses': True
  }

  # Session configuration
  SESSION_TYPE = 'redis'
  SESSION_USE_SIGNER = True
  SESSION_PERMANENT = False
  PERMANENT_SESSION_LIFETIME = timedelta(hours=1)

  # Configure Redis session if URL available
  if REDIS_URL:
      SESSION_REDIS = redis.from_url(
          REDIS_URL,
          encoding="utf-8",
          decode_responses=True,
          socket_timeout=5,
          retry_on_timeout=True
      )
  else:
      SESSION_TYPE = 'filesystem'

  # Cache configuration
  CACHE_TYPE = 'redis'
  CACHE_REDIS_URL = REDIS_URL
  CACHE_DEFAULT_TIMEOUT = 300

  # OAuth configuration
  GOOGLE_OAUTH_CLIENT_ID = os.getenv('GOOGLE_OAUTH_CLIENT_ID')
  GOOGLE_OAUTH_CLIENT_SECRET = os.getenv('GOOGLE_OAUTH_CLIENT_SECRET')
  GOOGLE_CALLBACK_URL = os.getenv('GOOGLE_CALLBACK_URL', 'https://74e3e33d-3b18-467f-a089-9456794a9991-00-3pxtem8jlppau.sisko.replit.dev/google_login/callback')
  OAUTHLIB_INSECURE_TRANSPORT = True  # Only for development

  # Stripe settings
  STRIPE_PUBLIC_KEY = os.getenv('STRIPE_PUBLIC_KEY')
  STRIPE_SECRET_KEY = os.getenv('STRIPE_SECRET_KEY')
  STRIPE_WEBHOOK_SECRET = os.getenv('STRIPE_WEBHOOK_SECRET')

# Ensure required settings are present
@staticmethod
def init_app(app):
    # Add ProxyFix middleware for Cloudflare
    app.wsgi_app = ProxyFix(
        app.wsgi_app,
        x_for=Config.PROXY_FIX_SETTINGS['x_for'],
        x_proto=Config.PROXY_FIX_SETTINGS['x_proto'],
        x_host=Config.PROXY_FIX_SETTINGS['x_host'],
        x_port=Config.PROXY_FIX_SETTINGS['x_port'],
        x_prefix=Config.PROXY_FIX_SETTINGS['x_prefix']
    )

    # Set secure headers
    @app.after_request
    def add_security_headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        return response

    if not app.config['STRIPE_PUBLIC_KEY']:
        app.logger.warning('Stripe public key not set')

# Logging configuration
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')

def __init__(self):
    # Configure logging
    logging.basicConfig(
        level=getattr(logging, self.LOG_LEVEL),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Initialize Redis connection for session
    if self.REDIS_URL:
        try:
            # Add SSL config for secure connections
            connection_config = self.REDIS_SSL_CONFIG.copy()
            if self.REDIS_URL.startswith('rediss://'):
                connection_config.update({
                    'ssl': True,
                    'ssl_cert_reqs': None
                })

            # Initialize Redis connection
            self.SESSION_REDIS = redis.from_url(
                self.REDIS_URL,
                **connection_config
            )
            self.SESSION_REDIS.ping()
            logger.info(f"Successfully initialized Redis connection to {self.REDIS_URL}")
        except Exception as e:
            logger.error(f"Failed to initialize Redis connection: {str(e)}")
            # Fallback to localhost:6380 if connection fails
            fallback_url = "redis://localhost:6380"
            try:
                self.SESSION_REDIS = redis.from_url(
                    fallback_url,
                    **self.REDIS_SSL_CONFIG
                )
                logger.warning(f"Falling back to local Redis at {fallback_url}")
            except Exception as fallback_error:
                logger.error(f"Failed to initialize fallback Redis connection: {str(fallback_error)}")
                self.SESSION_REDIS = None
    else:
        logger.warning("No Redis URL available, session persistence will be limited")
        self.SESSION_REDIS = None
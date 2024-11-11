import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db
from sqlalchemy import text
import logging
from datetime import datetime
import redis
import json

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_redis_connection():
    """Get Redis connection using Replit secrets"""
    try:
        redis_url = os.environ.get('UPSTASH_REDIS_URL')
        redis_token = os.environ.get('UPSTASH_REDIS_TOKEN')

        if not redis_url or not redis_token:
            logger.warning("Upstash Redis credentials not found in environment")
            return None

        # Initialize Redis connection
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

def setup_currency_cache(redis_client):
    """Setup currency-related cache keys in Redis"""
    if not redis_client:
        return

    try:
        # Set default currency mappings
        default_mappings = {
            'MYR': 'Malaysian Ringgit',
            'USD': 'US Dollar',
            'SGD': 'Singapore Dollar',
            'JPY': 'Japanese Yen',
            'EUR': 'Euro',
            'GBP': 'British Pound'
        }

        # Cache currency mappings with 24-hour expiry
        redis_client.setex(
            'currency:mappings',
            86400,  # 24 hours
            json.dumps(default_mappings)
        )

        # Set default exchange rates (example rates)
        default_rates = {
            'MYR': 1.0,
            'USD': 0.24,
            'SGD': 0.32,
            'JPY': 26.39,
            'EUR': 0.22,
            'GBP': 0.19
        }

        # Cache exchange rates with 1-hour expiry
        redis_client.setex(
            'currency:rates',
            3600,  # 1 hour
            json.dumps(default_rates)
        )

        logger.info("Successfully initialized currency cache in Redis")

    except Exception as e:
        logger.error(f"Error setting up currency cache: {str(e)}")

def upgrade():
    """Add currency support to user table and itinerary table"""
    app = create_app()

    with app.app_context():
        try:
            # Get Redis connection
            redis_client = get_redis_connection()

            # Database migrations
            with db.engine.connect() as conn:
                # Add currency columns to user table
                conn.execute(text("""
                    ALTER TABLE "user" 
                    ADD COLUMN IF NOT EXISTS preferred_currency VARCHAR(3) DEFAULT 'MYR',
                    ADD COLUMN IF NOT EXISTS last_currency_update TIMESTAMP
                """))

                # Add currency column to itinerary table
                conn.execute(text("""
                    ALTER TABLE itinerary 
                    ADD COLUMN IF NOT EXISTS currency VARCHAR(3) DEFAULT 'MYR'
                """))

                # Add currency conversion cache table
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS currency_cache (
                        id SERIAL PRIMARY KEY,
                        from_currency VARCHAR(3) NOT NULL,
                        to_currency VARCHAR(3) NOT NULL,
                        rate DECIMAL(20, 10) NOT NULL,
                        last_updated TIMESTAMP NOT NULL,
                        UNIQUE(from_currency, to_currency)
                    )
                """))

                # Add index for currency lookups
                conn.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_currency_pairs 
                    ON currency_cache(from_currency, to_currency)
                """))

                # Set default values for existing records
                conn.execute(text("""
                    UPDATE "user" 
                    SET preferred_currency = 'MYR',
                        last_currency_update = :timestamp
                    WHERE preferred_currency IS NULL
                """), {'timestamp': datetime.utcnow()})

                conn.execute(text("""
                    UPDATE itinerary 
                    SET currency = 'MYR'
                    WHERE currency IS NULL
                """))

                # Add validation constraint
                conn.execute(text("""
                    DO $$ 
                    BEGIN
                        IF NOT EXISTS (
                            SELECT 1 FROM pg_constraint WHERE conname = 'valid_currency_check'
                        ) THEN
                            ALTER TABLE "user"
                            ADD CONSTRAINT valid_currency_check
                            CHECK (preferred_currency ~ '^[A-Z]{3}$');
                        END IF;
                    END
                    $$;
                """))

            # Initialize Redis cache if available
            if redis_client:
                setup_currency_cache(redis_client)
                logger.info("Currency cache initialized in Redis")
            else:
                logger.warning("Skipping Redis cache initialization - no connection available")

            db.session.commit()
            logger.info("Successfully added currency support to database")

        except Exception as e:
            logger.error(f"Error adding currency support: {str(e)}")
            db.session.rollback()
            raise e

def downgrade():
    """Remove currency support from user table and itinerary table"""
    app = create_app()

    with app.app_context():
        try:
            # Get Redis connection
            redis_client = get_redis_connection()

            # Clear Redis cache if available
            if redis_client:
                try:
                    redis_client.delete('currency:mappings', 'currency:rates')
                    logger.info("Cleared currency cache from Redis")
                except Exception as e:
                    logger.warning(f"Error clearing Redis cache: {str(e)}")

            # Database cleanup
            with db.engine.connect() as conn:
                # Remove constraint first
                conn.execute(text("""
                    ALTER TABLE "user" 
                    DROP CONSTRAINT IF EXISTS valid_currency_check
                """))

                # Drop currency cache table
                conn.execute(text("""
                    DROP TABLE IF EXISTS currency_cache CASCADE
                """))

                # Remove currency columns
                conn.execute(text("""
                    ALTER TABLE "user" 
                    DROP COLUMN IF EXISTS preferred_currency,
                    DROP COLUMN IF EXISTS last_currency_update
                """))

                conn.execute(text("""
                    ALTER TABLE itinerary 
                    DROP COLUMN IF EXISTS currency
                """))

            db.session.commit()
            logger.info("Successfully removed currency support")

        except Exception as e:
            logger.error(f"Error removing currency support: {str(e)}")
            db.session.rollback()
            raise e

if __name__ == "__main__":
    upgrade()
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import create_app, db
from sqlalchemy import text
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def upgrade():
    app = create_app()
    with app.app_context():
        try:
            # Add subscription tracking columns
            with db.engine.connect() as conn:
                conn.execute(text("""
                    ALTER TABLE "user" 
                    ADD COLUMN IF NOT EXISTS subscription_status VARCHAR(20) DEFAULT 'active',
                    ADD COLUMN IF NOT EXISTS subscription_end_date TIMESTAMP,
                    ADD COLUMN IF NOT EXISTS stripe_customer_id VARCHAR(120) UNIQUE,
                    ADD COLUMN IF NOT EXISTS last_reset_date TIMESTAMP
                """))

            # Set default subscription tier for existing users
            conn.execute(text("""
                UPDATE "user" 
                SET subscription_tier = 'solo_backpacker' 
                WHERE subscription_tier IS NULL
            """))

            db.session.commit()
            logger.info("Successfully added subscription tracking columns")

        except Exception as e:
            logger.error(f"Error adding subscription columns: {str(e)}")
            db.session.rollback()
            raise e

if __name__ == '__main__':
    upgrade()